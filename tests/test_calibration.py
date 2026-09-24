"""Metrics on inputs whose answer is known by hand."""
from __future__ import annotations

import random

import pytest

from judge_audit.metrics.calibration import (
    accuracy_ci,
    accuracy_coverage,
    bootstrap_ci,
    clopper_pearson,
    ece_ci,
    expected_calibration_error,
    interpolated_quantile,
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


def test_accuracy_coverage_is_permutation_invariant():
    # Same fixture as zero_error_coverage's permutation test: ties at 0.9 and 0.7 with a
    # mix of right/wrong inside the ties. Any cut that split a tied group used to depend
    # on which of the tied rows the stable sort happened to put first.
    conf = [0.9, 0.9, 0.9, 0.8, 0.7, 0.7, 0.5]
    ok = [True, False, True, True, True, False, True]
    expected = accuracy_coverage(conf, ok, steps=7)
    rng = random.Random(2)
    for _ in range(1000):
        idx = list(range(len(conf)))
        rng.shuffle(idx)
        shuffled = accuracy_coverage([conf[i] for i in idx], [ok[i] for i in idx], steps=7)
        assert shuffled == expected


def test_accuracy_coverage_cuts_at_whole_confidence_groups():
    # Group {0.9, 0.9} (k=2), group {0.8, 0.8, 0.8} (k=5, one wrong), group {0.7} (k=6).
    # A target that would have cut inside the {0.8} group (k=3 or k=4, straddling the old
    # cut) snaps up to the end of that group instead, so every reported point's accuracy
    # is well defined regardless of which tied row sorted first.
    conf = [0.9, 0.9, 0.8, 0.8, 0.8, 0.7]
    ok = [True, True, True, False, True, True]
    curve = accuracy_coverage(conf, ok, steps=6)
    assert [(r["coverage"], r["n"], r["min_confidence"]) for r in curve] == [
        (0.3333, 2, 0.9), (0.8333, 5, 0.8), (1.0, 6, 0.7)]
    assert [r["accuracy"] for r in curve] == [1.0, 0.8, 0.8333]


def test_accuracy_coverage_all_rows_tied():
    # One group covering everything: no point can be reported before the whole set.
    conf = [0.5] * 5
    ok = [True, True, False, True, False]
    curve = accuracy_coverage(conf, ok, steps=5)
    assert curve == [{"coverage": 1.0, "accuracy": 0.6, "n": 5, "min_confidence": 0.5}]


def test_accuracy_coverage_two_groups():
    conf = [0.9, 0.9, 0.9, 0.9, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    ok = [True, True, False, True, True, True, True, False, True, True]
    curve = accuracy_coverage(conf, ok, steps=10)
    # Every target below k=4 snaps up to the group boundary; every target above it (and
    # below n) snaps to the only remaining boundary, k=10.
    assert [(r["coverage"], r["n"]) for r in curve] == [(0.4, 4), (1.0, 10)]
    assert curve[0]["accuracy"] == 0.75
    assert curve[1]["accuracy"] == 0.8


def test_accuracy_coverage_degenerate_n_1():
    curve = accuracy_coverage([0.6], [True])
    assert curve == [{"coverage": 1.0, "accuracy": 1.0, "n": 1, "min_confidence": 0.6}]


def test_accuracy_coverage_empty():
    assert accuracy_coverage([], []) == []


def test_accuracy_coverage_jev_clean_shape():
    # The shape of docs/audit-jev-real.json, by hand: 10 distinct confidences (1.0 x187,
    # 0.99 x2, 0.98 x2, 0.96 x2, 0.95, 0.94, 0.93, 0.92, 0.91, 0.89 x2), all correct.
    # Real thresholds sit at n = 187, 189, 191, 193, 194, ..., 198, 200. The 20 targets
    # (10, 20, ..., 200) snap to 187 (targets 10..180), 191 (target 190) and 200.
    counts = [(1.0, 187), (0.99, 2), (0.98, 2), (0.96, 2), (0.95, 1), (0.94, 1),
              (0.93, 1), (0.92, 1), (0.91, 1), (0.89, 2)]
    conf = [c for c, k in counts for _ in range(k)]
    curve = accuracy_coverage(conf, [True] * len(conf))
    assert [(r["coverage"], r["n"], r["min_confidence"]) for r in curve] == [
        (0.935, 187, 1.0), (0.955, 191, 0.98), (1.0, 200, 0.89)]
    assert {r["accuracy"] for r in curve} == {1.0}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_selective_coverage_refuses_non_finite_confidence(bad):
    # NaN never equals itself, so the group walk could not advance past it: it looped
    # forever. Unknown confidence is reported, never imputed — the metric refuses it.
    conf = [0.9, bad, 0.7]
    ok = [True, True, False]
    with pytest.raises(ValueError, match="finite"):
        accuracy_coverage(conf, ok)
    with pytest.raises(ValueError, match="finite"):
        zero_error_coverage(conf, ok)


def test_zero_error_coverage_stops_at_first_error():
    conf = [0.9, 0.8, 0.7, 0.6]
    ok = [True, True, False, True]
    z = zero_error_coverage(conf, ok)
    assert z == {"coverage": 0.5, "n": 2, "threshold": 0.8}


def test_zero_error_coverage_empty():
    assert zero_error_coverage([], []) == {"coverage": 0.0, "n": 0, "threshold": None}


def test_zero_error_coverage_is_permutation_invariant():
    # Ties at 0.9 with one error inside the tie: the old prefix cut depended on which
    # of the tied rows the sort happened to put first.
    conf = [0.9, 0.9, 0.9, 0.8, 0.7, 0.7, 0.5]
    ok = [True, False, True, True, True, False, True]
    expected = zero_error_coverage(conf, ok)
    rng = random.Random(1)
    for _ in range(50):
        idx = list(range(len(conf)))
        rng.shuffle(idx)
        shuffled = zero_error_coverage([conf[i] for i in idx], [ok[i] for i in idx])
        assert shuffled == expected


def test_zero_error_coverage_cuts_at_whole_confidence_groups():
    # Groups from the top: {0.9, 0.9} all correct -> in; {0.8, 0.8, 0.8} has an error -> out,
    # and nothing below it counts even though the 0.7 row is correct.
    conf = [0.9, 0.9, 0.8, 0.8, 0.8, 0.7]
    ok = [True, True, True, False, True, True]
    assert zero_error_coverage(conf, ok) == {"coverage": 0.3333, "n": 2, "threshold": 0.9}
    # An error inside the top group -> nothing is covered, even though the group has correct rows.
    assert zero_error_coverage([0.9, 0.9, 0.5], [True, False, True]) == {
        "coverage": 0.0, "n": 0, "threshold": None}
    # With no ties the group rule is the classic first-error prefix.
    assert zero_error_coverage([0.9, 0.8, 0.7], [True, True, False]) == {
        "coverage": 0.6667, "n": 2, "threshold": 0.8}


def test_zero_error_coverage_degenerate_inputs():
    assert zero_error_coverage([0.7], [True]) == {"coverage": 1.0, "n": 1, "threshold": 0.7}
    assert zero_error_coverage([0.7], [False]) == {"coverage": 0.0, "n": 0, "threshold": None}
    # All tied and all correct: the whole set is one group.
    assert zero_error_coverage([0.5, 0.5, 0.5], [True, True, True]) == {
        "coverage": 1.0, "n": 3, "threshold": 0.5}


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


def test_bootstrap_ci_of_all_correct_is_the_exact_interval():
    # The bootstrap degenerates at the boundary (every resample is 1.0), so the
    # published interval there is the exact binomial one — see the tests below.
    assert accuracy_ci([True] * 10) == clopper_pearson(10, 10)
    assert accuracy_ci([False] * 10) == clopper_pearson(0, 10)


def test_bootstrap_ci_degenerate_inputs():
    assert bootstrap_ci([], _mean) is None
    assert accuracy_ci([True]) == clopper_pearson(1, 1)  # n = 1: 2.5 % tail, nothing else
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
    assert zero_error_coverage_ci([0.9, 0.8], [True, True]) == clopper_pearson(2, 2)


def test_percentile_matches_statistics_quantiles_inclusive():
    import random
    import statistics

    assert interpolated_quantile([1, 2, 3, 4], 0.025) == pytest.approx(1.075)
    assert interpolated_quantile([1, 2, 3, 4], 0.975) == pytest.approx(3.925)
    xs = sorted(random.Random(3).random() for _ in range(2000))
    cuts = statistics.quantiles(xs, n=40, method="inclusive")   # 2.5 %, 5 %, …, 97.5 %
    assert interpolated_quantile(xs, 0.025) == pytest.approx(cuts[0])
    assert interpolated_quantile(xs, 0.975) == pytest.approx(cuts[-1])


def test_cluster_bootstrap_resamples_groups_not_rows():
    # Four texts, each judged three times with the same outcome: the row-i.i.d. interval
    # treats them as twelve observations, the cluster interval as four.
    ok = [True, True, True, True, True, True, False, False, False, True, True, True]
    groups = ["a"] * 3 + ["b"] * 3 + ["c"] * 3 + ["d"] * 3
    rows = bootstrap_ci(ok, _mean)
    cluster = bootstrap_ci(ok, _mean, groups=groups)
    assert rows[0] <= 0.75 <= rows[1] and cluster[0] <= 0.75 <= cluster[1]
    assert cluster[1] - cluster[0] > rows[1] - rows[0]
    # Every resample is a mix of whole groups, so the statistic is a multiple of 1/4.
    assert cluster == (0.25, 1.0)
    # One row per group is the ordinary bootstrap.
    assert bootstrap_ci(ok, _mean, groups=list(range(12))) == rows
    assert accuracy_ci(ok, groups=groups) == cluster
    with pytest.raises(ValueError):
        bootstrap_ci(ok, _mean, groups=groups[:-1])


# --- exact (Clopper–Pearson) intervals at the boundary -------------------------------

def test_clopper_pearson_matches_published_values():
    # Textbook 95 % exact binomial intervals (Beta quantiles): the boundary cases are
    # closed form — 1 - 0.025**(1/10) = 0.3085 and 0.025**(1/10) = 0.6915.
    assert clopper_pearson(0, 10) == (0.0, 0.3085)
    assert clopper_pearson(10, 10) == (0.6915, 1.0)
    assert clopper_pearson(8, 10) == (0.4439, 0.9748)
    assert clopper_pearson(5, 10) == (0.1871, 0.8129)
    assert clopper_pearson(0, 1) == (0.0, 0.975)
    assert clopper_pearson(1, 1) == (0.025, 1.0)


def test_clopper_pearson_brackets_the_point_estimate_and_widens_with_alpha():
    lo, hi = clopper_pearson(3, 20)
    assert lo <= 3 / 20 <= hi
    lo99, hi99 = clopper_pearson(3, 20, alpha=0.01)
    assert lo99 < lo and hi < hi99                      # 99 % is wider than 95 %
    assert clopper_pearson(3, 20).method == "clopper-pearson"


def test_clopper_pearson_narrows_with_n():
    narrow = clopper_pearson(500, 1000)
    wide = clopper_pearson(5, 10)
    assert narrow[1] - narrow[0] < (wide[1] - wide[0]) / 5


def test_clopper_pearson_rejects_impossible_counts():
    for bad in ((-1, 10), (11, 10), (0, 0)):
        with pytest.raises(ValueError):
            clopper_pearson(*bad)


def test_accuracy_ci_is_exact_at_the_boundary_and_bootstrap_elsewhere():
    all_right = accuracy_ci([True] * 10)
    assert all_right == (0.6915, 1.0) and all_right.method == "clopper-pearson"
    none_right = accuracy_ci([False] * 10)
    assert none_right == (0.0, 0.3085) and none_right.method == "clopper-pearson"
    mixed = accuracy_ci([True] * 8 + [False] * 4)
    assert mixed.method == "bootstrap" and mixed[0] < 8 / 12 < mixed[1]


def test_exact_interval_ignores_clustering():
    # Twelve rows over four texts, all correct: the exact interval reads n = 12 rows and
    # is therefore narrower than the truth — documented as a lower bound on the width.
    ok = [True] * 12
    groups = ["a"] * 3 + ["b"] * 3 + ["c"] * 3 + ["d"] * 3
    assert accuracy_ci(ok, groups=groups) == clopper_pearson(12, 12)


def test_zero_error_coverage_ci_is_exact_at_the_boundary():
    full = zero_error_coverage_ci([0.9, 0.8], [True, True])
    assert full == clopper_pearson(2, 2) and full.method == "clopper-pearson"
    none = zero_error_coverage_ci([0.9, 0.8], [False, False])
    assert none == clopper_pearson(0, 2) and none.method == "clopper-pearson"


def test_ece_ci_stays_a_bootstrap_and_flags_a_degenerate_resample():
    conf, ok = [0.9] * 4, [True] * 4                     # every resample is identical
    ci = ece_ci(conf, ok)
    assert ci[0] == ci[1] == pytest.approx(0.1)
    assert ci.method == "bootstrap" and ci.degenerate
    assert not ece_ci([0.9, 0.9, 0.5, 0.5], [True, False, True, False]).degenerate


def test_a_proportion_that_can_still_move_keeps_its_clustered_bootstrap():
    """0 % is not automatically exact: what decides is whether the resamples move.

    Zero-error coverage is 0 here because the single most confident row is wrong, but a
    resample that misses that text covers everything — so the bootstrap has width and it
    is the one published; the exact interval would claim a precision the data denies.
    """
    conf = [1.0] + [0.9] * 5
    ok = [False] + [True] * 5
    ci = zero_error_coverage_ci(conf, ok, groups=[f"t{i}" for i in range(6)])
    assert ci[0] == 0.0 < ci[1] and ci.method == "bootstrap"


def test_latency_percentiles_are_type_7_and_agree_with_numpy_default():
    from judge_audit.runner import _percentile

    xs = [0.2, 0.9, 0.4, 7.5, 0.3, 8.2, 0.5, 0.6, 0.7, 0.8]
    s = sorted(xs)
    # type 7: position p * (n - 1) between order statistics
    assert _percentile(xs, 50) == pytest.approx((s[4] + s[5]) / 2)
    assert _percentile(xs, 99) == pytest.approx(s[8] + 0.91 * (s[9] - s[8]))
    assert _percentile([], 99) == 0.0
    np = pytest.importorskip("numpy")
    assert _percentile(xs, 99) == pytest.approx(float(np.percentile(xs, 99)))
