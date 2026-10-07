"""Review of the hosted decision judges (#155): a published cost never undercounts, an
invalid probability is never a parsed answer, evidence is always valid JSON, and no error
carries a credential or an account id. Network stubbed."""
from __future__ import annotations

import io
import json
import math
import urllib.error
import urllib.request

import pytest

from judge_audit.judges import hosted
from judge_audit.judges import jev as jev_mod
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.hosted import ClefHostedJudge, OpenAIDecisionsJudge, valid_distribution
from judge_audit.judges.llm import LLMJudge

ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["billing", "returns", "other"])
URGENT = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")
SECRET = "cf-token-not-real-0123456789abcdef"
ACCOUNT = "4f1e2d3c4b5a69788796a5b4c3d2e1f0"


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _install(monkeypatch, replies):
    queue = list(replies)

    def urlopen(req, timeout=0):
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, tuple):
            code, body = reply
            raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(body.encode()))
        return _Resp(json.dumps(reply).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(hosted.time, "sleep", lambda s: None)
    monkeypatch.setattr(hosted.time, "monotonic", _clock())


def _clock():
    t = [0.0]

    def now():
        t[0] += 0.001
        return t[0]
    return now


@pytest.fixture
def cf(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", SECRET)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT)
    for v in ("CLEF_HOSTED_MODEL", "CLEF_HOSTED_QUESTIONS_PER_REQUEST"):
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def oa(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.delenv("DECISIONS_QUESTIONS_PER_REQUEST", raising=False)


def _clef(answer, tokens=1_000_000):
    return {"success": True, "errors": [], "result": {
        "model": "clef-flash", "usage": {"input_tokens": tokens, "output_tokens": 0},
        "answers": {"route": answer}}}


GOOD = {"type": "choice", "choice": "billing", "confidence": 0.8,
        "probabilities": {"billing": 0.9, "returns": 0.06, "other": 0.04}}


# --- 1. every request's reported tokens are billed, whatever the answer --------------------

@pytest.mark.parametrize("answer", [
    {"type": "choice", "choice": "billing"},                        # no probabilities
    {"error": "max_length_exceeded"},                               # refused per question
    None])                                                          # no answer at all
def test_clef_a_request_that_gives_no_answer_still_costs_its_tokens(monkeypatch, cf, answer):
    reply = _clef(answer)
    if answer is None:
        reply["result"]["answers"] = {}
    _install(monkeypatch, [reply])
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer"
    assert j.cost_usd == pytest.approx(0.09)


def test_clef_nine_calls_one_third_refused_cost_all_nine(monkeypatch, cf):
    """The reviewer's case: 9 calls of 1,000 tokens at $0.09 per M, 3 of them refused."""
    replies = [_clef(GOOD if i % 3 else {"type": "choice", "choice": "billing"}, tokens=1000)
               for i in range(9)]
    _install(monkeypatch, replies)
    judge = ClefHostedJudge()
    total = math.fsum(judge.decide("x", [ROUTE])[0].cost_usd for _ in range(9))
    assert total == pytest.approx(9 * 1000 / 1e6 * 0.09)            # 0.00081


def test_decisions_a_refusal_still_costs_its_tokens(monkeypatch, oa):
    _install(monkeypatch, [{"answers": [{"type": "refusal", "name": "route"}],
                            "usage": {"input_tokens": 1_000_000}}])
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.cost_usd == pytest.approx(0.10)


def test_decisions_without_reported_tokens_a_refusal_has_unknown_cost(monkeypatch, oa):
    _install(monkeypatch, [{"answers": [{"type": "refusal", "name": "route"}]}])
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.cost_usd is None


def test_jev_typesafe_without_reported_tokens_has_unknown_cost_not_zero(monkeypatch):
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", SECRET)
    monkeypatch.delenv("JEV_ENDPOINT", raising=False)
    monkeypatch.delenv("JEV_MODEL", raising=False)
    body = {"model": "jev-1.13.0", "answers": {"route": {
        "type": "choice", "choice": "billing", "confidence": 0.8,
        "probabilities": {"billing": 0.9, "returns": 0.06, "other": 0.04}}}}
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _Resp(
        json.dumps(body).encode()))
    (j,) = jev_mod.JevJudge().decide("x", [ROUTE])
    assert j.cost_usd is None


def test_llm_a_priced_reply_without_usage_has_unknown_cost_not_zero(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    reply = {"model": "gpt-5-mini", "choices": [{"message": {"content":
             '{"answers": {"route": {"decision": "billing", "confidence": 0.8}}}'}}]}
    from judge_audit.judges import llm as llm_mod
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp(json.dumps(reply).encode()))
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    (j,) = LLMJudge().decide("x", [ROUTE])
    assert j.cost_usd is None


def test_llm_a_free_local_reply_without_usage_still_costs_nothing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen3-8b")
    for v in ("LLM_INPUT_PRICE", "LLM_OUTPUT_PRICE"):
        monkeypatch.delenv(v, raising=False)
    reply = {"model": "qwen3-8b", "choices": [{"message": {"content":
             '{"answers": {"route": {"decision": "billing", "confidence": 0.8}}}'}}]}
    from judge_audit.judges import llm as llm_mod
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp(json.dumps(reply).encode()))
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    (j,) = LLMJudge().decide("x", [ROUTE])
    assert j.cost_usd == 0.0


# --- 2. an invalid probability is no answer, with a reason ---------------------------------

BAD = [
    ({"billing": float("nan"), "returns": 0.5, "other": 0.5}, "not a finite number"),
    ({"billing": 1.5, "returns": 0.0, "other": 0.0}, "outside [0, 1]"),
    ({"billing": -0.2, "returns": 0.6, "other": 0.6}, "outside [0, 1]"),
    ({"billing": 0.5, "returns": 0.2, "other": 0.1}, "sum to"),
]


@pytest.mark.parametrize("probs, reason", BAD)
def test_clef_an_invalid_distribution_is_no_answer_with_its_reason(monkeypatch, cf, probs,
                                                                  reason):
    _install(monkeypatch, [_clef({"type": "choice", "choice": "billing", "confidence": 0.5,
                                  "probabilities": probs})])
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.confidence is None
    assert reason in j.raw["invalid"]
    assert j.cost_usd == pytest.approx(0.09)


@pytest.mark.parametrize("probs, reason", BAD)
def test_decisions_an_invalid_distribution_is_no_answer_with_its_reason(monkeypatch, oa,
                                                                       probs, reason):
    _install(monkeypatch, [{"answers": [{"type": "choice", "name": "route", "choice": "billing",
                                         "confidence": 0.5, "probabilities": [
                                             {"value": k, "probability": v}
                                             for k, v in probs.items()]}]}])
    (j,) = OpenAIDecisionsJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and reason in j.raw["invalid"]


@pytest.mark.parametrize("p", [float("nan"), 1.5, -0.2, float("inf")])
def test_a_yes_no_probability_out_of_range_is_no_answer_never_false(monkeypatch, cf, p):
    reply = _clef(None)
    reply["result"]["answers"] = {"urgent": {"type": "noul", "noul": p}}
    _install(monkeypatch, [reply])
    (j,) = ClefHostedJudge().decide("x", [URGENT])
    assert j.parse_status == "no_answer" and j.decision == "" and j.confidence is None


def test_a_chosen_option_absent_from_the_distribution_is_no_answer(monkeypatch, cf):
    _install(monkeypatch, [_clef({"type": "choice", "choice": "nope", "confidence": 0.5,
                                  "probabilities": {"billing": 0.9, "returns": 0.06,
                                                    "other": 0.04}})])
    (j,) = ClefHostedJudge().decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and "not among" in j.raw["invalid"]


def test_valid_distribution_by_hand():
    from judge_audit.judges.hosted import decimals, sum_tolerance
    assert valid_distribution({"a": 0.6, "b": 0.4}) is None
    # two options at 2 decimals: the rounding can move the sum by 2 x 0.005 = 0.01 at most
    assert sum_tolerance({"a": 0.6, "b": 0.42}) == pytest.approx(0.01 + 1e-9)
    assert "sum to" in valid_distribution({"a": 0.6, "b": 0.42})          # 0.02 off
    # full precision leaves no room for rounding: 0.009 off is not rounding
    assert "sum to" in valid_distribution({"a": 0.6, "b": 0.4 + 0.009})
    assert "no probabilities" in valid_distribution({})
    assert [decimals(x) for x in (0.5, 0.54, 0.123, 1.0, 0, 1e-05)] == [1, 2, 3, 0, 0, 5]


def _rounded(k: int, total: float) -> dict[str, float]:
    """`k` options at 2 decimals summing to `total` (exactly representable steps)."""
    cents = round(total * 100)
    base, extra = divmod(cents, k)
    return {f"o{i}": (base + (1 if i < extra else 0)) / 100 for i in range(k)}


def test_77_options_at_2_decimals_summing_to_1_03_are_accepted(monkeypatch, oa):
    """77 values each rounded by up to 0.005 can move the total by 0.385; 1.03 is rounding."""
    probs = _rounded(77, 1.03)
    probs["o0"] = 0.40                      # one clear choice, the rest spread
    rest = round(1.03 - 0.40, 2)
    for i, v in enumerate(_rounded(76, rest).values(), 1):
        probs[f"o{i}"] = v
    assert abs(sum(probs.values()) - 1.03) < 1e-9
    q = Question(name="intent", type=QuestionType.CHOICE, instructions="?",
                 options=list(probs))
    _install(monkeypatch, [{"answers": [{"type": "choice", "name": "intent", "choice": "o0",
                                         "confidence": 0.4, "probabilities": [
                                             {"value": k, "probability": v}
                                             for k, v in probs.items()]}]}])
    (j,) = OpenAIDecisionsJudge().decide("x", [q])
    assert j.parse_status == "parsed" and j.decision == "o0"
    assert j.confidence == 0.40                                     # as returned, not renormalised
    assert j.raw["probability_sum"] == pytest.approx(1.03)
    assert j.raw["probability_decimals"] == 2


def test_a_sum_beyond_what_rounding_explains_is_still_rejected(monkeypatch, oa):
    """77 options at 2 decimals allow 0.385; a total of 1.40 is not rounding."""
    probs = _rounded(77, 1.40)
    q = Question(name="intent", type=QuestionType.CHOICE, instructions="?",
                 options=list(probs))
    _install(monkeypatch, [{"answers": [{"type": "choice", "name": "intent", "choice": "o0",
                                         "confidence": 0.1, "probabilities": [
                                             {"value": k, "probability": v}
                                             for k, v in probs.items()]}]}])
    (j,) = OpenAIDecisionsJudge().decide("x", [q])
    assert j.parse_status == "no_answer" and "sum to" in j.raw["invalid"]
    assert j.raw["probability_sum"] == pytest.approx(1.40)


def test_evidence_with_an_invalid_probability_round_trips_as_strict_json(tmp_path,
                                                                       monkeypatch, cf):
    from judge_audit.runner import load_dataset, run_audit, write_judgments
    labels = tmp_path / "labels.jsonl"
    labels.write_text(json.dumps({"state": "x", "questions": [
        {"name": "route", "type": "choice", "instructions": "Which team?",
         "options": ["billing", "returns", "other"]}], "labels": {"route": "billing"}}) + "\n",
        encoding="utf-8")
    _install(monkeypatch, [_clef({"type": "choice", "choice": "billing", "confidence": 0.5,
                                  "probabilities": {"billing": float("nan"), "returns": 0.5,
                                                    "other": 0.5}})])
    rows, meta = load_dataset(str(labels))
    result = run_audit(ClefHostedJudge(), rows, str(labels), meta, ci=False)
    out = tmp_path / "j.jsonl"
    write_judgments(result, str(out))

    def strict(text):
        return json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    for line in out.read_text(encoding="utf-8").splitlines():
        strict(line)
    strict(json.dumps(result.to_dict(), allow_nan=False))


def test_write_judgments_refuses_to_write_a_non_finite_number(tmp_path):
    from judge_audit.runner import AuditResult, write_judgments
    r = AuditResult(judge="x", n=1, accuracy=0.0, ece=None,
                    records=[{"idx": 0, "confidence": float("nan")}])
    with pytest.raises(ValueError):
        write_judgments(r, str(tmp_path / "j.jsonl"))


# --- 3. no error carries the token or the account id ---------------------------------------

def test_a_connection_error_naming_the_url_hides_the_account(monkeypatch, cf):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run/@cf/cloudflare/clef"
    _install(monkeypatch, [urllib.error.URLError(f"cannot reach {url}")] * 20)
    with pytest.raises(RuntimeError) as e:
        ClefHostedJudge().decide("x", [ROUTE])
    assert ACCOUNT not in str(e.value) and SECRET not in str(e.value)


@pytest.mark.parametrize("code", [400, 403, 429])
def test_an_http_error_body_naming_the_account_or_token_hides_both(monkeypatch, cf, code):
    body = json.dumps({"errors": [{"message": f"account {ACCOUNT} token {SECRET} not allowed "
                                              f"on /accounts/{ACCOUNT}/ai/run"}]})
    _install(monkeypatch, [(code, body)] * 20)
    with pytest.raises(RuntimeError) as e:
        ClefHostedJudge().decide("x", [ROUTE])
    assert ACCOUNT not in str(e.value) and SECRET not in str(e.value)


def test_an_unsuccessful_envelope_naming_the_account_hides_it(monkeypatch, cf):
    _install(monkeypatch, [{"success": False, "result": None,
                            "errors": [{"message": f"no access to account {ACCOUNT}"}]}])
    with pytest.raises(RuntimeError) as e:
        ClefHostedJudge().decide("x", [ROUTE])
    assert ACCOUNT not in str(e.value) and "no access" in str(e.value)


# --- 4. limits --------------------------------------------------------------------------------

def test_clef_refuses_more_than_64_questions_in_one_request(cf, monkeypatch):
    monkeypatch.setenv("CLEF_HOSTED_QUESTIONS_PER_REQUEST", "all")
    qs = [Question(name=f"q{i}", type=QuestionType.NOUL, instructions="?") for i in range(65)]
    with pytest.raises(ValueError, match="64"):
        ClefHostedJudge().decide("x", qs)


def test_connection_retries_give_up_in_under_30_seconds(monkeypatch, cf):
    """A host that cannot be reached is reported within the budget, not after minutes."""
    slept: list[float] = []
    _install(monkeypatch, [urllib.error.URLError("nodename nor servname provided")] * 50)
    monkeypatch.setattr(hosted.time, "sleep", slept.append)
    with pytest.raises(RuntimeError, match="could not reach Workers AI"):
        ClefHostedJudge().decide("x", [ROUTE])
    assert sum(slept) < 30


# --- a bad value fails at its own row, not when the file is written --------------------------

class _NanAt:
    """A judge whose answer to row `bad` carries a NaN in raw; every other row is clean."""
    name = "nan-at"

    def __init__(self, bad: int):
        self.bad, self.calls = bad, 0

    def describe(self) -> dict:
        return {"name": self.name}

    def decide(self, state, questions):
        from judge_audit.judges.base import Judgment
        row, self.calls = self.calls, self.calls + 1
        raw = {"score": float("nan") if row == self.bad else 0.5}
        return [Judgment(question=q.name, decision=q.options[0], confidence=0.9, raw=raw)
                for q in questions]


def test_a_non_finite_value_fails_at_its_row_with_its_path(tmp_path):
    from judge_audit.runner import load_dataset, run_audit
    labels = tmp_path / "labels.jsonl"
    labels.write_text("".join(json.dumps({"state": f"s{i}", "questions": [
        {"name": "route", "type": "choice", "instructions": "?", "options": ["a", "b"]}],
        "labels": {"route": "a"}}) + "\n" for i in range(5)), encoding="utf-8")
    rows, meta = load_dataset(str(labels))
    judge = _NanAt(bad=2)
    with pytest.raises(ValueError, match=r"row 2.*'route'.*raw\.score.*NaN"):
        run_audit(judge, rows, str(labels), meta, ci=False)
    assert judge.calls == 3                       # stopped at the bad row, not after all five


# --- an infinite log loss is said, never printed as a bare number ---------------------------

def test_the_summary_line_explains_an_infinite_nll(tmp_path, capsys):
    from judge_audit import cli
    from judge_audit.runner import AuditResult
    line = cli.nll_text(AuditResult(judge="x", n=2, accuracy=0.5, ece=0.1, nll=None,
                                    nll_infinite=1))
    assert line == "inf(1 certain and wrong)"
    assert cli.nll_text(AuditResult(judge="x", n=2, accuracy=1.0, ece=0.1, nll=0.1234,
                                    nll_infinite=0)) == "0.1234"


def test_a_certain_wrong_answer_makes_nll_null_in_json_and_explained_in_markdown():
    from judge_audit.report import render_markdown
    from judge_audit.runner import summarize
    records = [{"confidence": 1.0, "correct": False, "latency_s": 0.1, "cost_usd": 0.0},
               {"confidence": 0.7, "correct": True, "latency_s": 0.1, "cost_usd": 0.0}]
    res = summarize("x", records, ci=False)
    d = res.to_dict()
    assert d["nll"] is None and d["nll_infinite"] == 1
    json.dumps(d, allow_nan=False)                        # the JSON never holds an infinity
    md = render_markdown(res)
    assert "NLL **∞** (1 answer declared certain and wrong)" in md
    assert "nll=inf" not in md and " inf " not in md
