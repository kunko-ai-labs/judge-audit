"""Laya: an open-weight judgment model run locally, the second "System One" judge beside Jev.

Laya (Convai Innovations, Apache-2.0, `pip install laya`) reads a state and typed questions
and scores every option in one forward pass of an encoder, returning a probability per
option. Like Jev, it is a model built to judge rather than a chat model writing a number; it
runs on a laptop and its weights are public, so anyone can reproduce its row.

What is recorded, and why:

- **Confidence is the probability of the chosen option** (`probabilities[choice]`, which Laya
  also returns as `answer_confidence`). Laya's `confidence` field is a normalised-entropy
  score on another scale; it is kept in `raw` as `entropy_confidence`, never used as the
  confidence.
- **The checkpoint's softmax temperatures.** Laya divides the logits by a temperature that
  ships with the checkpoint, per question type and number of options, and the library clamps
  values outside [0.5, 5], warning that confidence from a clamped entry should be treated as
  uncalibrated. The shipped and applied values, and which entries were clamped, are in the
  provenance. They are not a sampling temperature (Laya does not sample), so `temperature`
  is "n/a", as for the other encoders.
- **Token budgets are checked here, not left to Laya.** Laya 0.3.20 fits a question into
  its budgets by cutting: each option to 48 tokens, every option further when they
  together leave fewer than 16 of `head_max_len` tokens, the instructions to what is left,
  the state to `max_len`. A cut option can become identical to another. Before each call
  this adapter redoes that arithmetic with Laya's own tokenizer and rendering
  (`fit_problems`) and raises, naming what would be cut, instead of scoring a question
  the model would read truncated.
- **The act head.** Laya's `act_probability` is kept in `raw` and not analysed: Laya's own
  README says it carries no usable signal yet.
- **The revision loaded.** The checkpoint is downloaded here at LAYA_REVISION (Laya's own
  loader takes no revision) and the Hub commit loaded is recorded, pinned or not; so is the
  device Laya actually runs on, which can differ from the one requested.

Only choice questions are scored: yes/no (noul) questions depend on how Laya maps its
labels, which this adapter has not verified.

Laya's own README says its base checkpoints are near chance on typed decisions zero-shot
and are "a fast base to specialise, not a zero-shot decision engine": a zero-shot row from
this judge is a measurement of that, and says so wherever it is published.

Environment:
  LAYA_MODEL          Hub id or local directory (default convaiinnovations/laya)
  LAYA_REVISION       Hub commit to pin; the commit actually loaded is recorded either way
  LAYA_DEVICE         cpu | mps | cuda (default: Laya picks; the device used is recorded)
  LAYA_MAX_LEN, LAYA_HEAD_MAX_LEN   token budgets for this run (default: the checkpoint's)

Install: pip install 'kunko-judge-audit[laya]'
"""
from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from .base import Judge, Judgment, Question, QuestionType

DEFAULT_MODEL = "convaiinnovations/laya"
# What Laya's own loader downloads from a Hub checkpoint (laya 0.3.20, Agent.__init__).
CHECKPOINT_FILES = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]
# Laya 0.3.20's sequence arithmetic (laya.common.build_sequence).
OPTION_CAP = 48          # tokens kept per option
MIN_HEAD_ROOM = 16       # below this, every option is cut
MIN_OPTION_TOKENS = 4    # the cut never goes below this (marker included)
MIN_INSTRUCTION_TOKENS = 8


