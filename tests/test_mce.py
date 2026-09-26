"""MCE, the worst calibration bin (#12), on inputs whose answer is known by hand."""
from __future__ import annotations

import math
import random

import pytest

from judge_audit.metrics.calibration import (
    EQUAL_MASS,
    expected_calibration_error,
    maximum_calibration_error,
    mce_ci,
    worst_calibration_bin,
)


def test_mce_is_the_largest_gap_of_any_bin():
    # bin 0.9-1.0: ten at 0.95, nine right -> gap 0.05; bin 0.3-0.4: four at 0.35, one
    # right -> gap 0.10. ECE weights them (10/14 * 0.05 + 4/14 * 0.10); MCE takes 0.10.
    conf = [0.95] * 10 + [0.35] * 4
    ok = [True] * 9 + [False] + [True] + [False] * 3
    assert maximum_calibration_error(conf, ok) == pytest.approx(0.10)
    assert expected_calibration_error(conf, ok) == pytest.approx(10 / 14 * 0.05 + 4 / 14 * 0.10)
    worst = worst_calibration_bin(conf, ok)
    assert worst["n"] == 4
    assert worst["avg_confidence"] == pytest.approx(0.35)
    assert worst["accuracy"] == 0.25


def test_mce_is_never_below_ece_under_either_binning():
    rng = random.Random(0)
    for _ in range(30):
        conf = [round(rng.random(), 2) for _ in range(80)]
        ok = [rng.random() < c for c in conf]
        for binning in ("equal_width", EQUAL_MASS):
            assert (maximum_calibration_error(conf, ok, binning=binning)
                    >= expected_calibration_error(conf, ok, binning=binning) - 1e-12)


def test_mce_of_a_perfectly_calibrated_judge_is_zero():
    assert maximum_calibration_error([0.75] * 4, [True, True, True, False]) == pytest.approx(0.0)


def test_mce_does_not_depend_on_row_order():
    rng = random.Random(1)
    conf = [rng.choice([0.6, 0.8, 0.9, 1.0]) for _ in range(100)]
    ok = [rng.random() < c for c in conf]
    rows = list(zip(conf, ok, strict=True))
    for binning in ("equal_width", EQUAL_MASS):
        expected = maximum_calibration_error(conf, ok, binning=binning)
        for _ in range(20):
            rng.shuffle(rows)
            assert maximum_calibration_error([c for c, _ in rows], [o for _, o in rows],
                                             binning=binning) == expected


def test_mce_refuses_no_rows_nan_and_unknown_binning():
    with pytest.raises(ValueError, match="undefined"):
        maximum_calibration_error([], [])
    with pytest.raises(ValueError, match="finite"):
        maximum_calibration_error([math.nan], [True])
    with pytest.raises(ValueError, match="binning"):
        maximum_calibration_error([0.5], [True], binning="quantile")


def test_mce_interval_is_a_clustered_bootstrap():
    rng = random.Random(2)
    conf = [rng.choice([0.55, 0.7, 0.85, 0.95]) for _ in range(200)]
    ok = [rng.random() < c for c in conf]
    ci = mce_ci(conf, ok, n_boot=300, groups=[i // 2 for i in range(200)])
    assert ci is not None and ci.method == "bootstrap" and ci[0] <= ci[1]
    assert mce_ci([], []) is None
