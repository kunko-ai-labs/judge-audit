"""No judge lets a credential out: a server that echoes the key (or any bearer token, `sk-`
key, `key=` value or account id) in an error body never gets it printed, checkpointed or
recorded. Endpoint overrides only go to https, or to this computer. No outside host is
called: a local server stands in for each API."""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from judge_audit import cli
from judge_audit.judges.base import redact

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"
KEY = "sk-proj-Z9yX8wV7uT6sR5qP4oN3mL2kJ1iH0gF"       # the shape of a real key; not one
ACCOUNT = "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"


# --- the shared scrubber, by hand ------------------------------------------------------------

@pytest.mark.parametrize("text, gone", [
    (f"bad key {KEY}", KEY),
    ("Authorization: Bearer abc.def-ghi_123", "abc.def-ghi_123"),
    ("header was 'Bearer tok_live_0123456789'", "tok_live_0123456789"),
    ("Incorrect API key provided: sk-ant-api03-AbCdEf0123456789xyz",
     "sk-ant-api03-AbCdEf0123456789xyz"),
    ("GET /v1/x?key=AIzaSyA-0123456789abcdefghij&alt=json", "AIzaSyA-0123456789abcdefghij"),
    ("?api_key=s3cr3tvalue1234", "s3cr3tvalue1234"),
    (f"POST /client/v4/accounts/{ACCOUNT}/ai/run", ACCOUNT),
])
def test_redact_removes_every_secret_shape(text, gone):
    out = redact(text)
    assert gone not in out and "***" in out, out


def test_redact_removes_a_literal_secret_of_any_shape():
    assert "plainpassword42" not in redact("rejected plainpassword42 here", "plainpassword42")


@pytest.mark.parametrize("text", ["status 401: unauthorized", "row 3 of 200",
                                  "sent to that host as a bearer token.",
                                  "model gpt-6-luna", "https://api.example.test/v1/decisions"])
def test_redact_leaves_ordinary_text_alone(text):
    assert redact(text) == text


# --- each judge family, against a server that echoes the key --------------------------------

@pytest.fixture
def echo():
    """A local server whose error body repeats the Authorization header it received."""
    state = {"status": 401}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            sent = self.headers.get("Authorization", "")
            body = (state["body"].encode() if "body" in state else
                    json.dumps({"error": {"message": f"Incorrect API key provided: {sent} "
                                                    f"({sent.removeprefix('Bearer ')}) for "
                                                    f"/accounts/{ACCOUNT}/x"}}).encode())
            self.send_response(state["status"])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


FAMILIES = {
    "jev": lambda u: {"JEV_BACKEND": "typesafe", "TYPESAFE_API_KEY": KEY,
                      "JEV_ENDPOINT": f"{u}/v1/systemone", "JEV_MIN_INTERVAL_S": "0"},
    "llm": lambda u: {"LLM_PROVIDER": "openai-compatible", "LLM_BASE_URL": f"{u}/v1",
                      "LLM_MODEL": "gpt-5-mini", "LLM_API_KEY": KEY},
    "openai-decisions": lambda u: {"OPENAI_API_KEY": KEY,
                                   "DECISIONS_ENDPOINT": f"{u}/v1/decisions"},
    "clef-hosted": lambda u: {"CLOUDFLARE_API_TOKEN": KEY, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
                              "CLEF_HOSTED_ENDPOINT": f"{u}/ai/run/{{model_id}}"},
}


def _leaks(text: str) -> list[str]:
    return [s for s in (KEY, ACCOUNT, f"Bearer {KEY}") if s in text]


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("status", [401, 403, 500])
def test_a_server_echoing_the_key_never_gets_it_printed(echo, monkeypatch, capsys, tmp_path,
                                                         family, status):
    echo["status"] = status
    for k, v in FAMILIES[family](echo["url"]).items():
        monkeypatch.setenv(k, v)
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", family, "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                  "--judgments", str(tmp_path / "j.jsonl")])
    out = capsys.readouterr()
    assert e.value.code == 2
    assert not _leaks(out.out + out.err), _leaks(out.out + out.err)
    for f in tmp_path.iterdir():
        assert not _leaks(f.read_text(encoding="utf-8", errors="replace")), f.name


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_the_checkpointed_driver_never_writes_or_prints_the_key(echo, tmp_path, family):
    echo["status"] = 401
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), **FAMILIES[family](echo["url"])}
    ckpt = tmp_path / "x.ckpt.jsonl"
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_resumable.py"),
                          str(LABELS), "--judge", family, "--checkpoint", str(ckpt),
                          "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")],
                         capture_output=True, text=True, env=env, cwd=tmp_path)
    assert out.returncode == 2, out.stderr
    assert not _leaks(out.stdout + out.stderr), out.stderr
    for f in tmp_path.iterdir():
        assert not _leaks(f.read_text(encoding="utf-8", errors="replace")), f.name


