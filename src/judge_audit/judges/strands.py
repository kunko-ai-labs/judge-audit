"""Strands Decider: an open decision model (Apache-2.0), a LoRA adapter and readout head on
Qwen3.5-2B-Base, run locally through the `strands-decider` package.

What is recorded, and why (see `systemone.py` for what every local decision model shares):

- **Confidence is the probability of the chosen option.** Strands Decider's `confidence`
  field is derived: (n * p_max - 1)/(n - 1) for a choice, an ordinal measure for a score
  (0.769 where P(chosen) is 0.846 on the model card's example). It is kept in `raw` as
  `typesafe_confidence`, never audited. Probabilities are rounded to 4 decimals by the package.
- **Two revisions.** The checkpoint names its base model without a revision. The adapter
  downloads the checkpoint at its pinned commit and the base at the revision the checkpoint's
  own `provenance.json` records (which its publisher says was inferred, not pinned at
  training), and loads the pair from a local view whose config names that local base. Both
  commits are recorded.
- **Temperatures** per question type ship in the checkpoint config; they are recorded.
- **Precision.** The torso runs in the checkpoint's dtype (bfloat16), upcast to float32 on CPU
  by the package; the dtype used is recorded.
- **No truncated input.** The package fits a request into `max_length` tokens by cutting a
  long question from the front and the state from the end; the adapter redoes that arithmetic
  with the package's own tokenizer and rendering and raises instead.

Environment:
  STRANDS_MODEL          Hub id or local directory (default the 2B hobson-v19 checkpoint)
  STRANDS_REVISION       Hub commit of the checkpoint (default: pinned)
  STRANDS_BASE_REVISION  Hub commit of the base (default: the checkpoint's provenance.json)
  STRANDS_DEVICE         cpu | mps | cuda[:n] (default: CUDA, then MPS, then CPU)

Install: pip install 'kunko-judge-audit[strands]'
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from importlib import metadata
from pathlib import Path

from .systemone import LocalSystemOneJudge, best_device, captured_warnings

DEFAULT_MODEL = "StrandsAgents/strands-decider-2B-hobson-v19"
# Hub commit pinned on 2026-10-05.
PINNED_REVISIONS = {DEFAULT_MODEL: "bb282d786bc251fd4e3068de3ada9ddbb38127cd"}
CONFIG_NAMES = ("strands_decider_config.json", "hobson_config.json")

# The model card's example (its CLI names the questions noul_0, choice_0, score_0 and sends
# options without descriptions as "").
REFERENCE_STATE = "Help! My payouts have been failing for 3 days! "
REFERENCE_QUESTIONS = {
    "noul_0": {"type": "noul", "instructions": "Does this convey urgency?"},
    "choice_0": {"type": "choice", "instructions": "Which team should handle this?",
                 "criteria": {"billing": "", "sales": "", "retail": ""}},
    "score_0": {"type": "score", "instructions": "How frustrated is the writer?",
                "criteria": ["calm", "frustrated", "depressed"]},
}
# The outputs the model card prints for this checkpoint, to 3 decimals, held on every device.
REFERENCE_OUTPUTS = {
    (DEFAULT_MODEL, PINNED_REVISIONS[DEFAULT_MODEL], "*"): {
        "noul_0": {"type": "noul", "noul": 0.829},
        "choice_0": {"type": "choice", "choice": "billing",
                     "probabilities": {"billing": 0.846, "retail": 0.090, "sales": 0.064}},
        "score_0": {"type": "score",
                    "probabilities": {"0": 0.163, "1": 0.574, "2": 0.263}},
    },
}
REFERENCE_TOLERANCE = 0.005       # the card's rounding plus bfloat16 differences between devices


class _StrandsSystem:
    """The package's engine behind the keyword interface, with its window checked."""

    def __init__(self, engine, schema, prompting):
        self.engine = engine
        self._schema = schema
        self._prompting = prompting

    def system_one(self, *, state, questions) -> dict:
        request = self._schema.SystemOneRequest(state=state, questions=questions)
        return self.engine.evaluate(request).model_dump()

    def fit_problems(self, state, questions) -> list[str]:
        """What the engine's `_fit` would cut, from the same tokenizer and rendering."""
        request = self._schema.SystemOneRequest(state=state, questions=questions)
        tok, max_len = self.engine.tok, self.engine.model.config.max_length
        texts = {k: self._prompting.render_question(q).text for k, q in request.questions.items()}
        lens = {k: len(tok(t, add_special_tokens=False)["input_ids"]) for k, t in texts.items()}
        reserve = min(max(lens.values()),
                      max(1, int(max_len * self.engine.cfg.max_question_fraction)))
        problems = [f"question '{k}' ({n} tokens) would be cut to {reserve} from the front"
                    for k, n in lens.items() if n > reserve]
        n_state = len(tok(self._prompting.render_state(request.state),
                          add_special_tokens=True)["input_ids"])
        budget = max(1, max_len - reserve)
        if n_state > budget:
            problems.append(f"the state ({n_state} tokens) would be cut to {budget}")
        return problems


