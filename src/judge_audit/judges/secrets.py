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
URL, a resource identifier whole, a 12-digit account number as a path segment), also once a
percent-encoded run of text is decoded, once or twice. It reads at most `MAX_TEXT` characters
of a message, in time linear in them. A message is masked whole before it is cut to a length
limit, so no cut leaves 12 characters of a key unmasked.

`redact_evidence` masks every string of a JSON value (a judgment's `raw`, a run header) the
same way, never cut, and every value under a credential field name (`Authorization`,
`x-api-key`, `token`...) whole; `evidence_raw` marks a `raw` it changed with `redacted: true`:
a successful reply is evidence too, and a server may echo a credential in it as well as in an
error.
"""
from __future__ import annotations

import base64
import ipaddress
import math
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
# The resource part of an identifier: up to 512 characters, not ending on the punctuation
# that closes a sentence.
_RESOURCE = r"(?:[^\s'\"<>(){}\[\],;]{0,511}[^\s'\"<>(){}\[\],;.:!?])"
_WORDS = {"null", "none", "true", "false", "required", "undefined", "missing", ""}
# Shapes a credential takes in a message, masked whatever its value. Every repetition is
# bounded or anchored on a literal, so no input makes one slow.
_SECRET_SHAPES = (
    (re.compile(rf"(?i)(authorization{_Q}{_SEP}{_Q})(?:bearer{_SPACE}|(?:basic|token)\s{{1,8}})?"
                rf"{_VALUE}"),
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
    # a resource identifier, whole (`scheme:partition:service:zone:account:resource`, the
    # account a 12-digit number or empty): its segments name whose infrastructure served it
    (re.compile(r"(?i)\b[a-z]{2,32}:[a-z][a-z0-9-]{0,31}:[a-z0-9-]{0,63}:[a-z0-9-]{0,63}:"
                rf"(?:\d{{12}}(?![0-9])(?::{_RESOURCE})?|:{_RESOURCE})"), "***"),
    # and any part of one that still holds the account: two segments or more, then 12 digits
    (re.compile(r"(?i)\b[a-z0-9][a-z0-9-]{0,62}(?::[a-z0-9-]{0,63}){1,6}:\d{12}(?![0-9])"
                rf"(?::{_RESOURCE})?"), "***"),
    # an account number in plain text: `account 123456789012`, `acct no. 1234-5678-9012`
    (re.compile(r"(?i)(\b(?:account|acct|owner|tenant)\b[ \t]{0,4}(?:id|number|no\.?|#)?"
                r"[ \t]{0,4}[:=#]?[ \t]{0,4})\d{4}[- ]?\d{4}[- ]?\d{4}(?![0-9])"), r"\1***"),
    # a header written as text whose value is a credential whatever it looks like
    (re.compile(r"(?im)(\b(?:x-auth-token|proxy-authorization|set-cookie|cookie"
                r"|x-[a-z0-9-]{0,40}-(?:key|token|secret))[ \t]{0,8}:[ \t]{0,8}(?![ \t]))"
                rf"{_NOT_A_VALUE}[^\r\n\"]{{1,512}}"),
     r"\1***"),
    # a quoted `"name": "value"` whose name is a credential name (`sensitive_name`)
    (re.compile(r"([\"'])([A-Za-z0-9 ._-]{1,48})\1([ \t]{0,8}:[ \t]{0,8})([\"'])"
                r"([^\"'\\\r\n]{1,512})\4"),
     lambda m: (f"{m.group(1)}{m.group(2)}{m.group(1)}{m.group(3)}{m.group(4)}***{m.group(4)}"
                if sensitive_name(m.group(2)) and m.group(5).strip().lower() not in _WORDS
                else m.group(0))),
    # a 12-digit account number as a path segment; a timestamp (yyyymmddhhmm) is kept
    (re.compile(r"(?<=/)\d{12}(?=[/?#\s\"']|$)"),
     lambda m: m.group(0) if _timestamp12(m.group(0)) else "***"),
)


def _timestamp12(digits: str) -> bool:
    """Whether 12 digits read as a time, yyyymmddhhmm (1990-2099), not an account number."""
    y, mo, d, h, mi = (int(digits[:4]), int(digits[4:6]), int(digits[6:8]), int(digits[8:10]),
                       int(digits[10:]))
    return 1990 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31 and h <= 23 and mi <= 59

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
    return _redact_with(text, _held(secrets))


def _held(secrets) -> list[str]:
    """`secrets` and the credential variables' values worth masking, longest first."""
    return sorted({x for x in (*secrets, *credential_values()) if x and len(x) >= MIN_SECRET},
                  key=len, reverse=True)


def _redact_with(text: str, every: list[str], cut_at: int | None = MAX_TEXT) -> str:
    cut = cut_at is not None and len(text) > cut_at
    if cut:
        text = text[:cut_at]
    if every:
        text = _mask_held(text, every)
    text = _shapes(text)
    if "%" in text:
        text = _ENCODED_RUN.sub(lambda m: _decoded_masked(m.group(0)), text)
    return text + " [cut]" if cut else text


def _shapes(text: str) -> str:
    for pattern, repl in _SECRET_SHAPES:
        text = pattern.sub(repl, text)
    return text


# A run of text without whitespace or quotes (read in one linear pass); one that holds a
# percent-encoded byte, a URL or a header encoded once or twice (`%253A`), is decoded, up to
# twice, and scanned again.
_ENCODED_RUN = re.compile(r"[^\s'\"<>]+")
_PCT = re.compile(r"%[0-9A-Fa-f]{2}")


def _decoded_masked(run: str) -> str:
    """`run` as it was when it holds no encoded byte or no shape is found in its decodings
    (up to three: a URL encoded once, twice or three times); else its decoding, masked."""
    if not _PCT.search(run):
        return run
    forms = [urllib.parse.unquote(run)]
    for _ in range(2):
        forms.append(urllib.parse.unquote(forms[-1]))
    for form in reversed(forms):
        masked = _shapes(form)
        if masked != form:
            return masked
    return run


# Field names whose value is a credential whatever it holds (compared lower-cased, `-` read as
# `_`), and the endings that make one: `gateway_key`, `refresh_token`, `client_secret`.
SENSITIVE_NAMES = frozenset({
    "authorization", "proxy_authorization", "x_api_key", "api_key", "apikey", "key", "token",
    "access_token", "auth_token", "x_auth_token", "secret", "password", "passwd", "cookie",
    "set_cookie", "credential", "credentials", "bearer", "session", "session_id", "sid",
    "sig", "signature", "jwt"})
_SENSITIVE_ENDINGS = ("_key", "_token", "_secret", "_password", "_cookie", "_credential")
# Field names that hold an account, tenant or owner id: their id-like values are masked whole.
_ACCOUNT_WORDS = ("account", "acct", "owner", "tenant")
# Containers of HTTP headers, and the only header names evidence keeps from them.
HEADER_CONTAINERS = frozenset({"headers", "header", "request_headers", "response_headers",
                               "http_headers"})
HARMLESS_HEADERS = frozenset({"content_type", "content_length"})
# The fields of a name/value pair (`{"name": "Authorization", "value": ...}`).
_PAIR_NAMES = ("name", "key", "header", "field")


def _norm(name: str) -> str:
    """A field name compared as one: camelCase split, lower-cased, `-`, `.` and spaces read as
    `_`, a trailing `:` dropped (`X-Api-Key`, `x.api.key`, `api key`, `Authorization:`)."""
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip().rstrip(":").strip())
    return re.sub(r"[-. ]", "_", name.lower())