def test_the_jev_gateway_bridge_error_never_prints_the_key(monkeypatch):
    """The Node bridge's stderr can repeat the key; it is masked before it leaves the
    adapter."""
    from judge_audit.judges import jev
    monkeypatch.setenv("AI_GATEWAY_API_KEY", KEY)
    monkeypatch.setattr(jev, "_BRIDGE", Path(__file__))                  # exists
    monkeypatch.setattr(jev.Path, "exists", lambda self: True)
    monkeypatch.setattr(jev.time, "sleep", lambda s: None)
    monkeypatch.setattr(jev, "_MIN_INTERVAL_S", 0.0)

    class Proc:
        returncode = 1
        stdout = b""
        stderr = f"Error: 401 invalid key {KEY} (Authorization: Bearer {KEY})".encode()
    monkeypatch.setattr(jev.subprocess, "run", lambda *a, **k: Proc())
    from judge_audit.judges.base import Question, QuestionType
    q = Question(name="c", type=QuestionType.CHOICE, instructions="?", options=["a", "b"])
    with pytest.raises(RuntimeError) as e:
        jev.JevJudge().decide("x", [q])
    assert not _leaks(str(e.value)), str(e.value)


# --- endpoint overrides go to https or to this computer only -------------------------------

@pytest.mark.parametrize("judge_cls, env, var", [
    ("OpenAIDecisionsJudge", {"OPENAI_API_KEY": KEY}, "DECISIONS_ENDPOINT"),
    ("ClefHostedJudge", {"CLOUDFLARE_API_TOKEN": KEY, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT},
     "CLEF_HOSTED_ENDPOINT"),
])
@pytest.mark.parametrize("url, allowed", [
    ("http://api.example.test/v1", False), ("ftp://api.example.test/v1", False),
    ("http://192.168.1.5/v1", False), ("https://proxy.example.test/v1", True),
    ("http://127.0.0.1:8080/v1", True), ("http://127.5.4.3/v1", True),
    ("http://localhost:9/v1", True), ("http://[::1]:9/v1", True),
])
def test_an_override_must_be_https_or_this_computer(monkeypatch, judge_cls, env, var, url,
                                                     allowed):
    from judge_audit.judges import hosted
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv(var, url)
    cls = getattr(hosted, judge_cls)
    if allowed:
        cls()
    else:
        with pytest.raises(ValueError, match=f"{var}.*https"):
            cls()


