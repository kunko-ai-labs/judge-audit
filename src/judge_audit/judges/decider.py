"""decider: Mapika's open decision models (Apache-2.0; 0.8B, 2B, 4B), run locally.

decider reads the letter logits at an answer slot after the lettered options, one row per
question, and returns a probability per option through its own System One method
(`decider.infer.Decider.system_one`). The code ships inside each model repository, so the
adapter imports it from the snapshot it downloads, at the same pinned commit as the weights.

What is recorded, and why (see `systemone.py` for what every local decision model shares):

- **Confidence is the probability of the chosen option** (`probabilities[choice]`, which
  decider also returns as `x_p_max`). Its `confidence` field follows TypeSafe's definitions:
  (n * p_max - 1)/(n - 1) for a choice, and for a score `score_confidence`, 1 minus the expected
  distance from the most likely level divided by the mean distance of the levels from the middle
  of the scale. Its `certainty` is a normalized entropy. Both are kept in `raw` as
  `typesafe_confidence` and `entropy_confidence`, never audited.
- **Probabilities are rounded to 4 decimals by decider's `system_one`**; the provenance says so.
- **Temperatures.** The softmax temperature per answer type comes from the repository's
  `decider_config.json` (decider-2b v11: choice 1.164, yes/no 1.624, score 1.124); the global
  and per-type values applied are recorded.
- **Precision.** decider runs in float16 on Apple MPS and bfloat16 elsewhere; the dtype loaded
  is recorded. The two precisions can choose differently (they do on the model card's own
  example), so reference outputs are recorded per kind of device.
- **One question per request on MPS.** On MPS a question's answer depends on the other
  questions in the same request (they are padded into one float16 batch): on the model card's
  example, `department` is billing at 0.5122 alone and 0.5155 with the other two questions,
  where decider's own docstring says that other questions cannot change an answer. On MPS the
  adapter therefore sends each question in its own request (`questions_per_request` 1 in the
  provenance); on CPU and CUDA it sends them together, as decider does.
- **One size per process.** decider's code is imported from the snapshot of the model loaded;
  a second size (another snapshot) in the same process is refused. Run each size in its own
  process (an Arena or MCP run over several sizes included).
- **No truncated state.** decider cuts the state at 32,768 tokens; the adapter records the
  request's questions as no answer instead.

Environment:
  DECIDER_MODEL     Hub id or local directory (default Mapika/decider-2b)
  DECIDER_REVISION  Hub commit (default: the pinned one for decider-0.8b, -2b and -4b)
  DECIDER_DEVICE    cpu | mps | cuda[:n] (default: CUDA, then MPS, then CPU)

Install: pip install 'kunko-judge-audit[decider]'
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .systemone import LocalSystemOneJudge, best_device, captured_warnings

DEFAULT_MODEL = "Mapika/decider-2b"
# Hub commits pinned on 2026-10-05 (decider-2b main is v11; the tags v10 and v8 are older).
PINNED_REVISIONS = {
    "Mapika/decider-2b": "533964dae8be954c5b5e19fa4948e48408094c1e",
    "Mapika/decider-0.8b": "a0a01d6f8135298f400a8c856b355793012ae971",
    "Mapika/decider-4b": "eb5fbdfc9448473ec25e399882912863afbdb70e",
}
MAX_STATE_TOKENS = 32768          # decider's system_one default: the state is cut beyond it

# The model card's System One example.
REFERENCE_STATE = {
    "ticket": {"messages": [{"from": "customer", "text": "I was charged twice for order A-104. "
                                                         "Please refund the duplicate."}]},
    "refund_policy": "Duplicate charges are eligible for a refund."}
REFERENCE_QUESTIONS = {
    "department": {"type": "choice", "instructions": "Which team should handle this?",
                   "criteria": {"returns": "Exchanges, refunds, wrong or damaged items",
                                "billing": {"what": "Charges, invoices", "not_for": "delivery"},
                                "other": None}},
    "refund_requested": {"type": "noul",
                         "instructions": "Does `ticket.messages[0].text` request a refund?"},
    "frustration": {"type": "score", "instructions": "How frustrated is the customer?",
                    "criteria": ["calm", "frustrated", "very frustrated"]},
}
# Its answers by (model, revision, kind of device), recorded with transformers 5.17.0 and torch
# 2.14.0 on an Apple laptop: float16 on MPS, bfloat16 on CPU (decider's defaults), each through
# the adapter (on MPS one question per request). The two precisions choose differently on this
# very example (billing at 0.5122 on MPS; returns on CPU, where returns and billing both round
# to 0.4953): a run's device is part of what it measures.
REFERENCE_OUTPUTS: dict[tuple[str, str, str], dict] = {
    (DEFAULT_MODEL, PINNED_REVISIONS[DEFAULT_MODEL], "mps"): {
        "department": {"type": "choice", "choice": "billing",
                       "probabilities": {"returns": 0.479, "billing": 0.5122, "other": 0.0088}},
        "refund_requested": {"type": "noul", "noul": 0.9588},
        "frustration": {"type": "score",
                        "probabilities": {"0": 0.1638, "1": 0.5809, "2": 0.2553}},
    },
    (DEFAULT_MODEL, PINNED_REVISIONS[DEFAULT_MODEL], "cpu"): {
        "department": {"type": "choice", "choice": "returns",
                       "probabilities": {"returns": 0.4953, "billing": 0.4953, "other": 0.0093}},
        "refund_requested": {"type": "noul", "noul": 0.9576},
        "frustration": {"type": "score",
                        "probabilities": {"0": 0.1617, "1": 0.5783, "2": 0.26}},
    },
}
REFERENCE_TOLERANCE = 2e-4        # decider rounds to 1e-4: one rounding step either way


class _DeciderSystem:
    """decider's Decider behind the keyword interface, with its state budget checked. With
    `one_per_request` every question goes in its own request (on MPS, where an answer depends
    on the other questions of the request)."""

    def __init__(self, decider, render_state, one_per_request: bool = False):
        self.decider = decider
        self._render_state = render_state
        self.one_per_request = one_per_request

    def system_one(self, *, state, questions) -> dict:
        if not self.one_per_request or len(questions) == 1:
            return self.decider.system_one(state, questions)
        answers: dict = {}
        tokens, model = 0, None
        for name, question in questions.items():
            result = self.decider.system_one(state, {name: question})
            answers.update(result.get("answers") or {})
            tokens += (result.get("usage") or {}).get("input_tokens", 0)
            model = result.get("model")
        return {"model": model, "answers": answers,
                "usage": {"input_tokens": tokens, "output_tokens": 0}}

    def fit_problems(self, state, questions) -> list[str]:
        tok = self.decider.m.tok
        n = len(tok.encode("Context:\n" + self._render_state(state), add_special_tokens=False))
        if n > MAX_STATE_TOKENS:
            return [f"the state ({n} tokens) would be cut to {MAX_STATE_TOKENS}"]
        return []


def _import_decider(path: Path):
    """decider's Decider and render_state from the code in the model repository at `path`."""
    loaded = sys.modules.get("decider")
    if loaded is not None and not str(getattr(loaded, "__file__", "")).startswith(str(path)):
        raise RuntimeError(f"another `decider` package is already imported ({loaded.__file__}); "
                           "the decider judge runs the code shipped in the model repository")
    sys.path.insert(0, str(path))
    try:
        from decider.infer import Decider
        from decider.systemone import render_state
    finally:
        sys.path.remove(str(path))
    return Decider, render_state