def sensitive_name(name: str) -> bool:
    """Whether a field called `name` holds a credential (`SENSITIVE_NAMES`, or an ending in
    `_key`, `_token`, `_secret`...). `input_tokens` is a count, not a token."""
    n = _norm(name)
    return n in SENSITIVE_NAMES or n.endswith(_SENSITIVE_ENDINGS)


def _account_name(name: str) -> bool:
    n = _norm(name)
    return any(w in n for w in _ACCOUNT_WORDS)


def _id_like(value) -> bool:
    """A value that can be an id: a string of 8 characters or more, or a number of 8 digits
    or more (a probability, or a count, is not)."""
    if isinstance(value, bool):
        return False
    return (isinstance(value, str) and len(value.strip()) >= MIN_SECRET) or \
        (isinstance(value, (int, float)) and abs(value) >= 10_000_000)


def _mask_whole(value, changed: list[bool], only_ids: bool = False):
    """`value` under a credential name: every string in it (an id-like one under an account
    name) and every id-like number replaced by `***`; probabilities, booleans and None are
    kept."""
    if isinstance(value, dict):
        return {k: _mask_whole(v, changed, only_ids) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mask_whole(v, changed, only_ids) for v in value]
    if (isinstance(value, str) and value and not only_ids) or _id_like(value):
        changed[0] = True
        return "***"
    return value


