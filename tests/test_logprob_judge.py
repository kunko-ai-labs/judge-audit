"""LogprobJudge: normalisation and decisions with a fake backend; the MLX scoring path on a
tiny random model when mlx is installed (Apple silicon, or Linux CPU)."""
from __future__ import annotations

import math

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.logprob import (
    SYSTEM,
    LogprobJudge,
    option_distribution,
    prompt_sha256,
    render,
)

Q = Question(name="intent", type=QuestionType.CHOICE, instructions="Which intent?",
             options=["card_arrival", "top_up_failed", "other"],
             descriptions={"other": "none of the above"})


class FakeBackend:
    chat_kwargs = {"enable_thinking": False}
    end_ids = [1]
    cache_mode = "trim"

    def __init__(self, logprobs):
        self.logprobs = logprobs
        self.prompts: list[str] = []

    def prompt_text(self, system, user):
        return f"{system}\n{user}"

    def option_logprobs(self, prompt, labels):
        self.prompts.append(prompt)
        return {lab: self.logprobs[lab] for lab in labels}


def test_distribution_normalises_and_keeps_the_mass_on_the_options():
    probs, mass = option_distribution({"a": math.log(0.3), "b": math.log(0.1)})
    assert probs == {"a": pytest.approx(0.75), "b": pytest.approx(0.25)}
    assert mass == pytest.approx(0.4)
    with pytest.raises(ValueError):
        option_distribution({})
    with pytest.raises(ValueError, match="zero"):
        option_distribution({"a": -math.inf})


def test_decision_is_the_most_probable_option_and_confidence_its_share():
    backend = FakeBackend({"card_arrival": math.log(0.05), "top_up_failed": math.log(0.6),
                           "other": math.log(0.15)})
    (out,) = LogprobJudge(model="m", backend=backend, version="0.31.3").decide("x", [Q])
    assert out.decision == "top_up_failed"
    assert out.confidence == pytest.approx(0.6 / 0.8)
    assert out.raw["option_mass"] == pytest.approx(0.8) and out.cost_usd == 0.0
    assert "- other: none of the above" in backend.prompts[0]


def test_a_tie_goes_to_the_first_listed_option():
    backend = FakeBackend({"card_arrival": -1.0, "top_up_failed": -1.0, "other": -5.0})
    (out,) = LogprobJudge(model="m", backend=backend).decide("x", [Q])
    assert out.decision == "card_arrival"


def test_provenance_and_refusals():
    j = LogprobJudge(model="mlx-community/Qwen3-8B-4bit", backend=FakeBackend({}),
                     revision="abc", version="0.31.3")
    d = j.describe()
    assert d["name"] == "logprob:Qwen3-8B-4bit" and d["revision"] == "abc"
    assert d["temperature"] == "n/a" and d["prompt_sha256"] == prompt_sha256()
    assert d["chat_template_kwargs"] == {"enable_thinking": False}
    yes_no = Question(name="u", type=QuestionType.NOUL, instructions="urgent?")
    with pytest.raises(RuntimeError, match="choice questions"):
        j.decide("x", [yes_no])


def test_prompt_lists_every_option_and_its_hash_is_stable():
    text = render("hello", Q)
    assert "STATE:\nhello" in text and "- card_arrival" in text and "Which intent?" in text
    assert prompt_sha256() == prompt_sha256() and "option" in SYSTEM
