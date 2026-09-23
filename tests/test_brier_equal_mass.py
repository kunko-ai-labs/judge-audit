"""Brier score and equal-mass ECE on inputs whose answer is known by hand (US-004-012)."""
from __future__ import annotations

import math
import random

import pytest

from judge_audit.metrics.calibration import (
    bootstrap_ci,
    brier_ci,
    brier_score,
    ece_ci,
    expected_calibration_error,
)

# --- Brier score -----------------------------------------------------------------------


def test_brier_is_the_mean_squared_gap_between_confidence_and_outcome():
    # (0.8-1)^2 + (0.6-0)^2 + (1.0-0)^2 + (0.5-1)^2 = 0.04 + 0.36 + 1.0 + 0.25 = 1.65
    conf = [0.8, 0.6, 1.0, 0.5]
    ok = [True, False, False, True]
    assert brier_score(conf, ok) == pytest.approx(1.65 / 4)


def test_brier_of_confident_and_always_wrong_is_the_confidence_squared():
    assert brier_score([0.9, 0.9, 0.9], [False] * 3) == pytest.approx(0.81)


def test_brier_is_zero_only_for_certain_and_right():
    assert brier_score([1.0, 0.0], [True, False]) == 0.0
    # all correct at one confidence: (1 - 0.9)^2, however many rows
    assert brier_score([0.9] * 5, [True] * 5) == pytest.approx(0.01)


def test_brier_degenerate_inputs():
    assert brier_score([0.7], [True]) == pytest.approx(0.09)        # n = 1
    assert brier_score([0.7], [False]) == pytest.approx(0.49)
    with pytest.raises(ValueError, match="no rows"):
        brier_score([], [])                                         # a mean of nothing
    with pytest.raises(ValueError):
        brier_score([0.5, 0.5], [True])                              # a bug, not a truncation


def test_identical_judges_get_identical_numbers():
    conf = [0.95, 0.6, 0.6, 1.0, 0.3]
    ok = [True, False, True, True, False]
    assert brier_score(conf, ok) == brier_score(list(conf), list(ok))
    assert (expected_calibration_error(conf, ok, binning="equal_mass")
            == expected_calibration_error(list(conf), list(ok), binning="equal_mass"))


# --- equal-mass ECE --------------------------------------------------------------------


def test_equal_mass_ece_on_distinct_confidences():
    # n=6, 3 bins of 2 rows: {0.1 F, 0.2 F} gap 0.15, {0.3 T, 0.7 T} gap 0.5,
    # {0.8 T, 0.9 F} gap 0.35 -> (2/6) * (0.15 + 0.5 + 0.35) = 1/3
    conf = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
    ok = [False, False, True, True, True, False]
    assert expected_calibration_error(conf, ok, 3, binning="equal_mass") == pytest.approx(1 / 3)
    # the equal-width ECE of the same rows (10 bins, one row each) is mean |ok - conf|
    assert expected_calibration_error(conf, ok) == pytest.approx(2.4 / 6)


def test_equal_mass_bins_never_split_a_tie():
    # n=6, 3 bins: the cut at row 2 would fall inside the 0.5 tie (rows 1-3); it moves to
    # the nearer group edge (row 1), the cut at row 4 is already one. Bins: {0.2 F},
    # {0.5 T, 0.5 F, 0.5 T}, {0.9 T, 0.9 T}:
    #   (1/6) * 0.2 + (3/6) * |2/3 - 0.5| + (2/6) * 0.1 = 0.15
    conf = [0.2, 0.5, 0.5, 0.5, 0.9, 0.9]
    ok = [False, True, False, True, True, True]
    assert expected_calibration_error(conf, ok, 3, binning="equal_mass") == pytest.approx(0.15)
    # a split tie would have made the number depend on which 0.5 row sat first
    for order in ([1, 0, 2, 3, 4, 5], [0, 2, 1, 3, 4, 5], [5, 3, 2, 1, 4, 0]):
        c = [conf[i] for i in order]
        o = [ok[i] for i in order]
        assert expected_calibration_error(c, o, 3, binning="equal_mass") == pytest.approx(0.15)


def test_equal_mass_cut_equidistant_from_two_group_edges_takes_the_lower_one():
    # n=4, 2 bins: the cut at row 2 is inside the 0.5 tie (rows 1-2), one row from either
    # edge; it goes to row 1. Bins {0.2 F} and {0.5 T, 0.5 T, 0.8 F}:
    #   (1/4) * 0.2 + (3/4) * |2/3 - 0.6| = 0.05 + 0.05 = 0.1
    conf = [0.2, 0.5, 0.5, 0.8]
    ok = [False, True, True, False]
    assert expected_calibration_error(conf, ok, 2, binning="equal_mass") == pytest.approx(0.1)


def test_one_big_tie_is_its_own_bin():
    # 125 of 200 at 1.0 (Gemini 3 Flash says 1.0 on 125/200 emails): no cut can enter the
    # tie, so the 1.0 rows are one bin and are not averaged with lower confidences.
    conf = [0.8] * 75 + [1.0] * 125
    ok = [True] * 60 + [False] * 15 + [True] * 120 + [False] * 5
    # bins that lie inside the 0.8 group merge too: {0.8 x 75} and {1.0 x 125}
    want = 75 / 200 * abs(60 / 75 - 0.8) + 125 / 200 * abs(120 / 125 - 1.0)
    assert expected_calibration_error(conf, ok, binning="equal_mass") == pytest.approx(want)