def _pair_name(value: dict) -> str | None:
    """The name of a name/value pair (`{"name": "Authorization", "value": ...}`), or None."""
    if "value" not in value:
        return None
    for field in _PAIR_NAMES:
        if isinstance(value.get(field), str):
            return value[field]
    return None


def _header_name(item) -> str | None:
    """The header name of one entry of a header list: a pair object or a [name, value] list."""
    if isinstance(item, dict):
        return _pair_name(item)
    if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str):
        return item[0]
    return None


def _headers_kept(value, path: str, dropped: list[str]):
    """A container of HTTP headers with only `HARMLESS_HEADERS` kept, in the form it came in
    (a mapping, a list of pairs or of [name, value] lists, a flat [name, value, ...] list);
    every other header is recorded by name in `dropped`, never kept."""
    def keep(name: str) -> bool:
        if _norm(name) in HARMLESS_HEADERS:
            return True
        dropped.append(f"{path}.{name}")
        return False
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if isinstance(k, str) and keep(k)}
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(x, str) for x in value) and len(value) % 2 == 0:
            pairs = list(zip(value[::2], value[1::2], strict=True))
            return [x for n, v in pairs if keep(n) for x in (n, v)]
        names = [_header_name(x) for x in value]
        if all(n is not None for n in names):
            return [x for n, x in zip(names, value, strict=True) if keep(str(n))]
    if value is not None:
        dropped.append(path)
    return None


def _walk(value, every: list[str], changed: list[bool], cut_at: int | None = MAX_TEXT,
          path: str = "", dropped: list[str] | None = None):
    dropped = [] if dropped is None else dropped
    if isinstance(value, str):
        text = _redact_with(value, every, cut_at)
        if text != value:
            changed[0] = True
        return text
    if isinstance(value, dict):
        pair = _pair_name(value)
        out: dict = {}
        for k, v in value.items():
            here = f"{path}.{k}" if path else str(k)
            if isinstance(k, str) and _norm(k) in HEADER_CONTAINERS:
                v = _headers_kept(v, here, dropped)
            elif pair is not None and k == "value":
                if sensitive_name(pair):
                    v = _mask_whole(v, changed)
            elif pair is not None and k in _PAIR_NAMES and v == pair:
                pass                            # the pair's name: a field name, not a secret
            elif isinstance(k, str) and sensitive_name(k):
                v = _mask_whole(v, changed)
            elif isinstance(k, str) and _account_name(k):
                v = _mask_whole(v, changed, only_ids=True)
            key = _walk(k, every, changed, cut_at, here, dropped) if isinstance(k, str) else k
            n = 2
            while key in out:                   # two names masked alike: both entries kept
                key = f"{key.rsplit('#', 1)[0] if n > 2 else key}#{n}"
                n += 1
            out[key] = _walk(v, every, changed, cut_at, here, dropped)
        return out
    if isinstance(value, (list, tuple)):
        items = list(value)
        for i in range(len(items) - 1):        # [name, value, ...]: the item after a name
            if isinstance(items[i], str) and sensitive_name(items[i]):
                items[i + 1] = _mask_whole(items[i + 1], changed)
        return [_walk(v, every, changed, cut_at, path, dropped) for v in items]
    return value


