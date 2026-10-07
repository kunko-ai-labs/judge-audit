"""Hosted decision models behind an HTTP API: the OpenAI Decisions API (`openai-decisions`)
and Clef / Clef-flash on Workers AI (`clef-hosted`).

Both take a state and typed questions and return a probability per option. What is recorded,
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
- **Credentials from the environment only.** No key, token or account id is recorded or
  printed: every error message passes through `_redact`, which masks the token, the account
  id and the URL segment that holds it. A server that cannot be reached is reported within
  `CONNECT_BUDGET_S`.

Environment:
  openai-decisions  OPENAI_API_KEY; DECISIONS_MODEL (default gpt-6-luna);
                    DECISIONS_QUESTIONS_PER_REQUEST (1 | all, default 1)
  clef-hosted       CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID; CLEF_HOSTED_MODEL
                    (clef-flash | clef, default clef-flash);
                    CLEF_HOSTED_QUESTIONS_PER_REQUEST (1 | all, default 1)
  both              HOSTED_MIN_INTERVAL_S (seconds between calls, default 0);
                    DECISIONS_ENDPOINT, CLEF_HOSTED_ENDPOINT (another server speaking the
                    same API, e.g. a proxy; CLEF_HOSTED_ENDPOINT may hold {model_id})
"""
from __future__ import annotations

import json
import math
import os
import random
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
    redact,
    served_of,
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

RETRY_STATUS = (429, 500, 502, 503, 504, 529)
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


def post_json(url: str, body: dict, label: str, secrets: tuple[str, ...]) -> dict:
    """POST `body` with the first secret as the bearer token; the reply's JSON. A busy server
    (429, 5xx) is retried with backoff; one that cannot be reached is retried within
    `CONNECT_BUDGET_S`. Every error names the service (`label`) and the status, with the
    secrets and the account segment of the URL masked."""
    data = json.dumps(body, allow_nan=False).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {secrets[0]}"}
    last, waited, unreachable = "", 0.0, False
    for attempt in range(ATTEMPTS):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with OPENER.open(req, timeout=TIMEOUT_S) as resp:      # refuses redirects
                return json.load(resp)
        except urllib.error.HTTPError as e:
            last = _redact(f"{e.code}: {e.read().decode(errors='replace')}", secrets)[:300]
            unreachable = False
            if e.code not in RETRY_STATUS:
                raise RuntimeError(f"{label} returned {last}") from None
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


def _no_answer(q: Question, latency: float, cost: float | None, raw: dict) -> Judgment:
    return Judgment(question=q.name, decision="", confidence=None, latency_s=latency,
                    cost_usd=cost, raw=as_evidence(raw), parse_status="no_answer")


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
        reply = post_json(self.endpoint, body, "the OpenAI Decisions API", (self._key,))
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = {a.get("name"): a for a in reply.get("answers") or [] if isinstance(a, dict)}
        usage = reply.get("usage") or None
        cost = self._share(self._cost(usage), len(questions))     # billed whatever the answers
        served = served_of({"model": reply.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            base = {"answer": ans, "usage": usage, "served": served,
                    "response_id": reply.get("id")}
            if isinstance(ans, dict) and isinstance(ans.get("probabilities"), list):
                base.update(declared_sum(x.get("probability") for x in ans["probabilities"]
                                         if isinstance(x, dict)))
            if not isinstance(ans, dict) or ans.get("type") == "refusal":
                refused = isinstance(ans, dict) and ans.get("type") == "refusal"
                out.append(_no_answer(q, latency, cost, {**base, "refusal": refused}))
                continue
            got = self.read(q, ans)
            if isinstance(got, str):
                out.append(_no_answer(q, latency, cost, {**base, "invalid": got}))
                continue
            decision, confidence, probs = got
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw=as_evidence({**base, "probabilities": probs,
                                                 "native_confidence": ans.get("confidence")})))
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
            base = {"answer": ans, "usage": usage, "served": served}
            if isinstance(ans, dict) and isinstance(ans.get("probabilities"), dict):
                base.update(declared_sum(ans["probabilities"].values()))
            if not isinstance(ans, dict) or "error" in ans:
                out.append(_no_answer(q, latency, cost, base))
                continue
            probs = ans.get("probabilities")
            chosen = ans.get("choice")
            got = read_checked(q, ans.get("type", ""),
                               {str(k): v for k, v in probs.items()} if isinstance(probs, dict)
                               else {}, ans.get("noul"),
                               None if chosen is None else str(chosen))
            if isinstance(got, str):
                out.append(_no_answer(q, latency, cost, {**base, "invalid": got}))
                continue
            decision, confidence, checked = got
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw=as_evidence({**base, "probabilities": checked,
                                                 "native_confidence": ans.get("confidence")})))
        return out
