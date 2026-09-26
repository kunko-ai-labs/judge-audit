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
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_decide_normalises_option_case_and_rejects_out_of_range_confidence(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "SPAM", "confidence": 1.7}}}')
    (out,) = j.decide("x", [Q])
    assert out.decision == "spam" and out.confidence is None
    assert out.parse_status == "no_confidence"
    assert out.cost_usd == pytest.approx((100 * 0.25 + 20 * 2.0) / 1e6)
    assert out.raw["priced"] is True and "text" in out.raw


@pytest.mark.parametrize(
    "answer",
    [
        {"decision": "spam"},
        {"decision": "spam", "confidence": "not-a-number"},
        {"decision": "spam", "confidence": "NaN"},
        {"decision": "spam", "confidence": float("nan")},
        {"decision": "spam", "confidence": float("inf")},
        {"decision": "spam", "confidence": -0.01},
        {"decision": "spam", "confidence": 1.01},
        {"decision": "spam", "confidence": True},   # float(True) would impute 1.0
        {"decision": "spam", "confidence": False},
    ],
)
def test_missing_or_invalid_confidence_stays_unknown(monkeypatch, answer):
    j = make(monkeypatch, json.dumps({"answers": {"category": answer}}))
    (out,) = j.decide("x", [Q])
    assert out.decision == "spam"
    assert out.confidence is None
    assert out.parse_status == "no_confidence"


def test_unparseable_reply_is_wrong_with_unknown_confidence(monkeypatch):
    j = make(monkeypatch, "I cannot decide.")
    (out,) = j.decide("x", [Q])
    assert out.decision == "" and out.confidence is None
    assert out.parse_status == "no_answer"


def test_answer_without_decision_has_unknown_confidence(monkeypatch):
    # llama3.2 wrote this in jury round 2: a confidence that belongs to no decision
    reply = '{"answers": {"category": {"spam": "order", "confidence": 0.0}}}'
    (out,) = make(monkeypatch, reply).decide("x", [Q])
    assert out.decision == "" and out.confidence is None
    assert out.parse_status == "no_answer"


def test_decision_outside_the_options_is_a_wrong_answer_with_its_confidence(monkeypatch):
    reply = '{"answers": {"category": {"decision": "invoice", "confidence": 0.8}}}'
    (out,) = make(monkeypatch, reply).decide("x", [Q])
    assert out.decision == "invoice" and out.confidence == 0.8
    assert out.parse_status == "parsed"


def test_valid_answer_is_parsed(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "order", "confidence": 0.8}}}')
    (out,) = j.decide("x", [Q])
    assert out.confidence == 0.8 and out.parse_status == "parsed"


def test_unknown_hosted_model_reports_unknown_cost(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "order", "confidence": 0.8}}}',
             model="llama3.1")
    (out,) = j.decide("x", [Q])
    assert out.cost_usd is None and out.raw["priced"] is False


def test_unknown_local_model_is_known_free(monkeypatch):
    j = make(monkeypatch, '{"answers": {"category": {"decision": "order", "confidence": 0.8}}}',
             model="llama3.1")
    j.base_url = "http://localhost:11434/v1"
    (out,) = j.decide("x", [Q])
    assert out.cost_usd == 0.0 and out.raw["priced"] is True


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


def test_extract_json_scans_past_prose_braces_and_fenced_then_prose():
    prose = ("Looking at this task: merge `{'a': 1}` with `{'b': 2}`.\n\n"
             '{"answers": {"route": {"decision": "route_easy", "confidence": 0.9}}}'
             "\n\n**Reasoning:** short.")
    assert _extract_json(prose)["answers"]["route"]["decision"] == "route_easy"
    fenced = ('```json\n{"answers": {"route": {"decision": "route_strong", "confidence": 0.7}}}'
              "\n```\n\n**Reasoning:** the task hides edge cases.")
    assert _extract_json(fenced)["answers"]["route"]["confidence"] == 0.7
    with pytest.raises(ValueError):
        _extract_json("No JSON here, only `{'python': 'dict'}` syntax.")


def test_the_served_model_version_is_recorded_as_the_provider_reports_it(monkeypatch):
    import io
    import urllib.request

    from judge_audit.judges import llm as llm_mod

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    reply = {"model": "gpt-5-mini-2026-08-07", "system_fingerprint": "fp_abc",
             "choices": [{"message": {"content":
                          '{"answers": {"category": {"decision": "spam", "confidence": 0.8}}}'}}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: Resp(json.dumps(reply).encode()))
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    (out,) = LLMJudge().decide("x", [Q])
    assert out.raw["served"] == {"model": "gpt-5-mini-2026-08-07", "system_fingerprint": "fp_abc"}


def test_no_reported_version_is_unknown_not_the_requested_name(monkeypatch):
    import io
    import urllib.request

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    reply = {"choices": [{"message": {"content":
             '{"answers": {"category": {"decision": "spam", "confidence": 0.8}}}'}}]}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: Resp(json.dumps(reply).encode()))
    (out,) = LLMJudge().decide("x", [Q])  # the real HTTP path, no "model" in the reply
    assert out.raw["served"] == {"model": None, "system_fingerprint": None}