def test_equal_mass_degenerate_inputs():
    assert expected_calibration_error([], [], binning="equal_mass") == 0.0   # as equal-width
    assert expected_calibration_error([0.7], [False], binning="equal_mass") == pytest.approx(0.7)
    # every row tied: one bin, so both binnings agree
    conf, ok = [0.9] * 5, [True, True, True, True, False]
    assert expected_calibration_error(conf, ok, binning="equal_mass") == pytest.approx(0.1)
    assert expected_calibration_error(conf, ok) == pytest.approx(0.1)
    # all correct at one confidence: the gap is 1 - confidence
    assert expected_calibration_error([0.9] * 4, [True] * 4,
                                      binning="equal_mass") == pytest.approx(0.1)
    # fewer rows than bins: every distinct confidence is its own bin -> mean |ok - conf|
    assert expected_calibration_error([0.2, 0.6, 0.9], [True, False, True],
                                      binning="equal_mass") == pytest.approx(1.5 / 3)


def test_equal_mass_and_brier_are_permutation_invariant():
    """1,000 shuffles of a heavily tied sample: the value does not move by one bit."""
    rng = random.Random(7)
    conf = [rng.choice([0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]) for _ in range(57)]
    ok = [rng.random() < c for c in conf]
    em = expected_calibration_error(conf, ok, binning="equal_mass")
    br = brier_score(conf, ok)
    idx = list(range(len(conf)))
    for _ in range(1000):
        rng.shuffle(idx)
        c = [conf[i] for i in idx]
        o = [ok[i] for i in idx]
        assert expected_calibration_error(c, o, binning="equal_mass") == em
        assert brier_score(c, o) == br


def test_default_binning_is_the_published_equal_width_ece():
    rng = random.Random(11)
    for _ in range(50):
        conf = [round(rng.random(), 2) for _ in range(rng.randint(1, 60))]
        ok = [rng.random() < 0.7 for _ in conf]
        legacy = _legacy_equal_width_ece(conf, ok)
        assert expected_calibration_error(conf, ok) == legacy
        assert expected_calibration_error(conf, ok, binning="equal_width") == legacy


def _legacy_equal_width_ece(confidences, correct, n_bins=10):
    """The v0.4.0 implementation, verbatim: the published ECE must not move."""
    bins = [[] for _ in range(n_bins)]
    conf_bins = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, correct, strict=True):
        i = min(int(c * n_bins), n_bins - 1)
        bins[i].append(ok)
        conf_bins[i].append(c)
    ece, n = 0.0, len(correct)
    for b, cb in zip(bins, conf_bins, strict=True):
        if not b:
            continue
        ece += len(b) / n * abs(sum(b) / len(b) - math.fsum(cb) / len(cb))
    return ece


def test_unknown_binning_is_refused():
    with pytest.raises(ValueError, match="binning"):
        expected_calibration_error([0.5], [True], binning="quantile")


# --- non-finite confidences are refused, never imputed ---------------------------------


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_confidence_is_refused_by_every_calibration_number(bad):
    conf, ok = [0.9, bad, 0.4], [True, True, False]
    with pytest.raises(ValueError, match="finite"):
        brier_score(conf, ok)
    for binning in ("equal_width", "equal_mass"):
        with pytest.raises(ValueError, match="finite"):
            expected_calibration_error(conf, ok, binning=binning)


# --- bootstrap intervals: same machinery and resampling unit as the ECE interval ----------


def test_brier_ci_is_the_clustered_bootstrap_of_the_brier_score():
    conf = [0.9, 0.9, 0.6, 0.6, 0.8, 0.3, 1.0, 0.7]
    ok = [True, False, True, True, False, False, True, True]
    groups = ["a", "a", "b", "b", "c", "d", "e", "e"]
    rows = list(zip(conf, ok, strict=True))
    want = bootstrap_ci(rows, lambda rs: brier_score([c for c, _ in rs], [o for _, o in rs]),
                        groups=groups)
    ci = brier_ci(conf, ok, groups=groups)
    assert tuple(ci) == want and ci.method == "bootstrap"
    assert ci[0] <= round(brier_score(conf, ok), 4) <= ci[1]
    # clustering is honoured: rows-as-units is a different interval
    assert tuple(brier_ci(conf, ok)) != want


def test_equal_mass_ece_ci_rebuilds_its_bins_on_every_resample():
    conf = [0.9, 0.9, 0.6, 0.6, 0.8, 0.3, 1.0, 0.7]
    ok = [True, False, True, True, False, False, True, True]
    groups = ["a", "a", "b", "b", "c", "d", "e", "e"]
    rows = list(zip(conf, ok, strict=True))
    want = bootstrap_ci(rows, lambda rs: expected_calibration_error(
        [c for c, _ in rs], [o for _, o in rs], binning="equal_mass"), groups=groups)
    ci = ece_ci(conf, ok, groups=groups, binning="equal_mass")
    assert tuple(ci) == want and ci.method == "bootstrap"
    point = round(expected_calibration_error(conf, ok, binning="equal_mass"), 4)
    assert ci[0] <= point <= ci[1]
    # the equal-width interval is unchanged by the new parameter
    assert ece_ci(conf, ok, groups=groups) == ece_ci(conf, ok, groups=groups,
                                                     binning="equal_width")


def test_new_intervals_flag_a_degenerate_resample_and_skip_empty_input():
    conf, ok = [0.9] * 4, [True] * 4
    b = brier_ci(conf, ok)
    assert b[0] == b[1] == pytest.approx(0.01) and b.degenerate
    e = ece_ci(conf, ok, binning="equal_mass")
    assert e[0] == e[1] == pytest.approx(0.1) and e.degenerate
    assert brier_ci([], []) is None and ece_ci([], [], binning="equal_mass") is None
