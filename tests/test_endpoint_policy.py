"""Every endpoint a key is sent to follows one rule (`judges.base.checked_endpoint`): parsed
once, https only (plain http to this computer only), no userinfo, backslash, whitespace,
control character or non-ASCII host, and the request built from the validated parts. And
`redact` catches the key in every form a server may echo it. No outside host is called."""
from __future__ import annotations

import base64
import json
import urllib.parse

import pytest

from judge_audit.judges.base import checked_endpoint, redact

KEY = "sk-proj-Z9yX8wV7uT6sR5qP4oN3mL2kJ1iH0gF/plus+eq=="
ACCOUNT = "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"


# --- the rule, by hand ------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://api.example.test/v1", "https://api.example.test:8443/v1?x=1",
    "http://127.0.0.1:8080/v1", "http://127.9.8.7/v1", "http://localhost:11434/v1",
    "http://[::1]:9/v1", "https://[2001:db8::1]/v1"])
def test_these_endpoints_are_accepted(url):
    assert checked_endpoint(url, "X_URL").url.startswith(url.split("?")[0].rstrip("/")[:8])


@pytest.mark.parametrize("url, why", [
    ("http://example.com\\@127.0.0.1/", "backslash"),          # the reviewer's differential
    ("http://example.com@127.0.0.1/", "user"),
    ("https://user:pw@api.example.test/", "user"),
    ("https://:pw@api.example.test/", "user"),
    ("http://127.0.0.1@example.com/", "user"),
    ("http://api.example.test/v1", "https"),
    ("http://192.168.1.5/v1", "https"),
    ("http://0.0.0.0/v1", "https"),
    ("ftp://api.example.test/", "https"),
    ("https://api.exa mple.test/", "whitespace"),
    ("https://api.example.test/\x00x", "control"),
    ("https://api.example.test/\tx", "control"),
    ("https://xn--nxasmq6b.example/", None),                     # punycode is ASCII: allowed
    ("https://api.ëxample.test/", "ASCII"),
    ("https:///v1", "host"),
    ("", "empty"),
])
def test_these_endpoints_are_refused_with_the_reason(url, why):
    if why is None:
        checked_endpoint(url, "X_URL")
        return
    with pytest.raises(ValueError, match="X_URL") as e:
        checked_endpoint(url, "X_URL")
    assert why.lower() in str(e.value).lower(), str(e.value)


def test_the_request_url_is_rebuilt_from_the_validated_parts():
    ep = checked_endpoint("https://API.Example.test:8443/v1/decisions?a=1#frag", "X_URL")
    assert ep.url == "https://api.example.test:8443/v1/decisions?a=1"       # no fragment
    assert ep.host == "api.example.test:8443"
    assert urllib.parse.urlsplit(ep.url).hostname == "api.example.test"


def test_plain_http_to_a_lan_server_is_allowed_only_without_a_key():
    """A keyless local server (Ollama on the LAN) may stay plain http: no credential goes."""
    checked_endpoint("http://192.168.1.5:11434/v1", "LLM_BASE_URL", sends_key=False)
    with pytest.raises(ValueError, match="https"):
        checked_endpoint("http://192.168.1.5:11434/v1", "LLM_BASE_URL", sends_key=True)


# --- every endpoint that can carry a key -----------------------------------------------------

@pytest.mark.parametrize("env, make", [
    ({"JEV_BACKEND": "typesafe", "TYPESAFE_API_KEY": KEY, "JEV_ENDPOINT": "{url}"},
     lambda: __import__("judge_audit.judges.jev", fromlist=["x"]).JevJudge()),
    ({"LLM_PROVIDER": "openai-compatible", "LLM_BASE_URL": "{url}", "LLM_MODEL": "m",
      "LLM_API_KEY": KEY},
     lambda: __import__("judge_audit.judges.llm", fromlist=["x"]).LLMJudge()),
    ({"OPENAI_API_KEY": KEY, "DECISIONS_ENDPOINT": "{url}"},
     lambda: __import__("judge_audit.judges.hosted", fromlist=["x"]).OpenAIDecisionsJudge()),
    ({"CLOUDFLARE_API_TOKEN": KEY, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
      "CLEF_HOSTED_ENDPOINT": "{url}"},
     lambda: __import__("judge_audit.judges.hosted", fromlist=["x"]).ClefHostedJudge()),
], ids=["jev", "llm", "openai-decisions", "clef-hosted"])
@pytest.mark.parametrize("url", ["http://example.com\\@127.0.0.1/", "http://api.example.test/v1",
                                 "https://u:p@api.example.test/v1"])
