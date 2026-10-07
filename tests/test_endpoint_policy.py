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
from judge_audit.judges.secrets import OPENER

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
    monkeypatch.setattr(OPENER, "open", lambda *a, **k: pytest.fail("a request"))
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
        # a JSON body that splits the key with an escaped newline, or zero-width characters
        "split by a JSON \\n": key[:10] + "\\n" + key[10:],
        # wrapped and indented: every fragment shorter than 12 characters
        "wrapped and indented": key[:8] + "\n    " + key[8:16] + "\n    " + key[16:],
        "wrapped, CRLF and tabs": key[:8] + "\r\n\t\t\t\t" + key[8:16] + "\r\n\t\t\t\t" + key[16:],
        "JSON \\n then spaces": key[:8] + "\\n        " + key[8:16] + "\\n        " + key[16:],
        "split by a JSON \\r\\n": key[:10] + "\\r\\n" + key[10:],
        "split by a JSON \\u000a": key[:10] + "\\u000a" + key[10:],
        "zero-width characters inside": (key[:4] + "\u200b" + key[4:8] + "\u200c" + key[8:12]
                                         + "\u200d" + key[12:16] + "\ufeff" + key[16:]),
        # cut short and followed by something else
        "truncated, then ...": key[:14] + "...",
        "truncated, then .": key[:13] + ".",
        "truncated, then -": key[:13] + "-",
        "truncated, then other characters": key[:13] + "Q7Q7Q7Q7",
        # echoed in another case, or escaped differently
        "upper-cased": key.upper(),
        "lower-cased": key.lower(),
        "json \\u escapes, upper-case hex": "".join(f"\\u{ord(c):04X}" for c in key),
        "json-encoded twice": json.dumps(json.dumps(key[:10] + "\n" + key[10:]))[1:-1],
        "zero-width characters, json-escaped": json.dumps(
            key[:4] + "\u200b" + key[4:8] + "\ufeff" + key[8:])[1:-1],
        "json \\u escapes, partial": "".join(f"\\u{ord(c):04x}" if i % 2 else c
                                              for i, c in enumerate(key)),
    }


def _gone(key: str, out: str) -> bool:
    """No 12-character run of the key, in any case, is left in `out`."""
    low = out.lower()
    return not any(key[i:i + 12].lower() in low for i in range(len(key) - 11))


