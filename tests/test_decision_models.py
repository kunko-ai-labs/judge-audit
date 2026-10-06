"""The local decision-model judges of #137 (decider, Strands Decider, Clef) with stubbed models:
what they send, which confidence they audit, what they keep, what they refuse."""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import pytest

from judge_audit.judges import clef, decider, strands
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.clef import ClefJudge
from judge_audit.judges.decider import DeciderJudge
from judge_audit.judges.strands import StrandsJudge
from judge_audit.judges.systemone import best_device, read_answer, systemone_question, tidy

ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["billing", "sales"], descriptions={"billing": "payments"})
URGENT = Question(name="urgent", type=QuestionType.NOUL, instructions="Urgent?")
LEVEL = Question(name="level", type=QuestionType.SCORE, instructions="How bad?",
                 options=["calm", "upset", "furious"])


class FakeSystem:
    """Answers the reference request with `reference`, anything else from `answers`."""

    def __init__(self, answers=None, reference=None, reference_state=None, problems=None):
        self.answers, self.reference = answers or {}, reference
        self.reference_state, self.problems = reference_state, problems or []
        self.calls: list[tuple] = []

    def system_one(self, *, state, questions):
        self.calls.append((state, questions))
        answers = self.reference if state == self.reference_state else self.answers
        return {"model": "served-name", "answers": answers,
                "usage": {"input_tokens": 12, "output_tokens": 0}}

    def fit_problems(self, state, questions):
        return self.problems


def make(cls, revision_info=None, **system):
    model = FakeSystem(**system)
    info = {"loaded_revision": "abc", "device": "mps", "loader_warnings": []}
    info.update(revision_info or {})
    return cls(model_id=cls.default_model, system=model, info=info), model


# --- shared reading of a System One answer ----------------------------------------------------


def test_read_answer_by_hand():
    assert read_answer(ROUTE, {"choice": "sales", "probabilities": {"billing": 0.3,
                                                                    "sales": 0.7}}) \
        == ("sales", 0.7, {"billing": 0.3, "sales": 0.7})
    assert read_answer(URGENT, {"noul": 0.25})[:2] == ("false", 0.75)
    assert read_answer(LEVEL, {"probabilities": {"0": 0.4, "1": 0.4, "2": 0.2}})[:2] \
        == ("calm", 0.4)                                        # a tie goes to the first level
    assert systemone_question(ROUTE, blank="")["criteria"] == {"billing": "payments",
                                                               "sales": ""}
    assert systemone_question(LEVEL)["criteria"] == ["calm", "upset", "furious"]


def test_tidy_hides_the_home_directory_and_temporary_paths():
    home = os.path.expanduser("~")
    msg = f"loaded {home}/.cache/x from '/private/var/folders/ab/T/strands-view-1/cfg' ok"
    assert tidy(msg) == "loaded ~/.cache/x from '<tmp>' ok"


def test_best_device_keeps_a_requested_device():
    assert best_device("cpu") == "cpu"


# --- decider ----------------------------------------------------------------------------------


def test_decider_audits_p_chosen_and_keeps_its_native_fields_under_their_meaning():
    j, model = make(DeciderJudge, answers={
        "route": {"type": "choice", "choice": "billing", "confidence": 0.86, "x_p_max": 0.93,
                  "certainty": 0.63, "probabilities": {"billing": 0.93, "sales": 0.07}}})
    (out,) = j.decide("charged twice", [ROUTE])
    assert model.calls[-1][1] == {"route": {"type": "choice", "instructions": "Which team?",
                                            "criteria": {"billing": "payments", "sales": None}}}
    assert out.decision == "billing" and out.confidence == 0.93
    assert out.raw["typesafe_confidence"] == 0.86 and out.raw["entropy_confidence"] == 0.63
    assert out.raw["x_p_max"] == 0.93 and out.raw["served"]["model"] == "served-name"


