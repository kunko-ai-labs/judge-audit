"""Hosted decision models behind an HTTP API: the OpenAI Decisions API (`openai-decisions`),
Clef / Clef-flash on Workers AI (`clef-hosted`) and Microsoft-Decision-1 through OpenRouter's
Decisions route (`microsoft-decision`).

Each takes a state and typed questions and return a probability per option. What is recorded,
and why:

- **Confidence is the probability of the chosen option**, read from the answer's per-option
  probabilities, as for every decision model here. Each API also returns its own
  `confidence` field, which it does not define as that probability (the Decisions API's
  documented example has 0.93 next to a top probability of 0.95; Workers AI says "derived
  from the probabilities"); it is kept in `raw.native_confidence` and never audited in its
  place.
- **An answer is checked before it is used** (`valid_distribution`): every probability a
  finite number in [0, 1], the distribution summing to 1 within what rounding explains
  (`sum_tolerance`: K options rounded to d decimals can move the total by K x 0.5 x 10^-d,
  with d the most decimals any of them shows), the chosen option among them. The total is
  kept in `raw.probability_sum` and d in `raw.probability_decimals`; the chosen option's
  probability is audited as returned, never renormalised. One that fails, or has no
  probabilities, is no answer with the reason in `raw.invalid`, and counted against the
  judge: a confidence is never invented or repaired.
- **One question per request by default.** Several questions may share a request
  (`*_QUESTIONS_PER_REQUEST=all`); other decision models have changed an answer with the
  other questions of the request, so sharing is opt-in and recorded. Clef takes at most 64
  questions per request.
- **Every request's reported tokens are billed**, whatever its answers were: a refused or
  unreadable answer costs what its request cost, shared between the request's questions.
  The price is the documented base rate (`*_PRICE_PER_MTOK`); the Decisions API's regional
  and long-context multipliers, which the adapter cannot see, are not applied. A response
  that reports no tokens has an unknown cost (`None`), never $0 and never a count guessed
  with another tokenizer. The Decisions API's documentation describes no `usage` field,
  but the live API returns `usage.input_tokens` (2026-10-07); it is read when present.
- **What was served**: any model id and response id the response carries.
- **Microsoft-Decision-1 is pinned.** OpenRouter routes a model to any provider serving it
  unless told not to: the request names the model's one listed endpoint with
  `allow_fallbacks: false`, and a reply that names another served version or provider stops
  the run (`MICROSOFT_DECISION_VERSION` moves the pin on purpose). The served model and
  provider are kept as typed fields, and OpenRouter's own `usage.cost` beside the cost
  computed here (`reported_cost_usd`). Always one question per request.
- **Over length is no answer, never a truncated one.** A request whose text is over a
  heuristic byte bound (`MICROSOFT_MAX_REQUEST_BYTES`) is withheld unsent. A request of at
  least half the context in bytes that the route refuses with its own context-length error
  (`route_over_context`), or a reply reporting input tokens at or over the model's context,
  is no answer with `raw.error` `max_length_exceeded`, counted against the judge. Any other
  400 or 413 stops the run. The tokenizer is not public, so no exact count
  is made before sending.
- **Only what the audit reads is kept** (deny by default): of an answer, its type, choice,
  score, probabilities, confidence and refusal (`DECISIONS_ANSWER`, `CLEF_ANSWER`); of a
  usage record, its counts. Every other field, a header, a trace or a debug object, is left
  out and named in `raw.dropped_fields`.
- **Credentials from the environment only.** No key, token or account id is recorded or
  printed: every error message passes through `_redact`, which masks the token, the account
  id and the URL segment that holds it, and every `raw`, a successful reply's included,
  through `evidence_raw` (a record it changed says `redacted: true`). A server that cannot
  be reached is reported within `CONNECT_BUDGET_S`.

Environment:
  openai-decisions  OPENAI_API_KEY; DECISIONS_MODEL (default gpt-6-luna);
                    DECISIONS_QUESTIONS_PER_REQUEST (1 | all, default 1)
  clef-hosted       CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID; CLEF_HOSTED_MODEL
                    (clef-flash | clef, default clef-flash);
                    CLEF_HOSTED_QUESTIONS_PER_REQUEST (1 | all, default 1)
  microsoft-decision
                    OPENROUTER_API_KEY; MICROSOFT_DECISION_VERSION (the served version it
                    pins, default microsoft/microsoft-decision-1-20261009); always one
                    question per request
  all               HOSTED_MIN_INTERVAL_S (seconds between calls, default 0);
                    DECISIONS_ENDPOINT, CLEF_HOSTED_ENDPOINT, MICROSOFT_DECISION_ENDPOINT
                    (another server speaking the same API, e.g. a proxy;
                    CLEF_HOSTED_ENDPOINT may hold {model_id})
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import (
    OPENER,
    Endpoint,
    Judge,
    Judgment,
    Question,
    QuestionType,
    checked_endpoint,
    evidence_raw,
    redact,
    served_of,
)
from .secrets import (
    BOOL,
    ERROR,
    ID,
    KEYED,
    NUMBER,
    NUMBER_OR_OPTION,
    OPAQUE,
    OPTION,
    ROWS,
    USAGE,
    count,
    kept_fields,
    model_id,
    one_of,
    with_dropped,
)
from .systemone import CRITERIA_VERSION, systemone_question

DECISIONS_ENDPOINT = "https://api.openai.com/v1/decisions"
DECISIONS_MODEL = "gpt-6-luna"
# Base rate per million input tokens; output is not billed (2026-10-07). Regional processing
# and long-context multipliers may apply on top and are not seen by the adapter.
DECISIONS_PRICE_PER_MTOK = 0.10

CLEF_ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model_id}"
# Workers AI model id and unit price per million input tokens (2026-10-07).
CLEF_MODELS = {"clef-flash": ("@cf/cloudflare/clef-flash", 0.09),
               "clef": ("@cf/cloudflare/clef", 0.24)}
CLEF_MAX_QUESTIONS = 64            # per request, as the Workers AI schema says

RETRY_STATUS = (429, 500, 502, 503, 504, 524, 529)
ATTEMPTS = 6                       # for a server that answers busy
CONNECT_BUDGET_S = 20.0            # total backoff for a server that cannot be reached
TIMEOUT_S = 120


def endpoint_override(var: str) -> Endpoint | None:
    """The endpoint in `var`, checked (`checked_endpoint`: https, or plain http to this
    computer only; no userinfo, backslash, whitespace or control character), or None when
    unset. Refused before any request is built."""
    url = (os.environ.get(var) or "").strip()
    return checked_endpoint(url, var) if url else None


CLEF_PLACEHOLDERS = ("{model_id}", "{account}")


def clef_endpoint(var: str) -> Endpoint | None:
    """The endpoint template in `var`, as `endpoint_override`, or None when unset. It may hold
    `{model_id}` and `{account}`, in its path only, and no other brace: a placeholder in the
    host would let the account id choose the host the token is sent to, and any other field
    (`{account.__class__}`, `{0}`) would be read by `str.format`. Refused before any request
    is built."""
    url = (os.environ.get(var) or "").strip()
    if not url:
        return None
    netloc = urllib.parse.urlsplit(url).netloc
    if "{" in netloc or "}" in netloc:
        raise ValueError(f"{var} holds a placeholder in its host: {{model_id}} and {{account}} "
                         f"are allowed in the path only")
    rest = url
    for p in CLEF_PLACEHOLDERS:
        rest = rest.replace(p, "")
    if "{" in rest or "}" in rest:
        raise ValueError(f"{var} holds a brace that is not {{model_id}} or {{account}}")
    return checked_endpoint(url, var)


def fill_endpoint(ep: Endpoint, var: str, **values: str) -> str:
    """`ep`'s URL with its placeholders replaced by `values` (plain replacement, never
    `str.format`), checked again (`checked_endpoint`) and refused unless it still names the
    host that was checked."""
    url = ep.url
    for name, value in values.items():
        for form in (f"{{{name}}}", f"%7B{name}%7D"):
            url = url.replace(form, value)
    final = checked_endpoint(url, var)
    if final.host != ep.host:
        raise ValueError(f"{var} names another host once its placeholders are filled")
    return final.url


def _per_request(env: str) -> int | None:
    """Questions per request: 1 (the default) or None for all of them."""
    value = os.environ.get(env, "1").strip().lower()
    if value == "all":
        return None
    if value == "1":
        return 1
    raise ValueError(f"{env} must be 1 or all, got {value!r}")


def _redact(text: str, secrets: tuple[str, ...]) -> str:
    """`text` with the judge's secrets and every credential-shaped value masked (`redact`)."""
    return redact(text, *secrets)


