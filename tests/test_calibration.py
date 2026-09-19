"""Metrics on inputs whose answer is known by hand."""
from __future__ import annotations

import pytest

from judge_audit.metrics.calibration import (
    accuracy_coverage,
    expected_calibration_error,
    reliability_bins,
    zero_error_coverage,
)


def test_ece_is_zero_when_confidence_matches_accuracy_in_every_bin():
    # bin 0.7-0.8: four at 0.75, three correct -> acc 0.75 == avg conf
    conf = [0.75] * 4
    ok = [True, True, True, False]
    assert expected_calibration_error(conf, ok) == pytest.approx(0.0)


def test_ece_of_confident_and_always_wrong_is_the_confidence():
    conf = [0.9, 0.9, 0.9]
    ok = [False, False, False]
    assert expected_calibration_error(conf, ok) == pytest.approx(0.9)


def test_ece_is_weighted_by_bin_size():
    # 3 rows in bin 0.9-1.0 perfectly honest, 1 row at 0.5 wrong -> 0.25 * 0.5
    conf = [0.95, 0.95, 0.95, 0.5]
    ok = [True, True, True, False]
    # bin 0.9: acc 1.0 vs conf 0.95 -> gap 0.05 * 3/4 ; bin 0.5: gap 0.5 * 1/4
    assert expected_calibration_error(conf, ok) == pytest.approx(0.05 * 0.75 + 0.5 * 0.25)


def test_reliability_bins_put_confidence_one_in_the_top_bin():
    bins = reliability_bins([1.0, 0.0, 0.55], [True, False, True])
    assert bins[-1]["n"] == 1 and bins[-1]["avg_confidence"] == 1.0
    assert bins[0]["n"] == 1
    assert bins[5]["n"] == 1
    assert sum(b["n"] for b in bins) == 3


def test_accuracy_coverage_is_sorted_by_confidence_desc():
    conf = [0.9, 0.6, 0.3, 0.1]
    ok = [True, True, False, False]
    curve = accuracy_coverage(conf, ok, steps=4)
    assert [r["coverage"] for r in curve] == [0.25, 0.5, 0.75, 1.0]
    assert [r["accuracy"] for r in curve] == [1.0, 1.0, 0.6667, 0.5]
    assert curve[0]["min_confidence"] == 0.9


def test_zero_error_coverage_stops_at_first_error():
    conf = [0.9, 0.8, 0.7, 0.6]
    ok = [True, True, False, True]
    z = zero_error_coverage(conf, ok)
    assert z == {"coverage": 0.5, "n": 2, "threshold": 0.8}


def test_zero_error_coverage_empty():
    assert zero_error_coverage([], []) == {"coverage": 0.0, "n": 0, "threshold": None}


def test_mismatched_lengths_are_a_bug_not_a_silent_truncation():
    with pytest.raises(ValueError):
        expected_calibration_error([0.5, 0.5], [True])