def redact_evidence(value, *secrets: str | None):
    """`value` (a JSON value: a judgment's `raw`, a run header) with every string in it, keys
    included, passed through `redact` with `secrets` (the key, token or account id a judge
    holds), whole: evidence is never cut, so a stored reply re-parses to what was recorded.
    A value under a credential field name (`sensitive_name`: `Authorization`, `x-api-key`,
    `token`, `*_secret`..., as a dict entry, a name/value pair or the item after a name in a
    list, at any depth) is masked whole whatever it holds, and an id under an account, owner
    or tenant name likewise. A container of HTTP headers keeps only `HARMLESS_HEADERS`.
    Numbers (other than such ids), booleans and None are kept; a tuple becomes a list, as JSON
    writes it; two names masked alike stay two entries (`***`, `***#2`). The credential
    variables are read once per call."""
    return _walk(value, _held(secrets), [False], None)


def evidence_raw(raw, *secrets: str | None):
    """A judgment's `raw` as evidence may keep it (`redact_evidence`), with `redacted: true`
    added when masking changed any of it (the decision was read from the reply as it arrived,
    and the record says that what it keeps was altered after), and the headers it dropped
    added to `dropped_fields`. A `raw` that is not a dict is masked and returned without the
    marks."""
    changed: list[bool] = [False]
    dropped: list[str] = []
    out = _walk(raw, _held(secrets), changed, None, "", dropped)
    if isinstance(out, dict):
        if dropped:
            with_dropped(out, dropped)
        if changed[0]:
            out["redacted"] = True
    return out


# --- what evidence keeps of a provider's reply ------------------------------------------------
#
# Deny by default, and typed: a field is kept only when the audit reads it, and only with the
# type and shape the audit expects. A spec is an atom (a function of the value and the
# question's options that returns what to keep, or _DROP), a dict of field name -> spec, or
# a one-item list (the spec of every item).

_DROP = object()
UNRECOGNISED = "<unrecognised>"
OPAQUE = "<opaque>"
_ID = re.compile(r"[A-Za-z0-9._:/-]{1,80}")
# the one fingerprint judge-audit writes itself, for a server on this computer (llm.py)
_LOCAL_FINGERPRINT = re.compile(r"mlx-lm [0-9][0-9.]{0,15} / mlx [0-9][0-9.]{0,15}")
_WORD = re.compile(r"[a-z][a-z0-9_]{0,39}")


def model_id(value) -> str | None:
    """A served model id or fingerprint as evidence keeps it: None when none was given, the
    string when it is a short plain id (`[A-Za-z0-9._:/-]{1,80}`), else `<unrecognised>`:
    an object, or a string that could carry more than an id, is never kept."""
    if value is None or value == "":
        return None
    ok = isinstance(value, str) and (_ID.fullmatch(value) or _LOCAL_FINGERPRINT.fullmatch(value))
    return value if ok else UNRECOGNISED


