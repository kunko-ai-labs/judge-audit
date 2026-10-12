"""A successful reply never carries a credential into evidence (#161). A server, a gateway or a
provider module that echoes the key, the account id, a URL with a secret in it or an
Authorization header in a 200 reply gets it masked before the judgment's `raw`, the
checkpoint row or the run header is written; the record then says `redacted: true`. A clean
reply is stored exactly as before. No outside host is called."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from judge_audit.judges import hosted, jev, llm
from judge_audit.judges.base import Judge, Judgment, Question, QuestionType
from judge_audit.judges.secrets import OPENER, evidence_raw, redact_evidence

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "audit_resumable.py"
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"

HELD = "Zq9heldTOKENvalue77x41"          # no known shape: masked only because a judge holds it
ENV = "Wv3envSECRETvalue88y52"           # no known shape: masked only because a variable holds it
ACCOUNT = "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"

ROUTE = Question(name="route", type=QuestionType.CHOICE, instructions="Which team?",
                 options=["billing", "returns", "other"])
CATEGORY = Question(name="category", type=QuestionType.CHOICE, instructions="classify",
                    options=["spam", "order"])


def _runs(secret: str, text: str) -> list[str]:
    """Every 12-character run of `secret` left in `text`, in any case."""
    low = text.lower()
    return [secret[i:i + 12] for i in range(len(secret) - 11) if secret[i:i + 12].lower() in low]


def _clean(value, *secrets: str) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    return not any(_runs(s, text) for s in secrets)


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch):
    """Only the credentials a test sets: none of the caller's own variables."""
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_API_KEY", "TYPESAFE_API_KEY",
                 "AI_GATEWAY_API_KEY", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID",
                 "JEV_API_KEY", "ANTHROPIC_BASE_URL", "LLM_TEMPERATURE", "LLM_SAMPLES",
                 "LLM_EXTRA_BODY", "LLM_PROMPT_TEMPLATE", "DECISIONS_ENDPOINT",
                 "CLEF_HOSTED_ENDPOINT", "DECISIONS_QUESTIONS_PER_REQUEST",
                 "CLEF_HOSTED_QUESTIONS_PER_REQUEST"):
        monkeypatch.delenv(name, raising=False)


# --- the helper, by hand ----------------------------------------------------------------------

def test_redact_evidence_masks_every_string_and_keeps_the_rest():
    value = {"text": f"echo {HELD}", "n": 3, "p": 0.25, "ok": True, "none": None,
             "list": [f"Bearer {HELD}", 7], "tuple": ("a", f"https://u:{HELD}@h.test/x"),
             HELD: "a key as a key"}
    out = redact_evidence(value, HELD)
    assert _clean(out, HELD), out
    assert (out["n"], out["p"], out["ok"], out["none"]) == (3, 0.25, True, None)
    assert out["list"][1] == 7 and out["tuple"][0] == "a" and isinstance(out["tuple"], list)
    assert "a key as a key" in out.values()


def test_redact_evidence_reads_the_credential_variables(monkeypatch):
    monkeypatch.setenv("SOME_SERVICE_TOKEN", ENV)
    assert _clean(redact_evidence({"a": [f"x{ENV}y"]}), ENV)


def test_evidence_raw_flags_only_what_it_changed():
    clean = {"text": '{"answers": {}}', "usage": {"input_tokens": 3}, "served": {"model": None}}
    assert evidence_raw(clean, HELD) == clean
    assert "redacted" not in evidence_raw(clean, HELD)
    out = evidence_raw({"text": f"key {HELD}"}, HELD)
    assert out["redacted"] is True and _clean(out, HELD)
    # a raw that was redacted once keeps its flag when it is passed through again
    assert evidence_raw(out)["redacted"] is True


def test_evidence_raw_keeps_tuples_as_json_would_without_flagging():
    out = evidence_raw({"pair": ("a", "b")}, HELD)
    assert out == {"pair": ["a", "b"]} and "redacted" not in out


@pytest.mark.parametrize("rid", [
    "urn:example:svc:zone-1:123456789012:profile/model-x",
    "urn:example:svc:zone-1:123456789012",                 # the account last
    "urn:example:svc:zone-1::profile/model-x",             # no account: the rest still names
    "urn:example:svc:zone-1:123456789012:profile/a:b",
])
def test_a_resource_identifier_is_replaced_whole(rid):
    """Its partition, service and zone segments can name whose infrastructure served the
    model, so none of it is kept, not only the account number."""
    out = redact_evidence({"served": {"model": rid}, "text": f"served by {rid}."})
    text = json.dumps(out)
    for part in ("example:svc", "zone-1", "123456789012", "profile/"):
        assert part not in text, text
    assert out["text"].startswith("served by ") and out["text"].endswith(".")


@pytest.mark.parametrize("value", [
    "/v1/123456789012/run", "https://h.test/projects/123456789012?x=1",
    {"owner_id": "123456789012"}, {"account": 123456789012}, {"accountId": "123456789012"},
    {"Account-Id": "abcdef123456"}, {"tenant": "abcdef123456"},
])
def test_an_account_in_other_positions_and_forms_is_masked(value):
    out = redact_evidence(value)
    assert "123456789012" not in json.dumps(out) and "abcdef123456" not in json.dumps(out)


