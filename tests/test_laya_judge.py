"""LayaJudge with a fake agent: what it sends, which confidence it keeps, what it records."""
from __future__ import annotations

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.laya import LayaJudge, fit_problems, laya_question


def fits(agent, state, qdef):
    """Token counts of a question that fits: (instructions, options, state)."""
    return 5, [3] * len(qdef["criteria"]), 10


class FakeAgent:
    cfg = {"max_len": 512, "head_max_len": 192}
    temperature_raw = [1.0, 1.0, 0.8]
    temperature = [1.0, 1.0, 0.8]
    temperature_by_options_raw = {"choice:11+": 0.1006}
    temperature_by_options = {"choice:11+": 0.5}
    device = "cpu"

    def __init__(self, answers):
        self.answers = answers
        self.calls: list[tuple] = []

    def predict(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        return {"answers": self.answers}


CHOICE = Question(name="intent", type=QuestionType.CHOICE, instructions="Which intent?",
                  options=["card_arrival", "top_up_failed"],
                  descriptions={"top_up_failed": "a top-up did not go through"})
YESNO = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")


def test_choice_sends_criteria_and_keeps_the_chosen_option_probability():
    agent = FakeAgent({"intent": {"type": "choice", "choice": "top_up_failed",
                                  "probabilities": {"card_arrival": 0.3, "top_up_failed": 0.7},
                                  "confidence": 0.12,           # entropy-based: never used
                                  "answer_confidence": 0.7,
                                  "action": {"act_probability": 0.4}}})
    (out,) = LayaJudge(agent=agent, version="0.3.20", token_counts=fits).decide(
        "my top up failed", [CHOICE])
    state, sent, kwargs = agent.calls[0]
    assert state == "my top up failed" and kwargs == {}
    assert sent == {"intent": {"type": "choice", "instructions": "Which intent?",
                               "criteria": {"card_arrival": None,
                                            "top_up_failed": "a top-up did not go through"}}}
    assert out.decision == "top_up_failed" and out.confidence == 0.7
    assert out.raw["entropy_confidence"] == 0.12 and out.raw["act_probability"] == 0.4
    assert out.cost_usd == 0.0 and out.parse_status == "parsed"


def test_yes_no_questions_are_refused_until_laya_label_handling_is_verified():
    agent = FakeAgent({})
    with pytest.raises(RuntimeError, match="choice questions"):
        LayaJudge(agent=agent, token_counts=fits).decide("whenever", [YESNO])
    assert agent.calls == []


def test_a_missing_answer_is_no_answer_with_unknown_confidence():
    (out,) = LayaJudge(agent=FakeAgent({}), token_counts=fits).decide("x", [CHOICE])
    assert out.decision == "" and out.confidence is None and out.parse_status == "no_answer"


def test_token_budgets_from_the_environment_reach_the_call_and_the_provenance(monkeypatch):
    monkeypatch.setenv("LAYA_HEAD_MAX_LEN", "448")
    agent = FakeAgent({"intent": {"type": "choice", "choice": "card_arrival",
                                  "probabilities": {"card_arrival": 0.9, "top_up_failed": 0.1}}})
    judge = LayaJudge(agent=agent, version="0.3.20", revision="main", loaded_revision="abc123",
                      device="mps", token_counts=fits)
    judge.decide("where is my card", [CHOICE])
    assert agent.calls[0][2] == {"head_max_len": 448}
    d = judge.describe()
    assert d["head_max_len"] == 448 and d["max_len"] == 512
    assert d["revision"] == "main" and d["loaded_revision"] == "abc123"
    assert d["laya_version"] == "0.3.20" and d["temperature"] == "n/a"
    assert d["device"] == "cpu" and d["device_requested"] == "mps"   # what Laya fell back to
    assert d["softmax_temperature"]["shipped"]["by_options"] == {"choice:11+": 0.1006}
    assert d["softmax_temperature"]["applied"]["by_options"] == {"choice:11+": 0.5}
    assert d["softmax_temperature"]["clamped_by_options"] == ["choice:11+"]
    monkeypatch.setenv("LAYA_MAX_LEN", "big")
    with pytest.raises(ValueError, match="LAYA_MAX_LEN"):
        LayaJudge(agent=agent)


def test_unsupported_questions_are_refused():
    score = Question(name="s", type=QuestionType.SCORE, instructions="rate", options=["a", "b"])
    with pytest.raises(RuntimeError, match="scores choice questions"):
        laya_question(score)
    with pytest.raises(RuntimeError, match="no options"):
        laya_question(Question(name="c", type=QuestionType.CHOICE, instructions="?"))


def test_without_the_package_the_error_says_how_to_install(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_laya(name, *args, **kwargs):
        if name == "laya":
            raise ImportError("no module named laya")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_laya)
    with pytest.raises(RuntimeError, match=r"kunko-judge-audit\[laya\]"):
        LayaJudge()


# --- token budgets: refuse what Laya would truncate ----------------------------------------


def test_fit_problems_by_hand():
    # 77 options of 4 tokens: 77 x (1 marker + 4) = 385 head tokens
    banking = [4] * 77
    problems = fit_problems(20, banking, 30, max_len=512, head_max_len=192)
    assert len(problems) == 2
    assert "the 77 options need 385 of head_max_len=192 tokens: 77 would be cut to 3 tokens" \
        in problems                                              # max(4, 176 // 77) - 1
    assert "the instructions (20 tokens) would be cut to 8" in problems
    assert fit_problems(20, banking, 30, max_len=512, head_max_len=448) == []
    # room 448 - 385 = 63; prefix 1 + 20 + 1 + 385 + 1 = 408; state room 512 - 409 = 103
    assert fit_problems(20, banking, 103, max_len=512, head_max_len=448) == []
    assert fit_problems(20, banking, 104, max_len=512, head_max_len=448) == [
        "the state (104 tokens) would be cut to 103"]
    assert fit_problems(5, [49, 3], 10, max_len=512, head_max_len=192) == [
        "1 option(s) longer than Laya's 48-token cap"]
    assert "the options run past max_len=64" in fit_problems(5, [10] * 10, 1, 64, 192)


def test_a_question_that_does_not_fit_is_refused_before_laya_reads_it():
    agent = FakeAgent({})

    def too_many(agent, state, qdef):
        return 20, [4] * 77, 30

    with pytest.raises(ValueError, match="does not fit Laya's token budgets.*cut to 3 tokens"):
        LayaJudge(agent=agent, token_counts=too_many).decide("x", [CHOICE])
    assert agent.calls == []


# --- against the real package, where it is installed -----------------------------------------


def test_load_arguments_match_the_installed_laya():
    laya = pytest.importorskip("laya")
    import inspect

    params = inspect.signature(laya.Agent.__init__).parameters
    assert "device" in params and "model_id_or_path" in params
    assert callable(getattr(laya.Agent, "_to_internal", None))


def test_fit_problems_agrees_with_laya_build_sequence():
    common = pytest.importorskip("laya.common")
    import random

    def tok(text, add_special_tokens=False, truncation=False, max_length=None):
        """A word-per-token tokenizer with the special tokens Laya reads."""
        ids = [10 + len(w) for w in text.split()]
        return {"input_ids": ids[:max_length] if truncation else ids}

    tok.mask_token, tok.mask_token_id, tok.cls_token_id, tok.sep_token_id = "[MASK]", 1, 2, 3
    rng = random.Random(0)
    for _ in range(2000):
        k = rng.randint(2, 80)
        q = {"t": "choice", "ins": " ".join(["i"] * rng.randint(1, 40)),
             "crit": {f"o{i}": " ".join(["w"] * rng.randint(0, 12)) or None for i in range(k)}}
        state = " ".join(["s"] * rng.randint(1, 300))
        max_len, head = rng.choice([256, 512]), rng.choice([192, 448])
        head_len = len(tok(f"choice question: {q['ins']}")["input_ids"])
        olens = [len(tok(" " + o)["input_ids"]) for o in common.render_options(q)]
        slen = len(tok(state)["input_ids"])
        ids, markers = common.build_sequence(tok, state, q, max_len, head)
        whole = 1 + head_len + 1 + sum(1 + n for n in olens) + 1 + slen + 1
        truncated = len(ids) != whole or len(markers) != k
        assert truncated == bool(fit_problems(head_len, olens, slen, max_len, head))