def count(value) -> int | None:
    """A token count as evidence keeps it: a non-negative integer, else None (unknown)."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 \
        else None


def NUMBER(value, options):
    """A finite number (not a boolean, not a string)."""
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return value if ok else _DROP


def BOOL(value, options):
    return value if isinstance(value, bool) else _DROP


def ID(value, options):
    """A short plain id, else `<unrecognised>`; None stays None."""
    return model_id(value)


def one_of(*allowed: str):
    def check(value, options):
        return value if isinstance(value, str) and value in allowed else _DROP
    return check


def _is_option(value, options) -> bool:
    """One of the options sent, or a level's index (a score's levels may be named by it)."""
    if isinstance(value, str):
        return value in options or (value.isdigit() and int(value) < len(options))
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < len(options)


def OPTION(value, options):
    """One of the options the question sent (or a level index), never another string."""
    return value if _is_option(value, options) else _DROP


def NUMBER_OR_OPTION(value, options):
    got = NUMBER(value, options)
    return got if got is not _DROP else OPTION(value, options)


_ERROR_FIELDS = ("code", "type")


def ERROR(value, options):
    """An error as evidence keeps it: a code (`max_length_exceeded`) or, of an object, its
    `code` / `type` when each is a plain word and its HTTP `status`; anything else is
    `<unrecognised>`: an error's text can echo what was sent."""
    if isinstance(value, str):
        return value if _WORD.fullmatch(value) else UNRECOGNISED
    if isinstance(value, dict):
        kept = {k: value[k] for k in _ERROR_FIELDS
                if isinstance(value.get(k), str) and _WORD.fullmatch(value[k])}
        status = value.get("status")
        if isinstance(status, int) and not isinstance(status, bool) and 100 <= status <= 599:
            kept["status"] = status
        return kept or UNRECOGNISED
    return UNRECOGNISED


# The counts a usage record may hold (`inputTokens` is read as `input_tokens`); any other
# field, whatever it holds, is left out.
USAGE_COUNTS = frozenset({
    "input_tokens", "output_tokens", "total_tokens", "hidden_output_tokens", "cached_tokens",
    "cache_write_tokens", "cache_read_tokens", "cache_creation_input_tokens",
    "cache_read_input_tokens", "cached_input_tokens", "reasoning_tokens", "prompt_tokens",
    "completion_tokens", "audio_tokens", "accepted_prediction_tokens",
    "rejected_prediction_tokens"})
USAGE_DETAILS = frozenset({"input_tokens_details", "output_tokens_details",
                           "prompt_tokens_details", "completion_tokens_details",
                           "input_token_details", "output_token_details"})


def USAGE(value, options, path: str = "usage", dropped: list[str] | None = None):
    """A usage record: its known counts as finite numbers, its known detail objects likewise."""
    dropped = [] if dropped is None else dropped
    if value is None:
        return None
    if not isinstance(value, dict):
        dropped.append(path)
        return _DROP
    out = {}
    for k, v in value.items():
        here = f"{path}.{k}"
        name = _norm(k) if isinstance(k, str) else ""
        if name in USAGE_COUNTS and NUMBER(v, options) is not _DROP:
            out[k] = v
        elif name in USAGE_DETAILS and isinstance(v, dict):
            got = USAGE(v, options, here, dropped)
            if got is not _DROP:
                out[k] = got
        else:
            dropped.append(here)
    return out


def KEYED(value_spec):
    """A mapping keyed by the options sent (per-option probabilities): any other key is left
    out, whatever its value."""
    return ("keyed", value_spec)


def ROWS(row_spec: dict, required: str):
    """A list of objects (`row_spec` each); a row whose `required` field is not kept is left
    out whole."""
    return ("rows", row_spec, required)


def kept_fields(value, spec, path: str, dropped: list[str], options=()):
    """`value` with only the fields `spec` names, each of the type it names: deny by default.
    Every field left out is recorded by its path in `dropped` (`answer.debug`). A value left
    out whole is None."""
    got = _keep(value, spec, path, dropped, tuple(options))
    return None if got is _DROP else got