@pytest.mark.parametrize("text", [
    "t:202610071230:x", "at 12:34:56", "build 202610071230", "/runs/202610071230/x",
    '{"answers": {"intent": {"decision": "alarm_set", "confidence": 1.0}}}',
])
def test_timestamps_and_plain_text_are_not_masked(text):
    assert evidence_raw({"text": text}) == {"text": text}


@pytest.mark.parametrize("raw", [
    {"headers": {"Authorization": "plainOPAQUEvalue123"}},
    {"headers": {"authorization": "Basic plainOPAQUEvalue123"}},
    {"headers": {"Proxy-Authorization": "plainOPAQUEvalue123"}},
    {"x-api-key": "plainOPAQUEvalue123"}, {"X-Api-Key": "plainOPAQUEvalue123"},
    {"api-key": "plainOPAQUEvalue123"}, {"api_key": "plainOPAQUEvalue123"},
    {"apikey": "plainOPAQUEvalue123"}, {"token": "plainOPAQUEvalue123"},
    {"access_token": "plainOPAQUEvalue123"}, {"refresh-token": "plainOPAQUEvalue123"},
    {"client_secret": "plainOPAQUEvalue123"}, {"password": "plainOPAQUEvalue123"},
    {"Cookie": "sid=plainOPAQUEvalue123"}, {"Set-Cookie": "sid=plainOPAQUEvalue123; Path=/"},
    {"gateway_key": "plainOPAQUEvalue123"}, {"X-Auth-Token": "plainOPAQUEvalue123"},
    {"deep": [{"inner": {"API_KEY": "plainOPAQUEvalue123"}}]},
    {"token": {"value": "plainOPAQUEvalue123", "n": 12345678901}},
    {"headers": [["x-api-key", "plainOPAQUEvalue123"]]},
    {"headers": [("Authorization", "Bearer plainOPAQUEvalue123")]},
])
def test_a_value_under_a_credential_name_is_masked_whole(raw):
    """No key is held and the value has no credential shape: its field name is what says it
    is one, at any depth, in any letter case, as a dict entry or a [name, value] pair."""
    out = evidence_raw(raw)
    assert "OPAQUE" not in json.dumps(out), out
    assert out.get("redacted") is True or out.get("dropped_fields"), out   # never silent


def test_counts_and_probabilities_under_ordinary_names_are_kept():
    raw = {"usage": {"input_tokens": 625, "output_tokens": 48, "max_tokens": 4096,
                     "prompt_tokens_details": {"cached_tokens": 0}},
           "probabilities": {"terminate_account": 1, "token": 0.0, "password_reset": 0.0},
           "answer": {"choice": "terminate_account"}}
    assert evidence_raw(raw) == raw


def test_masked_field_names_never_merge_entries():
    raw = {"probabilities": {"sk-aaaaaaaa1": 0.4, "sk-aaaaaaaa2": 0.6}}
    out = evidence_raw(raw)["probabilities"]
    assert len(out) == 2 and sorted(out.values()) == [0.4, 0.6]
    assert "aaaaaaaa" not in json.dumps(out)


@pytest.mark.parametrize("text", [
    "see https%3A%2F%2Fh.test%2Fx%3Fkey%3DplainOPAQUEvalue123 now",
    "see https%253A%252F%252Fh.test%252Fx%253Fkey%253DplainOPAQUEvalue123 now",   # twice
    "see https%3A%2F%2Fuser%3AplainOPAQUEvalue123%40h.test%2Fx now",
    "hdr Authorization%3A%20Bearer%20plainOPAQUEvalue123 end",
])
def test_percent_encoded_shapes_are_decoded_before_they_are_scanned(text):
    out = evidence_raw({"text": text})
    assert "OPAQUE" not in out["text"] and out["redacted"] is True, out
    assert out["text"].split()[0] == text.split()[0] and out["text"].split()[-1] == \
        text.split()[-1]                                  # the words around it are kept


def test_a_long_reply_is_never_cut_and_reparses_the_same():
    """A reply over 64,000 characters: masking keeps every character it does not mask, so
    the stored text gives the decision, confidence and cost the judge recorded."""
    reasoning = "Thinking about it. " * 3400                     # ~64,600 characters
    text = (reasoning + f"(key {HELD}) "
            + '{"answers": {"category": {"decision": "spam", "confidence": 0.9}}}')
    assert len(text) > 64_000
    before = llm.parse_reply(text, [CATEGORY])["category"]
    raw = {"text": text, "usage": {"input_tokens": 9, "output_tokens": 70_000}}
    out = evidence_raw(raw, HELD)
    after = llm.parse_reply(out["text"], [CATEGORY])["category"]
    assert after == before and before[:2] == ("spam", 0.9)
    assert out["usage"] == raw["usage"] and "[cut]" not in out["text"]
    assert _clean(out, HELD) and len(out["text"]) == len(text) - len(HELD) + 3


# --- the hosted decision APIs: a 200 reply that echoes the credentials ----------------------

class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _wire(monkeypatch, reply: dict):
    monkeypatch.setattr(OPENER, "open",
                        lambda req, timeout=0: _Resp(json.dumps(reply).encode()))