def _view(checkpoint: Path, base: str) -> Path:
    """A directory with the checkpoint's files, whose config names the local `base`."""
    view = Path(tempfile.mkdtemp(prefix="strands-view-"))
    for entry in checkpoint.iterdir():
        if entry.name not in CONFIG_NAMES:
            (view / entry.name).symlink_to(entry.resolve())
    for name in CONFIG_NAMES:
        if (checkpoint / name).exists():
            config = json.loads((checkpoint / name).read_text(encoding="utf-8"))
            config["base_model"] = base
            (view / name).write_text(json.dumps(config, indent=2), encoding="utf-8")
    return view


def _load(model_id: str, revision: str | None, device: str | None):
    try:
        import torch
        import transformers
        from huggingface_hub import snapshot_download
        from strands_decider import infer, prompting, schema
    except ImportError as e:
        raise RuntimeError("the strands judge needs: pip install 'kunko-judge-audit[strands]'") \
            from e
    if Path(model_id).exists():
        checkpoint, loaded = Path(model_id), None
    else:
        checkpoint = Path(snapshot_download(model_id, revision=revision))
        loaded = checkpoint.name
    provenance = json.loads((checkpoint / "provenance.json").read_text(encoding="utf-8")) \
        if (checkpoint / "provenance.json").exists() else {}
    config_file = next(checkpoint / n for n in CONFIG_NAMES if (checkpoint / n).exists())
    config = json.loads(config_file.read_text(encoding="utf-8"))
    base_id = config["base_model"]
    base_revision = (os.environ.get("STRANDS_BASE_REVISION")
                     or provenance.get("base_model_revision"))
    if not base_revision:
        raise ValueError(f"{model_id} records no revision for its base {base_id}: set "
                         "STRANDS_BASE_REVISION")
    base = Path(snapshot_download(base_id, revision=base_revision))
    used = best_device(device)
    view = _view(checkpoint, str(base))
    try:
        with captured_warnings("transformers", "peft", "strands_decider") as messages:
            engine = infer.load_engine(str(view), device=used)
    finally:
        shutil.rmtree(view, ignore_errors=True)       # links only; the weights are loaded
    info = {
        "loaded_revision": loaded,
        "base_model": base_id, "base_revision": base_revision,
        "base_revision_note": provenance.get("base_model_revision_note"),
        "checkpoint_name": provenance.get("name"),
        "strands_decider_version": metadata.version("strands-decider"),
        "softmax_temperature": {"global": config.get("temperature"),
                                "by_type": config.get("temperature_by_kind")},
        "max_length": config.get("max_length"),
        "use_prefix_cache": engine.cfg.use_prefix_cache,
        "device": str(engine.device),
        "dtype": str(next(engine.model.torso.parameters()).dtype).replace("torch.", ""),
        "probability_resolution": 1e-4,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "loader_warnings": messages,
    }
    return _StrandsSystem(engine, schema, prompting), info


class StrandsJudge(LocalSystemOneJudge):
    name = family = "strands"
    env = "STRANDS"
    default_model = DEFAULT_MODEL
    pinned = PINNED_REVISIONS
    reference_state = REFERENCE_STATE
    reference_questions = REFERENCE_QUESTIONS
    reference_outputs = REFERENCE_OUTPUTS
    reference_tolerance = REFERENCE_TOLERANCE
    blank_description = ""                    # the package requires a string per option
    raw_fields = {"confidence": "typesafe_confidence", "score": "expected_level"}
    native_confidence = ("Strands Decider's `confidence` field: (n * p_max - 1)/(n - 1) for a "
                         "choice, an ordinal measure for a score; kept in raw as "
                         "typesafe_confidence, not audited")

    def load(self, model_id: str, revision: str | None, device: str | None):
        return _load(model_id, revision, device)