class HostedHTTPError(RuntimeError):
    """An HTTP error a hosted API answered and that is not retried, with its `status` and
    its `body`; both texts are already masked (`_redact`), the message cut."""

    def __init__(self, message: str, status: int, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def post_json(url: str, body: dict, label: str, secrets: tuple[str, ...]) -> dict:
    """POST `body` with the first secret as the bearer token; the reply's JSON. A busy server
    (429, 5xx) is retried with backoff; one that cannot be reached is retried within
    `CONNECT_BUDGET_S`. Every error names the service (`label`) and the status, with the
    secrets and the account segment of the URL masked; one that is not retried is a
    `HostedHTTPError` carrying its status."""
    data = json.dumps(body, allow_nan=False).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {secrets[0]}"}
    last, waited, unreachable = "", 0.0, False
    for attempt in range(ATTEMPTS):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with OPENER.open(req, timeout=TIMEOUT_S) as resp:      # refuses redirects
                return json.load(resp)
        except urllib.error.HTTPError as e:
            answered = _redact(e.read().decode(errors="replace"), secrets)
            last = f"{e.code}: {answered}"[:300]
            unreachable = False
            if e.code not in RETRY_STATUS:
                raise HostedHTTPError(f"{label} returned {last}", e.code,
                                      answered[:4000]) from None
            wait = min(2 ** attempt * 2 + random.uniform(0, 1), 60)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            # reported by class only: its text can hold the URL, and the URL the account
            last, unreachable = type(e).__name__, True
            wait = min(2 ** attempt + random.uniform(0, 0.5), CONNECT_BUDGET_S - waited)
            if wait <= 0:
                break
        waited += wait
        time.sleep(wait)
    if unreachable:
        raise RuntimeError(f"could not reach {label} ({last}) within "
                           f"{CONNECT_BUDGET_S:.0f} s; check the network and the endpoint")
    # "rate-limited" is what scripts/audit_resumable.py looks for before sleeping.
    raise RuntimeError(f"rate-limited by {label} after {ATTEMPTS} attempts ({last})")


def decimals(x: float) -> int:
    """How many decimals `x` shows in its shortest round-trip form (0.54 -> 2, 1e-05 -> 5):
    the digits the server sent, since JSON numbers parse to that form."""
    text = repr(float(x)).lower()
    mantissa, _, exponent = text.partition("e")
    places = len(mantissa.partition(".")[2].rstrip("0"))
    return max(0, places - int(exponent or 0))


def sum_tolerance(probs: dict[str, float]) -> float:
    """How far from 1 rounding can move the total: K options rounded to d decimals, each off
    by at most 0.5 x 10^-d, with d the most decimals any of them shows (77 options at 2
    decimals: 0.385). Full-precision probabilities leave almost no room."""
    d = max((decimals(v) for v in probs.values()), default=0)
    return len(probs) * 0.5 * 10.0 ** -d + 1e-9


def valid_distribution(probs: dict[str, float], chosen: str | None = None) -> str | None:
    """Why a declared distribution cannot be used, or None when it can: every probability a
    finite number in [0, 1], the total within `sum_tolerance` of 1, and `chosen` (when
    given) among the options."""
    if not probs:
        return "no probabilities"
    for k, v in probs.items():
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
            return f"probability of {k!r} is not a finite number"
        if not 0.0 <= v <= 1.0:
            return f"probability of {k!r} is {v}, outside [0, 1]"
    total = math.fsum(probs.values())
    tolerance = sum_tolerance(probs)
    if abs(total - 1.0) > tolerance:
        return (f"probabilities sum to {total:.4f}, not 1: more than rounding "
                f"{len(probs)} options explains ({tolerance:.4g})")
    if chosen is not None and chosen not in probs:
        return f"chosen option {chosen!r} is not among its probabilities"
    return None


def declared_sum(values) -> dict:
    """`probability_sum` and `probability_decimals` of the probabilities an answer declares,
    as returned (recorded whether or not the answer is used); {} when there are none."""
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v)]
    if not nums:
        return {}
    return {"probability_sum": round(math.fsum(nums), 9),
            "probability_decimals": max(decimals(v) for v in nums)}