def test_decisions_reply_echoing_the_key_is_masked_in_raw(monkeypatch):
    _wire(monkeypatch, {
        "id": f"dec_{HELD}", "model": f"https://user:{HELD}@gw.test/v1?key={HELD}",
        "usage": {"input_tokens": 10, "note": f"Authorization: Bearer {HELD}"},
        "answers": [{"type": "choice", "name": "route", "choice": "billing",
                     "confidence": 0.9, "echo": f"x-api-key: {HELD}",
                     "probabilities": [{"value": "billing", "probability": 0.9},
                                       {"value": "returns", "probability": 0.1},
                                       {"value": "other", "probability": 0.0}]}]})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert (j.decision, j.confidence) == ("billing", 0.9)        # read before masking
    assert _clean(j.raw, HELD) and j.raw["redacted"] is True, j.raw


def test_decisions_refusal_echoing_the_key_is_masked_in_raw(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "refusal", "name": "route",
                                     "message": f"refused for key {HELD}"}]})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and _clean(j.raw, HELD)
    assert "answer.message" in j.raw["dropped_fields"]["names"]          # left out, not kept masked


def test_decisions_clean_reply_is_stored_as_before(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "choice", "name": "route", "choice": "billing",
                                     "confidence": 0.9,
                                     "probabilities": [{"value": "billing", "probability": 1.0}]
                                     }], "model": "gpt-6-luna", "id": "dec_1"})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert "redacted" not in j.raw and j.raw["response_id"] == "dec_1"


def test_clef_answer_echoing_token_and_account_is_masked_in_raw(monkeypatch):
    _wire(monkeypatch, {"success": True, "result": {
        "model": f"/client/v4/accounts/{ACCOUNT}/ai/run",
        "answers": {"route": {"error": f"token {HELD} not valid for account {ACCOUNT}"}}}})
    judge = hosted.ClefHostedJudge(token=HELD, account=ACCOUNT)
    (j,) = judge.decide("x", [ROUTE])
    assert j.parse_status == "no_answer"
    assert _clean(j.raw, HELD, ACCOUNT) and j.raw["redacted"] is True, j.raw


# --- Jev: the direct API and the gateway bridge ----------------------------------------------

