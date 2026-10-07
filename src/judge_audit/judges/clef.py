"""Clef and Clef-flash: open multimodal decision models (Apache-2.0), post-trained from
Qwen3.8-27B and Qwen3.5-9B, run locally through the code in their repositories.

A joint schema head reads the backbone's final hidden states and scores every option of every
question in one forward pass; `joint_schema_model.systemone` answers a System One request. The
adapter imports that file from the snapshot it downloads, at the pinned commit of the weights.

What is recorded, and why (see `systemone.py` for what every local decision model shares):

- **Confidence is the probability of the chosen option.** Clef's `confidence` field is the same
  number (rounded); it is kept in `raw` as `native_confidence`. Probabilities are rounded to 4
  decimals by `systemone`; the provenance says so.
- **The question ID is part of the prompt** (`ID: <name>` in each schema field), unlike the
  other decision models: renaming a question can change an answer.
- **Weights as released, in bfloat16.** No quantized variant is offered by this adapter.
- **No truncated state.** `encode_record` cuts the state to fit 16,384 tokens; the adapter
  measures the request with the same function and records its questions as no answer instead.

Memory: Clef-flash needs about 19 GB in bfloat16, Clef about 55 GB; both are tested with
stubbed models only.

Environment:
  CLEF_MODEL     Hub id or local directory (default Cloudflare/clef-flash)
  CLEF_REVISION  Hub commit (default: the pinned one for clef and clef-flash)
  CLEF_DEVICE    cpu | mps | cuda[:n] (default: CUDA, then MPS, then CPU)

Install: pip install 'kunko-judge-audit[clef]'
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from .systemone import LocalSystemOneJudge, best_device, captured_warnings

DEFAULT_MODEL = "Cloudflare/clef-flash"
# Hub commits pinned on 2026-10-05.
PINNED_REVISIONS = {
    "Cloudflare/clef-flash": "17f0b0ad64efb65d273590632833508766b2aae6",
    "Cloudflare/clef": "2f3de3dd85f379784083b0814d997ab627200f0c",
}
MAX_LENGTH = 16384                 # `systemone`'s window: the state is cut to fit it


class _ClefSystem:
    """The repository's `systemone` behind the keyword interface, with its window checked."""

    def __init__(self, module, model, processor, label: str):
        self.module, self.model, self.processor, self.label = module, model, processor, label

    def system_one(self, *, state, questions) -> dict:
        return self.module.systemone(self.model, self.processor,
                                     {"model": self.label, "state": state,
                                      "questions": questions}, max_length=MAX_LENGTH)

    def fit_problems(self, state, questions) -> list[str]:
        whole = self.module.encode_record(self.processor.tokenizer,
                                          {"state": state, "questions": questions},
                                          max_length=10**9, processor=self.processor)
        n = len(whole.input_ids)
        return [f"the request ({n} tokens) would be cut to {MAX_LENGTH}"] if n > MAX_LENGTH \
            else []


def _load(model_id: str, revision: str | None, device: str | None):
    try:
        import torch
        import transformers
        from huggingface_hub import snapshot_download
    except ImportError as e:
        raise RuntimeError("the clef judge needs: pip install 'kunko-judge-audit[clef]'") from e
    if Path(model_id).exists():
        path, loaded = Path(model_id), None
    else:
        path = Path(snapshot_download(model_id, revision=revision))
        loaded = path.name
    spec = importlib.util.spec_from_file_location(
        f"clef_joint_schema_{(loaded or 'local')[:12]}", path / "joint_schema_model.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"{path} has no joint_schema_model.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    used = best_device(device)
    with captured_warnings("transformers") as messages:
        model, processor = module.load_release_model(path, device=used, dtype=torch.bfloat16)
    label = model_id.rstrip("/").split("/")[-1]
    info = {
        "loaded_revision": loaded,
        "code": "joint_schema_model.py from the model repository at the loaded revision",
        "dtype": "bfloat16", "quantization": None,
        "device": used,
        "max_length": MAX_LENGTH,
        "softmax_temperature": "none: softmax of the joint head's logits",
        "probability_resolution": 1e-4,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "loader_warnings": messages,
    }
    return _ClefSystem(module, model, processor, label), info


class ClefJudge(LocalSystemOneJudge):
    name = family = "clef"
    env = "CLEF"
    default_model = DEFAULT_MODEL
    pinned = PINNED_REVISIONS
    raw_fields = {"confidence": "native_confidence", "score": "expected_level"}
    native_confidence = ("Clef's `confidence` field is P(chosen option) rounded to 4 decimals "
                         "(score: P(most probable level)); kept in raw as native_confidence")

    def load(self, model_id: str, revision: str | None, device: str | None):
        return _load(model_id, revision, device)