def test_decider_score_keeps_level_fits():
    j, _ = make(DeciderJudge, answers={"level": {
        "type": "score", "score": 1.2, "confidence": 0.5, "x_p_max": 0.6,
        "probabilities": {"0": 0.1, "1": 0.6, "2": 0.3}, "level_fit": {"0": 0.1},
        "fit_mass": 0.98}})
    (out,) = j.decide("x", [LEVEL])
    assert out.decision == "upset" and out.confidence == 0.6
    assert out.raw["expected_level"] == 1.2 and out.raw["fit_mass"] == 0.98


def test_decider_is_pinned_and_unknown_models_need_a_revision(monkeypatch):
    monkeypatch.delenv("DECIDER_REVISION", raising=False)
    j, _ = make(DeciderJudge)
    assert j.requested_revision == decider.PINNED_REVISIONS["Mapika/decider-2b"]
    assert j.describe()["reference_check"]["status"] == "unchecked"
    assert j.name == "decider:decider-2b" and j.describe()["temperature"] == "n/a"
    with pytest.raises(ValueError, match="DECIDER_REVISION"):
        DeciderJudge(model_id="someone/decider-fork", system=FakeSystem(), info={})


def test_decider_state_budget_by_hand():
    tok = SimpleNamespace(encode=lambda text, add_special_tokens=False: text.split())
    system = decider._DeciderSystem(SimpleNamespace(m=SimpleNamespace(tok=tok)),
                                    render_state=lambda s: s)
    assert system.fit_problems("word " * 32767, {}) == []      # "Context:" + 32,767 words
    assert system.fit_problems("word " * 32768, {}) == [
        "the state (32769 tokens) would be cut to 32768"]


def test_decider_reference_is_enforced_on_cpu_only_mps_and_cuda_are_unchecked():
    """CPU outputs are recorded; MPS float16 changes with whether mlx is installed (billing
    0.5122 with it, 0.5155 without, on the same single question), so nothing is enforced
    there."""
    sha = decider.PINNED_REVISIONS["Mapika/decider-2b"]
    assert {k[2] for k in decider.REFERENCE_OUTPUTS} == {"cpu"}
    cpu = decider.REFERENCE_OUTPUTS[("Mapika/decider-2b", sha, "cpu")]
    assert cpu["department"]["choice"] == "returns"
    j, _ = make(DeciderJudge, revision_info={"loaded_revision": sha, "device": "cpu"},
                reference=cpu, reference_state=decider.REFERENCE_STATE)
    assert j.describe()["reference_check"]["status"] == "passed"
    mps_float16 = {**cpu, "department": {"type": "choice", "choice": "billing",
                                         "probabilities": {"returns": 0.479,
                                                           "billing": 0.5122,
                                                           "other": 0.0088}}}
    with pytest.raises(RuntimeError, match="department: chose 'billing', reference 'returns'"):
        make(DeciderJudge, revision_info={"loaded_revision": sha, "device": "cpu"},
             reference=mps_float16, reference_state=decider.REFERENCE_STATE)
    for device in ("mps", "cuda:0"):
        j, _ = make(DeciderJudge, revision_info={"loaded_revision": sha, "device": device},
                    reference=mps_float16, reference_state=decider.REFERENCE_STATE)
        assert j.describe()["reference_check"]["status"] == "unchecked"


def test_decider_defaults_to_cpu_not_mps_on_apple_silicon(monkeypatch):
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    assert decider.default_device(None) == "cpu"
    assert decider.default_device("mps") == "mps"              # only when asked
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert decider.default_device(None) == "cuda"


def test_strands_base_revision_must_be_a_commit(monkeypatch):
    monkeypatch.delenv("STRANDS_BASE_REVISION", raising=False)
    sha = "b1485b2fa6dfa1287294f269f5fb618e03d52d7c"
    assert strands.base_revision_of("m", "Qwen/Qwen3.5-2B-Base",
                                    {"base_model_revision": sha}) == sha
    for bad in ({}, {"base_model_revision": "main"}):
        with pytest.raises(ValueError, match="40-hex Hub commit"):
            strands.base_revision_of("m", "Qwen/Qwen3.5-2B-Base", bad)
    monkeypatch.setenv("STRANDS_BASE_REVISION", "v1.0")
    with pytest.raises(ValueError, match="'v1.0'"):
        strands.base_revision_of("m", "Qwen/Qwen3.5-2B-Base", {"base_model_revision": sha})


