"""Pluggable judge interface. Anything that maps (state, questions) -> judgments fits."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class QuestionType(str, Enum):
    CHOICE = "choice"   # pick one of options
    SCORE = "score"     # rate against ordered levels
    NOUL = "noul"       # probability a yes/no claim is true


@dataclass
class Question:
    name: str
    type: QuestionType
    instructions: str
    options: list[str] = field(default_factory=list)  # for CHOICE
    # Optional option -> human description. Judges that accept per-option
    # criteria (Jev via the AI SDK) receive these instead of the bare label.
    descriptions: dict[str, str] = field(default_factory=dict)


@dataclass
class Judgment:
    question: str
    decision: str             # the chosen option / level / "true"/"false"
    confidence: float | None  # 0..1 when declared; None when unknown
    latency_s: float = 0.0
    cost_usd: float | None = 0.0
    raw: dict = field(default_factory=dict)
    parse_status: str = "parsed"  # parsed | no_answer | no_confidence


class Judge:
    """Implement decide(); judge-audit handles the rest."""

    name: str = "judge"

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        raise NotImplementedError

    def describe(self) -> dict:
        """Metadata recorded in every audit (model, backend, version...)."""
        return {"name": self.name}