def test_every_keyed_endpoint_follows_the_rule(monkeypatch, env, make, url):
    for k, v in env.items():
        monkeypatch.setenv(k, v.format(url=url))
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize("env, make, var", [
    ({"JEV_BACKEND": "typesafe", "TYPESAFE_API_KEY": KEY,
      "JEV_ENDPOINT": "https://jev.example.test:9443/v1/systemone?k=1"},
     lambda: __import__("judge_audit.judges.jev", fromlist=["x"]).JevJudge(), "jev"),
    ({"LLM_PROVIDER": "openai-compatible", "LLM_MODEL": "m", "LLM_API_KEY": KEY,
      "LLM_BASE_URL": "https://llm.example.test:9443/v1?k=1"},
     lambda: __import__("judge_audit.judges.llm", fromlist=["x"]).LLMJudge(), "llm"),
], ids=["jev", "llm"])
def test_the_provenance_records_the_host_and_the_flag_only(monkeypatch, env, make, var):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    d = make().describe()
    text = json.dumps(d)
    assert d["endpoint_overridden"] is True and d["endpoint_host"].endswith(":9443")
    assert "/v1" not in json.dumps({k: v for k, v in d.items() if "endpoint" in k})
    assert "k=1" not in text and KEY not in text


def test_a_refused_endpoint_exits_2_before_any_request(monkeypatch, capsys, tmp_path):
    from pathlib import Path

    from judge_audit import cli
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", KEY)
    monkeypatch.setenv("JEV_ENDPOINT", "http://example.com\\@127.0.0.1/")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("a request"))
    labels = Path(__file__).resolve().parent.parent / "examples/email-routing/labels.jsonl"
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(labels), "--judge", "jev", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "JEV_ENDPOINT" in err and KEY not in err


# --- redact: every echoed form of the key ----------------------------------------------------

def _forms(key: str) -> dict[str, str]:
    return {
        "literal": key,
        "json-escaped slash": json.dumps(key)[1:-1].replace("/", "\\/"),
        "json-escaped unicode": "".join(f"\\u{ord(c):04x}" for c in key),
        "percent-encoded": urllib.parse.quote(key, safe=""),
        "quote_plus": urllib.parse.quote_plus(key),
        "base64": base64.b64encode(key.encode()).decode(),
        "base64-url": base64.urlsafe_b64encode(key.encode()).decode(),
        "split by a newline": key[:20] + "\n" + key[20:],
        "truncated prefix": key[:14],
    }


@pytest.mark.parametrize("form", sorted(_forms(KEY)))
def test_redact_masks_every_echoed_form_of_a_held_key(form):
    shown = _forms(KEY)[form]
    out = redact(f"server said: ... {shown} ...", KEY)
    assert shown not in out, (form, out)
    assert KEY[:12] not in out


def test_a_key_cut_at_the_300_character_limit_is_masked():
    body = ("x" * 280) + KEY                                   # the cut leaves 20 characters
    out = redact(body[:300], KEY)
    assert KEY[:20] not in out and KEY[:12] not in out


@pytest.mark.parametrize("text, gone", [
    ("key AIzaSyA-0123456789abcdefghijklmnopq", "AIzaSyA-0123456789abcdefghijklmnopq"),
    ("token hf_AbCdEfGhIjKlMnOpQrStUvWxYz0123", "hf_AbCdEfGhIjKlMnOpQrStUvWxYz0123"),
    ("x-api-key: s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("api-key: s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("X-Api-Key=s3cr3t-value-0123456", "s3cr3t-value-0123456"),
])
def test_redact_masks_these_shapes_without_knowing_the_key(text, gone):
    assert gone not in redact(text)


@pytest.mark.parametrize("text", [
    "the key ends in a period.", "status 401", "row 12 of 300",
    "https://api.example.test/v1/decisions", "x-api-key header missing"])
def test_redact_still_leaves_ordinary_text_alone(text):
    assert redact(text) == text


def test_an_endpoint_with_userinfo_is_masked_in_a_message():
    out = redact("could not reach https://user:p4ssw0rd@api.example.test/v1 (URLError)")
    assert "p4ssw0rd" not in out and "user:" not in out


PLAIN = "Qv7mPz2LwX9tR4nK8yB3"          # a held key with no recognisable shape


def test_a_key_with_no_shape_is_masked_only_because_it_is_held(monkeypatch):
    for v in list(__import__("os").environ):
        if v.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_ACCOUNT_ID")):
            monkeypatch.delenv(v, raising=False)
    assert PLAIN in redact(f"echo {PLAIN}")                 # no shape: not caught by pattern


@pytest.mark.parametrize("form", sorted(_forms(PLAIN)))
def test_a_held_key_with_no_shape_is_masked_in_every_form(form):
    shown = _forms(PLAIN)[form]
    out = redact(f"server said: ... {shown} ...", PLAIN)
    assert shown not in out, (form, out)