@pytest.mark.parametrize("cls", [DeciderJudge, StrandsJudge, ClefJudge])
def test_a_request_the_runtime_would_truncate_is_counted_as_no_answer_not_sent(cls):
    """One rule for every local decision model (Decision 2.0's runtime does it itself): the
    row's questions are no answer, counted against the judge, and the run goes on."""
    j, model = make(cls, problems=["the state (40000 tokens) would be cut to 32768"])
    route, urgent = j.decide("long", [ROUTE, URGENT])
    assert model.calls == []                                     # never sent
    for out in (route, urgent):
        assert out.parse_status == "no_answer" and out.confidence is None
        assert out.decision == "" and out.raw["error"] == "max_length_exceeded"
        assert out.raw["problems"] == ["the state (40000 tokens) would be cut to 32768"]
    model.problems = []
    model.answers = {"route": {"type": "choice", "choice": "sales",
                               "probabilities": {"billing": 0.2, "sales": 0.8}}}
    (out,) = j.decide("short", [ROUTE])                          # the next row is read
    assert out.parse_status == "parsed" and out.confidence == 0.8


class CoQuestionDecider:
    """Answers like decider-2b on MPS: a question's probabilities move with the other questions
    sent in the same request."""

    def __init__(self):
        self.requests: list[list[str]] = []

    def system_one(self, state, questions):
        self.requests.append(list(questions))
        shift = 0.01 * (len(questions) - 1)
        return {"model": "decider-2b-v11", "usage": {"input_tokens": 10 * len(questions)},
                "answers": {k: {"type": "choice", "choice": "billing",
                                "probabilities": {"billing": 0.6 + shift, "sales": 0.4 - shift}}
                            for k in questions}}


def test_on_mps_each_question_goes_in_its_own_request_so_co_questions_cannot_move_it():
    route_b = {"type": "choice", "instructions": "Again?", "criteria": {"billing": None,
                                                                       "sales": None}}
    route = systemone_question(ROUTE)
    batched = decider._DeciderSystem(CoQuestionDecider(), lambda s: s, one_per_request=False)
    alone = batched.system_one(state="x", questions={"route": route})
    together = batched.system_one(state="x", questions={"route": route, "again": route_b})
    assert alone["answers"]["route"] != together["answers"]["route"]        # the dependence
    fake = CoQuestionDecider()
    split = decider._DeciderSystem(fake, lambda s: s, one_per_request=True)
    together = split.system_one(state="x", questions={"route": route, "again": route_b})
    assert together["answers"]["route"] == alone["answers"]["route"]
    assert fake.requests == [["route"], ["again"]]
    assert together["usage"] == {"input_tokens": 20, "output_tokens": 0}


def test_mlx_loaded_reports_whether_mlx_core_is_imported(monkeypatch):
    """On MPS decider's own code uses an MLX kernel when mlx imports, which changes its
    half-precision answers: the provenance records whether it was loaded."""
    monkeypatch.setitem(sys.modules, "mlx.core", object())
    assert decider.mlx_loaded() is True
    monkeypatch.setitem(sys.modules, "mlx.core", None)          # a blocked import
    assert decider.mlx_loaded() is False
    monkeypatch.delitem(sys.modules, "mlx.core")
    assert decider.mlx_loaded() is False


# --- Strands Decider --------------------------------------------------------------------------

SERVED = {"noul_0": {"type": "noul", "noul": 0.8291},
          "choice_0": {"type": "choice", "choice": "billing", "confidence": 0.7686,
                       "probabilities": {"billing": 0.8457, "sales": 0.0641,
                                         "retail": 0.0902}},
          "score_0": {"type": "score", "score": 1.1, "confidence": 0.519,
                      "legend": {"0": "calm", "1": "frustrated", "2": "depressed"},
                      "probabilities": {"0": 0.1631, "1": 0.5742, "2": 0.2627}}}


def strands_judge(reference=SERVED, **kwargs):
    return make(StrandsJudge, revision_info={
        "loaded_revision": strands.PINNED_REVISIONS[strands.DEFAULT_MODEL]},
        reference=reference, reference_state=strands.REFERENCE_STATE, **kwargs)


