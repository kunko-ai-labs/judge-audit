"""Hosted decision models behind an HTTP API: the OpenAI Decisions API (`openai-decisions`)
and Clef / Clef-flash on Workers AI (`clef-hosted`).

Both take a state and typed questions and return a probability per option. What is recorded,
and why:

- **Confidence is the probability of the chosen option**, read from the answer's per-option
  probabilities, as for every decision model here. Each API also returns its own
  `confidence` field, which it does not define as that probability (the Decisions API's
  documented example has 0.93 next to a top probability of 0.95; Workers AI says "derived
  from the probabilities"); it is kept in `raw.native_confidence` and never audited in its
  place. An answer without probabilities is no answer: a confidence is never invented.
- **One question per request by default.** Several questions may share a request
  (`*_QUESTIONS_PER_REQUEST=all`); other decision models have changed an answer with the
  other questions of the request, so sharing is opt-in and recorded.
- **Cost from the tokens the response reports**, at the documented price. A response that
  reports none has an unknown cost (`None`), never a count guessed with another tokenizer.
- **What was served**: any model id and response id the response carries.
- **Credentials from the environment only**; no key, token or account id is recorded or
  printed, and an HTTP error is reported by status and the server's message.

Environment:
  openai-decisions  OPENAI_API_KEY; DECISIONS_MODEL (default gpt-6-luna);
                    DECISIONS_QUESTIONS_PER_REQUEST (1 | all, default 1)
  clef-hosted       CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID; CLEF_HOSTED_MODEL
                    (clef-flash | clef, default clef-flash);
                    CLEF_HOSTED_QUESTIONS_PER_REQUEST (1 | all, default 1)
  both              HOSTED_MIN_INTERVAL_S (seconds between calls, default 0)
"""
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request

from .base import Judge, Judgment, Question, QuestionType, served_of
from .systemone import CRITERIA_VERSION, read_answer, systemone_question

DECISIONS_ENDPOINT = "https://api.openai.com/v1/decisions"
DECISIONS_MODEL = "gpt-6-luna"
DECISIONS_PRICE_PER_MTOK = 0.10        # input; output is not billed (2026-10-07)

CLEF_ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model_id}"
# Workers AI model id and unit price per million input tokens (2026-10-07).
CLEF_MODELS = {"clef-flash": ("@cf/cloudflare/clef-flash", 0.09),
               "clef": ("@cf/cloudflare/clef", 0.24)}

RETRY_STATUS = (429, 500, 502, 503, 504, 529)
ATTEMPTS = 6
TIMEOUT_S = 120


def _per_request(env: str) -> int | None:
    """Questions per request: 1 (the default) or None for all of them."""
    value = os.environ.get(env, "1").strip().lower()
    if value == "all":
        return None
    if value == "1":
        return 1
    raise ValueError(f"{env} must be 1 or all, got {value!r}")


