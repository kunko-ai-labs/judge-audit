from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture
def labels_path(tmp_path: Path) -> Path:
    rows = [
        {"state": f"email {i}: please send a quote for {i} units",
         "questions": [{"name": "category", "type": "choice", "instructions": "classify",
                        "options": ["quote_request", "spam"]}],
         "labels": {"category": "quote_request"},
         "_meta": {"synthetic": True}}
        for i in range(12)
    ]
    p = tmp_path / "labels.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p



# Every family's environment prefix: the over-length warning of one family names none of the
# others' (a decider run must never be told to raise LAYA_MAX_LEN).
FAMILY_VARIABLES = ("LAYA_", "DECIDER_", "STRANDS_", "CLEF_", "DECISION2_")


@pytest.fixture
def over_length_warning():
    """judge -> the NotSentWarning of a one-row run whose only question it withholds, and
    the family prefixes it names."""
    from judge_audit.runner import NotSentWarning, run_audit
    rows = [{"state": "long", "labels": {"route": "billing"},
             "questions": [{"name": "route", "type": "choice", "instructions": "Which team?",
                            "options": ["billing", "sales"]}]}]

    def warning_of(judge) -> tuple[str, set[str]]:
        with pytest.warns(NotSentWarning) as caught:
            result = run_audit(judge, rows, ci=False)
        assert result.not_sent == 1
        (w,) = [w for w in caught if w.category is NotSentWarning]
        message = str(w.message)
        return message, {v for v in FAMILY_VARIABLES if v in message}
    return warning_of
