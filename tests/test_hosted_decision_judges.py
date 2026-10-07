"""The hosted decision APIs with the network stubbed: the OpenAI Decisions API
(`openai-decisions`) and Clef / Clef-flash on Workers AI (`clef-hosted`). What each sends,
which confidence it audits, what it keeps, what it costs, and what it never records."""
from __future__ import annotations

import io
import json
import os
import urllib.error
import urllib.request

import pytest

from judge_audit.judges import hosted
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.hosted import ClefHostedJudge, OpenAIDecisionsJudge

ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["billing", "returns", "other"],
                 descriptions={"billing": "Payments and charges", "returns": "Refunds"})
URGENT = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")
LEVEL = Question(name="level", type=QuestionType.SCORE, instructions="How severe?",
                 options=["low", "high"])

SECRET = "sk-test-not-a-real-key-0123456789"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Wire:
    """Records every request and answers from a queue (a body, or an HTTP status)."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests: list[tuple[str, dict, dict]] = []

    def __call__(self, req, timeout=0):
        self.requests.append((req.full_url, dict(req.header_items()),
                              json.loads(req.data.decode())))
        reply = self.replies.pop(0)
        if isinstance(reply, int):
            raise urllib.error.HTTPError(req.full_url, reply, "err", {},
                                         io.BytesIO(b'{"error": "busy"}'))
        return _Resp(json.dumps(reply).encode())


@pytest.fixture
def wire(monkeypatch):
    def install(*replies):
        w = Wire(*replies)
        monkeypatch.setattr(urllib.request, "urlopen", w)
        monkeypatch.setattr(hosted.time, "sleep", lambda s: None)
        return w
    return install


def _decisions_answer(name="route", choice="billing", probs=None, confidence=0.93):
    probs = probs or {"billing": 0.95, "returns": 0.03, "other": 0.02}
    return {"type": "choice", "name": name, "choice": choice, "confidence": confidence,
            "probabilities": [{"value": k, "probability": v} for k, v in probs.items()]}


@pytest.fixture
def openai_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.delenv("DECISIONS_QUESTIONS_PER_REQUEST", raising=False)


# --- OpenAI Decisions API -------------------------------------------------------------------

def test_decisions_sends_the_documented_request(wire, openai_env):
    w = wire({"answers": [_decisions_answer()]})
    OpenAIDecisionsJudge().decide("I was charged twice.", [ROUTE])
    url, headers, body = w.requests[0]
    assert url == "https://api.openai.com/v1/decisions"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert body == {"model": "gpt-6-luna", "input": "I was charged twice.", "questions": [
        {"type": "choice", "name": "route", "instructions": "Which team?", "choices": [
            {"value": "billing", "description": "Payments and charges"},
            {"value": "returns", "description": "Refunds"},
            {"value": "other", "description": "other"}]}]}


def test_decisions_audits_p_chosen_and_keeps_its_confidence_field(wire, openai_env):
    wire({"answers": [_decisions_answer()]})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.decision == "billing" and j.confidence == 0.95
    assert j.raw["native_confidence"] == 0.93
    assert j.raw["probabilities"] == {"billing": 0.95, "returns": 0.03, "other": 0.02}


def test_decisions_predicate_and_score_map_to_noul_and_score(wire, openai_env):
    wire({"answers": [{"type": "predicate", "name": "urgent", "probability": 0.2},
                      {"type": "score", "name": "level", "score": 0.7, "confidence": 0.4,
                       "probabilities": [{"value": 0, "label": "low", "probability": 0.3},
                                         {"value": 1, "label": "high", "probability": 0.7}]}]})
    os.environ["DECISIONS_QUESTIONS_PER_REQUEST"] = "all"
    try:
        u, lv = OpenAIDecisionsJudge().decide("x", [URGENT, LEVEL])
    finally:
        del os.environ["DECISIONS_QUESTIONS_PER_REQUEST"]
    assert (u.decision, u.confidence) == ("false", 0.8)
    assert (lv.decision, lv.confidence) == ("high", 0.7)


def test_decisions_sends_one_question_per_request_by_default(wire, openai_env):
    w = wire({"answers": [_decisions_answer()]},
             {"answers": [{"type": "predicate", "name": "urgent", "probability": 0.9}]})
    out = OpenAIDecisionsJudge().decide("x", [ROUTE, URGENT])
    assert [len(b["questions"]) for _, _, b in w.requests] == [1, 1]
    assert [j.decision for j in out] == ["billing", "true"]


def test_decisions_can_share_one_request_when_asked(wire, openai_env, monkeypatch):
    monkeypatch.setenv("DECISIONS_QUESTIONS_PER_REQUEST", "all")
    w = wire({"answers": [_decisions_answer(),
                          {"type": "predicate", "name": "urgent", "probability": 0.9}]})
    judge = OpenAIDecisionsJudge()
    judge.decide("x", [ROUTE, URGENT])
    assert len(w.requests) == 1 and len(w.requests[0][2]["questions"]) == 2
    assert judge.describe()["questions_per_request"] == "all"


def test_decisions_a_refusal_is_no_answer_and_counted(wire, openai_env):
    wire({"answers": [{"type": "refusal", "name": "route"}]})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None and j.decision == ""
    assert j.raw["refusal"] is True


def test_decisions_a_missing_answer_is_no_answer(wire, openai_env):
    wire({"answers": []})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None


def test_decisions_costs_its_input_tokens_when_the_response_counts_them(wire, openai_env):
    wire({"answers": [_decisions_answer()], "usage": {"input_tokens": 200_000}})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.cost_usd == pytest.approx(0.02)          # 0.2 M tokens x $0.10


def test_decisions_without_a_token_count_the_cost_is_unknown_not_guessed(wire, openai_env):
    wire({"answers": [_decisions_answer()]})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.cost_usd is None


def test_decisions_records_what_was_served(wire, openai_env):
    wire({"answers": [_decisions_answer()], "model": "gpt-6-luna-2026-09-30",
          "id": "dec_123"})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.raw["served"]["model"] == "gpt-6-luna-2026-09-30"
    assert j.raw["response_id"] == "dec_123"


def test_decisions_retries_a_busy_server_then_answers(wire, openai_env):
    w = wire(429, 503, {"answers": [_decisions_answer()]})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.decision == "billing" and len(w.requests) == 3


def test_decisions_without_a_key_says_which_variable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIDecisionsJudge()


def test_decisions_provenance_names_the_model_and_never_the_key(wire, openai_env):
    d = OpenAIDecisionsJudge().describe()
    assert d["model"] == "gpt-6-luna" and d["provider"] == "hosted-api"
    assert d["input_price_per_mtok_usd"] == 0.10 and d["output_price_per_mtok_usd"] == 0.0
    assert d["questions_per_request"] == 1
    assert "P(chosen option)" in d["confidence_method"]
    assert SECRET not in json.dumps(d)


def test_decisions_an_http_error_never_echoes_the_key(wire, openai_env):
    wire(401)
    with pytest.raises(RuntimeError) as e:
        OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert SECRET not in str(e.value) and "401" in str(e.value)


def test_decisions_a_server_that_echoes_the_key_does_not_get_it_printed(monkeypatch,
                                                                        openai_env):
    def echo(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 401, "err", {}, io.BytesIO(
            f'{{"error": "Incorrect API key provided: {SECRET}"}}'.encode()))
    monkeypatch.setattr(urllib.request, "urlopen", echo)
    with pytest.raises(RuntimeError) as e:
        OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert SECRET not in str(e.value) and "Incorrect API key" in str(e.value)


# --- Clef / Clef-flash on Workers AI ---------------------------------------------------------

@pytest.fixture
def cf_env(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", SECRET)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct123")
    monkeypatch.delenv("CLEF_HOSTED_MODEL", raising=False)
    monkeypatch.delenv("CLEF_HOSTED_QUESTIONS_PER_REQUEST", raising=False)


def _clef_reply(model="clef-flash", answers=None, tokens=180):
    return {"result": {"model": model, "usage": {"input_tokens": tokens, "output_tokens": 0},
                       "answers": answers or {"route": {
                           "type": "choice", "choice": "billing", "confidence": 0.81,
                           "probabilities": {"billing": 0.9, "returns": 0.06,
                                             "other": 0.04}}}},
            "success": True, "errors": [], "messages": []}


def test_clef_hosted_sends_a_system_one_request(wire, cf_env):
    w = wire(_clef_reply())
    ClefHostedJudge().decide("Charged twice", [ROUTE])
    url, headers, body = w.requests[0]
    assert url == ("https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/"
                   "@cf/cloudflare/clef-flash")
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert body == {"model": "clef-flash", "state": "Charged twice", "questions": {
        "route": {"type": "choice", "instructions": "Which team?",
                  "criteria": {"billing": "Payments and charges", "returns": "Refunds",
                               "other": None}}}}


def test_clef_hosted_audits_p_chosen_and_keeps_its_confidence(wire, cf_env):
    wire(_clef_reply())
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.decision == "billing" and j.confidence == 0.9
    assert j.raw["native_confidence"] == 0.81


def test_clef_hosted_costs_its_reported_input_tokens(wire, cf_env):
    wire(_clef_reply(tokens=1_000_000))
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.cost_usd == pytest.approx(0.09)          # clef-flash, $0.09 per M input tokens


def test_clef_hosted_clef_is_the_27b_at_its_own_price(wire, cf_env, monkeypatch):
    monkeypatch.setenv("CLEF_HOSTED_MODEL", "clef")
    w = wire(_clef_reply(model="clef", tokens=1_000_000))
    judge = ClefHostedJudge()
    (j,) = judge.decide("x", [ROUTE])
    assert w.requests[0][0].endswith("/@cf/cloudflare/clef")
    assert w.requests[0][2]["model"] == "clef"
    assert j.cost_usd == pytest.approx(0.24)
    assert judge.describe()["model"] == "clef"


def test_clef_hosted_refuses_an_unknown_model(cf_env, monkeypatch):
    monkeypatch.setenv("CLEF_HOSTED_MODEL", "clef-ultra")
    with pytest.raises(ValueError, match="clef-flash"):
        ClefHostedJudge()


def test_clef_hosted_an_unsuccessful_envelope_is_an_error_without_the_token(wire, cf_env):
    wire({"result": None, "success": False, "errors": [{"code": 5006, "message": "bad input"}]})
    with pytest.raises(RuntimeError) as e:
        ClefHostedJudge().decide("x", [ROUTE])
    assert "bad input" in str(e.value) and SECRET not in str(e.value)


def test_clef_hosted_an_answer_without_probabilities_is_no_answer(wire, cf_env):
    wire(_clef_reply(answers={"route": {"type": "choice", "choice": "billing"}}))
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None


def test_clef_hosted_one_question_per_request_by_default(wire, cf_env):
    w = wire(_clef_reply(), _clef_reply(answers={"urgent": {"type": "noul", "noul": 0.7}}))
    out = ClefHostedJudge().decide("x", [ROUTE, URGENT])
    assert [len(b["questions"]) for _, _, b in w.requests] == [1, 1]
    assert [j.decision for j in out] == ["billing", "true"]


def test_clef_hosted_without_credentials_names_both_variables(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    with pytest.raises(RuntimeError, match="CLOUDFLARE_API_TOKEN.*CLOUDFLARE_ACCOUNT_ID"):
        ClefHostedJudge()


def test_clef_hosted_provenance_names_the_model_never_the_account_or_token(cf_env):
    d = ClefHostedJudge().describe()
    assert d["model"] == "clef-flash" and d["model_id"] == "@cf/cloudflare/clef-flash"
    assert d["provider"] == "hosted-api" and d["input_price_per_mtok_usd"] == 0.09
    text = json.dumps(d)
    assert SECRET not in text and "acct123" not in text


# --- both ----------------------------------------------------------------------------------

@pytest.mark.parametrize("judge, env", [(OpenAIDecisionsJudge, "openai_env"),
                                        (ClefHostedJudge, "cf_env")])
def test_a_rate_limit_that_never_clears_raises_rate_limited(wire, judge, env, request):
    request.getfixturevalue(env)
    wire(*([429] * 10))
    with pytest.raises(RuntimeError, match="rate-limited"):
        judge().decide("x", [ROUTE])


# --- opt-in live smoke tests (never in CI) --------------------------------------------------

LIVE = pytest.mark.skipif(not os.environ.get("JUDGE_AUDIT_SMOKE_HOSTED"),
                          reason="set JUDGE_AUDIT_SMOKE_HOSTED=1 (calls a paid API)")


@LIVE
def test_smoke_openai_decisions_answers_the_documented_example():
    q = Question(name="department", type=QuestionType.CHOICE,
                 instructions="Which department should handle this complaint?",
                 options=["billing", "other"],
                 descriptions={"billing": "Payments, invoices, and refunds.",
                               "other": "Requests outside these categories."})
    (j,) = OpenAIDecisionsJudge().decide("I was charged twice for my order.", [q])
    assert j.decision == "billing" and 0.0 <= j.confidence <= 1.0


@LIVE
def test_smoke_clef_hosted_answers_a_choice():
    (j,) = ClefHostedJudge().decide("I was charged twice for my order.", [ROUTE])
    assert j.decision in ROUTE.options and 0.0 <= j.confidence <= 1.0


def test_decisions_reads_the_shape_the_live_api_returns(wire, openai_env):
    """The reply shape seen from the live API on 2026-10-07, ids and texts removed:
    probabilities at two decimals, a `confidence` within 0.01 of P(chosen), and a `usage`
    block the documentation does not describe."""
    wire({"model": "gpt-6-luna",
          "answers": [{"type": "choice", "name": "route", "choice": "billing",
                       "probabilities": [{"value": "billing", "probability": 0.54},
                                         {"value": "returns", "probability": 0.45},
                                         {"value": "other", "probability": 0.01}],
                       "confidence": 0.53}],
          "usage": {"input_tokens": 1045,
                    "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    "output_tokens": 0, "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 1045}})
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.parse_status == "parsed" and j.decision == "billing" and j.confidence == 0.54
    assert j.raw["native_confidence"] == 0.53
    assert j.cost_usd == pytest.approx(1045 / 1e6 * 0.10)
    assert j.raw["served"]["model"] == "gpt-6-luna" and j.raw["response_id"] is None