def _load(model_id: str, revision: str | None, device: str | None):
    try:
        import torch
        import transformers
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise RuntimeError("the decider judge needs: pip install 'kunko-judge-audit[decider]'") \
            from e
    if Path(model_id).exists():
        path, loaded = Path(model_id), None
    else:
        path = Path(snapshot_download(model_id, revision=revision))
        loaded = path.name                  # the cache stores a snapshot under its commit
    config = json.loads((path / "decider_config.json").read_text(encoding="utf-8"))
    used = best_device(device)
    with captured_warnings("transformers", "decider") as messages:
        Decider, render_state = _import_decider(path)
        d = Decider(str(path), device=used)
    info = {
        "loaded_revision": loaded,
        "decider_version": config.get("version"),
        "release_date": config.get("release_date"),
        "code": "decider/ from the model repository at the loaded revision",
        "softmax_temperature": {"global": d.T, "by_type": d.T_by_type},
        "layout": getattr(d, "layout", None),
        "isolated_levels": getattr(d, "isolated_levels", None),
        "neutralize_none": getattr(d, "neutralize_none", None),
        "device": str(d.dev),
        "dtype": str(next(d.m.parameters()).dtype).replace("torch.", ""),
        "max_state_tokens": MAX_STATE_TOKENS,
        "probability_resolution": 1e-4,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "loader_warnings": messages,
    }
    one_per_request = str(d.dev).startswith("mps")
    info["questions_per_request"] = 1 if one_per_request else "all"
    return _DeciderSystem(d, render_state, one_per_request), info


class DeciderJudge(LocalSystemOneJudge):
    name = family = "decider"
    env = "DECIDER"
    default_model = DEFAULT_MODEL
    pinned = PINNED_REVISIONS
    reference_state = REFERENCE_STATE
    reference_questions = REFERENCE_QUESTIONS
    reference_outputs = REFERENCE_OUTPUTS
    reference_tolerance = REFERENCE_TOLERANCE
    raw_fields = {"confidence": "typesafe_confidence", "certainty": "entropy_confidence",
                  "x_p_max": "x_p_max", "score": "expected_level", "level_fit": "level_fit",
                  "fit_mass": "fit_mass"}
    native_confidence = ("decider's `confidence` field follows TypeSafe: (n * p_max - 1)/(n - 1) "
                         "for a choice, score_confidence (ordinal) for a score "
                         "(raw.typesafe_confidence); `certainty` is a normalized entropy "
                         "(raw.entropy_confidence); neither is audited")

    def load(self, model_id: str, revision: str | None, device: str | None):
        return _load(model_id, revision, device)
