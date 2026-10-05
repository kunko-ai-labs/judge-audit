"""Decision 2.0: the open decision models of vLLM Semantic Router, run locally.

Decision 2.0 (Apache-2.0; 0.6B to 27B) reads a state and typed questions and returns a
probability for every option without generating text, through the model's own runtime
(`AutoModel.from_pretrained(..., trust_remote_code=True)`, then `model.system_one(...)`).

What is recorded, and why:

- **Confidence is the probability of the chosen option** (`probabilities[choice]`), as for Jev
  and Laya. The model's `confidence` field is a normalized entropy, 1 - H(p)/log K (the
  runtime's `product_answer`), on another scale: 0.83 where P(chosen) is 0.96 on the model
  card's example. It is kept in `raw` as `entropy_confidence`, never audited. Yes/no answers
  are P(true) (`noul`): the decision is "true" from 0.5 and its confidence max(p, 1 - p), as
  for Jev. A score answer's decision is its most probable level, mapped back to the option.
- **The revision.** The six repositories were changed on 2026-10-03, after release, and the
  runtime code ships with the weights. A known model loads at the commit pinned in
  `PINNED_REVISIONS` unless DECISION2_REVISION names another; any other Hub id needs one. The
  commit loaded is recorded, with the package's own weight identity (`model_sha256`).
- **The softmax temperatures and calibration file** the runtime applies, per question type
  (Kai-0.6B ships none: temperature 1, raw probabilities).
- **Loader warnings, and two checks before any decision.** Transformers 5.17 warns that the
  tokenizer has "an incorrect regex pattern" (it reads the package's config.json, which has no
  `transformers_version`, as a possible Mistral tokenizer; no fix is applied unless asked).
  Every warning the load emits is recorded. Then (1) the tokenizer the runtime uses must
  encode probe texts exactly as the package's own `tokenizer.json` does, and (2) the model
  card's example must give the outputs recorded in `REFERENCE_OUTPUTS` for that revision,
  within `REFERENCE_TOLERANCE`; either difference raises. A revision without recorded outputs
  is loaded and marked `unchecked` in the provenance.
- **Over-length input is not truncated.** The runtime answers `max_length_exceeded` instead;
  the adapter records it as no answer, with the error in `raw`.

Environment:
  DECISION2_MODEL     Hub id or local directory (default vllm-sr/Decision-2.0-Kai-0.6B)
  DECISION2_REVISION  Hub commit (default: the pinned one for the six released models)
  DECISION2_DEVICE    cpu | mps | cuda[:n] (default: the runtime's, cuda:0 if present else cpu)

Install: pip install 'kunko-judge-audit[decision2]'
"""
from __future__ import annotations

import logging
import os
import re
import time
import warnings
from pathlib import Path
from typing import Any

from .base import Judge, Judgment, Question, QuestionType, served_of

# What the judge is shown is `decision2_question`; bump when its shape changes.
CRITERIA_VERSION = 1

KAI = "vllm-sr/Decision-2.0-Kai-0.6B"
DEFAULT_MODEL = KAI
# Hub commits pinned on 2026-10-05; every repository was modified on 2026-10-03.
PINNED_REVISIONS = {
    KAI: "cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764",
    "vllm-sr/Decision-2.0-Eos-0.8B": "3594047d69f476f1d01cf84c593e213fc3a4dfe0",
    "vllm-sr/Decision-2.0-Sol-2B": "64235bef55dad29387dd16da7c90e038bf2f0972",
    "vllm-sr/Decision-2.0-Nox-4B": "25e8f67d1b486c647222df3aac640d2d5d736bbe",
    "vllm-sr/Decision-2.0-Lux-9B": "78bf3c03d9147aeb30b641edfe0e30ed04887ca5",
    "vllm-sr/Decision-2.0-Vega-27B": "7aec49ae11a18741706da549ab626b9052795fe7",
}

# The model card's example request.
REFERENCE_STATE = ("The order arrived damaged yesterday. The customer has a receipt and asks "
                   "for a replacement today.")
REFERENCE_QUESTIONS = {
    "route": {"type": "choice", "instructions": "Which team should handle this request?",
              "criteria": {"returns": "Refunds, replacements and damaged deliveries",
                           "billing": "Payments, invoices and charges",
                           "technical": "Product setup and faults"}},
    "receipt": {"type": "noul", "instructions": "Does the customer have a receipt?"},
    "urgency": {"type": "score", "instructions": "How urgent is this request?",
                "criteria": ["Routine", "Soon", "Today"]},
}
# Its answers, recorded with transformers 5.17.0 and torch 2.14.0 on Apple MPS (FP32); the
# same run on CPU differs by at most 5e-7.
REFERENCE_OUTPUTS: dict[tuple[str, str], dict[str, Any]] = {
    (KAI, PINNED_REVISIONS[KAI]): {
        "route": {"type": "choice", "choice": "returns",
                  "probabilities": {"returns": 0.962132, "billing": 0.013547,
                                    "technical": 0.024320},
                  "confidence": 0.830877},
        "receipt": {"type": "noul", "noul": 0.915762},
        "urgency": {"type": "score", "score": 1.475152,
                    "probabilities": {"0": 0.164247, "1": 0.196354, "2": 0.639399},
                    "confidence": 0.178708},
    },
}
REFERENCE_TOLERANCE = 1e-4          # the stored values are rounded to 1e-6
# Probe texts for the tokenizer check: punctuation, digits, accents, curly quotes, newlines.
TOKENIZER_PROBES = (REFERENCE_STATE,
                    "Mi tarjeta no llegó; ¿dónde está? Ref. #4521-B, 3x 12,50 €.",
                    "Line one\n\n  Line two\twith a TAB, CAPS'S and it’s “quoted”.",
                    '{"amount": 1200.5, "currency": "EUR", "items": [1, 2, 3]}')