def test_a_plain_http_override_is_refused_by_the_cli_with_exit_2(monkeypatch, capsys,
                                                                  tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    monkeypatch.setenv("DECISIONS_ENDPOINT", "http://api.example.test/v1/decisions")
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "openai-decisions", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "https" in err and KEY not in err
    assert not any(tmp_path.iterdir())                         # refused before any request


@pytest.mark.parametrize("judge_cls, env, var, url, host", [
    ("OpenAIDecisionsJudge", {"OPENAI_API_KEY": KEY}, "DECISIONS_ENDPOINT",
     f"https://proxy.example.test:8443/v1/decisions?key={KEY}", "proxy.example.test:8443"),
    ("ClefHostedJudge", {"CLOUDFLARE_API_TOKEN": KEY, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT},
     "CLEF_HOSTED_ENDPOINT", f"https://gw.example.test/accounts/{ACCOUNT}/{{model_id}}",
     "gw.example.test"),
])
def test_an_override_is_recorded_as_its_host_only(monkeypatch, judge_cls, env, var, url, host):
    from judge_audit.judges import hosted
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv(var, url)
    d = getattr(hosted, judge_cls)().describe()
    assert d["endpoint_overridden"] is True and d["endpoint_host"] == host
    text = json.dumps(d)
    assert KEY not in text and ACCOUNT not in text and "/v1" not in text


@pytest.mark.parametrize("judge_cls, env", [
    ("OpenAIDecisionsJudge", {"OPENAI_API_KEY": KEY}),
    ("ClefHostedJudge", {"CLOUDFLARE_API_TOKEN": KEY, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT})])
def test_without_an_override_the_provenance_says_so(monkeypatch, judge_cls, env):
    from judge_audit.judges import hosted
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    for var in ("DECISIONS_ENDPOINT", "CLEF_HOSTED_ENDPOINT"):
        monkeypatch.delenv(var, raising=False)
    d = getattr(hosted, judge_cls)().describe()
    assert d["endpoint_overridden"] is False


# --- every message leaves through one scrubber, local judges included ----------------------

HF = "hf_AbCdEfGhIjKlMnOpQrStUvWxYz0123"


@pytest.mark.parametrize("judge", ["decision2", "laya", "decider", "strands", "clef", "nli",
                                   "finetuned", "logprob"])
def test_a_local_judge_error_carrying_a_token_is_masked(monkeypatch, capsys, tmp_path, judge):
    """A gated download fails with the Hub token in its text: it never reaches the screen."""
    monkeypatch.setenv("HF_TOKEN", HF)

    class Boom:
        name = judge

        def describe(self):
            return {"name": judge}

        def decide(self, state, questions):
            raise RuntimeError(f"401 for url https://huggingface.co/x?token={HF} "
                               f"(Authorization: Bearer {HF}) using {HF}")
    monkeypatch.setattr(cli, "_judge", lambda name, rows: (Boom(), ""))
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", judge, "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                  "--judgments", str(tmp_path / "j.jsonl")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and HF not in err, err


def test_a_judge_that_cannot_be_built_never_prints_the_key(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)

    def bad(name, rows):
        raise RuntimeError(f"rejected credential {KEY}")
    monkeypatch.setattr(cli, "_judge", bad)
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "openai-decisions", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "not configured" in err and KEY not in err, err


def test_an_mcp_error_never_returns_the_key(monkeypatch):
    from judge_audit import mcp_server
    monkeypatch.setenv("LLM_API_KEY", KEY)

    def bad(name, rows):
        raise RuntimeError(f"bad key {KEY}")
    monkeypatch.setattr(mcp_server, "_judge", bad)
    out = mcp_server.run_audit(str(LABELS), judge="llm")
    assert "error" in out and KEY not in json.dumps(out), out


def test_scrub_masks_the_value_of_every_credential_variable(monkeypatch):
    from judge_audit.runner import scrub
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaPlainValueNoShape0123")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acctplainvalue42")
    out = scrub("failed with AIzaPlainValueNoShape0123 on acctplainvalue42")
    assert "AIzaPlainValueNoShape0123" not in out and "acctplainvalue42" not in out


def test_settings_that_are_not_credentials_are_not_masked(monkeypatch):
    from judge_audit.judges.base import credential_values
    monkeypatch.setenv("LLM_MAX_TOKENS", "1024")             # a budget, not a token
    monkeypatch.setenv("SOME_KEY", "abc")                    # too short to mask safely
    assert "1024" not in credential_values()
    assert redact("budget 1024, value abc") == "budget 1024, value abc"


def test_the_jev_gateway_reply_error_field_never_prints_the_key(monkeypatch):
    """The bridge exits 0 but its reply says ok: false with an error that repeats the key."""
    from judge_audit.judges import jev
    monkeypatch.setenv("AI_GATEWAY_API_KEY", KEY)
    monkeypatch.setattr(jev, "_BRIDGE", Path(__file__))
    monkeypatch.setattr(jev.Path, "exists", lambda self: True)
    monkeypatch.setattr(jev.time, "sleep", lambda s: None)
    monkeypatch.setattr(jev, "_MIN_INTERVAL_S", 0.0)

    class Proc:
        returncode = 0
        stderr = b""
        stdout = json.dumps([{"ok": False, "error": f"Unauthorized: key {KEY} rejected "
                                                    f"(Authorization: Bearer {KEY})"}]).encode()
    monkeypatch.setattr(jev.subprocess, "run", lambda *a, **k: Proc())
    from judge_audit.judges.base import Question, QuestionType
    q = Question(name="c", type=QuestionType.CHOICE, instructions="?", options=["a", "b"])
    with pytest.raises(RuntimeError) as e:
        jev.JevJudge().decide("x", [q])
    assert "jev evaluate error" in str(e.value) and not _leaks(str(e.value)), str(e.value)


# --- a key echoed in a disguised form, shapeless keys included ------------------------------

SHAPELESS = "Zq9fakeTOKENvalue77x"                    # no known shape; masked because it is held


