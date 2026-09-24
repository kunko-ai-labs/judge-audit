"""TypeSafe Jev judge adapter.

Jev is an *evaluation* model, not a chat model: it answers typed Choice /
Score / Boolean questions with calibrated probabilities instead of text.

Two backends:
  - "gateway"  (default): via the AI Gateway + AI SDK `evaluate` API.
                 Needs an AI Gateway API key (AI_GATEWAY_API_KEY).
                 Jev is NOT reachable via /v1/chat/completions.
  - "typesafe": direct TypeSafe HTTP API (https://api.typesafe.ai/v1/systemone).
                 Needs TYPESAFE_API_KEY (waitlist). Set JEV_ENDPOINT to point the
                 same client at any Jev-compatible server (OpenJev and friends
                 implement this API); the key is then optional.

The audited "confidence" is P(chosen option) from the per-option
probability distribution — the actual probabilistic claim. TypeSafe's
separate `confidence` statistic is preserved in `raw` for analysis.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .base import Judge, Judgment, Question, QuestionType

# Version of what the judge is shown: `_sdk_question` / `_direct_question`, the criteria
# map built from each question's options and descriptions. Jev has no text prompt, so this
# plays the role `prompt_sha256` plays for a chat model — bump it when that shape changes.
CRITERIA_VERSION = 1

TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DIRECT_MODEL = "jev-latest"
INPUT_PRICE_PER_MTOK = 0.042  # USD, per TypeSafe's published pricing (output free)

_BRIDGE = Path(__file__).with_name("bridge") / "jev_bridge.mjs"


class _RateLimited(RuntimeError):
    pass


# Minimum seconds between gateway calls (free tier is rate-limited per model).
_MIN_INTERVAL_S = float(os.environ.get("JEV_MIN_INTERVAL_S", "3.0"))
_last_call_ts = 0.0


def _throttle() -> None:
    global _last_call_ts
    now = time.monotonic()
    wait = _MIN_INTERVAL_S - (now - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.monotonic()


def _is_rate_limit(text: str) -> bool:
    t = text.lower()
    return "rate" in t and "limit" in t or "429" in t or "too many requests" in t


class JevJudge(Judge):
    name = "jev"

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 backend: str | None = None):
        self.backend = backend or os.environ.get("JEV_BACKEND", "gateway")
        self.model = model or os.environ.get("JEV_MODEL", "typesafe-ai/jev")
        if self.backend == "gateway":
            self.api_key = api_key or os.environ.get("AI_GATEWAY_API_KEY", "")
            if not self.api_key:
                raise RuntimeError(
                    "AI_GATEWAY_API_KEY is not set. Jev is only reachable through the "
                    "AI Gateway evaluate API (the gateway dashboard → API Keys). "
                    "See docs/real-audits.md. To try the harness without a key: "
                    "--judge simulated")
            if not _BRIDGE.exists():
                raise RuntimeError(f"evaluate bridge not found: {_BRIDGE}")
            if not (_BRIDGE.parent / "node_modules").exists():
                raise RuntimeError(
                    "the Node bridge has no dependencies installed. Run: "
                    f"npm install --prefix {_BRIDGE.parent}  (needs Node >= 20)")
        elif self.backend == "typesafe":
            self.endpoint = os.environ.get("JEV_ENDPOINT", TYPESAFE_ENDPOINT)
            self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
            if model is None and "JEV_MODEL" not in os.environ:
                self.model = DIRECT_MODEL
            if self.endpoint == TYPESAFE_ENDPOINT and not self.api_key:
                raise RuntimeError("TYPESAFE_API_KEY is not set (waitlist: https://typesafe.ai)")
            if self.endpoint != TYPESAFE_ENDPOINT:
                self.name = os.environ.get("JEV_NAME", "jev-compatible")
        else:
            raise ValueError(f"unknown backend '{self.backend}' (gateway | typesafe)")

    def describe(self) -> dict:
        d = {"name": self.name, "model": self.model, "backend": self.backend,
             "bridge": "ai-sdk/experimental_evaluate" if self.backend == "gateway"
             else "typesafe-systemone-http",
             # Jev takes no sampling temperature: it returns a distribution, not a sample.
             # It has no text prompt either — what it is shown is the criteria map below.
             "temperature": "n/a",
             "criteria_version": CRITERIA_VERSION,
             "input_price_per_mtok_usd": INPUT_PRICE_PER_MTOK}
        if self.backend == "typesafe":
            d["endpoint"] = self.endpoint
        return d

    # ------------------------------------------------------------------ public
    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        if self.backend == "gateway":
            return self._decide_gateway(state, questions)
        return self._decide_typesafe(state, questions)

    # ----------------------------------------------------------------- gateway
    def _decide_gateway(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {
            "items": [{
                "state": state,
                "questions": {q.name: self._sdk_question(q) for q in questions},
            }]
        }
        _throttle()  # free tier is rate-limited per model
        last_err = ""
        for attempt in range(6):
            t0 = time.monotonic()
            proc = subprocess.run(
                ["node", str(_BRIDGE)],
                input=json.dumps(payload).encode(),
                capture_output=True,
                timeout=120,
                env={**os.environ, "AI_GATEWAY_API_KEY": self.api_key,
                     "JEV_MODEL": self.model},
            )
            wall = time.monotonic() - t0
            if proc.returncode != 0:
                last_err = proc.stderr.decode()[-300:]
                if _is_rate_limit(last_err):
                    time.sleep(min(2 ** attempt * 10 + random.uniform(0, 5), 300))
                    _throttle()
                    continue
                raise RuntimeError(f"jev bridge failed: {last_err}")
            (res,) = json.loads(proc.stdout.decode())
            if not res.get("ok"):
                last_err = str(res.get("error"))
                if _is_rate_limit(last_err):
                    # Free-tier windows look long (minutes); back off hard.
                    time.sleep(min(2 ** attempt * 10 + random.uniform(0, 5), 300))
                    _throttle()
                    continue
                raise RuntimeError(f"jev evaluate error: {last_err}")
            break
        else:
            raise _RateLimited(f"jev still rate-limited after retries: {last_err[-200:]}")

        answers = res.get("answers") or {}
        meta = res.get("providerMetadata") or {}
        ts_meta = (meta.get("typesafe") or {}).get("confidence") or {}
        usage = res.get("usage") or {}
        latency = (res.get("latencyMs") or 0) / 1000.0 or wall
        in_tok = usage.get("inputTokens") or usage.get("input_tokens") or 0
        cost = in_tok / 1e6 * INPUT_PRICE_PER_MTOK

        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name) or {}
            decision, confidence = self._parse_sdk(q, ans)
            out.append(Judgment(
                question=q.name, decision=decision, confidence=confidence,
                latency_s=latency / max(len(questions), 1),
                cost_usd=cost / max(len(questions), 1),
                raw={"answer": ans,
                     "typesafe_confidence": ts_meta.get(q.name),
                     "usage": usage},
            ))
        return out

    @staticmethod
    def _sdk_question(q: Question) -> dict:
        base: dict = {"type": q.type.value, "instructions": q.instructions}
        if q.type is QuestionType.CHOICE and q.options:
            # AI SDK choice questions take a criteria map: option -> description.
            # Without descriptions the judge only sees the bare label, which is
            # exactly what the router ablation (docs/audit-jev-router.md) tests.
            base["criteria"] = {opt: q.descriptions.get(opt, opt) for opt in q.options}
        return base

    @staticmethod
    def _parse_sdk(q: Question, ans: dict) -> tuple[str, float]:
        if q.type is QuestionType.NOUL:
            p = float(ans.get("probability", 0.5))
            return ("true" if p >= 0.5 else "false"), max(p, 1 - p)
        if q.type is QuestionType.CHOICE:
            probs = ans.get("probabilities") or {}
            if probs:
                best = max(probs, key=lambda k: probs[k])
                return best, float(probs[best])
            # No distribution: fall back to the choice + TypeSafe confidence.
            return str(ans.get("choice", "")), float(ans.get("confidence", 0.5))
        # SCORE
        return str(ans.get("score", "")), float(ans.get("confidence", 0.5))

    # ----------------------------------------------------------------- direct
    def _decide_typesafe(self, state: str, questions: list[Question]) -> list[Judgment]:
        payload = {"model": self.model, "state": state,
                   "questions": {q.name: self._direct_question(q) for q in questions}}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(),
                                     headers=headers)
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (429, 503, 529):
                raise _RateLimited(f"{self.endpoint} returned {e.code}: {detail}") from e
            raise RuntimeError(f"{self.endpoint} returned {e.code}: {detail}") from e
        latency = time.monotonic() - t0
        answers = body.get("answers") or {}
        usage = body.get("usage") or {}
        in_tok = usage.get("input_tokens", 0)
        cost = in_tok / 1e6 * INPUT_PRICE_PER_MTOK if self.endpoint == TYPESAFE_ENDPOINT else 0.0

        out: list[Judgment] = []
        for q in questions:
            ans = answers.get(q.name) or {}
            decision, confidence = self._parse_direct(q, ans)
            out.append(Judgment(
                question=q.name, decision=decision, confidence=confidence,
                latency_s=latency / max(len(questions), 1),
                cost_usd=cost / max(len(questions), 1),
                raw={"answer": ans, "typesafe_confidence": ans.get("confidence"),
                     "usage": usage, "model": body.get("model")},
            ))
        return out

    @staticmethod
    def _direct_question(q: Question) -> dict:
        """Wire shape of https://docs.typesafe.ai/api: criteria carries the options."""
        base: dict = {"type": q.type.value, "instructions": q.instructions}
        if q.type is QuestionType.CHOICE and q.options:
            base["criteria"] = {opt: q.descriptions.get(opt) for opt in q.options}
        elif q.type is QuestionType.SCORE and q.options:
            base["criteria"] = list(q.options)
        return base

    @staticmethod
    def _parse_direct(q: Question, ans: dict) -> tuple[str, float]:
        if q.type is QuestionType.NOUL:
            p = float(ans.get("noul", 0.5))
            return ("true" if p >= 0.5 else "false"), max(p, 1 - p)
        probs = ans.get("probabilities") or {}
        if q.type is QuestionType.CHOICE:
            if probs:
                best = max(probs, key=lambda k: probs[k])
                return best, float(probs[best])
            return str(ans.get("choice", "")), float(ans.get("confidence", 0.5))
        # SCORE: probability-weighted value; confidence is P(most likely level)
        conf = float(max(probs.values())) if probs else float(ans.get("confidence", 0.5))
        return str(ans.get("score", "")), conf