def _numbers(answer: dict) -> dict[str, float]:
    """The probabilities an answer declares, flat: per option, or P(true) for yes/no."""
    if answer.get("type") == "noul" and "noul" in answer:
        return {"noul": float(answer["noul"])}
    return {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}


def check_reference(got: dict, expected: dict,
                    tolerance: float = REFERENCE_TOLERANCE) -> dict:
    """Compare the model card example's answers with the recorded ones: same decisions, every
    declared probability within `tolerance`."""
    problems: list[str] = []
    worst = 0.0
    for qid, exp in expected.items():
        ans = got.get(qid)
        if not isinstance(ans, dict) or "error" in ans:
            problems.append(f"{qid}: no answer ({(ans or {}).get('error') if ans else None})")
            continue
        if exp.get("type") == "choice" and ans.get("choice") != exp["choice"]:
            problems.append(f"{qid}: chose {ans.get('choice')!r}, reference {exp['choice']!r}")
        a, e = _numbers(ans), _numbers(exp)
        if set(a) != set(e):
            problems.append(f"{qid}: options {sorted(a)}, reference {sorted(e)}")
            continue
        diff = max(abs(a[k] - e[k]) for k in e)
        worst = max(worst, diff)
        if diff > tolerance:
            problems.append(f"{qid}: probabilities differ by up to {diff:.6f}")
    return {"status": "failed" if problems else "passed", "max_abs_diff": round(worst, 7),
            "tolerance": tolerance, "problems": problems}


def tokenizer_check(tokenizer, tokenizer_json: Path) -> dict:
    """Does the tokenizer the runtime loaded encode the probes as the package's tokenizer.json?"""
    from tokenizers import Tokenizer

    raw = Tokenizer.from_file(str(tokenizer_json))
    differ = [i for i, text in enumerate(TOKENIZER_PROBES)
              if tokenizer(text, add_special_tokens=False)["input_ids"]
              != raw.encode(text, add_special_tokens=False).ids]
    return {"matches_tokenizer_json": not differ, "probes": len(TOKENIZER_PROBES),
            "differing_probes": differ}