def _runs(key: str, text: str) -> list[str]:
    """Every 12-character run of `key` left in `text`, in any case."""
    low = text.lower()
    return [key[i:i + 12] for i in range(len(key) - 11) if key[i:i + 12].lower() in low]


@pytest.fixture
def disguised():
    """A local server whose 401 body repeats the key it received split by a JSON-escaped
    newline, cut short and followed by `...`, and upper-cased."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            k = self.headers.get("Authorization", "").removeprefix("Bearer ")
            body = json.dumps({"error": {"message": f"invalid {k[:9]}\n{k[9:]}; "
                                                   f"got {k[:14]}...; echo {k.upper()}"}})
            data = body.encode()
            self.send_response(401)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("key", [KEY, SHAPELESS])
def test_a_key_echoed_in_a_disguised_form_never_gets_printed(disguised, monkeypatch, capsys,
                                                              tmp_path, family, key):
    for k, v in FAMILIES[family](disguised).items():
        monkeypatch.setenv(k, key if v == KEY else v)
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", family, "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    out = capsys.readouterr()
    assert e.value.code == 2
    assert len(out.err.strip().splitlines()) == 1, out.err
    assert not _runs(key, out.out + out.err), out.err


# --- a redirect is refused: the key never goes to the host it points to ----------------------

@pytest.fixture
def redirector():
    """Two local servers: the first answers every request with a 302 to the second, which
    counts what reaches it."""
    hits = {"second": 0}

    class Second(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits["second"] += 1
            self.send_response(200)
            self.end_headers()
        do_POST = do_GET  # noqa: N815

        def log_message(self, *a):
            pass

    second = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Second)
    target = f"http://127.0.0.1:{second.server_address[1]}/stolen"

    class First(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(302)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass

    first = http.server.ThreadingHTTPServer(("127.0.0.1", 0), First)
    for s in (first, second):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{first.server_address[1]}", hits
    first.shutdown()
    second.shutdown()


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_a_redirect_is_refused_and_the_key_never_follows_it(redirector, monkeypatch, capsys,
                                                             tmp_path, family):
    url, hits = redirector
    for k, v in FAMILIES[family](url).items():
        monkeypatch.setenv(k, v)
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", family, "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "redirect" in err, err
    assert hits["second"] == 0
    assert not _leaks(err), err


def test_the_logprob_smoke_script_refuses_a_redirect(redirector, monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("logprob_smoke_redirect",
                                                  ROOT / "scripts" / "logprob_smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    url, hits = redirector
    monkeypatch.setenv("LLM_API_KEY", KEY)
    code = smoke.main(["--model", "m", "--base-url", f"{url}/v1"])
    err = capsys.readouterr().err
    assert code == smoke.FAILED and "redirect" in err and KEY not in err, err
    assert hits["second"] == 0


# --- a long message is masked whole, then cut ------------------------------------------------

CUT_KEY = "sk-TESTKEY0123456789abcdef"
LONG = "y" * 400 + "Error: invalid " + CUT_KEY + " " + "z" * 275   # the last 300 keep a suffix


def test_the_jev_bridge_stderr_is_masked_before_it_is_cut(monkeypatch):
    from judge_audit.judges import jev
    monkeypatch.setenv("AI_GATEWAY_API_KEY", CUT_KEY)
    monkeypatch.setattr(jev, "_BRIDGE", Path(__file__))
    monkeypatch.setattr(jev.Path, "exists", lambda self: True)
    monkeypatch.setattr(jev.time, "sleep", lambda s: None)
    monkeypatch.setattr(jev, "_MIN_INTERVAL_S", 0.0)

    class Proc:
        returncode = 1
        stdout = b""
        stderr = LONG.encode()
    monkeypatch.setattr(jev.subprocess, "run", lambda *a, **k: Proc())
    from judge_audit.judges.base import Question, QuestionType
    q = Question(name="c", type=QuestionType.CHOICE, instructions="?", options=["a", "b"])
    with pytest.raises(RuntimeError) as e:
        jev.JevJudge().decide("x", [q])
    assert "TESTKEY0123" not in str(e.value) and "456789abcdef" not in str(e.value), str(e.value)


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_an_error_body_is_masked_before_it_is_cut(echo, monkeypatch, family):
    """A body whose first 300 characters end inside the key: what is left of it is masked."""
    body = "y" * 290 + CUT_KEY                     # [:300] keeps "sk-TESTKEY", 10 characters
    echo["status"], echo["body"] = 400, body
    for k, v in FAMILIES[family](echo["url"]).items():
        monkeypatch.setenv(k, CUT_KEY if v == KEY else v)
    from judge_audit.judges.base import Question, QuestionType
    judge, _ = cli._judge(family, [])
    q = Question(name="c", type=QuestionType.CHOICE, instructions="?", options=["a", "b"])
    with pytest.raises(RuntimeError) as e:          # the adapter's own error, before any cut
        judge.decide("x", [q])
    assert "returned 400" in str(e.value) and "sk-TESTKEY" not in str(e.value), str(e.value)


def test_a_long_exception_text_is_masked_before_it_is_cut(monkeypatch):
    from judge_audit.runner import request_failure
    monkeypatch.setenv("LLM_API_KEY", CUT_KEY)
    text = request_failure(RuntimeError("x" * 290 + CUT_KEY))
    assert "sk-TESTKEY" not in text, text


# --- the Anthropic path: an error keeps its status, never the key ----------------------------

def _fake_anthropic(raise_):
    import types

    class APIStatusError(Exception):
        def __init__(self, status=401, message=""):
            super().__init__(message)
            self.status_code, self.message = status, message

    class RateLimitError(APIStatusError):
        pass

    class Anthropic:
        def __init__(self, **kw):
            self.messages = self

        def create(self, **k):
            raise raise_(APIStatusError, RateLimitError)

    return types.SimpleNamespace(Anthropic=Anthropic, APIStatusError=APIStatusError,
                                 RateLimitError=RateLimitError)


@pytest.mark.parametrize("which, says", [
    (lambda s, r: s(401, f"invalid x-api-key {SHAPELESS}"), "401"),
    (lambda s, r: r(429, f"slow down, {SHAPELESS}"), "rate-limited"),
])
def test_an_anthropic_error_message_never_prints_the_key(monkeypatch, which, says):
    """Built by the real constructor: the key it holds is the one its errors mask."""
    from judge_audit.judges import llm
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic(which))
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SHAPELESS)
    judge = llm.LLMJudge()
    with pytest.raises(RuntimeError) as e:
        judge._call_anthropic("u")
    assert says in str(e.value) and not _runs(SHAPELESS, str(e.value)), str(e.value)


# --- clef-hosted: placeholders only in the path, only the two it fills ----------------------

@pytest.mark.parametrize("url", [
    "https://good.example{model_id}/x",
    "https://api.cloudflare.com.{account}.evil.com/x",
    "https://gw.example.test/{account.__class__}/{model_id}",
    "https://gw.example.test/{model_id[0]}",
    "https://gw.example.test/{0}/{model_id}",
    "https://gw.example.test/{model_id}}",
])
def test_a_clef_endpoint_template_that_could_move_the_host_is_refused(monkeypatch, capsys,
                                                                      tmp_path, url):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", KEY)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("CLEF_HOSTED_ENDPOINT", url)
    monkeypatch.setattr("judge_audit.judges.secrets.OPENER.open",
                        lambda *a, **k: pytest.fail("a request was sent"))
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "clef-hosted", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "CLEF_HOSTED_ENDPOINT" in err and not _leaks(err), err


def test_a_clef_endpoint_template_fills_its_two_placeholders_in_the_path(monkeypatch):
    from judge_audit.judges import hosted
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", KEY)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", ACCOUNT)
    monkeypatch.setenv("CLEF_HOSTED_ENDPOINT",
                       "https://gw.example.test/accounts/{account}/run/{model_id}")
    sent = []

    class Sent(Exception):
        pass

    def open_(req, timeout=0):
        sent.append(req.full_url)
        raise Sent
    monkeypatch.setattr("judge_audit.judges.secrets.OPENER.open", open_)
    with pytest.raises(Sent):
        hosted.ClefHostedJudge()._call("x", [])
    assert sent == [f"https://gw.example.test/accounts/{ACCOUNT}/run/@cf/cloudflare/clef-flash"]


# --- the Anthropic SDK path: no redirect, an endpoint checked like the others ----------------

def _stub_anthropic(monkeypatch, built: list):
    """A stub `anthropic` module that records how its client is built."""
    import types

    class APIStatusError(Exception):
        def __init__(self, status=401, message=""):
            super().__init__(message)
            self.status_code, self.message = status, message

    class RateLimitError(APIStatusError):
        pass

    class DefaultHttpxClient:
        def __init__(self, **kw):
            self.kw = kw

    class Anthropic:
        def __init__(self, **kw):
            built.append(kw)
            self.messages = self

        def create(self, **k):
            raise APIStatusError(307, "Error code: 307")

    mod = types.SimpleNamespace(Anthropic=Anthropic, APIStatusError=APIStatusError,
                                RateLimitError=RateLimitError,
                                DefaultHttpxClient=DefaultHttpxClient)
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", SHAPELESS)
    return mod


def test_the_anthropic_client_is_built_not_to_follow_redirects(monkeypatch):
    from judge_audit.judges import llm
    built: list = []
    _stub_anthropic(monkeypatch, built)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    llm.LLMJudge()
    (kw,) = built
    assert kw["http_client"].kw.get("follow_redirects") is False
    assert "base_url" not in kw                                    # the SDK's own default


def test_an_anthropic_redirect_answer_is_refused_in_one_line(monkeypatch):
    from judge_audit.judges import llm
    _stub_anthropic(monkeypatch, [])
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    with pytest.raises(RuntimeError) as e:
        llm.LLMJudge()._call_anthropic("u")
    assert "redirect" in str(e.value) and "307" in str(e.value)
    assert not _runs(SHAPELESS, str(e.value))


@pytest.mark.parametrize("url, host", [
    ("https://gw.example.test:8443/anthropic", "gw.example.test:8443"),
    ("http://127.0.0.1:9/x", "127.0.0.1:9")])
def test_anthropic_base_url_is_checked_and_passed_explicitly(monkeypatch, url, host):
    from judge_audit.judges import llm
    built: list = []
    _stub_anthropic(monkeypatch, built)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", url)
    d = llm.LLMJudge().describe()
    assert built[0]["base_url"] == url
    assert d["endpoint_overridden"] is True and d["endpoint_host"] == host
    assert "base_url" not in d and "/anthropic" not in json.dumps(d)


@pytest.mark.parametrize("url", ["http://gw.example.test/v1", "https://u:p@gw.example.test/",
                                 "http://example.com\\@127.0.0.1/", "ftp://gw.example.test/"])
def test_a_bad_anthropic_base_url_exits_2_before_any_request(monkeypatch, capsys, tmp_path, url):
    built: list = []
    _stub_anthropic(monkeypatch, built)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", url)
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "llm", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "ANTHROPIC_BASE_URL" in err and not _runs(SHAPELESS, err), err
    assert built == []                                             # no client, no request


@pytest.mark.parametrize("status", [302, 307])
def test_a_real_anthropic_client_never_follows_a_redirect(monkeypatch, capsys, tmp_path, status):
    """The installed SDK against a loopback server answering a redirect to `localhost`."""
    pytest.importorskip("anthropic")
    hits = {"second": 0}

    class Second(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            hits["second"] += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass

    second = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Second)
    target = f"http://localhost:{second.server_address[1]}/v1/messages"

    class First(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(status)
            self.send_header("Location", target)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *a):
            pass

    first = http.server.ThreadingHTTPServer(("127.0.0.1", 0), First)
    for s in (first, second):
        threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", SHAPELESS)
        monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{first.server_address[1]}")
        # the provider's own temperature: SDKs that refuse the keyword still send the request
        monkeypatch.setenv("LLM_TEMPERATURE", "default")
        with pytest.raises(SystemExit) as e:
            cli.main(["run", str(LABELS), "--judge", "llm", "--no-ci",
                      "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
        err = capsys.readouterr().err
        assert e.value.code == 2 and "redirect" in err and not _runs(SHAPELESS, err), err
        assert len(err.strip().splitlines()) == 1
        assert hits["second"] == 0
    finally:
        first.shutdown()
        second.shutdown()


# --- the Workers AI account id is an id ------------------------------------------------------

@pytest.mark.parametrize("account", ["acct/../x", "a.b", "abc def", "id?x=1", "x#y", "é1"])
def test_an_account_id_that_is_not_alphanumeric_is_refused(monkeypatch, capsys, tmp_path,
                                                            account):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", KEY)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", account)
    monkeypatch.delenv("CLEF_HOSTED_ENDPOINT", raising=False)
    monkeypatch.setattr("judge_audit.judges.secrets.OPENER.open",
                        lambda *a, **k: pytest.fail("a request was sent"))
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "clef-hosted", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "CLOUDFLARE_ACCOUNT_ID" in err and not _leaks(err), err