# The decision recorded for a chosen option that is not one of the options sent: it matches
# no option, so it is scored wrong at the confidence declared; the label itself is not kept.
UNSENT = "<unsent_option>"
UNSENT_REASON = "chosen option is not among the options sent"


def read_checked(q: Question, kind: str, probs: dict[str, float],
                 yes: float | None, chosen: str | None) -> tuple[str, float, dict] | str:
    """(decision, P(decision), probabilities), or the reason the answer cannot be used.
    `yes` is P(true) for a yes/no question; `probs` the per-option (or per-level) ones."""
    if q.type is QuestionType.NOUL:
        if yes is None:
            return "no probability"
        reason = valid_distribution({"true": yes, "false": 1 - yes}) \
            if isinstance(yes, (int, float)) and math.isfinite(yes) and 0 <= yes <= 1 \
            else valid_distribution({"true": yes})
        if reason:
            return reason
        return ("true" if yes >= 0.5 else "false"), max(yes, 1 - yes), {"true": yes,
                                                                        "false": 1 - yes}
    if q.type is QuestionType.CHOICE:
        reason = valid_distribution(probs, chosen if chosen is not None else "")
        if reason:
            return reason
        assert chosen is not None
        if chosen not in q.options:
            # an answer, wrong, at the confidence it declared, as every other judge scores it;
            # the label it invented is never stored (`UNSENT`)
            return UNSENT, probs[chosen], probs
        return chosen, probs[chosen], probs
    reason = valid_distribution(probs)
    if reason:
        return reason
    try:
        best = max(probs, key=lambda k: (probs[k], -int(k)))     # the first level on a tie
        return q.options[int(best)], probs[best], probs
    except (ValueError, IndexError):
        return f"levels {sorted(probs)} do not match the {len(q.options)} options"


