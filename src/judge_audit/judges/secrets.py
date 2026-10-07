"""What keeps a credential inside judge-audit: one rule for the endpoints a key is sent to,
and one scrubber for every message that leaves.

`checked_endpoint` parses an endpoint once and refuses what could send the key somewhere
other than where it looks: a scheme other than https (plain http only to this computer), a
userinfo part (`user@`), a backslash, whitespace or a control character anywhere, a non-ASCII
host, no host. The request is then built from the URL it returns, rebuilt from the parts it
checked, never from the string it was given, so the host that was checked is the host that is
called.

`redact` masks a credential in every form a server, a proxy or a library may echo it: the
value as held (literal, JSON-escaped, percent-encoded, base64, split across a line, or cut
short by a length limit), the value of every credential variable set in the process, and any
value shaped like a credential (bearer and Authorization values, `x-api-key` and `api-key`
headers, `sk-`, `AIza` and `hf_` keys, `key=` / `api_key=` / `token=` query values, userinfo
in a URL, the account segment of a Workers AI URL).
"""
from __future__ import annotations

import base64
import ipaddress
import os
import re
import urllib.parse
from dataclasses import dataclass

LOOPBACK_NAMES = {"localhost"}


@dataclass(frozen=True)
class Endpoint:
    """An endpoint that passed `checked_endpoint`: the URL to call, rebuilt from its checked
    parts, and the host and port provenance records."""
    url: str
    host: str


def _loopback(host: str) -> bool:
    if host in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def checked_endpoint(url: str, var: str, sends_key: bool = True) -> Endpoint:
    """`url` (from the variable or flag `var`) as an endpoint judge-audit may call, or a
    ValueError naming `var` and the reason. With `sends_key`, a credential goes with every
    request, so the scheme must be https, or plain http to this computer only (127.0.0.0/8,
    ::1, localhost); without one, plain http to any host is allowed."""
    raw = url if isinstance(url, str) else ""
    if not raw.strip():
        raise ValueError(f"{var} is empty")
    if "\\" in raw:
        raise ValueError(f"{var} holds a backslash, which URL parsers read differently")
    if any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ValueError(f"{var} holds a control character")
    if any(c.isspace() for c in raw):
        raise ValueError(f"{var} holds whitespace")
    parts = urllib.parse.urlsplit(raw)
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        raise ValueError(f"{var} holds a user part (`user@`): put the credential in its "
                         f"own variable, never in the URL")
    host = parts.hostname or ""
    if not host:
        raise ValueError(f"{var} has no host")
    if not host.isascii():
        raise ValueError(f"{var} has a non-ASCII host; write it in its ASCII (punycode) form")
    try:
        port = parts.port
    except ValueError as e:
        raise ValueError(f"{var} has an invalid port") from e
    scheme = parts.scheme.lower()
    if scheme == "https" or (scheme == "http" and (_loopback(host) or not sends_key)):
        pass
    else:
        raise ValueError(f"{var} must be an https URL (plain http only to this computer: "
                         f"127.0.0.0/8, ::1, localhost): the API key is sent to that host")
    shown = f"[{host}]" if ":" in host else host
    netloc = f"{shown}:{port}" if port else shown
    rebuilt = urllib.parse.urlunsplit((scheme, netloc, parts.path, parts.query, ""))
    return Endpoint(url=rebuilt, host=netloc)


# --- the scrubber -----------------------------------------------------------------------------

_TOKEN = r"[A-Za-z0-9._~+/=-]"
# Shapes a credential takes in a message, masked whatever its value.
_SECRET_SHAPES = (
    (re.compile(rf"(?i)(authorization\s*[:=]\s*)(?:bearer\s+|basic\s+)?{_TOKEN}{{8,}}"),
     r"\1***"),
    (re.compile(rf"(?i)(\bbearer\s+){_TOKEN}{{8,}}"), r"\1***"),
    (re.compile(rf"(?i)(\b(?:x-)?api-key\s*[:=]\s*){_TOKEN}{{8,}}"), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"), "AIza***"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}"), "hf_***"),
    (re.compile(r"(?i)([?&;\s](?:api[_-]?key|key|token|access_token)=)[^&\s'\"]+"), r"\1***"),
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/\s@'\"]+@"), r"\1***@"),        # userinfo
    (re.compile(r"(/accounts/)[^/\s'\"]+"), r"\1***"),
)

CREDENTIAL_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY",
                   "TYPESAFE_API_KEY", "AI_GATEWAY_API_KEY", "JEV_API_KEY", "HF_TOKEN",
                   "HUGGING_FACE_HUB_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
_CREDENTIAL_NAME = re.compile(r"(?:^|_)(?:API_KEY|KEY|TOKEN|SECRET|PASSWORD|ACCOUNT_ID)$")
MIN_SECRET = 8           # shorter values are not masked: masking them would garble plain text
MIN_PREFIX = 12          # a key cut short by a length limit is masked from this many characters


def credential_values() -> list[str]:
    """The values of the credential variables set in this process (`CREDENTIAL_VARS`, and any
    variable whose name ends in _KEY, _TOKEN, _SECRET, _PASSWORD or _ACCOUNT_ID)."""
    names = set(CREDENTIAL_VARS) | {n for n in os.environ if _CREDENTIAL_NAME.search(n)}
    return [v for n in names if (v := os.environ.get(n, "").strip())]


def _encodings(secret: str) -> set[str]:
    """The forms `secret` may be echoed in."""
    raw = secret.encode()
    forms = {secret,
             secret.replace("/", "\\/"),                                   # JSON-escaped slash
             "".join(f"\\u{ord(c):04x}" for c in secret),                  # JSON \u escapes
             urllib.parse.quote(secret, safe=""), urllib.parse.quote_plus(secret),
             base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode(),
             base64.b64encode(raw).decode().rstrip("="),
             base64.urlsafe_b64encode(raw).decode().rstrip("=")}
    return {f for f in forms if len(f) >= MIN_SECRET}


def _mask_held(text: str, secret: str) -> str:
    for form in sorted(_encodings(secret), key=len, reverse=True):
        text = text.replace(form, "***")
    # split across a line: the secret with a newline (and indentation) anywhere inside it
    pattern = r"\s*".join(re.escape(c) for c in secret)
    text = re.sub(pattern, "***", text)
    # cut short (by a length limit, or a server that truncates): a prefix of at least
    # MIN_PREFIX characters, where it ends the text or the token it is part of
    for n in range(len(secret) - 1, MIN_PREFIX - 1, -1):
        text = re.sub(re.escape(secret[:n]) + r"(?![A-Za-z0-9._~+/=-])", "***", text)
    return text


def redact(text: str, *secrets: str | None) -> str:
    """`text` with every credential masked before it leaves judge-audit: each of `secrets`
    (the key, token or account id a judge holds) and the value of every credential variable
    set in the process, in every form they may be echoed in (`_encodings`, split across a
    line, cut short), then any value shaped like a credential (`_SECRET_SHAPES`), whatever
    server, proxy or library sent it. Every message judge-audit prints or returns passes
    through it (`runner.scrub`)."""
    every = {x for x in (*secrets, *credential_values()) if x and len(x) >= MIN_SECRET}
    for s in sorted(every, key=len, reverse=True):
        text = _mask_held(text, s)
    for pattern, repl in _SECRET_SHAPES:
        text = pattern.sub(repl, text)
    return text