class _Echo(BaseHTTPRequestHandler):
    """A Jev-compatible server whose 200 reply repeats the Authorization header it got."""

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        auth = self.headers.get("Authorization") or ""
        reply = {"model": f"jev ({auth})", "answers": {"route": {
            "type": "choice", "choice": "billing", "confidence": 0.5, "seen": auth,
            "probabilities": {"billing": 0.8, "returns": 0.2}}},
            "usage": {"input_tokens": 5, "auth": auth}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def echo_server():
    srv = HTTPServer(("127.0.0.1", 0), _Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1/systemone"
    srv.shutdown()


def test_jev_direct_reply_echoing_the_header_is_masked_in_raw(echo_server, monkeypatch):
    monkeypatch.setenv("JEV_ENDPOINT", echo_server)
    (j,) = jev.JevJudge(api_key=HELD, backend="typesafe").decide("x", [ROUTE])
    assert (j.decision, j.confidence) == ("billing", 0.8)
    assert _clean(j.raw, HELD), j.raw
    assert j.raw["model"] == "<unrecognised>" and j.raw["dropped_fields"]["count"] >= 2


def test_jev_gateway_reply_echoing_the_key_is_masked_in_raw(monkeypatch):
    judge = jev.JevJudge.__new__(jev.JevJudge)       # no Node bridge needed: the run is stubbed
    judge.backend, judge.model, judge.api_key = "gateway", "typesafe-ai/jev", HELD
    out = [{"ok": True, "answers": {"route": {"probabilities": {"billing": 0.7, "other": 0.3},
                                              "echo": f"key={HELD}"}},
            "usage": {"inputTokens": 4, "gateway": f"Bearer {HELD}"}, "latencyMs": 10}]
    monkeypatch.setattr(jev, "_throttle", lambda: None)
    monkeypatch.setattr(jev.subprocess, "run", lambda *a, **k: types.SimpleNamespace(
        returncode=0, stdout=json.dumps(out).encode(), stderr=b""))
    (j,) = judge.decide("x", [ROUTE])
    assert j.decision == "billing" and _clean(j.raw, HELD)
    assert {"answer.echo", "usage.gateway"} <= set(j.raw["dropped_fields"]["names"])


# --- chat models: the OpenAI-compatible path, the custom module, the Anthropic SDK -----------

def test_openai_compatible_reply_echoing_the_key_is_masked_in_raw(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    text = ('{"answers": {"category": {"decision": "spam", "confidence": 0.9}}} '
            f"(you sent Authorization: Bearer {HELD})")
    monkeypatch.setattr(llm, "_fetch_json", lambda req, deadline: {
        "model": "m", "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    (j,) = llm.LLMJudge(api_key=HELD).decide("x", [CATEGORY])
    assert (j.decision, j.confidence) == ("spam", 0.9)
    assert _clean(j.raw, HELD) and j.raw["redacted"] is True, j.raw
    # what is kept still re-parses to the same decision
    assert llm.parse_reply(j.raw["text"], [CATEGORY])["category"][:2] == ("spam", 0.9)


def test_self_consistency_samples_echoing_the_key_are_masked(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_TEMPERATURE", "1")
    monkeypatch.setenv("LLM_SAMPLES", "2")
    text = f'{{"answers": {{"category": {{"decision": "spam", "confidence": 0.9}}}}}} {HELD}'
    monkeypatch.setattr(llm, "_fetch_json", lambda req, deadline: {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    (j,) = llm.LLMJudge(api_key=HELD).decide("x", [CATEGORY])
    assert j.decision == "spam" and _clean(j.raw, HELD) and j.raw["redacted"] is True


CUSTOM = '''
import os
def call(model, system, user, temperature=None):
    key = os.environ["SOME_PROVIDER_TOKEN"]
    text = '{"answers": {"category": {"decision": "spam", "confidence": 0.7}}} sig=' + key
    return text, 4, 2, {"model": "urn:example:svc:zone-1:123456789012:profile/m-x"}
def describe(model):
    return {"provider": "hosted-api",
            "route": "https://u:" + os.environ["SOME_PROVIDER_TOKEN"] + "@gw.test/x"}
def price(model):
    return (1.0, 2.0)
'''


def _custom(monkeypatch, tmp_path):
    mod = tmp_path / "provider.py"
    mod.write_text(CUSTOM)
    monkeypatch.setenv("SOME_PROVIDER_TOKEN", ENV)
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m-x")
    return mod


def test_custom_provider_reply_and_served_id_are_masked_in_raw(monkeypatch, tmp_path):
    _custom(monkeypatch, tmp_path)
    (j,) = llm.LLMJudge().decide("x", [CATEGORY])
    assert j.decision == "spam" and _clean(j.raw, ENV) and j.raw["redacted"] is True
    assert "123456789012" not in json.dumps(j.raw)


def test_the_run_header_masks_what_describe_carries(monkeypatch, tmp_path):
    from judge_audit.runner import run_metadata
    _custom(monkeypatch, tmp_path)
    meta = run_metadata(llm.LLMJudge())
    assert _clean(meta, ENV) and meta["judge"]["provider"] == "hosted-api"


class _Leaky(Judge):
    """Any adapter: one that does not mask its own raw."""
    name = "leaky"

    def decide(self, state, questions):
        return [Judgment(question=q.name, decision="spam", confidence=0.9,
                         raw={"text": f"token={ENV}", "served": {"model": None}})
                for q in questions]


ROW = {"state": "x", "questions": [{"name": "category", "type": "choice",
                                    "instructions": "classify", "options": ["spam", "order"]}],
       "labels": {"category": "spam"}}


def test_the_runner_masks_raw_whatever_the_adapter(monkeypatch):
    from judge_audit.runner import run_audit
    monkeypatch.setenv("SOME_PROVIDER_TOKEN", ENV)
    result = run_audit(_Leaky(), [ROW], ci=False)
    (rec,) = result.records
    assert rec["correct"] and _clean(rec, ENV) and rec["raw"]["redacted"] is True


def test_the_checkpoint_row_masks_raw_whatever_the_adapter(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_resumable
    monkeypatch.setenv("SOME_PROVIDER_TOKEN", ENV)
    rec = audit_resumable.checkpoint_row(0, ROW, _Leaky().decide("x", [CATEGORY]))
    assert _clean(rec, ENV) and rec["judgments"][0]["raw"]["redacted"] is True


def test_a_resumable_checkpoint_never_holds_the_key(monkeypatch, tmp_path):
    """End to end: a provider module that echoes its token in every reply, in the id of what
    it served and in describe(); the checkpoint, report and result JSON hold none of it."""
    mod = tmp_path / "provider.py"
    mod.write_text(CUSTOM)
    labels = tmp_path / "labels.jsonl"
    labels.write_text("".join(LABELS.read_text(encoding="utf-8").splitlines(True)[:3]),
                      encoding="utf-8")
    env = {k: v for k, v in __import__("os").environ.items()
           if not k.startswith(("LLM_", "ANTHROPIC_", "OPENAI_"))}
    env.update({"SOME_PROVIDER_TOKEN": ENV, "LLM_PROVIDER": "custom",
                "LLM_PROVIDER_MODULE": str(mod), "LLM_MODEL": "m-x",
                "JUDGE_AUDIT_BOOTSTRAP": "0"})
    ckpt, out, js = tmp_path / "c.ckpt.jsonl", tmp_path / "r.md", tmp_path / "r.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), str(labels), "--judge", "llm",
                           "--checkpoint", str(ckpt), "--out", str(out), "--json", str(js)],
                          cwd=tmp_path, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    for f in (ckpt, out, js):
        text = f.read_text(encoding="utf-8")
        assert not _runs(ENV, text) and "123456789012" not in text, f.name
    rows = [json.loads(line) for line in ckpt.read_text(encoding="utf-8").splitlines()]
    assert all(j["raw"]["redacted"] for r in rows[1:] for j in r["judgments"])


# --- the Anthropic SDK: temperature reaches the model on every SDK the extra allows ----------

def _sdk(monkeypatch, takes_temperature: bool, sent: list, text: str = "", version="1.8.0"):
    """A stub `anthropic` module whose `messages.create` has an explicit signature, as the
    real one does: with `temperature` (SDK 0.x) or without it (SDK 1.0 onward)."""
    reply = types.SimpleNamespace(
        stop_reason="end_turn", model="claude-sonnet-4-5",
        content=[types.SimpleNamespace(type="text", text=text or json.dumps(
            {"answers": {"category": {"decision": "spam", "confidence": 0.8}}}))],
        usage=types.SimpleNamespace(input_tokens=1, output_tokens=1))

    if takes_temperature:
        def create(*, max_tokens, messages, model, system=None, temperature=None,
                   extra_body=None):
            sent.append({"temperature": temperature, "extra_body": extra_body})
            return reply
    else:
        def create(*, max_tokens, messages, model, system=None, output_config=None,
                   extra_body=None):
            sent.append({"extra_body": extra_body})
            return reply

    class APIStatusError(Exception):
        pass

    class Anthropic:
        def __init__(self, **kw):
            self.messages = types.SimpleNamespace(create=create)

    mod = types.SimpleNamespace(Anthropic=Anthropic, APIStatusError=APIStatusError,
                                RateLimitError=APIStatusError, __version__=version,
                                DefaultHttpxClient=lambda **kw: object())
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-4.5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", HELD)


def test_an_sdk_without_the_temperature_keyword_still_sends_t0(monkeypatch):
    """SDK 1.x has no `temperature` in `messages.create`: passing it raised TypeError."""
    sent: list = []
    _sdk(monkeypatch, takes_temperature=False, sent=sent)
    (j,) = llm.LLMJudge().decide("x", [CATEGORY])
    assert j.decision == "spam" and sent == [{"extra_body": {"temperature": 0}}]
    d = llm.LLMJudge().describe()
    assert d["temperature"] == 0 and d["temperature_sent_as"] == "extra_body"
    assert d["sdk"] == "anthropic 1.8.0"


def test_an_sdk_with_the_temperature_keyword_gets_it_as_a_keyword(monkeypatch):
    sent: list = []
    _sdk(monkeypatch, takes_temperature=True, sent=sent, version="0.125.0")
    llm.LLMJudge().decide("x", [CATEGORY])
    assert sent == [{"temperature": 0, "extra_body": None}]
    d = llm.LLMJudge().describe()
    assert d["temperature_sent_as"] == "keyword" and d["sdk"] == "anthropic 0.125.0"


def test_the_provider_default_temperature_sends_none(monkeypatch):
    sent: list = []
    _sdk(monkeypatch, takes_temperature=False, sent=sent)
    monkeypatch.setenv("LLM_TEMPERATURE", "default")
    llm.LLMJudge().decide("x", [CATEGORY])
    assert sent == [{"extra_body": None}]
    assert "temperature_sent_as" not in llm.LLMJudge().describe()


def test_the_sdk_version_reaches_the_run_header(monkeypatch):
    from judge_audit.runner import run_metadata
    _sdk(monkeypatch, takes_temperature=False, sent=[])
    judge = run_metadata(llm.LLMJudge())["judge"]
    assert judge["sdk"] == "anthropic 1.8.0" and judge["temperature_sent_as"] == "extra_body"
    assert _clean(judge, HELD)


def test_an_anthropic_reply_echoing_the_key_is_masked_in_raw(monkeypatch):
    sent: list = []
    text = ('{"answers": {"category": {"decision": "spam", "confidence": 0.8}}} '
            f"x-api-key: {HELD}")
    _sdk(monkeypatch, takes_temperature=False, sent=sent, text=text)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    (j,) = llm.LLMJudge(api_key=HELD).decide("x", [CATEGORY])
    assert j.decision == "spam" and _clean(j.raw, HELD) and j.raw["redacted"] is True


# --- deny by default: an adapter keeps only the fields the audit reads (#161, round 2) -------

TOK = "plainOPAQUEvalue123"


def test_decisions_keeps_only_the_fields_the_audit_reads(monkeypatch):
    _wire(monkeypatch, {
        "id": "dec_1", "model": "gpt-6-luna", "headers": {"Authorization": TOK},
        "usage": {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 2},
                  "service_tier": TOK},
        "answers": [{"type": "choice", "name": "route", "choice": "billing", "confidence": 0.9,
                     "debug": {"headers": [{"name": "x-api-key", "value": TOK}]},
                     "trace": TOK,
                     "probabilities": [{"value": "billing", "probability": 0.9, "note": TOK},
                                       {"value": "returns", "probability": 0.1}]}]})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert (j.decision, j.confidence) == ("billing", 0.9)
    assert "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["usage"] == {"input_tokens": 10, "input_tokens_details": {"cached_tokens": 2}}
    assert j.raw["native_confidence"] == 0.9 and j.raw["served"]["model"] == "gpt-6-luna"
    assert {"answer.debug", "answer.trace", "answer.probabilities.note",
            "usage.service_tier"} <= set(j.raw["dropped_fields"]["names"])


def test_clef_keeps_only_the_fields_the_audit_reads(monkeypatch):
    _wire(monkeypatch, {"success": True, "result": {
        "model": "clef-flash", "usage": {"input_tokens": 3, "request": TOK},
        "answers": {"route": {"choice": "billing", "confidence": 0.7, "meta": {"cookie": TOK},
                              "probabilities": {"billing": 0.8, "returns": 0.2}}}}})
    (j,) = hosted.ClefHostedJudge(token=HELD, account=ACCOUNT).decide("x", [ROUTE])
    assert j.decision == "billing" and "OPAQUE" not in json.dumps(j.raw)
    assert j.raw["answer"]["probabilities"] == {"billing": 0.8, "returns": 0.2}
    assert {"answer.meta", "usage.request"} <= set(j.raw["dropped_fields"]["names"])


def test_a_clean_reply_drops_nothing(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "choice", "name": "route", "choice": "billing",
                                     "confidence": 0.9,
                                     "probabilities": [{"value": "billing", "probability": 1.0}]
                                     }], "usage": {"input_tokens": 4}})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert "dropped_fields" not in j.raw and "redacted" not in j.raw


def test_jev_gateway_keeps_only_the_fields_the_audit_reads(monkeypatch):
    judge = jev.JevJudge.__new__(jev.JevJudge)
    judge.backend, judge.model, judge.api_key = "gateway", "typesafe-ai/jev", HELD
    out = [{"ok": True, "answers": {"route": {"probabilities": {"billing": 0.7, "other": 0.3},
                                              "rawResponse": {"headers": {"x-api-key": TOK}}}},
            "usage": {"inputTokens": 4, "gateway": {"routing": TOK}}, "latencyMs": 10}]
    monkeypatch.setattr(jev, "_throttle", lambda: None)
    monkeypatch.setattr(jev.subprocess, "run", lambda *a, **k: types.SimpleNamespace(
        returncode=0, stdout=json.dumps(out).encode(), stderr=b""))
    (j,) = judge.decide("x", [ROUTE])
    assert j.decision == "billing" and "OPAQUE" not in json.dumps(j.raw)
    assert j.raw["usage"] == {"inputTokens": 4}
    assert {"answer.<opaque>", "usage.gateway"} <= set(j.raw["dropped_fields"]["names"])


def test_jev_direct_keeps_only_the_fields_the_audit_reads(echo_server, monkeypatch):
    monkeypatch.setenv("JEV_ENDPOINT", echo_server)
    (j,) = jev.JevJudge(api_key=HELD, backend="typesafe").decide("x", [ROUTE])
    assert "seen" not in j.raw["answer"] and "auth" not in j.raw["usage"]
    assert {"answer.seen", "usage.auth"} <= set(j.raw["dropped_fields"]["names"])


def test_a_custom_module_cannot_put_more_than_the_served_version_in_raw(monkeypatch, tmp_path):
    mod = tmp_path / "p.py"
    mod.write_text("def call(model, system, user, temperature=None):\n"
                   "    return ('{\"answers\": {\"category\": {\"decision\": \"spam\", "
                   "\"confidence\": 0.7}}}', 1, 1, {\"model\": \"m-1\", \"headers\": "
                   f"{{\"Authorization\": \"{TOK}\"}}}})\n")
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m")
    (j,) = llm.LLMJudge().decide("x", [CATEGORY])
    assert set(j.raw) == {"text", "usage", "parsed", "priced", "served"}
    assert "OPAQUE" not in json.dumps(j.raw)


# --- the second layer: headers at any depth, name/value pairs, text shapes ------------------

@pytest.mark.parametrize("raw", [
    {"headers": [{"name": "Authorization", "value": TOK}]},
    {"headers": [{"key": "x-api-key", "value": TOK}]},
    {"headers": [{"header": "X-Auth-Token", "value": TOK}]},
    {"headers": [["x-api-key", TOK]]},
    {"headers": {"Authorization": TOK, "Content-Type": "application/json"}},
    {"deep": [{"response": {"response_headers": [{"name": "Set-Cookie", "value": TOK}]}}]},
    {"list": ["x-api-key", TOK, "accept", "json"]}, {"list": ["x-api-key", TOK, "x"]},
    {"pair": {"name": "Authorization", "value": TOK}},
    {"field": {"key": "x-api-key", "value": TOK}},
])
def test_header_lists_in_every_form_and_depth_hold_no_credential(raw):
    out = evidence_raw(raw)
    assert "OPAQUE" not in json.dumps(out), out


def test_only_harmless_headers_are_kept_and_the_rest_is_recorded():
    raw = {"response": {"headers": {"Content-Type": "application/json", "Authorization": TOK,
                                    "X-Request-Id": "r-1"}}}
    out = evidence_raw(raw)
    assert out["response"]["headers"] == {"Content-Type": "application/json"}
    assert {"response.headers.authorization", "response.headers.x_request_id"} <= \
        set(out["dropped_fields"]["names"]) and out["dropped_fields"]["count"] == 2


def test_a_name_value_pair_keeps_its_name():
    out = evidence_raw({"field": {"key": "x-api-key", "value": TOK}})
    assert out["field"] == {"key": "x-api-key", "value": "***"}


@pytest.mark.parametrize("text", [
    f'{{"token": "{TOK}"}}', f'{{"Vendor-Subscription-Key": "{TOK}"}}',
    f"X-Auth-Token: {TOK}", f"Cookie: session={TOK}; theme=dark", f"set-cookie: sid={TOK}",
    f"Authorization: Token {TOK}",
])
def test_credential_names_in_text_mask_their_value(text):
    assert "OPAQUE" not in evidence_raw({"text": text})["text"]


@pytest.mark.parametrize("raw", [
    {"x.api.key": TOK}, {"api key": TOK}, {"Authorization:": TOK}, {"session_id": TOK},
    {"sig": TOK}, {"jwt": TOK}, {"acct": "123456789012"}, {"account": 123456789012.0},
])
def test_more_credential_and_account_names(raw):
    assert "OPAQUE" not in json.dumps(evidence_raw(raw))
    assert "123456789012" not in json.dumps(evidence_raw(raw))


def test_text_encoded_three_times_is_scanned():
    from urllib.parse import quote
    url = f"https://h.test/x?key={TOK}"
    text = "see " + quote(quote(quote(url, safe=""), safe=""), safe="") + " now"
    assert "OPAQUE" not in evidence_raw({"text": text})["text"]


@pytest.mark.parametrize("text", [
    "svc:zone-1:123456789012:profile/x", "p1:svc:zone-1:123456789012:model/x",
    "longschemename:p:svc:zone-1:123456789012:x", "account 123456789012",
    "acct no. 1234-5678-9012",
])
def test_partial_resource_ids_and_plain_text_accounts_are_masked(text):
    out = evidence_raw({"text": f"from {text}."})["text"]
    assert "123456789012" not in out and "5678" not in out and "zone-1" not in out, out


# --- typed evidence: a kept value has the type and shape the audit expects (#161, round 3) ----

OPAQUE_NAME = "Zq9OPAQUEname77"          # a provider field name that is itself a token


def test_a_dropped_name_that_is_not_a_plain_word_is_recorded_as_opaque(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "choice", "name": "route", "choice": "billing",
                                     "confidence": 0.9, OPAQUE_NAME: 1, "trace_id": "t",
                                     "probabilities": [{"value": "billing", "probability": 1.0}]
                                     }], "usage": {"input_tokens": 5, OPAQUE_NAME: 1}})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["usage"] == {"input_tokens": 5}
    names = j.raw["dropped_fields"]["names"]
    assert "answer.<opaque>" in names and "answer.trace_id" in names
    assert j.raw["dropped_fields"]["count"] == 3


def test_probability_keys_are_only_the_options_that_were_sent(monkeypatch):
    _wire(monkeypatch, {"success": True, "result": {"answers": {"route": {
        "choice": "billing", "probabilities": {"billing": 0.8, TOK: 0.2}}}}})
    (j,) = hosted.ClefHostedJudge(token=HELD, account=ACCOUNT).decide("x", [ROUTE])
    assert j.decision == "billing" and j.confidence == 0.8
    assert "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["answer"]["probabilities"] == {"billing": 0.8}
    assert j.raw["probabilities"] == {"billing": 0.8}


def test_an_unknown_probability_row_is_dropped_whole(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "choice", "name": "route", "choice": "billing",
                                     "confidence": TOK, "score": TOK, "refusal": TOK,
                                     "probabilities": [{"value": "billing", "probability": 0.9},
                                                       {"value": TOK, "label": TOK,
                                                        "probability": 0.1}]}]})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["answer"]["probabilities"] == [{"value": "billing", "probability": 0.9}]


