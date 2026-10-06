"""Decision2Judge with a stubbed model: what it sends, which confidence it keeps, what it records,
and the reference check that runs before any decision."""
from __future__ import annotations

import os

import pytest

from judge_audit.judges import decision2
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.decision2 import (
    KAI,
    PINNED_REVISIONS,
    REFERENCE_OUTPUTS,
    Decision2Judge,
    check_reference,
    decision2_question,
)

KAI_SHA = PINNED_REVISIONS[KAI]


class FakeModel:
    """Answers the reference request with the recorded outputs, anything else from `answers`."""

    def __init__(self, answers=None, reference=None):
        self.answers = answers or {}
        self.reference = (reference if reference is not None
                          else REFERENCE_OUTPUTS[(KAI, KAI_SHA, "mps")])
        self.calls: list[tuple] = []

    def system_one(self, *, state, questions):
        self.calls.append((state, questions))
        if state == decision2.REFERENCE_STATE:
            return {"model": "Decision-2.0-Kai-0.6B", "answers": self.reference,
                    "usage": {"input_tokens": 286, "output_tokens": 0}}
        return {"model": "Decision-2.0-Kai-0.6B",
                "answers": {k: v for k, v in self.answers.items() if k in questions},
                "usage": {"input_tokens": 40, "output_tokens": 0}}


INFO = {"loaded_revision": KAI_SHA, "model_sha256": "bb806f31", "profile": "qwen-full",
        "calibration": None, "softmax_temperature": {"choice": 1.0, "noul": 1.0, "score": 1.0},
        "device": "mps", "max_input_tokens": 8192, "transformers_version": "5.17.0",
        "torch_version": "2.14.0", "runtime_tested_transformers": ["5.17.0", "5.18.0"],
        "loader_warnings": ["transformers.tokenization_utils_tokenizers: The tokenizer you are "
                            "loading from '...' with an incorrect regex pattern"],
        "tokenizer_check": {"matches_tokenizer_json": True, "probes": 4}}


def judge(answers=None, **kwargs):
    model = FakeModel(answers, **kwargs)
    return Decision2Judge(model_id=KAI, system=model, info=dict(INFO)), model


ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["returns", "billing"], descriptions={"returns": "refunds"})
RECEIPT = Question(name="receipt", type=QuestionType.NOUL, instructions="Has a receipt?")
URGENCY = Question(name="urgency", type=QuestionType.SCORE, instructions="How urgent?",
                   options=["routine", "soon", "today"], descriptions={"today": "Today"})


def test_choice_audits_the_chosen_option_probability_and_keeps_the_entropy_field():
    j, model = judge({"route": {"type": "choice", "choice": "returns",
                                "probabilities": {"returns": 0.96, "billing": 0.04},
                                "confidence": 0.83}})
    (out,) = j.decide("damaged order", [ROUTE])
    state, sent = model.calls[-1]
    assert state == "damaged order"
    assert sent == {"route": {"type": "choice", "instructions": "Which team?",
                              "criteria": {"returns": "refunds", "billing": None}}}
    assert out.decision == "returns" and out.confidence == 0.96
    assert out.raw["entropy_confidence"] == 0.83          # native field: kept, never audited
    assert out.raw["probabilities"] == {"returns": 0.96, "billing": 0.04}
    assert out.raw["served"] == {"model": "Decision-2.0-Kai-0.6B", "system_fingerprint": None}
    assert out.cost_usd == 0.0 and out.parse_status == "parsed"


def test_noul_is_true_or_false_with_the_probability_of_that_answer():
    j, _ = judge({"receipt": {"type": "noul", "noul": 0.2}})
    (out,) = j.decide("x", [RECEIPT])
    assert out.decision == "false" and out.confidence == pytest.approx(0.8)
    assert out.raw["probabilities"] == {"true": 0.2, "false": pytest.approx(0.8)}
    j, model = judge({"receipt": {"type": "noul", "noul": 0.5}})
    (out,) = j.decide("x", [RECEIPT])
    assert out.decision == "true" and out.confidence == 0.5          # a tie reads "true", as Jev
    assert model.calls[-1][1] == {"receipt": {"type": "noul", "instructions": "Has a receipt?"}}