def _keep(value, spec, path: str, dropped: list[str], options: tuple):
    if spec is USAGE:
        return USAGE(value, options, path, dropped)
    if callable(spec):
        if value is None:
            return None
        got = spec(value, options)
        if got is _DROP:
            dropped.append(path)
        return got
    if isinstance(spec, tuple) and spec[0] == "keyed":
        if not isinstance(value, dict):
            return value if value is None else _skip(path, dropped)
        out = {}
        for k, v in value.items():
            if not _is_option(k, options):
                dropped.append(f"{path}.{OPAQUE}")      # a key not sent is never named
                continue
            got = _keep(v, spec[1], f"{path}.{k}", dropped, options)
            if got is not _DROP and got is not None:
                out[k] = got
        return out
    if isinstance(spec, tuple) and spec[0] == "rows":
        if not isinstance(value, (list, tuple)):
            return value if value is None else _skip(path, dropped)
        rows = []
        for v in value:
            got = _keep(v, spec[1], path, dropped, options)
            if isinstance(got, dict) and got.get(spec[2]) is not None:
                rows.append(got)
            elif got is not _DROP:
                dropped.append(f"{path}.{spec[2]}")
        return rows
    if not isinstance(value, dict):
        return value if value is None else _skip(path, dropped)
    out = {}
    for k, v in value.items():
        here = f"{path}.{k}" if path else str(k)
        sub = spec.get(k)
        if sub is None:
            dropped.append(here)
            continue
        got = _keep(v, sub, here, dropped, options)
        if got is not _DROP:
            out[k] = got
    return out


def _skip(path: str, dropped: list[str]):
    dropped.append(path)
    return _DROP


_HEADER_CASE = re.compile(r"[A-Z][a-z0-9]*(?:-[A-Z]?[a-z0-9]+){0,7}")


def _safe_name(path: str) -> str:
    """A dropped field's path as evidence records it: each part that is a plain lower-case
    word (`trace_id`, `x-request-id`) or a header name in its usual case (`X-Request-Id`),
    lower-cased with `-` as `_`; any other part is `<opaque>` (`rawResponse` too): a field
    name a server chose can itself be a token."""
    parts = []
    for part in str(path).split("."):
        name = part.replace("-", "_").lower()
        plain = _WORD.fullmatch(part.replace("-", "_")) or _HEADER_CASE.fullmatch(part)
        parts.append(name if plain and _WORD.fullmatch(name) else OPAQUE)
    return ".".join(parts)


def with_dropped(raw: dict, dropped: list[str]) -> dict:
    """`raw` with `dropped_fields`, `{"count": n, "names": [...]}`, when anything was left
    out: how many fields, and the plain-word paths of them (`_safe_name`)."""
    if not dropped:
        return raw
    found = raw.get("dropped_fields")
    prior: dict = found if isinstance(found, dict) else {}
    n: int = prior["count"] if isinstance(prior.get("count"), int) else 0
    had = [x for x in prior.get("names") or [] if isinstance(x, str)]
    raw["dropped_fields"] = {"count": n + len(dropped),
                             "names": sorted({*had, *(_safe_name(d) for d in dropped)})}
    return raw


# What a run header keeps of a provider module's `describe()`: these fields, typed.
def _prices(value, options):
    ok = isinstance(value, (list, tuple)) and len(value) == 2 and \
        all(NUMBER(x, ()) is not _DROP for x in value)
    return list(value) if ok else _DROP


DESCRIBE_FIELDS = {"provider": ID, "model": ID, "model_id": ID, "max_tokens": NUMBER,
                   "prices_usd_per_mtok": _prices, "input_price_per_mtok_usd": NUMBER,
                   "output_price_per_mtok_usd": NUMBER}


def kept_describe(extra) -> tuple[dict, list[str]]:
    """A provider module's `describe()` as the run header keeps it (`DESCRIBE_FIELDS`), and
    what was left out. A value of the wrong type, or an id that is not a short plain one, is
    left out, never kept as `<unrecognised>`."""
    dropped: list[str] = []
    if not isinstance(extra, dict):
        return {}, ["describe"]
    out = {}
    for k, v in extra.items():
        check = DESCRIBE_FIELDS.get(k) if isinstance(k, str) else None
        got = check(v, ()) if check is not None and v is not None else _DROP
        if got is _DROP or got == UNRECOGNISED:
            dropped.append(f"describe.{k}")
        else:
            out[k] = got
    return out, dropped
