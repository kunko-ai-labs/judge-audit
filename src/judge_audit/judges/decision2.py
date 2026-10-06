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
  commit loaded is recorded, with the package's own weight identity (`model_sha256`). The
  revision must be a 40-hex commit, not a branch or tag. A local directory loads as it is,
  without a revision: `loaded_revision` is then whatever its config records, and the reference
  check is `unchecked`.
- **The softmax temperatures, calibration file and score offsets** the runtime applies, per
  question type. Kai-0.6B ships no calibration file (temperature 1) but does ship
  `score_bias.json`: fixed per-level logit offsets added to 5-level score questions before the
  softmax, so those probabilities are not raw. The file, its sha256 and the level counts it
  covers are recorded (`score_bias`).
- **Loader warnings, and two checks before any decision.** Transformers 5.17 warns that the
  tokenizer has "an incorrect regex pattern" (it reads the package's config.json, which has no
  `transformers_version`, as a possible Mistral tokenizer; no fix is applied unless asked).
  Every warning the load emits is recorded. Then (1) the tokenizer the runtime uses must
  encode probe texts exactly as the package's own `tokenizer.json` does, and (2) the model
  card's example must give the outputs recorded in `REFERENCE_OUTPUTS` for that revision and
  kind of device, within `REFERENCE_TOLERANCE`; either difference raises. The runtime computes
  in FP32 on CPU and MPS but in BF16 autocast on a CUDA GPU, so outputs are recorded per kind
  of device; a revision or device without recorded outputs is loaded and marked `unchecked`
  in the provenance.
- **Over-length input is not truncated.** The runtime answers `max_length_exceeded` instead;
  the adapter records it as no answer, with the error in `raw`.

Environment:
  DECISION2_MODEL     Hub id or local directory (default vllm-sr/Decision-2.0-Kai-0.6B)
  DECISION2_REVISION  Hub commit (default: the pinned one for the six released models)
  DECISION2_DEVICE    cpu | mps | cuda[:n] (default: the runtime's, cuda:0 if present else cpu)

Install: pip install 'kunko-judge-audit[decision2]'
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import Question
from .systemone import LocalSystemOneJudge, captured_warnings, systemone_question
from .systemone import check_reference as _check_reference

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
# Its answers by (model, revision, kind of device), recorded with transformers 5.17.0 and torch
# 2.14.0 on Apple MPS; the runtime computes in FP32 there and on CPU, where the same run
# differs by at most 5e-7. On CUDA it uses BF16 autocast: no outputs are recorded for it yet.
_KAI_FP32 = {
        "route": {"type": "choice", "choice": "returns",
                  "probabilities": {"returns": 0.962132, "billing": 0.013547,
                                    "technical": 0.024320},
                  "confidence": 0.830877},
        "receipt": {"type": "noul", "noul": 0.915762},
        "urgency": {"type": "score", "score": 1.475152,
                    "probabilities": {"0": 0.164247, "1": 0.196354, "2": 0.639399},
                    "confidence": 0.178708},
}
REFERENCE_OUTPUTS: dict[tuple[str, str, str], dict[str, Any]] = {
    (KAI, PINNED_REVISIONS[KAI], "mps"): _KAI_FP32,
    (KAI, PINNED_REVISIONS[KAI], "cpu"): _KAI_FP32,
}
REFERENCE_TOLERANCE = 1e-4          # the stored values are rounded to 1e-6
# Probe texts for the tokenizer check: punctuation, digits, accents, curly quotes, newlines.
TOKENIZER_PROBES = (REFERENCE_STATE,
                    "Mi tarjeta no llegó; ¿dónde está? Ref. #4521-B, 3x 12,50 €.",
                    "Line one\n\n  Line two\twith a TAB, CAPS'S and it’s “quoted”.",
                    '{"amount": 1200.5, "currency": "EUR", "items": [1, 2, 3]}')


def check_reference(got: dict, expected: dict,
                    tolerance: float = REFERENCE_TOLERANCE) -> dict:
    """Compare the model card example's answers with the recorded ones: same decisions, every
    declared probability within `tolerance`."""
    return _check_reference(got, expected, tolerance)


def score_bias_of(manifest: dict, applied) -> dict | None:
    """The fixed per-level logit offsets the runtime adds to score questions before the softmax
    (Kai-0.6B: 5-level scores), as the manifest names them; None when the package has none."""
    entry = manifest.get("score_bias")
    if not entry:
        return None
    return {"file": entry.get("file"), "sha256": entry.get("sha256"),
            "levels": sorted(int(k) for k in (entry.get("offsets") or {})),
            "offsets": entry.get("offsets"), "applied": applied is not None}


def tokenizer_check(tokenizer, tokenizer_json: Path) -> dict:
    """Does the tokenizer the runtime loaded encode the probes as the package's tokenizer.json?"""
    from tokenizers import Tokenizer

    raw = Tokenizer.from_file(str(tokenizer_json))
    differ = [i for i, text in enumerate(TOKENIZER_PROBES)
              if tokenizer(text, add_special_tokens=False)["input_ids"]
              != raw.encode(text, add_special_tokens=False).ids]
    return {"matches_tokenizer_json": not differ, "probes": len(TOKENIZER_PROBES),
            "differing_probes": differ}


def _load(model_id: str, revision: str | None, device: str | None):
    """(the loaded model, its provenance), the load's warnings captured."""
    try:
        import torch
        import transformers
        from transformers import AutoModel
    except ImportError as e:
        raise RuntimeError("the decision2 judge needs: "
                           "pip install 'kunko-judge-audit[decision2]'") from e
    kwargs: dict = {"revision": revision} if revision else {}
    if device:
        kwargs["device"] = device
    with captured_warnings("transformers") as messages:
        model = AutoModel.from_pretrained(model_id, trust_remote_code=True, **kwargs)
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
        "score_bias": score_bias_of(manifest, getattr(backend, "score_bias", None)),
        "softmax_temperature": dict(getattr(backend, "temperatures", {}) or {}),
        "share_context": getattr(backend, "share_context", None),
        "device": str(getattr(backend, "device", "")) or None,
        "max_input_tokens": manifest.get("max_input_tokens"),
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "runtime_tested_transformers": (manifest.get("remote_code") or {}).get("tested"),
        "loader_warnings": messages,
        "tokenizer_check": tokenizer_check(backend.tokenizer, source / "tokenizer.json"),
    }
    return model, info


def decision2_question(q: Question) -> dict:
    """One judge-audit question in Decision 2.0's System One format."""
    return systemone_question(q)


class Decision2Judge(LocalSystemOneJudge):
    name = family = "decision2"
    env = "DECISION2"
    default_model = DEFAULT_MODEL
    pinned = PINNED_REVISIONS
    reference_state = REFERENCE_STATE
    reference_questions = REFERENCE_QUESTIONS
    reference_outputs = REFERENCE_OUTPUTS
    reference_tolerance = REFERENCE_TOLERANCE
    raw_fields = {"confidence": "entropy_confidence", "score": "expected_level"}
    native_confidence = ("the model's `confidence` field, a normalized entropy 1 - H(p)/log K; "
                         "kept in raw as entropy_confidence, not audited")

    def load(self, model_id: str, revision: str | None, device: str | None):
        return _load(model_id, revision, device)

    def preflight(self) -> None:
        check = self.info.get("tokenizer_check") or {}
        if check.get("matches_tokenizer_json") is False:
            raise RuntimeError(f"{self.label}: the tokenizer loaded encodes "
                               f"{check['differing_probes']} differently from the package's "
                               "tokenizer.json; outputs would change")