def as_evidence(value):
    """`value` as JSON can hold it: a non-finite number the server sent is kept as its text
    ("NaN", "Infinity", "-Infinity"), so the record shows what arrived and stays valid JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {k: as_evidence(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_evidence(v) for v in value]
    return value


# What evidence keeps of an answer: the fields the audit reads, each of the type it reads
# (deny by default). A choice, a value or a probability's key is kept only when it is one of
# the options sent. Every other field is left out and counted in `raw.dropped_fields`.
ANSWER_TYPES = one_of("choice", "score", "predicate", "noul", "boolean", "refusal")
DECISIONS_ANSWER = {"type": ANSWER_TYPES, "name": OPTION, "choice": OPTION,
                    "probability": NUMBER, "score": NUMBER_OR_OPTION, "confidence": NUMBER,
                    "refusal": BOOL,
                    "probabilities": ROWS({"value": OPTION, "label": OPTION,
                                           "probability": NUMBER}, "value")}
CLEF_ANSWER = {"type": ANSWER_TYPES, "choice": OPTION, "noul": NUMBER,
               "score": NUMBER_OR_OPTION, "confidence": NUMBER,
               "probabilities": KEYED(NUMBER), "error": ERROR}


def options_of(q: Question) -> list[str]:
    """What a question's answer may name: its options, `true` / `false` for a yes/no one,
    and the question's own name (a Decisions answer names its question)."""
    return [*(q.options if q.type is not QuestionType.NOUL else ["true", "false"]), q.name]


def kept_reply(answer, usage, spec, q: Question) -> dict:
    """`answer` and `usage` as evidence keeps them: the answer's fields in `spec`, typed, the
    usage record's known counts; what was left out is counted in `dropped_fields`."""
    dropped: list[str] = []
    return with_dropped({"answer": kept_fields(answer, spec, "answer", dropped, options_of(q)),
                         "usage": kept_fields(usage, USAGE, "usage", dropped)}, dropped)


def kept_probabilities(probs: dict, q: Question) -> dict:
    """The checked probabilities as evidence keeps them: of the options sent only."""
    return kept_fields(probs, KEYED(NUMBER), "probabilities", [], options_of(q)) or {}


_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def safe_reason(reason: str, q: Question) -> str:
    """Why an answer was not used, without echoing what the server sent: a quoted name that
    is not one of the options sent is `<opaque>`."""
    opts = set(options_of(q))
    return _QUOTED.sub(lambda m: m.group(0) if m.group(0)[1:-1] in opts else OPAQUE, reason)


def evidence(raw: dict, secrets: tuple[str, ...]) -> dict:
    """`raw` as a judgment keeps it: non-finite numbers as text (`as_evidence`), then the
    judge's secrets and every credential-shaped value masked (`evidence_raw`): a server may
    echo them in a reply it answers as well as in an error."""
    return evidence_raw(as_evidence(raw), *secrets)


def _no_answer(q: Question, latency: float, cost: float | None, raw: dict,
               secrets: tuple[str, ...]) -> Judgment:
    return Judgment(question=q.name, decision="", confidence=None, latency_s=latency,
                    cost_usd=cost, raw=evidence(raw, secrets), parse_status="no_answer")


class _HostedDecisionJudge(Judge):
    """Batching, pacing and cost shared by the hosted decision APIs."""

    per_request: int | None = 1
    max_questions: int | None = None
    price: float = 0.0
    _last = 0.0

    def _pace(self) -> None:
        gap = float(os.environ.get("HOSTED_MIN_INTERVAL_S", "0") or 0)
        wait = gap - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        raise NotImplementedError

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        size = self.per_request or max(len(questions), 1)
        if self.max_questions and size > self.max_questions:
            raise ValueError(f"{self.name} takes at most {self.max_questions} questions per "
                             f"request; this one has {size} (send one per request)")
        out: list[Judgment] = []
        for i in range(0, len(questions), size):
            self._pace()
            out += self._call(state, questions[i:i + size])
        return out

    _override: Endpoint | None = None

    def _endpoint_provenance(self, default: str) -> dict:
        """The endpoint as provenance records it: the documented one, or for an override its
        host only, flagged."""
        if self._override:
            return {"endpoint": None, "endpoint_overridden": True,
                    "endpoint_host": self._override.host}
        return {"endpoint": default, "endpoint_overridden": False}

    def _cost(self, usage) -> float | None:
        """One request's cost from the input tokens it reports; None when it reports none."""
        tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            return None
        return tokens / 1e6 * self.price

    @staticmethod
    def _share(value: float | None, n: int) -> float | None:
        return None if value is None else value / max(n, 1)