def test_strands_checks_the_model_card_outputs_before_any_decision():
    j, _ = strands_judge()
    check = j.describe()["reference_check"]
    assert check["status"] == "passed" and check["max_abs_diff"] <= 0.0005
    drifted = {**SERVED, "choice_0": {**SERVED["choice_0"], "choice": "sales"}}
    with pytest.raises(RuntimeError, match="choice_0: chose 'sales'"):
        strands_judge(reference=drifted)
    far = {**SERVED, "noul_0": {"type": "noul", "noul": 0.80}}
    with pytest.raises(RuntimeError, match="noul_0"):
        strands_judge(reference=far)


def test_strands_sends_blank_descriptions_and_keeps_its_derived_confidence():
    j, model = strands_judge(answers={"route": SERVED["choice_0"] | {
        "probabilities": {"billing": 0.8457, "sales": 0.1543}}})
    (out,) = j.decide("payouts failing", [ROUTE])
    assert model.calls[-1][1]["route"]["criteria"] == {"billing": "payments", "sales": ""}
    assert out.confidence == 0.8457 and out.raw["typesafe_confidence"] == 0.7686


def test_strands_window_arithmetic_by_hand():
    """`_fit`: reserve = min(longest question, max(1, int(max_len * 0.75))); a longer question
    is cut from the front; the state gets max_len - reserve tokens, special tokens included."""
    def tok(text, add_special_tokens=False):
        return {"input_ids": text.split() + (["<s>"] if add_special_tokens else [])}

    engine = SimpleNamespace(tok=tok, model=SimpleNamespace(config=SimpleNamespace(max_length=20)),
                             cfg=SimpleNamespace(max_question_fraction=0.75))
    schema = SimpleNamespace(SystemOneRequest=lambda state, questions: SimpleNamespace(
        state=state, questions=questions))
    prompting = SimpleNamespace(render_question=lambda q: SimpleNamespace(text=q),
                                render_state=lambda s: s)
    system = strands._StrandsSystem(engine, schema, prompting)
    q6, q16 = " ".join(["q"] * 6), " ".join(["q"] * 16)
    assert system.fit_problems(" ".join(["s"] * 13), {"a": q6}) == []        # 13 + 1 <= 14
    assert system.fit_problems(" ".join(["s"] * 14), {"a": q6}) == [
        "the state (15 tokens) would be cut to 14"]
    assert system.fit_problems("s", {"a": q16}) == [
        "question 'a' (16 tokens) would be cut to 15 from the front"]


def test_strands_view_names_the_local_base(tmp_path):
    ckpt = tmp_path / "ckpt"
    (ckpt / "lora").mkdir(parents=True)
    (ckpt / "head.safetensors").write_bytes(b"x")
    (ckpt / "hobson_config.json").write_text(json.dumps({"base_model": "Qwen/Qwen3.5-2B-Base",
                                                          "temperature": 0.96}))
    view = strands._view(ckpt, "/models/base@b1485b2")
    config = json.loads((view / "hobson_config.json").read_text())
    assert config == {"base_model": "/models/base@b1485b2", "temperature": 0.96}
    assert (view / "head.safetensors").resolve() == (ckpt / "head.safetensors").resolve()
    assert (view / "lora").is_dir()


# --- Clef -------------------------------------------------------------------------------------


def test_clef_keeps_its_confidence_field_and_has_no_reference_yet():
    j, model = make(ClefJudge, answers={"urgent": {"type": "noul", "noul": 0.9},
                                        "route": {"type": "choice", "choice": "billing",
                                                  "confidence": 0.71, "probabilities": {
                                                      "billing": 0.71, "sales": 0.29}}})
    route, urgent = j.decide("checkout errors", [ROUTE, URGENT])
    assert route.confidence == 0.71 and route.raw["native_confidence"] == 0.71
    assert urgent.decision == "true" and urgent.confidence == 0.9
    assert j.describe()["reference_check"]["status"] == "unchecked"
    assert j.requested_revision == clef.PINNED_REVISIONS["Cloudflare/clef-flash"]


