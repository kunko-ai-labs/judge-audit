"""Zero-shot NLI judge: a small encoder that cannot follow instructions.

The classic "small model" baseline. A DeBERTa-class cross-encoder scores every
option as a hypothesis against the state (entailment vs contradiction) and the
softmax over options is the confidence — a real probability, not a number the
model wrote. It runs locally, costs nothing per call and has no notion of
instructions, so prompt injection cannot reach it by construction. It also
cannot reason and sees a short context. That is exactly the baseline a judgment
model or an LLM judge has to beat.

Environment:
  NLI_MODEL       Hugging Face id (default MoritzLaurer/deberta-v3-base-zeroshot-v2.0, MIT)
  NLI_HYPOTHESIS  template with one {} for the option (default "This text is about {}.")
  NLI_DEVICE      cpu | mps | cuda | auto (default auto)

Install: pip install 'kunko-judge-audit[nli]'
"""
from __future__ import annotations

import os
import time

from .base import Judge, Judgment, Question, QuestionType

DEFAULT_MODEL = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
DEFAULT_HYPOTHESIS = "This text is about {}."


def _pick_device(requested: str) -> str:
    if requested and requested != "auto":
        return requested
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _load_pipeline(model: str, device: str):
    try:
        from transformers import pipeline
    except ImportError as e:
        raise RuntimeError("the nli judge needs: pip install 'kunko-judge-audit[nli]'") from e
    return pipeline("zero-shot-classification", model=model, device=device)


class NLIJudge(Judge):
    name = "nli"

    def __init__(self, model: str | None = None, hypothesis: str | None = None,
                 device: str | None = None, pipe=None):
        self.model = model or os.environ.get("NLI_MODEL", DEFAULT_MODEL)
        self.hypothesis = hypothesis or os.environ.get("NLI_HYPOTHESIS", DEFAULT_HYPOTHESIS)
        self.device = _pick_device(device or os.environ.get("NLI_DEVICE", "auto"))
        self.label = self.model.split("/")[-1]
        self.name = f"nli:{self.label}"
        self._pipe = pipe if pipe is not None else _load_pipeline(self.model, self.device)

    def describe(self) -> dict:
        return {"name": self.name, "provider": "local", "model": self.label,
                "model_id": self.model,
                "confidence_method": "NLI entailment softmax over options",
                # An encoder does not sample; the hypothesis template is its whole prompt.
                "temperature": "n/a",
                "hypothesis_template": self.hypothesis, "device": self.device}

    @staticmethod
    def _labels(q: Question) -> tuple[list[str], dict[str, str]]:
        """Candidate label text per option; descriptions win over bare names."""
        text_of: dict[str, str] = {}
        for opt in q.options:
            desc = q.descriptions.get(opt)
            text_of[opt] = desc if desc else opt.replace("_", " ")
        return list(text_of.values()), {v: k for k, v in text_of.items()}

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        out: list[Judgment] = []
        for q in questions:
            if q.type is QuestionType.SCORE:
                raise RuntimeError("the nli judge does not support score questions "
                                   "(ordered levels have no entailment reading)")
            t0 = time.monotonic()
            if q.type is QuestionType.NOUL:
                labels, back = ["yes", "no"], {"yes": "true", "no": "false"}
                res = self._pipe(state, candidate_labels=labels,
                                 hypothesis_template=q.instructions + " {}", multi_label=False)
            else:
                if not q.options:
                    raise RuntimeError(f"choice question '{q.name}' has no options")
                labels, back = self._labels(q)
                res = self._pipe(state, candidate_labels=labels,
                                 hypothesis_template=self.hypothesis, multi_label=False)
            latency = time.monotonic() - t0
            scores = {back[lbl]: float(sc) for lbl, sc in zip(res["labels"], res["scores"],
                                                              strict=True)}
            best = max(scores, key=lambda k: scores[k])
            out.append(Judgment(
                question=q.name, decision=best, confidence=scores[best],
                latency_s=latency, cost_usd=0.0,
                raw={"scores": scores, "labels": list(res["labels"]), "model": self.model},
            ))
        return out
