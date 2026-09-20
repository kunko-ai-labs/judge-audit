"""NLIJudge with the transformers pipeline faked — no model download in CI."""
from __future__ import annotations

import sys

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.nli import NLIJudge


class FakePipe:
    """Returns a fixed ranking; records what it was asked."""

    def __init__(self, ranking: list[tuple[str, float]]):
        self.ranking = ranking
        self.calls: list[dict] = []

    def __call__(self, text, candidate_labels, hypothesis_template, multi_label):
        self.calls.append({"text": text, "labels": list(candidate_labels),
                           "template": hypothesis_template, "multi": multi_label})
        wanted = {lbl: sc for lbl, sc in self.ranking}
        ordered = sorted(candidate_labels, key=lambda lb: -wanted.get(lb, 0.0))
        return {"labels": ordered, "scores": [wanted.get(lb, 0.0) for lb in ordered]}


def make(pipe, **env):
    return NLIJudge(model="org/tiny-nli", device="cpu", pipe=pipe)


def test_choice_maps_bare_option_names_and_takes_top_score():
    pipe = FakePipe([("quote request", 0.7), ("spam", 0.3)])
    q = Question(name="category", type=QuestionType.CHOICE, instructions="classify",
                 options=["quote_request", "spam"])
    (out,) = make(pipe).decide("please send a quote", [q])
    assert out.decision == "quote_request" and out.confidence == pytest.approx(0.7)
    assert pipe.calls[0]["labels"] == ["quote request", "spam"]
    assert pipe.calls[0]["multi"] is False and "{}" in pipe.calls[0]["template"]
    assert out.raw["scores"] == {"quote_request": 0.7, "spam": 0.3}
    assert out.cost_usd == 0.0 and out.latency_s >= 0.0


def test_choice_uses_descriptions_as_hypotheses_when_present():
    pipe = FakePipe([("Send to the frontier model", 0.8), ("Send to the cheap model", 0.2)])
    q = Question(name="route", type=QuestionType.CHOICE, instructions="route",
                 options=["route_easy", "route_strong"],
                 descriptions={"route_easy": "Send to the cheap model",
                               "route_strong": "Send to the frontier model"})
    (out,) = make(pipe).decide("implement dijkstra", [q])
    assert out.decision == "route_strong" and out.confidence == pytest.approx(0.8)
    assert set(pipe.calls[0]["labels"]) == {"Send to the cheap model", "Send to the frontier model"}


def test_noul_maps_yes_no_to_true_false_with_instructions_as_hypothesis():
    pipe = FakePipe([("no", 0.9), ("yes", 0.1)])
    q = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")
    (out,) = make(pipe).decide("no rush", [q])
    assert out.decision == "false" and out.confidence == pytest.approx(0.9)
    assert pipe.calls[0]["template"].startswith("Is it urgent?")


def test_score_questions_are_rejected_clearly():
    q = Question(name="level", type=QuestionType.SCORE, instructions="rate", options=["a", "b"])
    with pytest.raises(RuntimeError, match="score"):
        make(FakePipe([])).decide("x", [q])


def test_describe_names_method_and_model():
    d = make(FakePipe([])).describe()
    assert d["provider"] == "local" and d["model"] == "tiny-nli"
    assert "softmax" in d["confidence_method"] and d["device"] == "cpu"


def test_missing_transformers_is_a_config_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "transformers", None)
    with pytest.raises(RuntimeError, match=r"kunko-judge-audit\[nli\]"):
        NLIJudge(model="org/tiny-nli", device="cpu")