def test_score_maps_the_most_probable_level_back_to_its_option():
    j, model = judge({"urgency": {"type": "score", "score": 1.47, "confidence": 0.18,
                                  "probabilities": {"0": 0.16, "1": 0.2, "2": 0.64}}})
    (out,) = j.decide("x", [URGENCY])
    assert model.calls[-1][1]["urgency"]["criteria"] == ["routine", "soon", "Today"]
    assert out.decision == "today" and out.confidence == 0.64
    assert out.raw["expected_level"] == 1.47 and out.raw["entropy_confidence"] == 0.18


def test_a_refused_or_missing_answer_is_no_answer_with_unknown_confidence():
    j, _ = judge({"route": {"type": "choice", "error": "max_length_exceeded"}})
    (out,) = j.decide("a very long state", [ROUTE])
    assert out.decision == "" and out.confidence is None and out.parse_status == "no_answer"
    assert out.raw["error"] == "max_length_exceeded"
    (out,) = judge({})[0].decide("x", [ROUTE])
    assert out.parse_status == "no_answer" and out.confidence is None


def test_provenance_records_the_revision_warnings_and_both_checks():
    j, _ = judge()
    d = j.describe()
    assert d["name"] == "decision2:Decision-2.0-Kai-0.6B" and d["provider"] == "local"
    assert d["model_id"] == KAI and d["revision"] == KAI_SHA and d["loaded_revision"] == KAI_SHA
    assert d["temperature"] == "n/a" and d["softmax_temperature"]["choice"] == 1.0
    assert "incorrect regex pattern" in d["loader_warnings"][0]
    assert d["tokenizer_check"]["matches_tokenizer_json"] is True
    assert d["reference_check"]["status"] == "passed"
    assert d["reference_check"]["max_abs_diff"] == 0.0
    assert "normalized entropy" in d["native_confidence"]


def test_the_reference_check_refuses_a_model_that_answers_differently():
    ref = REFERENCE_OUTPUTS[(KAI, KAI_SHA, "mps")]
    drifted = {**ref, "route": {**ref["route"], "probabilities": {
        "returns": 0.90, "billing": 0.05, "technical": 0.05}}}
    with pytest.raises(RuntimeError, match="differs from the reference.*route"):
        judge(reference=drifted)
    flipped = {**ref, "receipt": {"type": "noul", "noul": 0.4}}
    with pytest.raises(RuntimeError, match="receipt"):
        judge(reference=flipped)


def test_check_reference_by_hand():
    ref = REFERENCE_OUTPUTS[(KAI, KAI_SHA, "mps")]
    close = {**ref, "receipt": {"type": "noul", "noul": ref["receipt"]["noul"] + 5e-5}}
    status = check_reference(close, ref)
    assert status["status"] == "passed" and status["max_abs_diff"] == pytest.approx(5e-5)
    assert check_reference({**ref, "urgency": {"error": "invalid_model_output"}},
                           ref)["status"] == "failed"


def test_a_revision_without_reference_outputs_is_recorded_as_unchecked():
    other = "0" * 40
    j = Decision2Judge(model_id=KAI, revision=other, system=FakeModel(),
                       info={**INFO, "loaded_revision": other})
    assert j.describe()["reference_check"]["status"] == "unchecked"


def test_outputs_are_checked_only_on_the_kind_of_device_they_were_recorded_on():
    # CPU and MPS run FP32 (recorded); CUDA runs BF16 autocast (not recorded yet)
    for device, status in (("cpu", "passed"), ("mps", "passed"), ("cuda:0", "unchecked")):
        j = Decision2Judge(model_id=KAI, system=FakeModel(), info={**INFO, "device": device})
        assert j.describe()["reference_check"]["status"] == status


def test_known_models_default_to_their_pinned_revision_and_unknown_ones_need_a_pin(monkeypatch):
    monkeypatch.delenv("DECISION2_REVISION", raising=False)
    assert Decision2Judge(model_id=KAI, system=FakeModel(), info=dict(INFO)).requested_revision \
        == KAI_SHA
    with pytest.raises(ValueError, match="DECISION2_REVISION"):
        Decision2Judge(model_id="someone/Decision-2.0-Fork", system=FakeModel(), info=INFO)
    assert len(PINNED_REVISIONS) == 6
    assert all(len(sha) == 40 for sha in PINNED_REVISIONS.values())


