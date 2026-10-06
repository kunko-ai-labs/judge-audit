"""What the local decision-model judges share: open models that answer Jev's System One request
(a state and typed questions) with a probability per option, run on your machine.

Decision 2.0, Clef, decider and Strands Decider each ship their own runtime, but the request
and the answer have the same shape: choice answers carry `probabilities` per option, yes/no
answers the probability of true (`noul`), score answers `probabilities` per level index. A
family adapter loads its runtime at a pinned revision and exposes `system_one(state=...,
questions=...)`, optionally `fit_problems(state, questions)` (what the runtime would cut to fit
its window); this base class does the rest:

- **Confidence is the probability of the chosen option** (`read_answer`): for a choice, the
  probability of the option chosen; for yes/no, of the answer given (max(p, 1 - p), "true"
  from 0.5, as for Jev); for a score, of the most probable level, mapped back to the option.
  A family's own `confidence` field, whatever its formula, is kept in `raw` under a name
  that says what it is, never audited.
- **A pinned revision.** These repositories change after release; a model the family knows
  loads at the commit pinned in its adapter, any other needs `<FAMILY>_REVISION`, and a
  revision must be a 40-hex commit. A local directory loads as it is, without a revision.
- **A reference request before any decision**, where outputs are recorded for the model,
  revision and kind of device (precision and kernels differ by device): same decisions, every
  probability within the family's tolerance, or the judge refuses to start. Without recorded
  outputs the check is `unchecked` in the provenance.
- **No truncated input, and no aborted run.** Where a runtime would cut the state or a question
  to fit its window, the adapter does not send the request: each of its questions is recorded
  as no answer (`max_length_exceeded`, with what would be cut in `raw.problems`), which counts
  against the judge like any unanswered question. Decision 2.0's runtime refuses such input
  itself, with the same error, so all four families follow one rule.
"""
from __future__ import annotations

import contextlib
import logging
import os
import re
import time
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .base import Judge, Judgment, Question, QuestionType, served_of

# What the judge is shown is `systemone_question`; bump when its shape changes.
CRITERIA_VERSION = 1
COMMIT = re.compile(r"[0-9a-f]{40}")      # a pinned Hub revision: a commit, not a branch or tag


def systemone_question(q: Question, blank: str | None = None) -> dict:
    """One judge-audit question as a System One question. An option without a description is
    sent as `blank` (None where the runtime accepts it: the model then sees the bare label)."""
    base: dict = {"type": q.type.value, "instructions": q.instructions}
    if q.type is QuestionType.CHOICE:
        if not q.options:
            raise RuntimeError(f"choice question '{q.name}' has no options")
        base["criteria"] = {opt: q.descriptions.get(opt, blank) for opt in q.options}
    elif q.type is QuestionType.SCORE:
        if not 2 <= len(q.options) <= 10:
            raise RuntimeError(f"score question '{q.name}' needs 2 to 10 levels, "
                               f"has {len(q.options)}")
        # Levels in order; the model returns their indices.
        base["criteria"] = [q.descriptions.get(opt) or opt for opt in q.options]
    return base


def read_answer(q: Question, ans: dict) -> tuple[str, float, dict[str, float]]:
    """(decision, confidence, the answer's probabilities) from one System One answer."""
    if q.type is QuestionType.NOUL:
        p = float(ans["noul"])
        return ("true" if p >= 0.5 else "false"), max(p, 1 - p), {"true": p, "false": 1 - p}
    probs = {str(k): float(v) for k, v in ans["probabilities"].items()}
    if q.type is QuestionType.CHOICE:
        decision = str(ans["choice"])
        return decision, probs[decision], probs
    best = max(probs, key=lambda k: (probs[k], -int(k)))       # the first level on a tie
    return q.options[int(best)], probs[best], probs


def _numbers(answer: dict) -> dict[str, float]:
    """The probabilities an answer declares, flat: per option, or P(true) for yes/no."""
    if answer.get("type") == "noul" and "noul" in answer:
        return {"noul": float(answer["noul"])}
    return {str(k): float(v) for k, v in (answer.get("probabilities") or {}).items()}


