"""TypeSafe Jev judge adapter.

Jev is an *evaluation* model, not a chat model: it answers typed Choice /
Score / Boolean questions with calibrated probabilities instead of text.

Two backends:
  - "gateway"  (default): via Vercel AI Gateway + AI SDK `evaluate` API.
                 Needs a Vercel AI Gateway API key (AI_GATEWAY_API_KEY).
                 Jev is NOT reachable via /v1/chat/completions.
  - "typesafe": direct TypeSafe API (https://api.typesafe.ai/v1/systemone).
                 Needs TYPESAFE_API_KEY (waitlist).

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
import urllib.request
from pathlib import Path

from .base import Judge, Judgment, Question, QuestionType

TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
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

    def __init__(self, api_key: str | None = None, model: str = "typesafe-ai/jev",
                 backend: str = "gateway"):
        self.backend = backend
        self.model = model
        if backend == "gateway":
            self.api_key = api_key or os.environ.get("AI_GATEWAY_API_KEY", "")
            if not self.api_key:
                raise RuntimeError(
                    "Set AI_GATEWAY_API_KEY (Vercel dashboard → AI Gateway → API Keys). "
                    "Jev is only reachable through the gateway's evaluation API.")
            if not _BRIDGE.exists():
                raise RuntimeError(f"evaluate bridge not found: {_BRIDGE}")
        elif backend == "typesafe":
            self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
            if not self.api_key:
                raise RuntimeError("Set TYPESAFE_API_KEY (waitlist: https://typesafe.ai)")
        else:
            raise ValueError(f"unknown backend '{backend}' (gateway | typesafe)")

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
                    time.sleep(min(2 ** attempt * 3 + random.uniform(0, 2), 90))
                    _throttle()
                    continue
                raise RuntimeError(f"jev bridge failed: {last_err}")
            (res,) = json.loads(proc.stdout.decode())
            if not res.get("ok"):
                last_err = str(res.get("error"))
                if _is_rate_limit(last_err):
                    time.sleep(min(2 ** attempt * 3 + random.uniform(0, 2), 90))
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
            base["criteria"] = {opt: opt for opt in q.options}
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
        payload = {
            "model": self.model,
            "state": state,
            "questions": {
                q.name: {
                    "type": q.type.value,
                    "instructions": q.instructions,
                    **({"options": q.options} if q.options else {}),
                }
                for q in questions
            },
        }
        req = urllib.request.Request(
            TYPESAFE_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
        )
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.load(resp)
        latency = time.monotonic() - t0

        out: list[Judgment] = []
        for q in questions:
            ans = body.get(q.name, {})
            decision, confidence = self._parse_direct(q, ans)
            in_tok = body.get("usage", {}).get("input_tokens", 0)
            out.append(Judgment(
                question=q.name, decision=decision, confidence=confidence,
                latency_s=latency / max(len(questions), 1),
                cost_usd=in_tok / 1e6 * INPUT_PRICE_PER_MTOK,
                raw=ans,
            ))
        return out

    @staticmethod
    def _parse_direct(q: Question, ans: dict) -> tuple[str, float]:
        if q.type is QuestionType.NOUL:
            p = float(ans.get("noul", 0.5))
            return ("true" if p >= 0.5 else "false"), max(p, 1 - p)
        if q.type is QuestionType.CHOICE:
            probs = ans.get("probabilities", {}) or {}
            best = max(probs, key=lambda k: probs[k]) if probs else ""
            return best, float(ans.get("confidence", probs.get(best, 0.0) if best else 0.0))
        return str(ans.get("score", ans.get("level", ""))), float(ans.get("confidence", 0.5))