def test_anthropic_path_records_the_model_the_api_says_it_served(monkeypatch):
    from types import SimpleNamespace

    j = make(monkeypatch, "{}")
    j.provider = "anthropic"
    resp = SimpleNamespace(stop_reason="end_turn", model="claude-sonnet-4-5-20250929",
                           content=[SimpleNamespace(type="text", text=json.dumps(
                               {"answers": {"category": {"decision": "spam",
                                                         "confidence": 0.8}}}))],
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1))
    j._client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: resp))
    j._anthropic = SimpleNamespace(RateLimitError=RuntimeError, APIStatusError=RuntimeError)
    del j._call  # the real dispatcher, not make()'s stub
    (out,) = j.decide("x", [Q])
    assert out.raw["served"] == {"model": "claude-sonnet-4-5-20250929",
                                 "system_fingerprint": None}


@pytest.mark.parametrize(
    "returned,served",
    [
        (("{}", 1, 1), {"model": None, "system_fingerprint": None}),
        (("{}", 1, 1, {"model": "m-2026-09"}), {"model": "m-2026-09", "system_fingerprint": None}),
        (("{}", 1, 1, "not a dict"), {"model": None, "system_fingerprint": None}),
    ],
)
def test_custom_provider_reports_a_version_only_through_its_optional_4th_element(
        monkeypatch, returned, served):
    from types import SimpleNamespace

    j = make(monkeypatch, "{}")
    j.provider = "custom"
    j._custom = SimpleNamespace(call=lambda model, system, user: returned)
    del j._call
    (out,) = j.decide("x", [Q])
    assert out.raw["served"] == served


# --- LLM_EXTRA_BODY: gateway routing fields, recorded in provenance ------------------------

def _gateway(monkeypatch, extra: str | None, response: dict):
    from judge_audit.judges import llm as llm_mod

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.test/v1")
    monkeypatch.setenv("LLM_MODEL", "vendor/model-mini")
    if extra is None:
        monkeypatch.delenv("LLM_EXTRA_BODY", raising=False)
    else:
        monkeypatch.setenv("LLM_EXTRA_BODY", extra)
    sent: list[dict] = []

    def fake_fetch(req, deadline):
        sent.append(json.loads(req.data))
        return response

    monkeypatch.setattr(llm_mod, "_fetch_json", fake_fetch)
    return LLMJudge(), sent


ANSWER = '{"answers": {"category": {"decision": "spam", "confidence": 0.9}}}'
REPLY = {"model": "vendor/model-mini", "provider": "Vendor",
         "choices": [{"message": {"content": ANSWER}}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
ROUTING = {"provider": {"order": ["vendor"], "allow_fallbacks": False}}


def test_extra_body_is_sent_recorded_and_a_pinned_upstream_kept(monkeypatch):
    j, sent = _gateway(monkeypatch, json.dumps(ROUTING), REPLY)
    (out,) = j.decide("buy now", [Q])
    assert sent[0]["provider"] == ROUTING["provider"] and sent[0]["temperature"] == 0
    assert j.describe()["extra_body"] == ROUTING
    assert out.raw["upstream_provider"] == "Vendor" and out.decision == "spam"


def test_an_upstream_outside_the_pinned_list_fails_the_decision(monkeypatch):
    j, _ = _gateway(monkeypatch, json.dumps(ROUTING), dict(REPLY, provider="Somewhere Else"))
    with pytest.raises(RuntimeError, match="outside the pinned list"):
        j.decide("buy now", [Q])


def test_without_a_pinned_list_no_upstream_is_recorded(monkeypatch):
    j, _ = _gateway(monkeypatch, '{"provider": {"allow_fallbacks": false}}', REPLY)
    (out,) = j.decide("buy now", [Q])
    assert "upstream_provider" not in out.raw


def test_without_extra_body_nothing_changes_even_if_the_reply_names_an_upstream(monkeypatch):
    j, sent = _gateway(monkeypatch, None, REPLY)
    (out,) = j.decide("buy now", [Q])
    assert "provider" not in sent[0] and "extra_body" not in j.describe()
    assert "upstream_provider" not in out.raw


@pytest.mark.parametrize("extra, message", [
    ('{"temperature": 1}', "may only set"),
    ('{"Temperature": 1, "MODEL": "other"}', "may only set"),
    ('{"models": ["a", "b"]}', "may only set"),
    ('{"transforms": ["middle-out"]}', "may only set"),
    ('{"max_tokens": 5}', "may only set"),
    ('["provider"]', "JSON object"),
    ("{not json", "not valid JSON"),
])
def test_extra_body_accepts_only_a_routing_object(monkeypatch, extra, message):
    with pytest.raises(ValueError, match=message):
        _gateway(monkeypatch, extra, REPLY)


def test_extra_body_is_refused_outside_openai_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_EXTRA_BODY", '{"provider": {}}')
    with pytest.raises(ValueError, match="openai-compatible only"):
        LLMJudge()
