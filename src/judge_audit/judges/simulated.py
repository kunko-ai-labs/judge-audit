"""SIMULATED judge for demos — explicitly a simulator, not a judge.

It is given the ground-truth labels up front (like any simulator owns its
data-generating process) and models observable behavior: reported confidence
tracks true correctness probability, mimicking the published Jev
email-benchmark pattern (high confidence ≈ always right, low confidence ≈
coin flip).

NEVER present its output as a real vendor audit. Every artifact it touches
must carry the SIMULATED tag.
"""
from __future__ import annotations

import hashlib
import random

from .base import Judge, Judgment, Question

SIMULATED_TAG = "SIMULATED — not a real vendor audit"


class SimulatedJudge(Judge):
    name = "simulated"

    def __init__(self, rows: list[dict] | None = None, seed: int = 7,
                 latency_s: float = 0.35, cost_per_1k: float = 0.08):
        self.seed = seed
        self.latency_s = latency_s
        self.cost_per_1k = cost_per_1k
        # oracle: (state, question) -> true label. A simulator owns its world.
        self.oracle: dict[tuple[str, str], str] = {}
        for r in rows or []:
            for qname, label in r.get("labels", {}).items():
                self.oracle[(r["state"], qname)] = str(label)

    def describe(self) -> dict:
        # No model and no sampling: the seed is what makes this run reproducible.
        return {"name": self.name, "seed": self.seed, "temperature": "n/a",
                "tag": SIMULATED_TAG}

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        out: list[Judgment] = []
        for q in questions:
            # stable seed from content (hash() is salted per-process — not reproducible)
            digest = hashlib.sha256(f"{self.seed}|{state}|{q.name}".encode()).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            p_correct = rng.betavariate(9, 1.5)  # skews high; some items are hard
            true_label = self.oracle.get((state, q.name))
            options = q.options or ["true", "false"]
            if true_label is not None and rng.random() < p_correct:
                decision = true_label
            else:
                wrong = [o for o in options if o != true_label] or options
                decision = rng.choice(wrong)
            confidence = max(0.01, min(0.999, p_correct + rng.gauss(0, 0.04)))
            out.append(Judgment(
                question=q.name, decision=decision, confidence=confidence,
                latency_s=self.latency_s * rng.uniform(0.7, 1.6),
                cost_usd=self.cost_per_1k / 1000,
                raw={"simulated": True, "tag": SIMULATED_TAG},
            ))
        return out
