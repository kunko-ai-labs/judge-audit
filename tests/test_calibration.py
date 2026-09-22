"""Metrics on inputs whose answer is known by hand."""
from __future__ import annotations

import pytest

from judge_audit.metrics.calibration import (
    accuracy_ci,
    accuracy_coverage,
    bootstrap_ci,
    ece_ci,
    expected_calibration_error,
    reliability_bins,
    zero_error_coverage,
    zero_error_coverage_ci,
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


# --- bootstrap confidence intervals -------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs)


def test_bootstrap_ci_contains_the_point_estimate():
    ok = [True] * 8 + [False] * 4                      # accuracy 2/3
    lo, hi = bootstrap_ci(ok, _mean)
    assert lo <= 8 / 12 <= hi
    assert lo < hi


def test_bootstrap_ci_width_shrinks_with_n():
    small = [True] * 8 + [False] * 4
    big = small * 20                                    # same accuracy, 240 rows
    lo_s, hi_s = bootstrap_ci(small, _mean)
    lo_b, hi_b = bootstrap_ci(big, _mean)
    assert hi_b - lo_b < (hi_s - lo_s) / 2


def test_bootstrap_ci_is_deterministic_for_a_seed():
    ok = [True, False, True, True, False, True, True]
    assert bootstrap_ci(ok, _mean, seed=0) == bootstrap_ci(ok, _mean, seed=0)
    assert bootstrap_ci(ok, _mean, seed=0, n_boot=200) != bootstrap_ci(ok, _mean, seed=1,
                                                                        n_boot=200)


def test_bootstrap_ci_of_all_correct_is_one_one():
    assert accuracy_ci([True] * 10) == (1.0, 1.0)
    assert accuracy_ci([False] * 10) == (0.0, 0.0)


def test_bootstrap_ci_degenerate_inputs():
    assert bootstrap_ci([], _mean) is None
    assert accuracy_ci([True]) == (1.0, 1.0)            # n = 1: every resample is the row itself
    assert accuracy_ci([]) is None


def test_bootstrap_ci_is_rounded_to_four_decimals():
    lo, hi = accuracy_ci([True] * 8 + [False] * 4)
    assert lo == round(lo, 4) and hi == round(hi, 4)


def test_ece_ci_on_a_six_row_fixture():
    # Two bins: 0.9 (three rows, two right) and 0.5 (three rows, one right).
    # Point ECE = 3/6*|2/3-0.9| + 3/6*|1/3-0.5| = 0.11667 + 0.08333 = 0.2
    conf = [0.9, 0.9, 0.9, 0.5, 0.5, 0.5]
    ok = [True, True, False, True, False, False]
    point = expected_calibration_error(conf, ok)
    assert point == pytest.approx(0.2)
    lo, hi = ece_ci(conf, ok)
    assert 0.0 <= lo <= point <= hi <= 1.0
    # Every resample is drawn from these six rows, so the extremes are attainable by hand:
    # all six draws right at 0.9 -> ECE 0.1; the worst mix stays below 0.9.
    assert lo >= 0.0 and hi <= 0.9
    assert ece_ci(conf, ok) == ece_ci(conf, ok)          # seed 0 both times


def test_zero_error_coverage_ci_brackets_the_point_estimate():
    conf = [0.9, 0.8, 0.7, 0.6]
    ok = [True, True, False, True]
    point = zero_error_coverage(conf, ok)["coverage"]     # 0.5
    lo, hi = zero_error_coverage_ci(conf, ok)
    assert lo <= point <= hi
    assert zero_error_coverage_ci([0.9, 0.8], [True, True]) == (1.0, 1.0)
