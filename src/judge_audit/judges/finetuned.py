"""Fine-tuned sequence classifier: "your own classifier" as an Arena row.

The answer to "isn't a judgment model just a classifier?". A DeBERTa-class
encoder with a classification head trained on the labelled rows of one dataset
(scripts/train_classifier.py) predicts one of its trained labels for the state
text; the confidence is the softmax probability of the chosen label — a real
probability from the head, not a number the model wrote.

What it cannot do, by construction, and what the report says out loud:
- It does not read the question, its instructions or the option descriptions.
  The only input is the state text. Prompt injection cannot *instruct* it; text
  that looks like another category can still fool it.
- It only answers choice questions whose options are labels it was trained on.
  Options it never saw are ignored (recorded in `raw.ignored_options`); a
  question with no trained option is an error, not a guess.
- It knows nothing outside the training rows' distribution. The held-out
  report (docs/finetuned-baseline-2026-09.md) is a same-generator test, not a
  drift test.

Temperature scaling (Guo et al. 2017): when the model directory's `judge-audit.json`
carries `temperature`, the logits are divided by it before the softmax — one scalar
fitted on a validation slice of the training half, never on the rows being judged.
It changes no decision, only the confidence. `FINETUNED_TEMPERATURE=1` switches it
off for an A/B run; the value used is recorded in `describe()` and in every `raw`.

Environment:
  FINETUNED_MODEL_DIR    directory written by scripts/train_classifier.py (required)
  FINETUNED_DEVICE       cpu | mps | cuda | auto (default auto)
  FINETUNED_MAX_LEN      tokens per state (default 256, the training value)
  FINETUNED_TEMPERATURE  override the sidecar's temperature (1 = off)

Install: pip install 'kunko-judge-audit[nli]'  (transformers + torch)
"""
from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable
from pathlib import Path

from .base import Judge, Judgment, Question, QuestionType
from .nli import _pick_device

DEFAULT_MAX_LEN = 256
SIDECAR = "judge-audit.json"   # provenance the training script leaves next to config.json

Predict = Callable[[str], list[float]]   # state text -> logits over labels, by label id


def softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    """Numerically stable softmax of logits / temperature; pure so tests can pin it."""
    if temperature <= 0:
        raise ValueError(f"temperature must be positive, got {temperature}")
    z = [x / temperature for x in logits]
    m = max(z)
    exps = [math.exp(x - m) for x in z]
    total = sum(exps)
    return [e / total for e in exps]


def read_model_dir(model_dir: str) -> tuple[list[str], dict]:
    """(labels by id, provenance sidecar) from a model directory; no torch needed."""
    d = Path(model_dir)
    cfg = d / "config.json"
    if not cfg.is_file():
        raise RuntimeError(f"FINETUNED_MODEL_DIR={model_dir}: no config.json "
                           "(run scripts/train_classifier.py first)")
    id2label = json.loads(cfg.read_text(encoding="utf-8")).get("id2label") or {}
    if not id2label:
        raise RuntimeError(f"{cfg}: config has no id2label; not a sequence classifier")
    labels = [str(id2label[k]) for k in sorted(id2label, key=int)]
    side = d / SIDECAR
    sidecar = json.loads(side.read_text(encoding="utf-8")) if side.is_file() else {}
    return labels, sidecar


def build_predict(model_dir: str, device: str, max_len: int) -> Predict:
    """Load tokenizer + classifier once; return a closure that scores one state."""
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError as e:
        raise RuntimeError("the finetuned judge needs: pip install 'kunko-judge-audit[nli]'") from e
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, dtype=torch.float32).to(device).eval()

    def predict(text: str) -> list[float]:
        enc = tok(text, truncation=True, max_length=max_len, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**enc).logits[0].float()
        return logits.cpu().tolist()

    return predict


class FinetunedJudge(Judge):
    name = "finetuned"

    def __init__(self, model_dir: str | None = None, device: str | None = None,
                 max_len: int | None = None, predict: Predict | None = None,
                 labels: list[str] | None = None, sidecar: dict | None = None,
                 temperature: float | None = None):
        self.model_dir = model_dir or os.environ.get("FINETUNED_MODEL_DIR", "")
        if not self.model_dir and predict is None:
            raise RuntimeError("set FINETUNED_MODEL_DIR to a directory written by "
                               "scripts/train_classifier.py")
        self.device = _pick_device(device or os.environ.get("FINETUNED_DEVICE", "auto"))
        self.max_len = int(max_len or os.environ.get("FINETUNED_MAX_LEN") or DEFAULT_MAX_LEN)
        if predict is None:
            labels, sidecar = read_model_dir(self.model_dir)
            predict = build_predict(self.model_dir, self.device, self.max_len)
        if not labels:
            raise RuntimeError("a finetuned judge needs its label list")
        self._predict = predict
        self.labels = [str(x) for x in labels]
        self.sidecar = dict(sidecar or {})
        self.label = self.sidecar.get("name") or Path(self.model_dir).name or "classifier"
        self.name = f"finetuned:{self.label}"
        env_t = os.environ.get("FINETUNED_TEMPERATURE")
        raw_t = (temperature if temperature is not None
                 else float(env_t) if env_t else self.sidecar.get("temperature", 1.0))
        self.temperature = float(raw_t)
        if self.temperature <= 0:
            raise RuntimeError(f"temperature must be positive, got {self.temperature}")
        self.temperature_source = ("argument" if temperature is not None else "env"
                                   if env_t else "sidecar" if "temperature" in self.sidecar
                                   else "none")

    def describe(self) -> dict:
        s = self.sidecar
        return {"name": self.name, "provider": "local", "model": self.label,
                "backbone": s.get("backbone"), "backbone_revision": s.get("backbone_revision"),
                "confidence_method": "softmax probability of the chosen option "
                                     "(fine-tuned classification head)"
                                     + (f", temperature-scaled (T={self.temperature:.3f})"
                                        if self.temperature != 1.0 else ""),
                "temperature": self.temperature, "temperature_source": self.temperature_source,
                "temperature_fit": s.get("temperature_scaling"),
                "labels": self.labels, "dataset": s.get("dataset"),
                "train_rows_sha256": s.get("train_rows_sha256"), "split": s.get("split"),
                "config_sha256": s.get("config_sha256"), "seed": s.get("seed"),
                "follows_instructions": False, "uses_option_descriptions": False,
                "device": self.device, "max_len": self.max_len}

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        out: list[Judgment] = []
        for q in questions:
            if q.type is not QuestionType.CHOICE:
                raise RuntimeError(f"the finetuned judge answers only choice questions "
                                   f"over its trained labels; '{q.name}' is {q.type.value}")
            if not q.options:
                raise RuntimeError(f"choice question '{q.name}' has no options")
            t0 = time.monotonic()
            logits = [float(x) for x in self._predict(state)]
            latency = time.monotonic() - t0
            probs = softmax(logits, self.temperature)
            scores = {lbl: p for lbl, p in zip(self.labels, probs, strict=True)}
            candidates = [o for o in q.options if o in scores]
            if not candidates:
                raise RuntimeError(f"none of the options of '{q.name}' is a label this model "
                                   f"was trained on ({', '.join(self.labels)})")
            best = max(candidates, key=lambda o: scores[o])
            out.append(Judgment(
                question=q.name, decision=best, confidence=scores[best],
                latency_s=latency, cost_usd=0.0,
                raw={"scores": scores, "logits": logits, "temperature": self.temperature,
                     "ignored_options": [o for o in q.options if o not in scores],
                     "descriptions_ignored": sorted(q.descriptions),
                     "model": self.label},
            ))
        return out
