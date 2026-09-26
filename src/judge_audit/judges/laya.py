"""Laya: an open-weight judgment model run locally, the second "System One" judge beside Jev.

Laya (Convai Innovations, Apache-2.0, `pip install laya`) reads a state and typed questions
and scores every option in one forward pass of an encoder, returning a probability per
option. Like Jev, it is a model built to judge rather than a chat model writing a number; it
runs on a laptop and its weights are public, so anyone can reproduce its row.

What is recorded, and why:

- **Confidence is the probability of the chosen option** (`probabilities[choice]`, which Laya
  also returns as `answer_confidence`). Laya's `confidence` field is a normalised-entropy
  score on another scale that its own documentation says is not calibrated; it is kept in
  `raw` as `entropy_confidence`, never used as the confidence.
- **The checkpoint's softmax temperatures.** Laya divides the logits by a temperature that
  ships with the checkpoint, per question type and number of options, and the library clamps
  values outside [0.5, 5]. Both the shipped and the applied values change every probability,
  so both are in the provenance. They are not a sampling temperature (Laya does not sample),
  so `temperature` is "n/a", as for the other encoders.
- **Token budgets.** A question's options share a budget (`head_max_len`, 192 tokens in the
  shipped config); options that do not fit make Laya raise, and the error is not caught
  here: a question the model cannot read is not an answer.
- **The act head.** Laya also returns an `act_probability` per answer (its own act-or-escalate
  signal); it is kept in `raw` for an abstention analysis, not used as the confidence.

Environment:
  LAYA_MODEL          Hub id or local directory (default convaiinnovations/laya)
  LAYA_REVISION       Hub commit to pin; the revision actually loaded is recorded either way
  LAYA_DEVICE         cpu | mps | cuda (default: Laya picks)
  LAYA_MAX_LEN, LAYA_HEAD_MAX_LEN   token budgets for this run (default: the checkpoint's)

Install: pip install 'kunko-judge-audit[laya]'
"""
from __future__ import annotations

import os
import time

from .base import Judge, Judgment, Question, QuestionType

DEFAULT_MODEL = "convaiinnovations/laya"


def _int_env(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {value!r}") from e


def _load_agent(model: str, revision: str | None, device: str | None):
    try:
        import laya
    except ImportError as e:
        raise RuntimeError("the laya judge needs: pip install 'kunko-judge-audit[laya]'") from e
    kwargs: dict = {}
    if revision:
        kwargs["revision"] = revision
    if device:
        kwargs["device"] = device
    return laya.Agent(model, **kwargs), getattr(laya, "__version__", None)


def laya_question(q: Question) -> dict:
    """One judge-audit question in Laya's question format."""
    if q.type is QuestionType.CHOICE:
        if not q.options:
            raise RuntimeError(f"choice question '{q.name}' has no options")
        # An option without a description is sent as None: Laya then shows the bare label.
        return {"type": "choice", "instructions": q.instructions,
                "criteria": {opt: q.descriptions.get(opt) for opt in q.options}}
    if q.type is QuestionType.NOUL:
        return {"type": "noul", "instructions": q.instructions}
    raise RuntimeError(f"the laya judge does not support {q.type.value} questions yet")


class LayaJudge(Judge):
    name = "laya"

    def __init__(self, model: str | None = None, revision: str | None = None,
                 device: str | None = None, agent=None, version: str | None = None):
        self.model = model or os.environ.get("LAYA_MODEL", DEFAULT_MODEL)
        self.requested_revision = revision or os.environ.get("LAYA_REVISION") or None
        self.device = device or os.environ.get("LAYA_DEVICE") or None
        self.max_len = _int_env("LAYA_MAX_LEN")
        self.head_max_len = _int_env("LAYA_HEAD_MAX_LEN")
        if agent is None:
            agent, version = _load_agent(self.model, self.requested_revision, self.device)
        self._agent = agent
        self.version = version
        self.label = self.model.rstrip("/").split("/")[-1]
        self.name = f"laya:{self.label}"

    def describe(self) -> dict:
        a = self._agent
        cfg = getattr(a, "cfg", {}) or {}
        return {
            "name": self.name, "provider": "local", "model": self.label, "model_id": self.model,
            "revision": getattr(a, "revision", None) or self.requested_revision,
            "laya_version": self.version,
            "confidence_method": "probability of the chosen option (softmax over options, "
                                 "with the checkpoint's temperature)",
            # an encoder does not sample; the softmax temperatures are recorded below
            "temperature": "n/a",
            "softmax_temperature": {
                "shipped": {"by_type": getattr(a, "temperature_raw", None),
                            "by_options": getattr(a, "temperature_by_options_raw", None)},
                "applied": {"by_type": getattr(a, "temperature", None),
                            "by_options": getattr(a, "temperature_by_options", None)},
            },
            "max_len": self.max_len if self.max_len is not None else cfg.get("max_len"),
            "head_max_len": (self.head_max_len if self.head_max_len is not None
                             else cfg.get("head_max_len")),
            "device": self.device or str(getattr(a, "device", "")) or None,
        }

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {q.name: laya_question(q) for q in questions}
        kwargs = {k: v for k, v in (("max_len", self.max_len),
                                    ("head_max_len", self.head_max_len)) if v is not None}
        t0 = time.monotonic()
        result = self._agent.predict(state, payload, **kwargs)
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = result.get("answers", {})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            if not isinstance(ans, dict):
                out.append(Judgment(question=q.name, decision="", confidence=None,
                                    latency_s=latency, cost_usd=0.0, raw={"answer": ans},
                                    parse_status="no_answer"))
                continue
            if q.type is QuestionType.NOUL:
                p_true = float(ans["noul"])
                decision = "true" if p_true >= 0.5 else "false"
                confidence = max(p_true, 1.0 - p_true)
                probs = {"true": p_true, "false": 1.0 - p_true}
            else:
                decision = ans["choice"]
                probs = {str(k): float(v) for k, v in ans["probabilities"].items()}
                confidence = probs[decision]
            out.append(Judgment(
                question=q.name, decision=decision, confidence=confidence,
                latency_s=latency, cost_usd=0.0,
                raw={"probabilities": probs,
                     "answer_confidence": ans.get("answer_confidence"),
                     "entropy_confidence": ans.get("confidence"),
                     "act_probability": (ans.get("action") or {}).get("act_probability")},
            ))
        return out