@pytest.mark.parametrize("error, kept", [
    ({"detail": {"upstream": TOK}}, "<unrecognised>"),
    ({"code": "max_length_exceeded", "message": TOK, "status": 413},
     {"code": "max_length_exceeded", "status": 413}),
    ("max_length_exceeded", "max_length_exceeded"),
    (f"failed: {TOK}", "<unrecognised>"),
])
def test_an_error_keeps_only_a_code_and_a_status(monkeypatch, error, kept):
    _wire(monkeypatch, {"success": True, "result": {"answers": {"route": {"error": error}}}})
    (j,) = hosted.ClefHostedJudge(token=HELD, account=ACCOUNT).decide("x", [ROUTE])
    assert j.parse_status == "no_answer" and j.raw["answer"]["error"] == kept
    assert "OPAQUE" not in json.dumps(j.raw)


class _Shaped(BaseHTTPRequestHandler):
    """A Jev-compatible server whose answer's `confidence` is an object."""

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        reply = {"model": {"route": TOK}, "answers": {"route": {
            "type": "choice", "choice": "billing", "confidence": {"upstream": TOK},
            "probabilities": {"billing": 0.8, "returns": 0.2}}}, "usage": {"input_tokens": 5}}
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_jev_keeps_no_object_where_a_number_or_an_id_belongs(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), _Shaped)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("JEV_ENDPOINT", f"http://127.0.0.1:{srv.server_port}/v1/systemone")
        (j,) = jev.JevJudge(api_key=HELD, backend="typesafe").decide("x", [ROUTE])
    finally:
        srv.shutdown()
    assert j.decision == "billing" and "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["typesafe_confidence"] is None
    assert j.raw["model"] == "<unrecognised>" and j.raw["served"]["model"] == "<unrecognised>"


