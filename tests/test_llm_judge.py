"""LLMJudge: prompt rendering, JSON parsing, normalisation — network mocked."""
from __future__ import annotations

import json

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.llm import LLMJudge, _extract_json, _render


def make(monkeypatch, reply: str, in_tok=100, out_tok=20, model="gpt-5-mini"):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", model)
    j = LLMJudge()
    j._call = lambda user: (reply, in_tok, out_tok)  # noqa: E731
    return j


Q = Question(name="category", type=QuestionType.CHOICE, instructions="classify",
             options=["spam", "order"], descriptions={"spam": "unsolicited"})


def test_render_includes_options_and_descriptions():
    text = _render("hello", [Q])
    assert "STATE:\nhello" in text and "- spam: unsolicited" in text and "- order" in text


def test_extract_json_tolerates_fences_and_prose():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _extract_json('Sure! {"a": 2} hope this helps') == {"a": 2}
    with pytest.raises(json.JSONDecodeError):
        _extract_json("no json here")


def test_decide_normalises_option_case_and_clamps_confidence(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "SPAM", "confidence": 1.7}}}')
    (out,) = j.decide("x", [Q])
    assert out.decision == "spam" and out.confidence == 1.0
    assert out.cost_usd == pytest.approx((100 * 0.25 + 20 * 2.0) / 1e6)
    assert out.raw["priced"] is True and "text" in out.raw


def test_unparseable_reply_is_wrong_with_zero_confidence(monkeypatch):
    j = make(monkeypatch, "I cannot decide.")
    (out,) = j.decide("x", [Q])
    assert out.decision == "" and out.confidence == 0.0


def test_unknown_model_reports_zero_cost_and_says_so(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "order", "confidence": 0.8}}}',
             model="llama3.1")
    (out,) = j.decide("x", [Q])
    assert out.cost_usd == 0.0 and out.raw["priced"] is False


def test_noul_question_maps_true_false(monkeypatch):
    q = Question(name="urgent", type=QuestionType.NOUL, instructions="urgent?")
    j = make(monkeypatch, '{"answers": {"urgent": {"decision": "True", "confidence": 0.9}}}')
    (out,) = j.decide("x", [q])
    assert out.decision == "true" and out.confidence == 0.9


def test_describe_names_provider_model_and_method(monkeypatch):
    j = make(monkeypatch, "{}")
    d = j.describe()
    assert d["provider"] == "openai-compatible" and d["model"] == "gpt-5-mini"
    assert "verbalized" in d["confidence_method"] and j.name == "llm:gpt-5-mini"


def test_missing_config_is_a_runtime_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        LLMJudge()
