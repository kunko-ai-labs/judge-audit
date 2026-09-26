"""The distinct-text robustness report: the dedup rule and the headline verdict."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from distinct_report import first_of_each_text, headline, mix, segments, shifts  # noqa: E402


def test_the_first_row_of_each_text_is_kept_in_file_order():
    rows = [{"state": "a"}, {"state": "b"}, {"state": "a"}, {"state": "c"}, {"state": "b"}]
    assert first_of_each_text(rows) == {0, 1, 3}


def test_router_segments_count_injected_rows_apart():
    rows = [{"_meta": {"difficulty": "easy"}}, {"_meta": {"difficulty": "hard"}},
            {"_meta": {"difficulty": "easy", "adversarial": True}}]
    assert segments(rows, range(3)) == {"easy": 1, "hard": 1, "injected": 1}


def test_the_headline_verdict_follows_the_intervals():
    def judge(zec, ci, method="bootstrap"):
        return {"distinct": {"zero_error_coverage": zec, "zero_error_coverage_ci": ci,
                             "zero_error_coverage_ci_method": method}}
    apart = headline({"gemini-3-flash": judge(0.0, [0.0, 0.019], "clopper-pearson"),
                      "jev": judge(0.72, [0.66, 0.94])})
    assert apart["separated"] is True
    overlap = headline({"gemini-3-flash": judge(0.0, [0.0, 0.7]),
                        "jev": judge(0.72, [0.66, 0.94])})
    assert overlap["separated"] is False


def test_the_committed_report_says_the_headline_holds_on_distinct_texts():
    data = json.loads((ROOT / "docs" / "robustness-distinct-2026-09.json").read_text())
    assert data["email-adversarial"]["distinct_texts"] == 189
    assert data["headline"]["separated"] is True
    md = (ROOT / "docs" / "robustness-distinct-2026-09.md").read_text()
    assert "The README headline holds on distinct texts" in md


def test_the_mix_of_every_dataset_is_reported_and_its_largest_shifts_named():
    rows = [{"labels": {"category": c}} for c in ["spam", "spam", "order", "order"]]
    m = {"all": mix("email-clean", rows, range(4)), "distinct": mix("email-clean", rows, [0, 2, 3])}
    assert m["all"] == {"order": 2, "spam": 2} and shifts(m) == "spam 2→1"