def post_json(url: str, body: dict, token: str, label: str) -> dict:
    """POST `body`, retrying a busy server with backoff; the reply's JSON. An error names the
    service (`label`) and the status, never the URL's account id or the token."""
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    last = ""
    for attempt in range(ATTEMPTS):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300].replace(token, "***")
            last = f"{e.code}: {detail}"
            if e.code not in RETRY_STATUS:
                raise RuntimeError(f"{label} returned {last}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = type(e).__name__
        time.sleep(min(2 ** attempt * 2 + random.uniform(0, 1), 60))
    # "rate-limited" is what scripts/audit_resumable.py looks for before sleeping.
    raise RuntimeError(f"rate-limited by {label} after {ATTEMPTS} attempts ({last})")


def _no_answer(q: Question, latency: float, raw: dict) -> Judgment:
    return Judgment(question=q.name, decision="", confidence=None, latency_s=latency,
                    cost_usd=0.0, raw=raw, parse_status="no_answer")


class _HostedDecisionJudge(Judge):
    """Batching, pacing and cost shared by the hosted decision APIs."""

    per_request: int | None = 1
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
        out: list[Judgment] = []
        for i in range(0, len(questions), size):
            self._pace()
            out += self._call(state, questions[i:i + size])
        return out

    def _cost(self, tokens) -> float | None:
        """Cost of one request from the input tokens it reports; None when it reports none."""
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
        self.per_request = _per_request("DECISIONS_QUESTIONS_PER_REQUEST")

    def describe(self) -> dict:
        return {"name": self.name, "provider": "hosted-api", "model": self.model,
                "endpoint": DECISIONS_ENDPOINT, "criteria_version": CRITERIA_VERSION,
                "confidence_method": "P(chosen option), from the answer's per-option "
                                     "probabilities (yes/no: of the answer given)",
                "native_confidence": "the API's `confidence` field, not defined by its "
                                     "documentation as P(chosen option); kept in raw as "
                                     "native_confidence, not audited",
                "temperature": "n/a",
                "questions_per_request": self.per_request or "all",
                "input_price_per_mtok_usd": self.price, "output_price_per_mtok_usd": 0.0}

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
    def read(q: Question, ans: dict) -> tuple[str, float, dict[str, float]]:
        """(decision, P(decision), probabilities) from one Decisions answer."""
        if q.type is QuestionType.NOUL:
            p = float(ans["probability"])
            return ("true" if p >= 0.5 else "false"), max(p, 1 - p), {"true": p,
                                                                      "false": 1 - p}
        probs = {str(x["value"]): float(x["probability"]) for x in ans["probabilities"]}
        if q.type is QuestionType.CHOICE:
            decision = str(ans["choice"])
            return decision, probs[decision], probs
        best = max(probs, key=lambda k: (probs[k], -int(k)))      # the first level on a tie
        return q.options[int(best)], probs[best], probs

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        body = {"model": self.model, "input": state,
                "questions": [self.wire_question(q) for q in questions]}
        t0 = time.monotonic()
        reply = post_json(DECISIONS_ENDPOINT, body, self._key, "the OpenAI Decisions API")
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        answers = {a.get("name"): a for a in reply.get("answers") or [] if isinstance(a, dict)}
        usage = reply.get("usage") or None
        tokens = (usage or {}).get("input_tokens")
        cost = self._share(self._cost(tokens), len(questions))
        served = served_of({"model": reply.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            base = {"answer": ans, "usage": usage, "served": served,
                    "response_id": reply.get("id")}
            if not isinstance(ans, dict) or ans.get("type") == "refusal":
                out.append(_no_answer(q, latency, {**base, "refusal": bool(
                    isinstance(ans, dict) and ans.get("type") == "refusal")}))
                continue
            try:
                decision, confidence, probs = self.read(q, ans)
            except (KeyError, ValueError, TypeError, IndexError):
                out.append(_no_answer(q, latency, base))
                continue
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw={**base, "probabilities": probs,
                                     "native_confidence": ans.get("confidence")}))
        return out


class ClefHostedJudge(_HostedDecisionJudge):
    """Clef / Clef-flash on Workers AI: a System One request at `/ai/run/@cf/...`."""

    name = "clef-hosted"

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

    def describe(self) -> dict:
        return {"name": self.name, "provider": "hosted-api", "model": self.model,
                "model_id": self.model_id, "criteria_version": CRITERIA_VERSION,
                "confidence_method": "P(chosen option), from the answer's per-option "
                                     "probabilities (yes/no: of the answer given)",
                "native_confidence": "the API's `confidence` field (\"derived from the "
                                     "probabilities\"); kept in raw as native_confidence, "
                                     "not audited",
                "temperature": "n/a",
                "questions_per_request": self.per_request or "all",
                "input_price_per_mtok_usd": self.price, "output_price_per_mtok_usd": 0.0}

    def _call(self, state: str, questions: list[Question]) -> list[Judgment]:
        body = {"model": self.model, "state": state,
                "questions": {q.name: systemone_question(q) for q in questions}}
        url = CLEF_ENDPOINT.format(account=self._account, model_id=self.model_id)
        t0 = time.monotonic()
        reply = post_json(url, body, self._token, "Workers AI")
        latency = (time.monotonic() - t0) / max(len(questions), 1)
        if not reply.get("success", True) or not isinstance(reply.get("result"), dict):
            errors = "; ".join(str(e.get("message", e)) for e in reply.get("errors") or [])
            raise RuntimeError(f"Workers AI refused the request: {errors or 'no result'}")
        result = reply["result"]
        answers = result.get("answers") or {}
        usage = result.get("usage") or None
        cost = self._share(self._cost((usage or {}).get("input_tokens")), len(questions))
        served = served_of({"model": result.get("model")})
        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name)
            base = {"answer": ans, "usage": usage, "served": served}
            if not isinstance(ans, dict) or "error" in ans:
                out.append(_no_answer(q, latency, base))
                continue
            try:
                decision, confidence, probs = read_answer(q, ans)
            except (KeyError, ValueError, TypeError, IndexError):
                out.append(_no_answer(q, latency, base))
                continue
            out.append(Judgment(question=q.name, decision=decision, confidence=confidence,
                                latency_s=latency, cost_usd=cost,
                                raw={**base, "probabilities": probs,
                                     "native_confidence": ans.get("confidence")}))
        return out