class OpenAIDecisionsJudge(_HostedDecisionJudge):
    """The OpenAI Decisions API (`POST /v1/decisions`)."""

    name = "openai-decisions"
    price = DECISIONS_PRICE_PER_MTOK

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._key:
            raise RuntimeError("OPENAI_API_KEY is not set (the OpenAI Decisions API)")
        self.model = model or os.environ.get("DECISIONS_MODEL", DECISIONS_MODEL)
        self._override = endpoint_override("DECISIONS_ENDPOINT")
        self.endpoint = self._override.url if self._override else DECISIONS_ENDPOINT
        self.per_request = _per_request("DECISIONS_QUESTIONS_PER_REQUEST")

    def describe(self) -> dict:
        return {"name": self.name, "provider": "hosted-api", "model": self.model,
                **self._endpoint_provenance(DECISIONS_ENDPOINT),
                "criteria_version": CRITERIA_VERSION,
                "confidence_method": "P(chosen option), from the answer's per-option "
                                     "probabilities (yes/no: of the answer given)",
                "native_confidence": "the API's `confidence` field, not defined by its "
                                     "documentation as P(chosen option); kept in raw as "
                                     "native_confidence, not audited",
                "temperature": "n/a",
                "questions_per_request": self.per_request or "all",
                "input_price_per_mtok_usd": self.price, "output_price_per_mtok_usd": 0.0,
                "price_note": "documented base rate; regional and long-context multipliers "
                              "are not applied",
                "sum_tolerance": "options x 0.5 x 10^-decimals (rounding)"}

    @staticmethod
    def wire_question(q: Question) -> dict:
        """A judge-audit question in the Decisions API's shape: a yes/no question is a
        `predicate`, a score's options are its `levels`, lowest first."""
        base: dict = {"type": {QuestionType.NOUL: "predicate"}.get(q.type, q.type.value),
                      "name": q.name, "instructions": q.instructions}
        if q.type is QuestionType.CHOICE:
            base["choices"] = [{"value": o, "description": q.descriptions.get(o, o)}
                               for o in q.options]
        elif q.type is QuestionType.SCORE:
            base["levels"] = [{"label": o, "description": q.descriptions.get(o, o)}
                              for o in q.options]
        return base

    @staticmethod
    def read(q: Question, ans: dict) -> tuple[str, float, dict] | str:
        """(decision, P(decision), probabilities) from one Decisions answer, or why not."""
        try:
            probs = {str(x["value"]): x["probability"] for x in ans.get("probabilities") or []}
        except (KeyError, TypeError):
            return "probabilities are not a list of {value, probability}"
        chosen = ans.get("choice")
        return read_checked(q, ans.get("type", ""), probs, ans.get("probability"),
                            None if chosen is None else str(chosen))

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        body = {"model": self.model, "input": state,
                "questions": [self.wire_question(q) for q in questions]}
        t0 = time.monotonic()
        secrets = (self._key,)
        reply = post_json(self.endpoint, body, "the OpenAI Decisions API", secrets)
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = {a.get("name"): a for a in reply.get("answers") or [] if isinstance(a, dict)}
        usage = reply.get("usage") or None
        cost = self._share(self._cost(usage), len(questions))     # billed whatever the answers
        served = served_of({"model": reply.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            base = {**kept_reply(ans, usage, DECISIONS_ANSWER, q), "served": served,
                    "response_id": kept_fields(reply.get("id"), ID, "response_id", [])}
            if isinstance(ans, dict) and isinstance(ans.get("probabilities"), list):
                base.update(declared_sum(x.get("probability") for x in ans["probabilities"]
                                         if isinstance(x, dict)))
            if not isinstance(ans, dict) or ans.get("type") == "refusal":
                refused = isinstance(ans, dict) and ans.get("type") == "refusal"
                out.append(_no_answer(q, latency, cost, {**base, "refusal": refused}, secrets))
                continue
            got = self.read(q, ans)
            if isinstance(got, str):
                out.append(_no_answer(q, latency, cost,
                                      {**base, "invalid": safe_reason(got, q)}, secrets))
                continue
            decision, confidence, probs = got
            if decision == UNSENT:
                base["invalid"] = UNSENT_REASON
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw=evidence({**base,
                                              "probabilities": kept_probabilities(probs, q),
                                              "native_confidence": kept_fields(
                                                  ans.get("confidence"), NUMBER,
                                                  "native_confidence", [])}, secrets)))
        return out