@pytest.mark.parametrize("form", sorted(_forms(KEY)))
def test_redact_masks_every_echoed_form_of_a_held_key(form):
    shown = _forms(KEY)[form]
    out = redact(f"server said: ... {shown} ...", KEY)
    assert shown not in out, (form, out)
    assert _gone(KEY, out), (form, out)


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
    ('{"x-api-key": "s3cr3t-value-0123456"}', "s3cr3t-value-0123456"),
    ("{'x-api-key': 's3cr3t-value-0123456'}", "s3cr3t-value-0123456"),
    ('{"Api-Key":"s3cr3t-value-0123456"}', "s3cr3t-value-0123456"),
    ("api_key: s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("x_api_key=s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("X-Api_Key: s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("key=s3cr3t-value-0123456&alt=json", "s3cr3t-value-0123456"),
    ("Authorization=Bearer%20s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("GET /x?auth=Bearer%20s3cr3t-value-0123456", "s3cr3t-value-0123456"),
    ("could not reach https://user:p4ss@w0rd99@api.example.test/v1", "w0rd99"),
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
    assert _gone(PLAIN, out), (form, out)


SHAPELESS = ["Zq9fakeTOKENvalue77x", "acct0fake12345abcd"]     # held keys with no known shape


@pytest.mark.parametrize("key", SHAPELESS)
@pytest.mark.parametrize("form", sorted(_forms(SHAPELESS[0])))
def test_a_shapeless_held_key_is_masked_in_every_form(key, form):
    shown = _forms(key)[form]
    out = redact(f"server said: {shown} (401)", key)
    assert _gone(key, out), (form, out)


# --- any 12-character piece of a held key, from anywhere in it --------------------------------

@pytest.mark.parametrize("key", [KEY, PLAIN, *SHAPELESS])
def test_every_12_character_window_of_a_held_key_is_masked(key):
    for i in range(len(key) - 11):
        piece = key[i:i + 12]
        out = redact(f"server said: {piece} (401)", key)
        assert piece.lower() not in out.lower(), (i, out)
        assert "server said:" in out and "(401)" in out, out           # the rest is kept


@pytest.mark.parametrize("key", [KEY, *SHAPELESS])
@pytest.mark.parametrize("cut", [lambda k: k[-14:], lambda k: k[5:19], lambda k: k[3:],
                                 lambda k: k[2:-2].upper(), lambda k: k[4:10] + "\\n" + k[10:20]],
                         ids=["suffix", "middle", "head cut", "middle upper-cased",
                              "middle split by a JSON \\n"])
def test_a_key_cut_at_its_head_is_masked(key, cut):
    shown = cut(key)
    out = redact(f"got {shown}...", key)
    assert _gone(key, out), out


def test_two_pieces_of_a_key_side_by_side_are_masked_whole():
    out = redact(f"a {PLAIN[0:14]}{PLAIN[6:20]} b", PLAIN)      # two 14-character pieces
    assert out == "a *** b", out
    assert redact(f"a {PLAIN[0:14]}{PLAIN[10:20]} b", PLAIN) == f"a ***{PLAIN[10:20]} b"


# --- no input makes the scrubber slow ---------------------------------------------------------

MB = 1_000_000


def _adversarial() -> str:
    piece = (" \t\u200b\\u000a\\\\n" + PLAIN[:11] + "\\" * 7 + "%2" + KEY[:11] + "\ufeff"
             + "a.a.a.a.b://" + "Bearer " + "authorization: " + "x-api-key=" + "/accounts/")
    return (piece * (MB // len(piece) + 1))[:MB]


@pytest.mark.parametrize("text", [lambda: "\\" * MB, _adversarial,
                                  lambda: "lorem ipsum " * (MB // 12),
                                  lambda: "a." * (MB // 2), lambda: "\\u00" * (MB // 4)],
                         ids=["backslashes", "adversarial mix", "plain text", "a.a.a", "\\u00"])
def test_redact_takes_under_a_second_on_a_megabyte(monkeypatch, text):
    import time
    for i, name in enumerate(("OPENAI_API_KEY", "LLM_API_KEY", "HF_TOKEN", "CLOUDFLARE_API_TOKEN",
                              "CLOUDFLARE_ACCOUNT_ID")):
        monkeypatch.setenv(name, f"{PLAIN[i:]}{SHAPELESS[0][:i + 4]}")
    body = text()
    t0 = time.perf_counter()
    redact(body, KEY, PLAIN)
    assert time.perf_counter() - t0 < 1.0


def test_a_long_message_is_capped_then_masked():
    out = redact("y" * 70_000 + KEY, KEY)
    assert len(out) < 70_000 and _gone(KEY, out)


# --- ordinary words next to a credential name are not masked ---------------------------------

@pytest.mark.parametrize("text", [
    "key=value pairs", "token=null", "token=None", "api_key=true", "key=false",
    "Authorization: required", "authorization=required", "x-api-key: required",
    "Bearer null", "see /accounts/settings/billing", "GET /accounts/me", "/accounts/***/ai/run",
    "the access_token=undefined case"])
def test_these_ordinary_texts_are_left_alone(text):
    assert redact(text) == text


@pytest.mark.parametrize("text, gone", [
    ("token=abcdefgh123", "abcdefgh123"),
    ("Authorization: Bearer requiredXYZ123", "requiredXYZ123"),
    ("/accounts/9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d/ai/run", "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"),
    ("/accounts/acct0fake12345abcd", "acct0fake12345abcd"),
])
def test_these_values_are_still_masked(text, gone):
    assert gone not in redact(text)
