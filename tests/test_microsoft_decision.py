"""Microsoft-Decision-1 through OpenRouter's Decisions route (`microsoft-decision`, #164),
with the network stubbed: what it sends, which provider and version it pins, which confidence
it audits, what it keeps, what it costs, and what it never records. Synthetic data only."""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.parse

import pytest

from judge_audit.judges import hosted
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.hosted import MicrosoftDecisionJudge
from judge_audit.judges.secrets import OPENER

ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["billing", "shipping", "other"],
                 descriptions={"billing": "Payments, charges and refunds.",
                               "shipping": "Delivery and tracking."})
URGENT = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")
LEVEL = Question(name="level", type=QuestionType.SCORE, instructions="How severe?",
                 options=["low", "medium", "high"])

LIVE_KEY = os.environ.get("OPENROUTER_API_KEY", "")
SECRET = "sk-or-test-not-a-real-key-0123456789abcdef"
VERSION = "microsoft/microsoft-decision-1-20261009"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Wire:
    """Records every request and answers from a queue: a body, an HTTP status, or
    (status, body text) for an error with a body."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[tuple[str, dict, dict]] = []

    def __call__(self, req, timeout=0):
        self.requests.append((req.full_url, dict(req.header_items()),
                              json.loads(req.data.decode())))
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            reply = (reply, '{"error": {"message": "busy"}}')
        if isinstance(reply, tuple):
            raise urllib.error.HTTPError(req.full_url, reply[0], "err", {},
                                         io.BytesIO(reply[1].encode()))
        return _Resp(json.dumps(reply).encode())


@pytest.fixture
def wire(monkeypatch):
    def install(*replies):
        w = Wire(*replies)
        monkeypatch.setattr(OPENER, "open", w)
        monkeypatch.setattr(hosted.time, "sleep", lambda s: None)
        return w
    return install


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    for name in ("MICROSOFT_DECISION_ENDPOINT", "MICROSOFT_DECISION_VERSION",
                 "HOSTED_MIN_INTERVAL_S"):
        monkeypatch.delenv(name, raising=False)


def reply(answers=None, model=VERSION, provider="Azure", tokens=76, cost=0.000003192,
          rid="gen-dec-0000000000-synthetic"):
    """A reply in the shape the live route returned on 2026-10-12 (synthetic values)."""
    body = {"model": model, "answers": answers if answers is not None else {"route": {
        "type": "choice", "choice": "billing",
        "probabilities": {"billing": 0.9971337392398688, "other": 0.0016987370192887016,
                          "shipping": 0.0011675237408424576},
        "confidence": 0.9957006088598033}},
            "usage": {"input_tokens": tokens, "output_tokens": 1, "cost": cost},
            "id": rid, "provider": provider}
    return {k: v for k, v in body.items() if v is not None}


# --- the request ---------------------------------------------------------------------------

def test_sends_a_system_one_request_with_the_provider_pinned(wire):
    w = wire(reply())
    MicrosoftDecisionJudge().decide("I was charged twice.", [ROUTE])
    url, headers, body = w.requests[0]
    assert url == "https://openrouter.ai/api/alpha/decisions"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert body == {
        "model": "microsoft/microsoft-decision-1",
        "provider": {"order": ["azure"], "allow_fallbacks": False},
        "state": "I was charged twice.",
        "questions": {"route": {"type": "choice", "instructions": "Which team?",
                                "criteria": {"billing": "Payments, charges and refunds.",
                                             "shipping": "Delivery and tracking.",
                                             "other": None}}}}


def test_sends_one_question_per_request(wire):
    w = wire(reply(), reply(answers={"urgent": {"type": "noul", "noul": 0.2}}))
    out = MicrosoftDecisionJudge().decide("x", [ROUTE, URGENT])
    assert [list(b["questions"]) for _, _, b in w.requests] == [["route"], ["urgent"]]
    assert [j.decision for j in out] == ["billing", "false"]


def test_retries_a_busy_server_then_answers(wire):
    w = wire(429, 503, 524, reply())
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.decision == "billing" and len(w.requests) == 4


def test_a_rate_limit_that_never_clears_raises_rate_limited(wire):
    wire(*([429] * 10))
    with pytest.raises(RuntimeError, match="rate-limited"):
        MicrosoftDecisionJudge().decide("x", [ROUTE])


def test_without_a_key_says_which_variable(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        MicrosoftDecisionJudge()


# --- confidence ----------------------------------------------------------------------------

def test_audits_p_chosen_and_keeps_its_own_confidence_apart(wire):
    wire(reply())
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "parsed" and j.decision == "billing"
    assert j.confidence == 0.9971337392398688
    assert j.raw["native_confidence"] == 0.9957006088598033
    assert j.raw["probabilities"] == {"billing": 0.9971337392398688,
                                      "other": 0.0016987370192887016,
                                      "shipping": 0.0011675237408424576}
    assert j.raw["probability_sum"] == pytest.approx(1.0)


def test_noul_and_score_answers(wire):
    wire(reply(answers={"urgent": {"type": "noul", "noul": 0.7}}),
         reply(answers={"level": {"type": "score", "score": 1.8, "confidence": 0.5,
                                  "legend": {"0": "low", "1": "medium", "2": "high"},
                                  "probabilities": {"0": 0.05, "1": 0.1, "2": 0.85}}}))
    u, lv = MicrosoftDecisionJudge().decide("x", [URGENT, LEVEL])
    assert (u.decision, u.confidence) == ("true", 0.7)
    assert (lv.decision, lv.confidence) == ("high", 0.85)
    assert lv.raw["native_confidence"] == 0.5


def test_an_unsent_option_is_a_wrong_answer_at_its_confidence(wire):
    wire(reply(answers={"route": {"type": "choice", "choice": "fraud-team",
                                  "probabilities": {"fraud-team": 0.6, "billing": 0.4}}}))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "parsed"
    assert (j.decision, j.confidence) == ("<unsent_option>", 0.6)
    assert j.raw["invalid"] == "chosen option is not among the options sent"
    assert "fraud-team" not in json.dumps(j.raw)


@pytest.mark.parametrize("answer, flag", [
    ({"type": "refusal"}, "refusal"),
    ({"type": "choice", "choice": "billing", "refusal": True,
      "probabilities": {"billing": 1.0}}, "refusal"),
    ({"type": "choice", "choice": "", "probabilities": {"billing": 1.0}}, "blank"),
    ({"type": "choice", "choice": None, "probabilities": {"billing": 1.0}}, "blank"),
    ({"type": "choice", "choice": "   "}, "blank"),
])
def test_a_refusal_or_a_blank_answer_is_no_answer(wire, answer, flag):
    wire(reply(answers={"route": answer}))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.decision == "" and j.confidence is None
    assert j.raw[flag] is True
    assert j.cost_usd == pytest.approx(76 * 0.042 / 1e6)       # billed all the same


def test_a_missing_answer_is_no_answer(wire):
    wire(reply(answers={}))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None


def test_a_distribution_that_does_not_sum_to_one_is_no_answer(wire):
    wire(reply(answers={"route": {"type": "choice", "choice": "billing",
                                  "probabilities": {"billing": 0.9, "shipping": 0.3,
                                                    "other": 0.1}}}))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and "sum" in j.raw["invalid"]


# --- cost, served, evidence ------------------------------------------------------------------

def test_costs_its_reported_input_tokens_and_keeps_the_route_s_own_figure(wire):
    wire(reply(tokens=1_000_000, cost=0.042))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.cost_usd == pytest.approx(0.042)
    assert j.raw["reported_cost_usd"] == 0.042


def test_the_live_smoke_reply_costs_what_the_route_billed(wire):
    wire(reply())
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.cost_usd == pytest.approx(0.000003192) == j.raw["reported_cost_usd"]


def test_without_a_token_count_the_cost_is_unknown(wire):
    r = reply()
    r["usage"] = {"output_tokens": 1}
    wire(r)
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.cost_usd is None


def test_records_the_served_model_provider_and_id_as_typed_fields(wire):
    wire(reply())
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.raw["served"]["model"] == VERSION
    assert j.raw["served_provider"] == "Azure"
    assert j.raw["response_id"] == "gen-dec-0000000000-synthetic"


@pytest.mark.parametrize("field, value", [("model", "microsoft/microsoft-decision-1-20261201"),
                                          ("provider", "SomeOtherHost"),
                                          ("model", None), ("provider", None)])
def test_another_served_version_or_provider_stops_the_run(wire, field, value):
    wire(reply(**{field: value}))
    with pytest.raises(RuntimeError, match="pinned") as e:
        MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert SECRET not in str(e.value)


@pytest.mark.parametrize("field", ["model", "provider"])
def test_the_stop_message_masks_a_key_echoed_as_the_served_model(wire, monkeypatch, field):
    """Masked at the source, not only by the CLI: the key is not in the environment here."""
    monkeypatch.delenv("OPENROUTER_API_KEY")
    wire(reply(**{field: SECRET}))
    with pytest.raises(RuntimeError, match="pinned") as e:
        MicrosoftDecisionJudge(api_key=SECRET).decide("x", [ROUTE])
    assert SECRET not in str(e.value)


def test_a_reported_cost_that_is_not_a_number_is_counted_as_dropped(wire):
    wire(reply(cost="0.01 USD"))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.raw["reported_cost_usd"] is None
    assert j.raw["dropped_fields"] == {"count": 1, "names": ["usage.cost"]}


def test_the_pinned_version_can_be_moved_explicitly_and_is_recorded(wire, monkeypatch):
    monkeypatch.setenv("MICROSOFT_DECISION_VERSION", "microsoft/microsoft-decision-1-20261201")
    wire(reply(model="microsoft/microsoft-decision-1-20261201"))
    judge = MicrosoftDecisionJudge()
    (j,) = judge.decide("x", [ROUTE])
    assert j.decision == "billing"
    assert judge.describe()["served_version"] == "microsoft/microsoft-decision-1-20261201"


def test_a_version_that_is_not_a_plain_id_is_refused(monkeypatch):
    monkeypatch.setenv("MICROSOFT_DECISION_VERSION", "x y {z}")
    with pytest.raises(ValueError, match="MICROSOFT_DECISION_VERSION"):
        MicrosoftDecisionJudge()


def test_keeps_only_what_the_audit_reads(wire):
    r = reply()
    r["answers"]["route"]["debug"] = {"trace": "abc"}
    r["answers"]["route"]["legend"] = {"0": "billing"}
    r["system_fingerprint_extra"] = {"x": 1}
    r["usage"]["cost_details"] = {"upstream": 1}
    wire(r)
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    names = j.raw["dropped_fields"]["names"]
    assert "answer.debug" in names and "answer.legend" in names
    assert "usage.cost" in names and "usage.cost_details" in names
    assert "debug" not in j.raw["answer"]


def test_a_reply_that_echoes_the_key_is_masked(wire):
    wire(reply(rid=SECRET))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert SECRET not in json.dumps(j.raw)


def test_an_http_error_never_echoes_the_key(wire):
    wire((401, f'{{"error": {{"message": "No auth credentials found for {SECRET}"}}}}'))
    with pytest.raises(RuntimeError) as e:
        MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert SECRET not in str(e.value) and "401" in str(e.value)


def test_provenance_names_the_model_pin_and_price_never_the_key():
    d = MicrosoftDecisionJudge().describe()
    assert d["name"] == "microsoft-decision" and d["provider"] == "hosted-api"
    assert d["model"] == "microsoft/microsoft-decision-1" and d["served_version"] == VERSION
    assert d["route"] == "openrouter" and d["route_provider"] == "azure"
    assert d["allow_fallbacks"] is False and d["questions_per_request"] == 1
    assert d["input_price_per_mtok_usd"] == 0.042 and d["output_price_per_mtok_usd"] == 0.0
    assert d["max_input_tokens"] == 32_768
    assert "P(chosen option)" in d["confidence_method"]
    assert d["endpoint_overridden"] is False
    assert SECRET not in json.dumps(d)


# --- over length ---------------------------------------------------------------------------

def context_error(status=400, limit=32768, requested=40000, code=True):
    """The route's context-length error, in OpenRouter's error shape."""
    err: dict = {"message": f"This endpoint's maximum context length is {limit} tokens. "
                            f"However, you requested about {requested} tokens. Please "
                            "reduce the length of the messages."}
    if code:
        err["code"] = status
    return status, json.dumps({"error": err})


CONTEXT_ERROR = context_error()[1]
# plausibly long: over the lower byte threshold, under the pre-send bound
LONG = "charged twice " * 2_000                                     # 28,000 bytes


@pytest.mark.parametrize("status", [400, 413])
def test_the_route_s_context_length_error_is_no_answer_not_a_crash(wire, status):
    wire(context_error(status))
    (j,) = MicrosoftDecisionJudge().decide(LONG, [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None and j.decision == ""
    assert j.raw["error"] == "max_length_exceeded" and j.raw["max_len"] == 32_768
    assert j.raw["problems"] and j.cost_usd is None


@pytest.mark.parametrize("status, message", [
    (400, "questions must not be empty"),
    (400, "max_tokens is too large"),
    (400, "criteria description too long"),
    (400, "question name too long"),
    (400, "token limit reached for this key"),
    (400, "context_length param unsupported"),
    (413, "Payload too large"),
])
def test_any_other_refusal_stops_the_run_never_over_length(wire, status, message):
    """A schema, quota or size error is not the judge's failure: never `max_length_exceeded`,
    and the run stops with the status and the message, the key masked."""
    wire((status, f'{{"error": {{"message": "{message} ({SECRET})"}}}}'))
    with pytest.raises(RuntimeError, match=str(status)) as e:
        MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert message in str(e.value) and SECRET not in str(e.value)


def test_a_reply_at_exactly_its_context_is_over_length(wire):
    wire(reply(tokens=32_768))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.raw["error"] == "max_length_exceeded"


def test_a_reply_just_under_its_context_is_used(wire):
    wire(reply(tokens=32_767))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "parsed"


def test_a_request_over_the_byte_bound_is_never_sent(wire):
    w = wire()
    big = "a" * (hosted.MICROSOFT_MAX_REQUEST_BYTES + 1)
    (j,) = MicrosoftDecisionJudge().decide(big, [ROUTE])
    assert w.requests == []
    assert j.parse_status == "no_answer" and j.raw["error"] == "max_length_exceeded"
    assert j.cost_usd == 0.0 and "bytes" in j.raw["problems"][0]


def test_the_byte_bound_counts_utf8_bytes_and_a_request_under_it_is_sent(wire):
    w = wire(reply())
    MicrosoftDecisionJudge().decide("é" * 1000, [ROUTE])          # 2,000 bytes
    assert len(w.requests) == 1
    assert hosted.MICROSOFT_MAX_REQUEST_BYTES == 4 * 32_768
    assert MicrosoftDecisionJudge().describe()["max_request_bytes"] == 4 * 32_768


def test_a_reply_that_read_more_than_its_context_is_not_used(wire):
    wire(reply(tokens=40_000))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.raw["error"] == "max_length_exceeded"
    assert j.cost_usd == pytest.approx(40_000 * 0.042 / 1e6)


def test_an_answer_error_for_length_is_over_length(wire):
    wire(reply(answers={"route": {"error": "max_length_exceeded"}}))
    (j,) = MicrosoftDecisionJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.raw["error"] == "max_length_exceeded"


def test_the_runner_counts_an_over_length_row_as_not_sent(wire):
    from judge_audit.runner import is_not_sent
    wire((400, CONTEXT_ERROR))
    (j,) = MicrosoftDecisionJudge().decide(LONG, [ROUTE])
    assert is_not_sent(j.raw)


@pytest.mark.parametrize("status, text, state", [
    # the reviewer's case: a schema error that echoes the phrase from the input
    (400, json.dumps({"error": {"code": 400, "message": "invalid criteria: 'maximum context "
                                                        "length is 5 tokens'"}}), LONG),
    # the route's exact error, but for a request far too short to have filled the context
    (*context_error(), "x"),
    # the exact sentence with another limit, or a count under the context
    (*context_error(limit=8192), LONG),
    (*context_error(requested=1200), LONG),
    # an error code that is not the status, or the sentence not at the start of the message
    (*context_error(code=False)[:1], json.dumps({"error": {"code": "invalid_request", "message":
        "This endpoint's maximum context length is 32768 tokens. However, you requested about "
        "40000 tokens."}}), LONG),
    (400, json.dumps({"error": {"code": 400, "message": "bad field: This endpoint's maximum "
                                "context length is 32768 tokens. However, you requested about "
                                "40000 tokens."}}), LONG),
    # not JSON at all
    (400, "This endpoint's maximum context length is 32768 tokens. However, you requested "
          "about 40000 tokens.", LONG),
])
def test_a_context_phrase_without_the_route_s_error_and_a_long_request_stops_the_run(
        wire, status, text, state):
    """Over length needs both: the route's own context-length error (its code the status, its
    message the route's sentence with the 32,768 limit and a larger count) and a request long
    enough to have filled the context. Anything else stops the run, the key masked."""
    wire((status, text))
    with pytest.raises(RuntimeError, match=str(status)) as e:
        MicrosoftDecisionJudge().decide(state, [ROUTE])
    assert SECRET not in str(e.value)


def test_the_route_s_error_without_a_code_still_counts_for_a_long_request(wire):
    wire(context_error(code=False))
    (j,) = MicrosoftDecisionJudge().decide(LONG, [ROUTE])
    assert j.raw["error"] == "max_length_exceeded"
    assert hosted.MICROSOFT_MIN_OVER_LENGTH_BYTES == 16_384


# --- the endpoint rule (#155) -----------------------------------------------------------------

@pytest.mark.parametrize("url", ["http://example.com\\@127.0.0.1/", "http://api.example.test/v1",
                                 "https://u:p@api.example.test/v1"])
def test_an_endpoint_override_follows_the_rule(monkeypatch, url):
    monkeypatch.setenv("MICROSOFT_DECISION_ENDPOINT", url)
    with pytest.raises(ValueError):
        MicrosoftDecisionJudge()


def test_an_endpoint_override_is_used_and_recorded_by_host_only(wire, monkeypatch):
    monkeypatch.setenv("MICROSOFT_DECISION_ENDPOINT",
                       "https://proxy.example.test:9443/api/alpha/decisions?k=1")
    w = wire(reply())
    judge = MicrosoftDecisionJudge()
    judge.decide("x", [ROUTE])
    sent = urllib.parse.urlsplit(w.requests[0][0])
    assert (sent.scheme, sent.hostname, sent.port, sent.path) == (
        "https", "proxy.example.test", 9443, "/api/alpha/decisions")
    d = judge.describe()
    assert d["endpoint_overridden"] is True and d["endpoint"] is None
    assert d["endpoint_host"] == "proxy.example.test:9443" and "k=1" not in json.dumps(d)


# --- registration --------------------------------------------------------------------------

def test_the_cli_and_mcp_offer_it():
    from judge_audit import cli, mcp_server
    assert "microsoft-decision" in cli.JUDGES
    assert "microsoft-decision" in {j["name"] for j in mcp_server.list_judges()["judges"]}
    judge, tag = cli._judge("microsoft-decision", [])
    assert isinstance(judge, MicrosoftDecisionJudge) and tag == ""


# --- opt-in live smoke test (never in CI) -------------------------------------------------------

@pytest.mark.skipif(not os.environ.get("JUDGE_AUDIT_SMOKE_HOSTED"),
                    reason="set JUDGE_AUDIT_SMOKE_HOSTED=1 (calls a paid API)")
def test_smoke_microsoft_decision_answers_a_synthetic_choice(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", LIVE_KEY)
    (j,) = MicrosoftDecisionJudge().decide(
        "Hi, my card was charged twice for order 4471 yesterday. Please refund one.", [ROUTE])
    assert j.decision in ROUTE.options and 0.0 <= j.confidence <= 1.0