class _Captured(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(f"{record.name}: {record.getMessage()}")


def _tidy(message: str) -> str:
    """A loader message for the provenance: the home directory and the runtime's temporary
    directory name hidden (they change between machines and loads), one line, bounded."""
    message = re.sub(r"\.decision2-view-[^/'\s]+", ".decision2-view-*",
                     message.replace(str(Path.home()), "~"))
    return " ".join(message.split())[:400]


def _load(model_id: str, revision: str | None, device: str | None):
    """(the loaded model, its provenance), the load's warnings captured."""
    try:
        import torch
        import transformers
        from transformers import AutoModel
    except ImportError as e:
        raise RuntimeError("the decision2 judge needs: "
                           "pip install 'kunko-judge-audit[decision2]'") from e
    handler = _Captured()
    hf_logger = logging.getLogger("transformers")
    hf_logger.addHandler(handler)
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            kwargs: dict = {"revision": revision} if revision else {}
            if device:
                kwargs["device"] = device
            model = AutoModel.from_pretrained(model_id, trust_remote_code=True, **kwargs)
    finally:
        hf_logger.removeHandler(handler)
    messages = handler.messages + [f"{w.category.__name__}: {w.message}" for w in caught]
    source = Path(model._source)
    loaded = (source.name if source.parent.name == "snapshots"
              else getattr(model.config, "_commit_hash", None))
    manifest = model.manifest
    backend = model.runtime.backend
    info = {
        "loaded_revision": loaded,
        "model_name": manifest.get("model_name"),
        "model_sha256": (manifest.get("identity") or {}).get("model_sha256"),
        "profile": manifest.get("profile"),
        "calibration": manifest.get("calibration"),
        "softmax_temperature": dict(getattr(backend, "temperatures", {}) or {}),
        "share_context": getattr(backend, "share_context", None),
        "device": str(getattr(backend, "device", "")) or None,
        "max_input_tokens": manifest.get("max_input_tokens"),
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "runtime_tested_transformers": (manifest.get("remote_code") or {}).get("tested"),
        "loader_warnings": [_tidy(m) for m in messages],
        "tokenizer_check": tokenizer_check(backend.tokenizer, source / "tokenizer.json"),
    }
    return model, info


def decision2_question(q: Question) -> dict:
    """One judge-audit question in Decision 2.0's System One format."""
    base: dict = {"type": q.type.value, "instructions": q.instructions}
    if q.type is QuestionType.CHOICE:
        if not q.options:
            raise RuntimeError(f"choice question '{q.name}' has no options")
        # An option without a description is sent as None: the model sees the bare label.
        base["criteria"] = {opt: q.descriptions.get(opt) for opt in q.options}
    elif q.type is QuestionType.SCORE:
        if not 2 <= len(q.options) <= 10:
            raise RuntimeError(f"score question '{q.name}' needs 2 to 10 levels, "
                               f"has {len(q.options)}")
        # Levels in order; the model returns their indices.
        base["criteria"] = [q.descriptions.get(opt) or opt for opt in q.options]
    return base


def _read(q: Question, ans: dict) -> tuple[str, float, dict]:
    """(decision, confidence, the answer's probabilities) from one parsed answer."""
    if q.type is QuestionType.NOUL:
        p = float(ans["noul"])
        return ("true" if p >= 0.5 else "false"), max(p, 1 - p), {"true": p, "false": 1 - p}
    probs = {str(k): float(v) for k, v in ans["probabilities"].items()}
    if q.type is QuestionType.CHOICE:
        decision = str(ans["choice"])
        return decision, probs[decision], probs
    best = max(probs, key=lambda k: (probs[k], -int(k)))       # the first level on a tie
    return q.options[int(best)], probs[best], probs


class Decision2Judge(Judge):
    name = "decision2"

    def __init__(self, model_id: str | None = None, revision: str | None = None,
                 device: str | None = None, system=None, info: dict | None = None):
        self.model_id = model_id or os.environ.get("DECISION2_MODEL", DEFAULT_MODEL)
        self.requested_revision = (revision or os.environ.get("DECISION2_REVISION")
                                   or PINNED_REVISIONS.get(self.model_id))
        if self.requested_revision is None and not Path(self.model_id).exists():
            raise ValueError(f"{self.model_id} has no pinned revision: set DECISION2_REVISION "
                             "to a Hub commit (the runtime code ships with the weights, so an "
                             "unpinned run is not reproducible)")
        self.device = device or os.environ.get("DECISION2_DEVICE") or None
        if system is None:
            system, info = _load(self.model_id, self.requested_revision, self.device)
        self._system = system
        self.info = dict(info or {})
        self.label = self.model_id.rstrip("/").split("/")[-1]
        self.name = f"decision2:{self.label}"
        if self.info.get("tokenizer_check", {}).get("matches_tokenizer_json") is False:
            raise RuntimeError(f"{self.label}: the tokenizer loaded encodes "
                               f"{self.info['tokenizer_check']['differing_probes']} differently "
                               "from the package's tokenizer.json; outputs would change")
        self.info["reference_check"] = self._check_reference()

    def _check_reference(self) -> dict:
        expected = REFERENCE_OUTPUTS.get((self.model_id, str(self.info.get("loaded_revision"))))
        if expected is None:
            return {"status": "unchecked",
                    "reason": "no reference outputs recorded for this model and revision"}
        got = self._system.system_one(state=REFERENCE_STATE, questions=REFERENCE_QUESTIONS)
        status = check_reference(got.get("answers") or {}, expected)
        if status["status"] != "passed":
            raise RuntimeError(f"{self.label} differs from the reference outputs of the model "
                               f"card's example: {'; '.join(status['problems'])}")
        return status

    def describe(self) -> dict:
        return {
            "name": self.name, "provider": "local", "model": self.label,
            "model_id": self.model_id, "revision": self.requested_revision,
            **self.info,
            "device_requested": self.device,
            "criteria_version": CRITERIA_VERSION,
            "confidence_method": "probability of the chosen option (yes/no: of the answer "
                                 "given) from the model's per-option probabilities",
            "native_confidence": "the model's `confidence` field, a normalized entropy "
                                 "1 - H(p)/log K; kept in raw as entropy_confidence, not "
                                 "audited",
            # nothing is sampled; the softmax temperatures are recorded above
            "temperature": "n/a",
        }

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {q.name: decision2_question(q) for q in questions}
        t0 = time.monotonic()
        result = self._system.system_one(state=state, questions=payload)
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = result.get("answers") or {}
        served = served_of({"model": result.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            if not isinstance(ans, dict) or "error" in ans:
                out.append(Judgment(question=q.name, decision="", confidence=None,
                                    latency_s=latency, cost_usd=0.0,
                                    raw={"error": (ans or {}).get("error") if ans else None,
                                         "answer": ans, "served": served},
                                    parse_status="no_answer"))
                continue
            decision, confidence, probs = _read(q, ans)
            raw = {"probabilities": probs, "entropy_confidence": ans.get("confidence"),
                   "usage": result.get("usage"), "served": served}
            if q.type is QuestionType.SCORE:
                raw["expected_level"] = ans.get("score")
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=0.0, raw=raw))
        return out