def test_clef_window_is_measured_with_its_own_encoder():
    seen = {}

    def encode_record(tokenizer, record, max_length, processor):
        seen.update(max_length=max_length)
        return SimpleNamespace(input_ids=[0] * len(record["state"].split()))

    module = SimpleNamespace(encode_record=encode_record)
    system = clef._ClefSystem(module, None, SimpleNamespace(tokenizer=None), "clef-flash")
    assert system.fit_problems(" ".join(["w"] * 16384), {}) == []
    assert system.fit_problems(" ".join(["w"] * 16385), {}) == [
        "the request (16385 tokens) would be cut to 16384"]
    assert seen["max_length"] > 10**6                         # measured whole, never cut


# --- registration -----------------------------------------------------------------------------


@pytest.mark.parametrize("cls,extra", [(DeciderJudge, "decider"), (StrandsJudge, "strands"),
                                       (ClefJudge, "clef")])
def test_without_the_runtime_the_error_says_how_to_install(monkeypatch, cls, extra):
    import builtins

    real_import = builtins.__import__

    def missing(name, *args, **kwargs):
        if name in ("transformers", "strands_decider"):
            raise ImportError(f"no module named {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(RuntimeError, match=rf"kunko-judge-audit\[{extra}\]"):
        cls()


def test_every_family_is_a_cli_and_mcp_judge():
    from judge_audit import cli, mcp_server

    for name in ("decision2", "decider", "strands", "clef"):
        assert name in cli.JUDGES
    assert {"decider", "strands", "clef"} <= {j["name"] for j in mcp_server.list_judges()["judges"]}


# --- opt-in smoke tests on the real models ----------------------------------------------------


@pytest.mark.skipif(os.environ.get("JUDGE_AUDIT_SMOKE_DECIDER") != "1",
                    reason="downloads decider-2b (3.8 GB); set JUDGE_AUDIT_SMOKE_DECIDER=1")
def test_smoke_decider_2b():
    j = DeciderJudge()
    d = j.describe()
    assert d["loaded_revision"] == decider.PINNED_REVISIONS["Mapika/decider-2b"]
    assert d["reference_check"]["status"] == (
        "passed" if d["device"].split(":")[0] == "cpu" else "unchecked")
    assert d["questions_per_request"] == (1 if d["device"].startswith("mps") else "all")
    assert d["mlx_loaded"] is decider.mlx_loaded()
    state = "My card was charged twice for the same purchase."
    (out,) = j.decide(state, [ROUTE])
    assert out.decision in ROUTE.options
    assert sum(out.raw["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)
    together, _ = j.decide(state, [ROUTE, URGENT])          # co-questions do not move it
    assert together.raw["probabilities"] == out.raw["probabilities"]


@pytest.mark.skipif(os.environ.get("JUDGE_AUDIT_SMOKE_CLEF") != "1",
                    reason="downloads Clef-flash (19 GB, needs a 24 GB machine); set "
                           "JUDGE_AUDIT_SMOKE_CLEF=1")
def test_smoke_clef_flash():
    j = ClefJudge()
    d = j.describe()
    assert d["loaded_revision"] == clef.PINNED_REVISIONS["Cloudflare/clef-flash"]
    (out,) = j.decide("Our checkout started returning errors and orders are blocked.", [ROUTE])
    assert out.decision in ROUTE.options and out.raw["native_confidence"] is not None
    assert sum(out.raw["probabilities"].values()) == pytest.approx(1.0, abs=1e-3)


@pytest.mark.skipif(os.environ.get("JUDGE_AUDIT_SMOKE_STRANDS") != "1",
                    reason="downloads Strands Decider and Qwen3.5-2B-Base (4.6 GB); set "
                           "JUDGE_AUDIT_SMOKE_STRANDS=1")
def test_smoke_strands_2b_matches_the_model_card():
    j = StrandsJudge()
    assert j.describe()["reference_check"]["status"] == "passed"
    assert j.describe()["base_revision"] == "b1485b2fa6dfa1287294f269f5fb618e03d52d7c"
    (out,) = j.decide("Help! My payouts have been failing for 3 days!", [ROUTE])
    assert out.decision in ROUTE.options and out.raw["typesafe_confidence"] is not None
