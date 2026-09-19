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