def _int_env(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {value!r}") from e


def _download(model: str, revision: str | None) -> tuple[str, str | None]:
    """(local directory, Hub commit loaded). A local directory is used as it is."""
    if Path(model).exists():
        return model, None
    from huggingface_hub import snapshot_download

    path = snapshot_download(model, revision=revision, allow_patterns=CHECKPOINT_FILES,
                             token=os.environ.get("HF_TOKEN") or None)
    return path, Path(path).name        # the cache stores a snapshot under its commit


def _load_agent(model: str, revision: str | None, device: str | None):
    try:
        import laya
    except ImportError as e:
        raise RuntimeError("the laya judge needs: pip install 'kunko-judge-audit[laya]'") from e
    local, commit = _download(model, revision)
    kwargs: dict = {"device": device} if device else {}
    return laya.Agent(local, **kwargs), getattr(laya, "__version__", None), commit


def fit_problems(head_len: int, option_lens: list[int], state_len: int, max_len: int,
                 head_max_len: int) -> list[str]:
    """What Laya 0.3.20 would cut to fit one question in its budgets, from token counts
    (instructions, each option without its marker, state); empty when nothing is cut.
    Mirrors `laya.common.build_sequence`."""
    problems: list[str] = []
    long = sum(1 for n in option_lens if n > OPTION_CAP)
    if long:
        problems.append(f"{long} option(s) longer than Laya's {OPTION_CAP}-token cap")
    kept = [1 + min(n, OPTION_CAP) for n in option_lens]          # marker + tokens
    room = head_max_len - sum(kept)
    if room < MIN_HEAD_ROOM:
        per = max(MIN_OPTION_TOKENS, (head_max_len - MIN_HEAD_ROOM) // max(1, len(kept)))
        cut = sum(1 for k in kept if k > per)
        if cut:
            problems.append(f"the {len(kept)} options need {sum(kept)} of head_max_len="
                            f"{head_max_len} tokens: {cut} would be cut to {per - 1} tokens")
        kept = [min(k, per) for k in kept]
        room = head_max_len - sum(kept)
    head_room = max(MIN_INSTRUCTION_TOKENS, room)
    if head_len > head_room:
        problems.append(f"the instructions ({head_len} tokens) would be cut to {head_room}")
    prefix = 1 + min(head_len, head_room) + 1 + sum(kept) + 1
    if prefix > max_len:
        problems.append(f"the options run past max_len={max_len}")
    state_room = max(0, max_len - prefix - 1)
    if state_len > state_room:
        problems.append(f"the state ({state_len} tokens) would be cut to {state_room}")
    return problems


def laya_token_counts(agent, state: str, qdef: dict) -> tuple[int, list[int], int]:
    """(instructions, each option, state) token counts as Laya 0.3.20 renders them."""
    from laya.common import render_options, serialize_state

    tok, mask = agent.tok, agent.tok.mask_token
    q = agent._to_internal(qdef)

    def n(text: str) -> int:
        return len(tok(text.replace(mask, " "), add_special_tokens=False)["input_ids"])

    return (n(f"{q['t']} question: {q['ins']}"),
            [n(" " + o) for o in render_options(q)], n(serialize_state(state)))


def laya_question(q: Question) -> dict:
    """One judge-audit choice question in Laya's question format."""
    if q.type is not QuestionType.CHOICE:
        raise RuntimeError(f"the laya judge scores choice questions; '{q.name}' is "
                           f"{q.type.value}, whose label handling in Laya is not verified here")
    if not q.options:
        raise RuntimeError(f"choice question '{q.name}' has no options")
    # An option without a description is sent as None: Laya then shows the bare label.
    return {"type": "choice", "instructions": q.instructions,
            "criteria": {opt: q.descriptions.get(opt) for opt in q.options}}


class LayaJudge(Judge):
    name = "laya"

    def __init__(self, model: str | None = None, revision: str | None = None,
                 device: str | None = None, agent=None, version: str | None = None,
                 loaded_revision: str | None = None,
                 token_counts: Callable[..., tuple[int, list[int], int]] = laya_token_counts):
        self.model = model or os.environ.get("LAYA_MODEL", DEFAULT_MODEL)
        self.requested_revision = revision or os.environ.get("LAYA_REVISION") or None
        self.device = device or os.environ.get("LAYA_DEVICE") or None
        self.max_len = _int_env("LAYA_MAX_LEN")
        self.head_max_len = _int_env("LAYA_HEAD_MAX_LEN")
        if agent is None:
            agent, version, loaded_revision = _load_agent(self.model, self.requested_revision,
                                                          self.device)
        self._agent = agent
        self.version = version
        self.loaded_revision = loaded_revision
        self._token_counts = token_counts
        self.label = self.model.rstrip("/").split("/")[-1]
        self.name = f"laya:{self.label}"

    def _budgets(self) -> tuple[int, int]:
        cfg = getattr(self._agent, "cfg", {}) or {}
        return (self.max_len if self.max_len is not None else cfg.get("max_len", 512),
                self.head_max_len if self.head_max_len is not None
                else cfg.get("head_max_len", 192))

    def describe(self) -> dict:
        a = self._agent
        max_len, head_max_len = self._budgets()
        shipped = getattr(a, "temperature_by_options_raw", None) or {}
        applied = getattr(a, "temperature_by_options", None) or {}
        return {
            "name": self.name, "provider": "local", "model": self.label, "model_id": self.model,
            "revision": self.requested_revision, "loaded_revision": self.loaded_revision,
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
                # Laya: "Treat confidence from the affected entries as uncalibrated."
                "clamped_by_options": sorted(k for k, v in shipped.items()
                                             if k in applied and applied[k] != v),
            },
            "max_len": max_len, "head_max_len": head_max_len,
            "device": str(getattr(a, "device", "")) or None,
            "device_requested": self.device,
        }

    def _check_fit(self, state: str, payload: dict[str, dict]) -> None:
        max_len, head_max_len = self._budgets()
        for name, qdef in payload.items():
            problems = fit_problems(*self._token_counts(self._agent, state, qdef),
                                    max_len=max_len, head_max_len=head_max_len)
            if problems:
                raise ValueError(
                    f"question '{name}' does not fit Laya's token budgets (max_len={max_len}, "
                    f"head_max_len={head_max_len}): {'; '.join(problems)}. Laya would read it "
                    "truncated; raise LAYA_HEAD_MAX_LEN / LAYA_MAX_LEN or shortlist the options "
                    "(a pre-registration decision) instead")

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {q.name: laya_question(q) for q in questions}
        self._check_fit(state, payload)
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