class ClefHostedJudge(_HostedDecisionJudge):
    """Clef / Clef-flash on Workers AI: a System One request at `/ai/run/@cf/...`."""

    name = "clef-hosted"
    max_questions = CLEF_MAX_QUESTIONS

    def __init__(self, token: str | None = None, account: str | None = None,
                 model: str | None = None):
        self._token = token or os.environ.get("CLOUDFLARE_API_TOKEN", "")
        self._account = account or os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
        if not self._token or not self._account:
            raise RuntimeError("clef-hosted needs CLOUDFLARE_API_TOKEN and "
                               "CLOUDFLARE_ACCOUNT_ID")
        if not (self._account.isascii() and self._account.isalnum()):
            # it is written into the URL's path: only letters and digits, so it cannot
            # change the path or the host the token is sent to
            raise ValueError("CLOUDFLARE_ACCOUNT_ID must hold letters and digits only")
        self.model = (model or os.environ.get("CLEF_HOSTED_MODEL") or "clef-flash").strip()
        if self.model not in CLEF_MODELS:
            raise ValueError(f"CLEF_HOSTED_MODEL must be one of {', '.join(CLEF_MODELS)}, "
                             f"got {self.model!r}")
        self.model_id, self.price = CLEF_MODELS[self.model]
        self.per_request = _per_request("CLEF_HOSTED_QUESTIONS_PER_REQUEST")
        self.name = f"clef-hosted:{self.model}"
        self._override = clef_endpoint("CLEF_HOSTED_ENDPOINT")

    def describe(self) -> dict:
        return {"name": self.name, "provider": "hosted-api", "model": self.model,
                "model_id": self.model_id,
                **self._endpoint_provenance("api.cloudflare.com/client/v4/accounts/***/ai/run"),
                "criteria_version": CRITERIA_VERSION,
                "confidence_method": "P(chosen option), from the answer's per-option "
                                     "probabilities (yes/no: of the answer given)",
                "native_confidence": "the API's `confidence` field (\"derived from the "
                                     "probabilities\"); kept in raw as native_confidence, "
                                     "not audited",
                "temperature": "n/a",
                "questions_per_request": self.per_request or "all",
                "input_price_per_mtok_usd": self.price, "output_price_per_mtok_usd": 0.0,
                "sum_tolerance": "options x 0.5 x 10^-decimals (rounding)"}

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        body = {"model": self.model, "state": state,
                "questions": {q.name: systemone_question(q) for q in questions}}
        url = (fill_endpoint(self._override, "CLEF_HOSTED_ENDPOINT", account=self._account,
                             model_id=self.model_id)
               if self._override else
               CLEF_ENDPOINT.format(account=self._account, model_id=self.model_id))
        secrets = (self._token, self._account)
        t0 = time.monotonic()
        reply = post_json(url, body, "Workers AI", secrets)
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        result = reply.get("result")
        if not reply.get("success", True) or not isinstance(result, dict):
            errors = "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e)
                               for e in reply.get("errors") or [])
            raise RuntimeError(_redact(f"Workers AI refused the request: "
                                       f"{errors or 'no result'}", secrets))
        answers = result.get("answers") or {}
        usage = result.get("usage") or None
        cost = self._share(self._cost(usage), len(questions))     # billed whatever the answers
        served = served_of({"model": result.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            base = {**kept_reply(ans, usage, CLEF_ANSWER, q), "served": served}
            if isinstance(ans, dict) and isinstance(ans.get("probabilities"), dict):
                base.update(declared_sum(ans["probabilities"].values()))
            if not isinstance(ans, dict) or "error" in ans:
                out.append(_no_answer(q, latency, cost, base, secrets))
                continue
            probs = ans.get("probabilities")
            chosen = ans.get("choice")
            got = read_checked(q, ans.get("type", ""),
                               {str(k): v for k, v in probs.items()} if isinstance(probs, dict)
                               else {}, ans.get("noul"),
                               None if chosen is None else str(chosen))
            if isinstance(got, str):
                out.append(_no_answer(q, latency, cost,
                                      {**base, "invalid": safe_reason(got, q)}, secrets))
                continue
            decision, confidence, checked = got
            if decision == UNSENT:
                base["invalid"] = UNSENT_REASON
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw=evidence({**base,
                                              "probabilities": kept_probabilities(checked, q),
                                              "native_confidence": kept_fields(
                                                  ans.get("confidence"), NUMBER,
                                                  "native_confidence", [])}, secrets)))
        return out


# Microsoft-Decision-1 through OpenRouter's Decisions route (alpha), checked 2026-10-12: one
# endpoint, served version `microsoft/microsoft-decision-1-20261009`, context 32,768 tokens,
# $0.042 per million input tokens, output not billed, no sampling parameter.
MICROSOFT_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MICROSOFT_MODEL = "microsoft/microsoft-decision-1"
MICROSOFT_VERSION = "microsoft/microsoft-decision-1-20261009"
MICROSOFT_ROUTE_PROVIDER = "azure"          # OpenRouter's slug for the model's one endpoint
MICROSOFT_PRICE_PER_MTOK = 0.042
MICROSOFT_MAX_INPUT_TOKENS = 32_768
# A heuristic pre-send bound: a request whose text (state, instructions, options) is over
# 4 UTF-8 bytes per token of context is withheld without a call. Text that long is past the
# context in most languages; a row under the bound that is still too long is caught by the
# route's own refusal or by the input tokens it reports. The tokenizer is not public, so no
# exact count is made before sending.
MICROSOFT_MAX_REQUEST_BYTES = 4 * MICROSOFT_MAX_INPUT_TOKENS
MICROSOFT_ANSWER = {**CLEF_ANSWER, "refusal": BOOL}
OVER_LENGTH = "max_length_exceeded"
# OpenRouter's own context-length error, and nothing broader: any other 400 or 413 (a schema,
# quota or size error) stops the run rather than be counted as the judge's over-length row.
# Both must hold: the error is the route's (JSON `error.message` opening with its sentence,
# the limit 32,768 and the count it read larger; `error.code`, when given, the status), and
# the request is long enough to have filled the context: each token is at least one byte of
# text, so a request under half the context in bytes cannot, whatever the route adds to it.
OVER_CONTEXT_STATUS = (400, 413)
_OVER_CONTEXT = re.compile(r"This endpoint's maximum context length is (\d+) tokens\. "
                           r"However, you requested about (\d+) tokens\b")