def check_reference(got: dict, expected: dict, tolerance: float) -> dict:
    """Compare a reference request's answers with the recorded ones: same decisions, every
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


class _Captured(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(f"{record.name}: {record.getMessage()}")


def tidy(message: str) -> str:
    """A loader message for the provenance: the home directory and temporary directory names
    hidden (they change between machines and loads), one line, bounded."""
    message = message.replace(str(Path.home()), "~")
    message = re.sub(r"\.decision2-view-[^/'\s]+", ".decision2-view-*", message)
    message = re.sub(r"/(?:private/)?(?:var/folders|tmp)/[^'\s]+", "<tmp>", message)
    return " ".join(message.split())[:400]


@contextlib.contextmanager
def captured_warnings(*loggers: str) -> Iterator[list[str]]:
    """Every warning logged under `loggers` (and every Python warning) while the block runs,
    tidied for the provenance."""
    handler = _Captured()
    targets = [logging.getLogger(name) for name in loggers or ("transformers",)]
    for target in targets:
        target.addHandler(handler)
    out: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            yield out
    finally:
        for target in targets:
            target.removeHandler(handler)
        out.extend(tidy(m) for m in handler.messages)
        out.extend(tidy(f"{w.category.__name__}: {w.message}") for w in caught)


def best_device(requested: str | None) -> str:
    """The device asked for, else CUDA, Apple MPS or CPU, the first available."""
    if requested:
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


class LocalSystemOneJudge(Judge):
    """A local decision model behind System One. Subclasses set the class attributes and
    `load`; tests pass `system` (anything with `system_one(state=..., questions=...)`) and
    `info` instead of loading."""

    family = "systemone"
    env = "SYSTEMONE"                         # <env>_MODEL, <env>_REVISION, <env>_DEVICE
    install = ""                              # the pip extra, for the error message
    default_model = ""
    pinned: dict[str, str] = {}
    reference_state: Any = None
    reference_questions: dict = {}
    reference_outputs: dict[tuple[str, str, str], dict] = {}   # model, revision, device
    reference_tolerance = 1e-4
    blank_description: str | None = None      # what an option without description is sent as
    raw_fields: dict[str, str] = {}           # native answer field -> name kept in raw
    native_confidence = ""                    # what the family's own confidence field is
    over_length_advice = ("the model's window is fixed: shorten the state or the questions, "
                          "or split the questions across rows")

    def __init__(self, model_id: str | None = None, revision: str | None = None,
                 device: str | None = None, system=None, info: dict | None = None):
        self.model_id = model_id or os.environ.get(f"{self.env}_MODEL", self.default_model)
        self.requested_revision = (revision or os.environ.get(f"{self.env}_REVISION")
                                   or self.pinned.get(self.model_id))
        if not Path(self.model_id).exists() and \
                not COMMIT.fullmatch(self.requested_revision or ""):
            raise ValueError(f"{self.model_id} needs a pinned revision: set {self.env}_REVISION "
                             "to a 40-hex Hub commit, not a branch or tag (these repositories "
                             "change after release, so an unpinned run is not reproducible); "
                             f"got {self.requested_revision!r}")
        self.device = device or os.environ.get(f"{self.env}_DEVICE") or None
        if system is None:
            system, info = self.load(self.model_id, self.requested_revision, self.device)
        self._system = system
        self.info = dict(info or {})
        self.label = self.model_id.rstrip("/").split("/")[-1]
        self.name = f"{self.family}:{self.label}"
        self._check_tokenizer()
        self.info["reference_check"] = self._check_reference()

    # ------------------------------------------------------------------ to override
    def load(self, model_id: str, revision: str | None, device: str | None) -> tuple[Any, dict]:
        raise NotImplementedError

    # ------------------------------------------------------------------ shared
    def _check_tokenizer(self) -> None:
        """Refuse before the reference request when the loader recorded a tokenizer that
        encodes its probes differently from the package's tokenizer.json."""
        check = self.info.get("tokenizer_check") or {}
        if check.get("matches_tokenizer_json") is False:
            raise RuntimeError(f"{self.label}: the tokenizer loaded encodes "
                               f"{check['differing_probes']} differently from the package's "
                               "tokenizer.json; outputs would change")

    def _check_reference(self) -> dict:
        # Numerics differ by device (precision, kernels), so outputs are recorded per kind of
        # device; "*" marks outputs that hold on every device within the tolerance.
        device_kind = str(self.info.get("device") or "").split(":")[0]
        key = (self.model_id, str(self.info.get("loaded_revision")))
        expected = (self.reference_outputs.get((*key, device_kind))
                    or self.reference_outputs.get((*key, "*")))
        if expected is None:
            return {"status": "unchecked",
                    "reason": "no reference outputs recorded for this model, revision and "
                              f"kind of device ({device_kind or 'unknown'})"}
        got = self._system.system_one(state=self.reference_state,
                                      questions=self.reference_questions)
        status = check_reference(got.get("answers") or {}, expected, self.reference_tolerance)
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
            "native_confidence": self.native_confidence,
            # nothing is sampled; the softmax temperatures are recorded above
            "temperature": "n/a",
        }

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {q.name: systemone_question(q, self.blank_description) for q in questions}
        fit = getattr(self._system, "fit_problems", None)
        problems = fit(state, payload) if fit else []
        if problems:                    # the runtime would cut it: refused, counted, not sent
            return [Judgment(question=q.name, decision="", confidence=None, latency_s=0.0,
                             cost_usd=0.0, parse_status="no_answer",
                             raw={"error": "max_length_exceeded", "problems": problems})
                    for q in questions]
        t0 = time.monotonic()
        result = self._system.system_one(state=state, questions=payload)
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = result.get("answers") or {}
        served = served_of({"model": result.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            if not isinstance(ans, dict) or "error" in ans:
                error = (ans or {}).get("error") if ans else None
                refused: dict = {"error": error, "answer": ans, "served": served}
                if error == "max_length_exceeded":   # refused by the runtime itself
                    refused["problems"] = ["the runtime refused the request as over length"]
                out.append(Judgment(question=q.name, decision="", confidence=None,
                                    latency_s=latency, cost_usd=0.0, raw=refused,
                                    parse_status="no_answer"))
                continue
            decision, confidence, probs = read_answer(q, ans)
            raw: dict = {"probabilities": probs}
            raw.update({kept: ans[field] for field, kept in self.raw_fields.items()
                        if field in ans})
            raw.update({"usage": result.get("usage"), "served": served})
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=0.0, raw=raw))
        return out
