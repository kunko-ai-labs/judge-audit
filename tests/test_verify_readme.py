"""The README tables must be the committed JSON, rounded — and the check must notice an edit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_readme import ROOT, check, rounded  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_committed_readme_matches_its_json():
    ck = check(README)
    assert ck.failures == []
    assert ck.checked > 250  # three tables, every numeric cell


def edit(old: str, new: str) -> str:
    assert README.count(old) >= 1, old
    return README.replace(old, new, 1)


@pytest.mark.parametrize(
    "old,new",
    [
        ("| Gemini 3 Flash | verbalized | 97.0%", "| Gemini 3 Flash | verbalized | 97.1%"),
        ("| DeepSeek R1 | verbalized | 80.5% [74.8, 85.6] | 0.127",
         "| DeepSeek R1 | verbalized | 80.5% [74.8, 85.6] | 0.128"),
        ("| Llama 3.3 70B | verbalized | 90.5% [86.1, 94.5]",
         "| Llama 3.3 70B | verbalized | 90.5% [86.1, 94.6]"),
    ],
)
def test_a_one_digit_edit_is_caught(old, new):
    assert check(edit(old, new)).failures


def test_a_dropped_exact_interval_mark_is_caught():
    row = ("| Gemini 3 Flash | verbalized | 97.0% [94.5, 99.0] | 0.015 [0.002, 0.040] "
           "| **0%** [0.0, 1.8]†")
    failures = check(edit(row, row[:-1])).failures
    assert any("Gemini" in f and "†" in f for f in failures)


def test_an_unknown_row_is_an_error_not_a_skip():
    row = "| Gemini 3 Flash | verbalized |"
    failures = check(edit(row, "| Gemini 9 Ultra | verbalized |")).failures
    assert any("unknown judge row 'Gemini 9 Ultra'" in f for f in failures)


@pytest.mark.parametrize(
    "value,shown,pct,ok",
    [
        (0.97, "97.0%", True, True),
        (0.9712, "97.1%", True, True),
        (0.9704, "97.1%", True, False),
        (0.0149, "0.015", False, True),
        (0.0149, "0.014", False, False),
    ],
)
def test_rounding_accepts_only_the_printed_precision(value, shown, pct, ok):
    text = shown.rstrip("%")
    assert (text in rounded(value, text, pct)) is ok
