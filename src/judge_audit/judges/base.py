"""Pluggable judge interface. Anything that maps (state, questions) -> judgments fits."""
from __future__ import annotations

import re
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


# Shapes a credential takes in a server's error text, masked whatever its value: a bearer or
# Authorization header value, an `sk-…` key, a `key=` / `api_key=` / `token=` query value, and
# the account segment of a Workers AI URL.
_SECRET_SHAPES = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*)(?:bearer\s+)?[A-Za-z0-9._~+/=-]{8,}"),
     r"\1***"),
    (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1***"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)([?&;\s](?:api[_-]?key|key|token|access_token)=)[^&\s'\"]+"), r"\1***"),
    (re.compile(r"(/accounts/)[^/\s'\"]+"), r"\1***"),
)


def redact(text: str, *secrets: str | None) -> str:
    """`text` with every credential masked before it leaves a judge: each of `secrets` (the
    key, token or account id the judge holds) wherever it appears, then any value shaped like
    one (`_SECRET_SHAPES`), whatever server sent it. Every judge's error paths use it."""
    for s in sorted((x for x in secrets if x and len(x) >= 4), key=len, reverse=True):
        text = text.replace(s, "***")
    for pattern, repl in _SECRET_SHAPES:
        text = pattern.sub(repl, text)
    return text


def served_of(reported: dict | None) -> dict:
    """What the provider said it served: model id and fingerprint as returned, None where it
    returned nothing — never the model name we asked for, which is what drift would hide."""
    reported = reported or {}
    return {"model": reported.get("model") or None,
            "system_fingerprint": reported.get("system_fingerprint") or None}


class Judge:
    """Implement decide(); judge-audit handles the rest."""

    name: str = "judge"
    # What to do when the judge withholds a question as over length (`raw.error`
    # max_length_exceeded); the runner's warning prints it. Adapters with budgets override it.
    over_length_advice: str = ("shorten the state or the options, or ask fewer questions "
                               "per row")

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        raise NotImplementedError

    def describe(self) -> dict:
        """Metadata recorded in every audit (model, backend, version...)."""
        return {"name": self.name}
