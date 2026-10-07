"""What keeps a credential inside judge-audit: one rule for the endpoints a key is sent to,
and one scrubber for every message that leaves.

`checked_endpoint` parses an endpoint once and refuses what could send the key somewhere
other than where it looks: a scheme other than https (plain http only to this computer), a
userinfo part (`user@`), a backslash, whitespace or a control character anywhere, a non-ASCII
host, no host. The request is then built from the URL it returns, rebuilt from the parts it
checked, never from the string it was given, so the host that was checked is the host that is
called.

`OPENER` sends every request that carries a key, and refuses a redirect (`RedirectRefused`)
instead of following it: urllib would resend the Authorization header to the host a 30x names,
which no rule checked, over plain http too.

`redact` masks a credential in every form a server, a proxy or a library may echo it: the
value as held, or any piece of it of at least 12 characters, from anywhere in it (literal, in
any letter case, JSON-escaped in whole or in part, percent-encoded, split by whitespace, an
escaped newline or a zero-width character), its base64, the value of every credential variable
set in the process, and any value shaped like a credential (bearer and Authorization values,
`x-api-key` and `api-key` headers quoted or not, `sk-`, `AIza` and `hf_` keys, `key=` /
`api_key=` / `token=` query values, userinfo in a URL, the account segment of a Workers AI
URL). It reads at most `MAX_TEXT` characters, in time linear in them. A message is masked
whole before it is cut to a length limit, so no cut leaves 12 characters of a key unmasked.
"""
from __future__ import annotations

import base64
import ipaddress
import os
import re
import urllib.parse
import urllib.request
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


# --- the opener -------------------------------------------------------------------------------

class RedirectRefused(RuntimeError):
    """A server answered with a redirect, which judge-audit does not follow with a key."""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectRefused(f"the server answered {code} (a redirect); judge-audit does not "
                              f"follow redirects, so the key is never sent to a host that "
                              f"was not checked: set the endpoint to the URL that answers")


# Every request that carries a key goes through this opener, never through `urlopen`.
OPENER = urllib.request.build_opener(_RefuseRedirects)


# --- the scrubber -----------------------------------------------------------------------------

_TOKEN = r"[A-Za-z0-9._~+/=-]"
_Q = r"[\"']?"                                       # a header name or value may be quoted
_SPACE = r"(?:\s{1,8}|%20|\+)"                       # the space after Bearer, as sent or encoded
_SEP = r"\s{0,8}[:=]\s{0,8}"
# A word that stands where a credential would, but is not one: never masked.
_NOT_A_VALUE = r"(?!(?:null|none|true|false|required|undefined|missing)(?![A-Za-z0-9]))"
_VALUE = rf"{_NOT_A_VALUE}{_TOKEN}{{8,}}"
# Shapes a credential takes in a message, masked whatever its value. Every repetition is
# bounded or anchored on a literal, so no input makes one slow.
_SECRET_SHAPES = (
    (re.compile(rf"(?i)(authorization{_Q}{_SEP}{_Q})(?:bearer{_SPACE}|basic\s{{1,8}})?{_VALUE}"),
     r"\1***"),
    (re.compile(rf"(?i)(\bbearer{_SPACE}){_VALUE}"), r"\1***"),
    (re.compile(rf"(?i)({_Q}\b(?:x[-_])?api[-_]key{_Q}{_SEP}{_Q}){_VALUE}"), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"\bAIza[A-Za-z0-9_\-]{20,}"), "AIza***"),
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}"), "hf_***"),
    (re.compile(rf"(?im)((?:^|[?&;\s])(?:api[_-]?key|key|token|access_token)=){_NOT_A_VALUE}"
                r"[^&\s'\"]{8,}"), r"\1***"),
    # userinfo, up to the last `@` of the authority: a password may hold one
    (re.compile(r"(?i)(\b[a-z][a-z0-9+.-]{0,31}://)[^/\s'\"?#]{1,512}@"), r"\1***@"),
    # the account segment of a Workers AI URL: an id, not a word such as `settings`
    (re.compile(r"(/accounts/)[A-Za-z0-9]{16,}(?![A-Za-z0-9])"), r"\1***"),
)

CREDENTIAL_VARS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY",
                   "TYPESAFE_API_KEY", "AI_GATEWAY_API_KEY", "JEV_API_KEY", "HF_TOKEN",
                   "HUGGING_FACE_HUB_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID")
_CREDENTIAL_NAME = re.compile(r"(?:^|_)(?:API_KEY|KEY|TOKEN|SECRET|PASSWORD|ACCOUNT_ID)$")
MIN_SECRET = 8           # shorter values are not masked: masking them would garble plain text
MIN_PIECE = 12           # any piece of a held key this long, from anywhere in it, is masked
MAX_TEXT = 64_000        # characters read; a longer message is cut first, then masked