@pytest.mark.parametrize("reported, model, fingerprint", [
    ({"model": {"route": TOK}}, "<unrecognised>", None),
    ({"model": "m@infra-name"}, "<unrecognised>", None),
    ({"model": "m-1", "system_fingerprint": "fp=" + TOK + "=="}, "m-1", "<unrecognised>"),
    ({"model": "claude-sonnet-4-5-20250929", "system_fingerprint": "fp_abc123"},
     "claude-sonnet-4-5-20250929", "fp_abc123"),
    ({"model": "x" * 81}, "<unrecognised>", None),
])
def test_served_ids_are_short_plain_strings_or_unrecognised(reported, model, fingerprint):
    from judge_audit.judges.base import served_of
    assert served_of(reported) == {"model": model, "system_fingerprint": fingerprint}


def test_decisions_served_and_response_id_are_typed(monkeypatch):
    _wire(monkeypatch, {"model": {"route": TOK}, "id": {"x": TOK},
                        "answers": [{"type": "choice", "name": "route", "choice": "billing",
                                     "probabilities": [{"value": "billing",
                                                        "probability": 1.0}]}]})
    (j,) = hosted.OpenAIDecisionsJudge(api_key=HELD).decide("x", [ROUTE])
    assert "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["served"]["model"] == "<unrecognised>"
    assert j.raw["response_id"] == "<unrecognised>"