def test_a_branch_or_tag_is_not_a_pin_but_a_local_directory_needs_none(monkeypatch, tmp_path):
    monkeypatch.delenv("DECISION2_REVISION", raising=False)
    for ref in ("main", "v2", KAI_SHA[:12], KAI_SHA.upper()):
        with pytest.raises(ValueError, match="40-hex Hub commit"):
            Decision2Judge(model_id=KAI, revision=ref, system=FakeModel(), info=dict(INFO))
    j = Decision2Judge(model_id=str(tmp_path), system=FakeModel(),
                       info={**INFO, "loaded_revision": None})
    assert j.requested_revision is None
    assert j.describe()["reference_check"]["status"] == "unchecked"


def test_a_tokenizer_that_differs_from_the_package_refuses_before_the_reference_request():
    model = FakeModel()
    bad = {**INFO, "tokenizer_check": {"matches_tokenizer_json": False, "probes": 4,
                                       "differing_probes": [1, 3]}}
    with pytest.raises(RuntimeError, match=r"encodes \[1, 3\] differently.*tokenizer.json"):
        Decision2Judge(model_id=KAI, system=model, info=bad)
    assert model.calls == []                       # refused before any request


def test_score_offsets_are_recorded_from_the_manifest():
    manifest = {"score_bias": {"file": "score_bias.json", "sha256": "7d3a06",
                               "offsets": {"5": [0.04, 0.2, 0.08, -0.15, -0.17]}}}
    assert decision2.score_bias_of(manifest, applied={5: [0.04]}) == {
        "file": "score_bias.json", "sha256": "7d3a06", "levels": [5],
        "offsets": {"5": [0.04, 0.2, 0.08, -0.15, -0.17]}, "applied": True}
    assert decision2.score_bias_of({}, applied=None) is None


def test_unsupported_questions_are_refused():
    with pytest.raises(RuntimeError, match="no options"):
        decision2_question(Question(name="c", type=QuestionType.CHOICE, instructions="?"))
    with pytest.raises(RuntimeError, match="2 to 10 levels"):
        decision2_question(Question(name="s", type=QuestionType.SCORE, instructions="?",
                                    options=["only"]))


def test_without_transformers_the_error_says_how_to_install(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_transformers(name, *args, **kwargs):
        if name == "transformers":
            raise ImportError("no module named transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_transformers)
    with pytest.raises(RuntimeError, match=r"kunko-judge-audit\[decision2\]"):
        Decision2Judge(model_id=KAI)


# --- opt-in: the real Kai-0.6B at its pinned revision -----------------------------------------


@pytest.mark.skipif(os.environ.get("JUDGE_AUDIT_SMOKE_DECISION2") != "1",
                    reason="downloads Decision-2.0-Kai-0.6B (1.4 GB); set "
                           "JUDGE_AUDIT_SMOKE_DECISION2=1")
def test_smoke_kai_06b_loads_pinned_and_matches_the_model_card_reference():
    j = Decision2Judge(model_id=KAI)
    d = j.describe()
    assert d["loaded_revision"] == KAI_SHA
    assert d["reference_check"]["status"] == (
        "unchecked" if d["device"].startswith("cuda") else "passed")
    assert d["tokenizer_check"]["matches_tokenizer_json"] is True
    assert d["score_bias"]["levels"] == [5] and d["score_bias"]["applied"] is True
    out = j.decide(decision2.REFERENCE_STATE, [
        Question(name="route", type=QuestionType.CHOICE,
                 instructions="Which team should handle this request?",
                 options=["returns", "billing", "technical"],
                 descriptions={"returns": "Refunds, replacements and damaged deliveries",
                               "billing": "Payments, invoices and charges",
                               "technical": "Product setup and faults"})])
    assert out[0].decision == "returns"
    assert out[0].confidence == pytest.approx(
        REFERENCE_OUTPUTS[(KAI, KAI_SHA, "mps")]["route"]["probabilities"]["returns"], abs=1e-4)
    assert sum(out[0].raw["probabilities"].values()) == pytest.approx(1.0)


def test_an_over_length_refusal_warns_with_a_reason_and_names_no_variable(over_length_warning):
    j, _ = judge({"route": {"type": "choice", "error": "max_length_exceeded"}})
    (out,) = j.decide("a very long state", [ROUTE])
    assert out.raw["problems"] == ["the runtime refused the request as over length"]
    message, variables = over_length_warning(j)
    assert "the runtime refused the request as over length" in message
    assert "window is fixed" in message and variables == set()
