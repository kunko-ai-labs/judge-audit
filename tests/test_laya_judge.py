"""LayaJudge with a fake agent: what it sends, which confidence it keeps, what it records."""
from __future__ import annotations

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.laya import LayaJudge, laya_question


class FakeAgent:
    revision = "abc123"
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
    (out,) = LayaJudge(agent=agent, version="0.3.20").decide("my top up failed", [CHOICE])
    state, sent, kwargs = agent.calls[0]
    assert state == "my top up failed" and kwargs == {}
    assert sent == {"intent": {"type": "choice", "instructions": "Which intent?",
                               "criteria": {"card_arrival": None,
                                            "top_up_failed": "a top-up did not go through"}}}
    assert out.decision == "top_up_failed" and out.confidence == 0.7
    assert out.raw["entropy_confidence"] == 0.12 and out.raw["act_probability"] == 0.4
    assert out.cost_usd == 0.0 and out.parse_status == "parsed"


def test_noul_confidence_is_the_probability_of_the_answer_given():
    agent = FakeAgent({"urgent": {"type": "noul", "noul": 0.2, "confidence": 0.8,
                                  "answer_confidence": 0.8, "action": {}}})
    (out,) = LayaJudge(agent=agent).decide("whenever", [YESNO])
    assert out.decision == "false" and out.confidence == pytest.approx(0.8)
    assert agent.calls[0][1] == {"urgent": {"type": "noul", "instructions": "Is it urgent?"}}


def test_a_missing_answer_is_no_answer_with_unknown_confidence():
    (out,) = LayaJudge(agent=FakeAgent({})).decide("x", [CHOICE])
    assert out.decision == "" and out.confidence is None and out.parse_status == "no_answer"


def test_token_budgets_from_the_environment_reach_the_call_and_the_provenance(monkeypatch):
    monkeypatch.setenv("LAYA_HEAD_MAX_LEN", "448")
    agent = FakeAgent({"intent": {"type": "choice", "choice": "card_arrival",
                                  "probabilities": {"card_arrival": 0.9, "top_up_failed": 0.1}}})
    judge = LayaJudge(agent=agent, version="0.3.20")
    judge.decide("where is my card", [CHOICE])
    assert agent.calls[0][2] == {"head_max_len": 448}
    d = judge.describe()
    assert d["head_max_len"] == 448 and d["max_len"] == 512
    assert d["revision"] == "abc123" and d["laya_version"] == "0.3.20"
    assert d["temperature"] == "n/a"
    assert d["softmax_temperature"]["shipped"]["by_options"] == {"choice:11+": 0.1006}
    assert d["softmax_temperature"]["applied"]["by_options"] == {"choice:11+": 0.5}
    monkeypatch.setenv("LAYA_MAX_LEN", "big")
    with pytest.raises(ValueError, match="LAYA_MAX_LEN"):
        LayaJudge(agent=agent)


def test_unsupported_questions_are_refused():
    score = Question(name="s", type=QuestionType.SCORE, instructions="rate", options=["a", "b"])
    with pytest.raises(RuntimeError, match="does not support"):
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
