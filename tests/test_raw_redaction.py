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


def test_an_account_number_inside_a_resource_identifier_is_masked():
    rid = "urn:example:svc:zone-1:123456789012:profile/model-x"
    out = redact_evidence({"served": {"model": rid}})
    assert "123456789012" not in json.dumps(out) and "profile/model-x" in json.dumps(out)


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
    assert j.parse_status == "no_answer" and _clean(j.raw, HELD) and j.raw["redacted"]


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
    assert _clean(j.raw, HELD) and j.raw["redacted"] is True, j.raw


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
    assert j.decision == "billing" and _clean(j.raw, HELD) and j.raw["redacted"] is True


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