def test_openai_compatible_counts_that_are_not_numbers_are_unknown(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://unit.test/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setattr(llm, "_fetch_json", lambda req, deadline: {
        "model": {"route": TOK}, "system_fingerprint": TOK + "=",
        "choices": [{"message": {"content":
                                 '{"answers": {"category": {"decision": "spam", '
                                 '"confidence": 0.9}}}'}}],
        "usage": {"prompt_tokens": TOK, "completion_tokens": 2}})
    (j,) = llm.LLMJudge(api_key=HELD).decide("x", [CATEGORY])
    assert j.decision == "spam" and "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["usage"] == {"input_tokens": None, "output_tokens": 2}
    assert j.cost_usd is None or j.cost_usd == 0.0


def test_a_custom_call_cannot_put_a_token_in_usage_or_served(monkeypatch, tmp_path):
    mod = tmp_path / "p.py"
    mod.write_text("def call(model, system, user, temperature=None):\n"
                   "    return ('{\"answers\": {\"category\": {\"decision\": \"spam\", "
                   f"\\\"confidence\\\": 0.7}}}}}}', '{TOK}', 1, "
                   f"{{'model': {{'x': '{TOK}'}}}})\n")
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m")
    (j,) = llm.LLMJudge().decide("x", [CATEGORY])
    assert j.decision == "spam" and "OPAQUE" not in json.dumps(j.raw), j.raw
    assert j.raw["usage"]["input_tokens"] is None
    assert j.raw["served"]["model"] == "<unrecognised>"


