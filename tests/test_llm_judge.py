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


def test_extract_json_ignores_trailing_garbage():
    text = '{"answers": {"route": {"decision": "route_easy", "confidence": 0.8}}}\n0.8}}}\n0.8}}}'
    assert _extract_json(text)["answers"]["route"]["decision"] == "route_easy"


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


def test_dropped_connection_is_retried(monkeypatch):
    """A server that closes the socket mid-request is as transient as a 503."""
    import http.client
    import io
    import urllib.request

    from judge_audit.judges import llm as llm_mod

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    calls = {"n": 0}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http.client.RemoteDisconnected("Remote end closed connection")
        return Resp(json.dumps({"choices": [{"message": {"content": "{}"}}],
                                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    text, _, _ = LLMJudge()._call("hello")
    assert text == "{}" and calls["n"] == 2


def test_timeout_in_json_mode_retries_without_it(monkeypatch):
    """An endpoint that hangs in JSON mode gets the same prompt again as plain text."""
    import urllib.request

    from judge_audit.judges import llm as llm_mod

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    bodies = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()

    def urlopen(req, timeout=0):
        bodies.append(json.loads(req.data))
        if len(bodies) == 1:
            raise TimeoutError("timed out")
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    assert LLMJudge()._call("hello")[0] == "{}"
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]


def test_wall_clock_deadline_trips_when_the_socket_never_times_out(monkeypatch):
    """A server that trickles keep-alive bytes never trips the socket timeout."""
    import threading
    import urllib.request

    from judge_audit.judges import llm as llm_mod

    def urlopen(req, timeout=0):
        threading.Event().wait(5)  # hangs longer than the deadline

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(TimeoutError):
        llm_mod._fetch_json(urllib.request.Request("http://unit.test/v1"), 0.2)