MICROSOFT_MIN_OVER_LENGTH_BYTES = MICROSOFT_MAX_INPUT_TOKENS // 2


def route_over_context(e: HostedHTTPError, size: int) -> bool:
    """Whether `e` is the route's context-length refusal of a request of `size` bytes."""
    if e.status not in OVER_CONTEXT_STATUS or size < MICROSOFT_MIN_OVER_LENGTH_BYTES:
        return False
    try:
        err = json.loads(e.body).get("error")
    except (ValueError, AttributeError):
        return False
    if not isinstance(err, dict) or not isinstance(err.get("message"), str):
        return False
    code = err.get("code")
    if code is not None and (isinstance(code, bool) or code != e.status):
        return False
    m = _OVER_CONTEXT.match(err["message"])
    if m is None:
        return False
    return int(m.group(1)) == MICROSOFT_MAX_INPUT_TOKENS \
        and int(m.group(2)) >= MICROSOFT_MAX_INPUT_TOKENS


class MicrosoftDecisionJudge(_HostedDecisionJudge):
    """Microsoft-Decision-1 through OpenRouter's Decisions route (`POST /api/alpha/decisions`):
    a System One request, the provider pinned without fallback, the served version checked."""

    name = "microsoft-decision"
    price = MICROSOFT_PRICE_PER_MTOK
    max_input_tokens = MICROSOFT_MAX_INPUT_TOKENS
    over_length_advice = ("shorten the state or the options: Microsoft-Decision-1 reads at "
                          f"most {MICROSOFT_MAX_INPUT_TOKENS:,} tokens per request")

    def __init__(self, api_key: str | None = None):
        self._key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self._key:
            raise RuntimeError("OPENROUTER_API_KEY is not set (Microsoft-Decision-1 through "
                               "OpenRouter)")
        version = (os.environ.get("MICROSOFT_DECISION_VERSION") or MICROSOFT_VERSION).strip()
        if model_id(version) != version:
            raise ValueError("MICROSOFT_DECISION_VERSION must be a plain model id such as "
                             f"{MICROSOFT_VERSION}")
        self.version = version
        self.model = MICROSOFT_MODEL
        self.per_request = 1
        self._override = endpoint_override("MICROSOFT_DECISION_ENDPOINT")
        self.endpoint = self._override.url if self._override else MICROSOFT_ENDPOINT

    def describe(self) -> dict:
        return {"name": self.name, "provider": "hosted-api", "model": self.model,
                "served_version": self.version, "route": "openrouter",
                "route_provider": MICROSOFT_ROUTE_PROVIDER, "allow_fallbacks": False,
                **self._endpoint_provenance(MICROSOFT_ENDPOINT),
                "criteria_version": CRITERIA_VERSION,
                "confidence_method": "P(chosen option), from the answer's per-option "
                                     "probabilities (yes/no: of the answer given)",
                "native_confidence": "the route's `confidence` field, not defined as "
                                     "P(chosen option); kept in raw as native_confidence, "
                                     "not audited",
                "temperature": "n/a",
                "questions_per_request": 1,
                "max_input_tokens": self.max_input_tokens,
                "max_request_bytes": MICROSOFT_MAX_REQUEST_BYTES,
                "min_over_length_bytes": MICROSOFT_MIN_OVER_LENGTH_BYTES,
                "input_price_per_mtok_usd": self.price, "output_price_per_mtok_usd": 0.0,
                "sum_tolerance": "options x 0.5 x 10^-decimals (rounding)"}

    def _over_length(self, q: Question, latency: float, cost: float | None, problem: str,
                     extra: dict | None = None) -> Judgment:
        """No answer for a request the route would not read whole (`max_length_exceeded`):
        counted against the judge, never truncated and answered."""
        return _no_answer(q, latency, cost, {**(extra or {}), "error": OVER_LENGTH,
                                             "max_len": self.max_input_tokens,
                                             "problems": [problem]}, (self._key,))

    def _check_served(self, reply: dict) -> None:
        """Stop unless the reply says it was served by the pinned version and provider: a
        judgment is never recorded under a version it was not made by."""
        served = model_id(reply.get("model"))
        provider = model_id(reply.get("provider"))
        if served != self.version or (provider or "").lower() != MICROSOFT_ROUTE_PROVIDER:
            # masked here, whatever the caller does: a server can echo the key as an id
            raise RuntimeError(_redact(
                f"Microsoft-Decision-1 was served as {served or 'an unnamed model'} by "
                f"{provider or 'an unnamed provider'}, not the pinned {self.version} by "
                f"{MICROSOFT_ROUTE_PROVIDER}; nothing was recorded for this row. Set "
                "MICROSOFT_DECISION_VERSION to pin another version on purpose",
                (self._key,)))

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        (q,) = questions                                  # one question per request
        body = {"model": self.model,
                "provider": {"order": [MICROSOFT_ROUTE_PROVIDER], "allow_fallbacks": False},
                "state": state, "questions": {q.name: systemone_question(q)}}
        secrets = (self._key,)
        size = len(json.dumps({"state": state, "questions": body["questions"]},
                              ensure_ascii=False).encode())
        if size > MICROSOFT_MAX_REQUEST_BYTES:            # withheld, never sent: costs nothing
            return [self._over_length(q, 0.0, 0.0,
                                      f"the request text is {size} UTF-8 bytes, over the "
                                      f"pre-send bound of {MICROSOFT_MAX_REQUEST_BYTES} bytes")]
        t0 = time.monotonic()
        try:
            reply = post_json(self.endpoint, body, "OpenRouter's Decisions route", secrets)
        except HostedHTTPError as e:
            if route_over_context(e, size):
                # refused before it was read; whether it was billed is not known
                return [self._over_length(q, time.monotonic() - t0, None,
                                          f"the route refused the request as over length "
                                          f"(HTTP {e.status})")]
            raise
        latency = time.monotonic() - t0
        if not isinstance(reply, dict):
            raise RuntimeError("OpenRouter's Decisions route returned no JSON object")
        self._check_served(reply)
        answers = reply.get("answers")
        ans = answers.get(q.name) if isinstance(answers, dict) else None
        usage = reply.get("usage") or None
        cost = self._cost(usage)                              # billed whatever the answer
        dropped: list[str] = []
        base = {**kept_reply(ans, usage, MICROSOFT_ANSWER, q),
                "served": served_of({"model": reply.get("model")}),
                "served_provider": kept_fields(reply.get("provider"), ID, "provider", dropped),
                "response_id": kept_fields(reply.get("id"), ID, "response_id", dropped),
                "reported_cost_usd": kept_fields(usage.get("cost") if isinstance(usage, dict)
                                                 else None, NUMBER, "usage.cost", [])}
        # (a `usage.cost` that is not a number is counted once, by the usage record above)
        if isinstance(ans, dict) and isinstance(ans.get("probabilities"), dict):
            base.update(declared_sum(ans["probabilities"].values()))
        with_dropped(base, dropped)
        tokens = count(usage.get("input_tokens")) if isinstance(usage, dict) else None
        if tokens is not None and tokens >= self.max_input_tokens:
            # at or past the context: what was read whole cannot be told from what was cut
            return [self._over_length(q, latency, cost,
                                      f"the route reports {tokens} input tokens, at or over "
                                      f"its context of {self.max_input_tokens}", base)]
        if isinstance(ans, dict) and ans.get("error") == OVER_LENGTH:
            return [self._over_length(q, latency, cost,
                                      "the route refused the question as over length", base)]
        refused = isinstance(ans, dict) and (ans.get("type") == "refusal"
                                             or ans.get("refusal") is True)
        if not isinstance(ans, dict) or "error" in ans or refused:
            return [_no_answer(q, latency, cost, {**base, "refusal": refused}, secrets)]
        chosen = ans.get("choice")
        if q.type is QuestionType.CHOICE and (chosen is None or str(chosen).strip() == ""):
            return [_no_answer(q, latency, cost, {**base, "blank": True}, secrets)]
        probs = ans.get("probabilities")
        got = read_checked(q, ans.get("type", ""),
                           {str(k): v for k, v in probs.items()} if isinstance(probs, dict)
                           else {}, ans.get("noul"), None if chosen is None else str(chosen))
        if isinstance(got, str):
            return [_no_answer(q, latency, cost, {**base, "invalid": safe_reason(got, q)},
                               secrets)]
        decision, confidence, checked = got
        if decision == UNSENT:
            base["invalid"] = UNSENT_REASON
        return [Judgment(question=q.name, decision=decision, confidence=confidence,
                         latency_s=latency, cost_usd=cost,
                         raw=evidence({**base, "probabilities": kept_probabilities(checked, q),
                                       "native_confidence": kept_fields(
                                           ans.get("confidence"), NUMBER,
                                           "native_confidence", [])}, secrets))]