def test_a_custom_describe_keeps_only_known_typed_fields(monkeypatch, tmp_path):
    from judge_audit.runner import run_metadata
    mod = tmp_path / "p.py"
    mod.write_text("def call(model, system, user, temperature=None):\n"
                   "    return '{}', 1, 1\n"
                   "def describe(model):\n"
                   f"    return {{'provider': 'hosted-api', 'route': '{TOK}', "
                   "'zone': 'zone-1', 'max_tokens': 4096, 'prices_usd_per_mtok': [3.0, 15.0], "
                   f"'model': {{'x': '{TOK}'}}}}\n")
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m")
    judge = run_metadata(llm.LLMJudge())["judge"]
    assert "OPAQUE" not in json.dumps(judge) and "zone-1" not in json.dumps(judge), judge
    assert judge["provider"] == "hosted-api" and judge["max_tokens"] == 4096
    assert judge["prices_usd_per_mtok"] == [3.0, 15.0] and judge["model"] == "m"
    assert judge["dropped_fields"]["count"] == 3


# --- an option that was never sent: wrong, at the confidence declared (#161, round 4) ---------

def _unsent_rows():
    return [{"state": "x", "questions": [{"name": "route", "type": "choice",
                                          "instructions": "Which team?",
                                          "options": ["billing", "returns", "other"]}],
             "labels": {"route": "billing"}}]


def _assert_wrong_at_097(judge):
    """Scored as `llm`, Jev and the local judges score it: an answer, wrong, keeping the
    confidence the judge declared, so it counts in calibration and in the high-confidence
    error rate. The invented label is never stored."""
    from judge_audit.runner import run_audit
    result = run_audit(judge, _unsent_rows(), ci=False)
    (rec,) = result.records
    assert rec["decision"] == "<unsent_option>" and rec["correct"] is False
    assert rec["confidence"] == 0.97 and rec["parse_status"] == "parsed"
    assert rec["raw"]["invalid"] == "chosen option is not among the options sent"
    assert "refunds" not in json.dumps(rec)
    levels = {x["confidence_at_least"]: x
              for x in result.to_dict()["high_confidence_error"]["levels"]}
    assert levels[0.95]["n"] == 1 and levels[0.95]["errors"] == 1, levels


def test_decisions_an_unsent_option_is_wrong_at_its_confidence(monkeypatch):
    _wire(monkeypatch, {"answers": [{"type": "choice", "name": "route", "choice": "refunds",
                                     "confidence": 0.97,
                                     "probabilities": [{"value": "refunds", "probability": 0.97},
                                                       {"value": "billing",
                                                        "probability": 0.03}]}]})
    _assert_wrong_at_097(hosted.OpenAIDecisionsJudge(api_key=HELD))


def test_clef_an_unsent_option_is_wrong_at_its_confidence(monkeypatch):
    _wire(monkeypatch, {"success": True, "result": {"answers": {"route": {
        "choice": "refunds", "probabilities": {"refunds": 0.97, "billing": 0.03}}}}})
    _assert_wrong_at_097(hosted.ClefHostedJudge(token=HELD, account=ACCOUNT))