def credential_values() -> list[str]:
    """The values of the credential variables set in this process (`CREDENTIAL_VARS`, and any
    variable whose name ends in _KEY, _TOKEN, _SECRET, _PASSWORD or _ACCOUNT_ID)."""
    names = set(CREDENTIAL_VARS) | {n for n in os.environ if _CREDENTIAL_NAME.search(n)}
    return [v for n in names if (v := os.environ.get(n, "").strip())]


# One unit of text as a key may be echoed in it: a JSON `\\uXXXX` escape (either case of hex,
# up to four backslashes: a message encoded more than once), an escaped newline, carriage
# return or tab, `\\/`, a percent-encoded byte, or one character. Every alternative has a
# bounded length, so reading a text unit by unit is linear in its length.
_UNIT = re.compile(r"\\{1,4}u([0-9A-Fa-f]{4})|\\{1,4}([nrt])|\\{1,4}(/)|%([0-9A-Fa-f]{2})|(.)",
                   re.DOTALL)
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def _units(text: str) -> tuple[str, list[int], list[int]]:
    """`text` as the characters it stands for, lower-cased, with whitespace and zero-width
    characters (raw or escaped) dropped, and where each of them starts and ends in `text`.
    A run of them, however long (a wrapped and indented line), joins the characters around it."""
    chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    for m in _UNIT.finditer(text):
        hexa, esc, slash, pct, one = m.groups()
        if hexa is not None:
            c = chr(int(hexa, 16))
        elif esc is not None:
            c = "\n"
        elif slash is not None:
            c = "/"
        elif pct is not None:
            c = chr(int(pct, 16))
        else:
            c = one
        if c.isspace() or c in _ZERO_WIDTH:
            continue
        low = c.lower()
        chars.append(low if len(low) == 1 else c)
        starts.append(m.start())
        ends.append(m.end())
    return "".join(chars), starts, ends


def _pieces(secret: str) -> set[str]:
    """Every MIN_PIECE-character window of `secret` as `_units` reads it (the whole of a
    shorter one)."""
    canon = _units(secret)[0]
    n = min(MIN_PIECE, len(canon))
    return {canon[i:i + n] for i in range(len(canon) - n + 1)} if n else set()


def _encodings(secret: str) -> set[str]:
    """The whole-value encodings of `secret` that a unit-by-unit reading cannot see."""
    raw = secret.encode()
    forms = {base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode()}
    forms |= {f.rstrip("=") for f in forms}
    return {f for f in forms if len(f) >= MIN_SECRET}


def _mask_held(text: str, secrets: list[str]) -> str:
    """`text` with every piece of every one of `secrets` masked: each window (`_pieces`) found
    in its unit reading marks the units it covers; overlapping or touching marks merge into
    one span of `text`, replaced by `***`."""
    for s in secrets:
        for form in sorted(_encodings(s), key=len, reverse=True):
            text = text.replace(form, "***")
    canon, starts, ends = _units(text)
    hits: list[tuple[int, int]] = []
    for piece in set().union(*(_pieces(s) for s in secrets)):
        i = canon.find(piece)
        while i != -1:
            hits.append((i, i + len(piece)))
            i = canon.find(piece, i + 1)
    if not hits:
        return text
    hits.sort()
    merged = [list(hits[0])]
    for a, b in hits[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out, at = [], 0
    for a, b in merged:
        out.append(text[at:starts[a]])
        out.append("***")
        at = ends[b - 1]
    out.append(text[at:])
    return "".join(out)


def redact(text: str, *secrets: str | None) -> str:
    """`text` with every credential masked before it leaves judge-audit: each of `secrets`
    (the key, token or account id a judge holds) and the value of every credential variable
    set in the process, whole or any piece of MIN_PIECE characters, in every form they may be
    echoed in (`_mask_held`), then any value shaped like a credential (`_SECRET_SHAPES`),
    whatever server, proxy or library sent it. A text longer than MAX_TEXT is cut to it first
    and says so; the time is linear in what is read. Every message judge-audit prints or
    returns passes through it (`runner.scrub`); a message is masked whole first, and only then
    cut to a length."""
    cut = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    every = sorted({x for x in (*secrets, *credential_values()) if x and len(x) >= MIN_SECRET},
                   key=len, reverse=True)
    if every:
        text = _mask_held(text, every)
    for pattern, repl in _SECRET_SHAPES:
        text = pattern.sub(repl, text)
    return text + " [cut]" if cut else text
