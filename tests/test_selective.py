"""Discrimination, selective prediction at a target risk and paired comparisons, on inputs
whose answer is known by hand or by brute force."""
from __future__ import annotations

import itertools
import math
import random

import pytest

from judge_audit.metrics.calibration import bootstrap_ci, clopper_pearson
from judge_audit.metrics.selective import (
    aurc,
    aurc_ci,
    bootstrap_defined,
    coverage_at_risk,
    coverage_at_risk_crossfit,
    failure_auroc,
    failure_auroc_ci,
    mcnemar_exact,
    min_rows_to_certify,
    paired_difference_ci,
    risk_upper_bound,
    split_by_group,
)


def _random_judge(n: int, seed: int, levels: int = 6) -> tuple[list[float], list[bool]]:
    """Few distinct confidences (ties everywhere), errors likelier at low confidence."""
    rng = random.Random(seed)
    conf = [rng.choice([round(0.5 + 0.5 * k / (levels - 1), 3) for k in range(levels)])
            for _ in range(n)]
    ok = [rng.random() < c for c in conf]
    return conf, ok


# --- failure_auroc ---------------------------------------------------------------------


def test_auroc_counts_the_pairs_it_ranks_right():
    # right {0.9, 0.7} vs wrong {0.8, 0.6}: 0.9>0.8, 0.9>0.6, 0.7<0.8, 0.7>0.6 -> 3/4
    assert failure_auroc([0.9, 0.8, 0.7, 0.6], [True, False, True, False]) == 0.75


def test_auroc_gives_a_tie_one_half():
    # right {1.0, 0.5} vs wrong {1.0}: a tie (1/2) and a loss (0) -> 0.25
    assert failure_auroc([1.0, 1.0, 0.5], [True, False, True]) == 0.25


def test_auroc_perfect_inverse_and_constant():
    assert failure_auroc([0.9, 0.8, 0.2], [True, True, False]) == 1.0
    assert failure_auroc([0.9, 0.8, 0.2], [False, False, True]) == 0.0
    assert failure_auroc([0.7] * 5, [True, False, True, True, False]) == 0.5


def test_auroc_is_undefined_without_both_outcomes():
    assert failure_auroc([0.9, 0.8], [True, True]) is None
    assert failure_auroc([0.9, 0.8], [False, False]) is None
    assert failure_auroc([], []) is None


def test_auroc_matches_brute_force_pair_counting():
    conf, ok = _random_judge(300, seed=7)
    right = [c for c, o in zip(conf, ok, strict=True) if o]
    wrong = [c for c, o in zip(conf, ok, strict=True) if not o]
    wins = sum(1.0 if r > w else 0.5 if r == w else 0.0 for r in right for w in wrong)
    assert failure_auroc(conf, ok) == pytest.approx(wins / (len(right) * len(wrong)), abs=1e-12)


def test_auroc_does_not_depend_on_row_order():
    conf, ok = _random_judge(200, seed=3)
    expected = failure_auroc(conf, ok)
    rows = list(zip(conf, ok, strict=True))
    rng = random.Random(0)
    for _ in range(50):
        rng.shuffle(rows)
        assert failure_auroc([c for c, _ in rows], [o for _, o in rows]) == expected


def test_auroc_refuses_a_non_finite_confidence():
    with pytest.raises(ValueError, match="finite"):
        failure_auroc([0.9, math.nan], [True, False])


# --- aurc ------------------------------------------------------------------------------


def test_aurc_is_the_mean_risk_over_every_cut():
    # sorted: right, wrong, right, wrong -> risks 0, 1/2, 1/3, 2/4 -> mean 1/3
    assert aurc([0.9, 0.8, 0.7, 0.6], [True, False, True, False]) == pytest.approx(1 / 3)


def test_aurc_of_a_tie_is_its_expectation_over_orders():
    # one group of two, one wrong: 0.5 at k=1 in expectation, 0.5 at k=2
    assert aurc([1.0, 1.0], [True, False]) == pytest.approx(0.5)


def test_aurc_equals_the_average_over_every_order_of_the_ties():
    conf = [0.9, 0.9, 0.9, 0.9, 0.7, 0.7, 0.5]
    ok = [True, False, True, False, True, False, False]
    total, count = 0.0, 0
    for perm in itertools.permutations(range(4)):          # the 0.9 group
        for perm2 in itertools.permutations(range(4, 6)):  # the 0.7 group
            order = list(perm) + list(perm2) + [6]
            errs, risks = 0, []
            for k, i in enumerate(order, start=1):
                errs += 0 if ok[i] else 1
                risks.append(errs / k)
            total += sum(risks) / len(risks)
            count += 1
    assert aurc(conf, ok) == pytest.approx(total / count, abs=1e-12)


def test_aurc_bounds_and_row_order():
    assert aurc([0.9, 0.5], [True, True]) == 0.0
    assert aurc([0.9, 0.5], [False, False]) == 1.0
    conf, ok = _random_judge(150, seed=11)
    expected = aurc(conf, ok)
    rows = list(zip(conf, ok, strict=True))
    random.Random(1).shuffle(rows)
    assert aurc([c for c, _ in rows], [o for _, o in rows]) == expected


def test_aurc_of_no_rows_raises():
    with pytest.raises(ValueError, match="undefined"):
        aurc([], [])


# --- risk_upper_bound ------------------------------------------------------------------


def test_zero_errors_need_299_rows_for_a_one_percent_bound():
    assert risk_upper_bound(0, 299) < 0.01 < risk_upper_bound(0, 298)
    assert risk_upper_bound(0, 100) == pytest.approx(1 - 0.05 ** (1 / 100))


def test_upper_bound_matches_the_one_sided_clopper_pearson():
    for errors, n in [(2, 500), (5, 1000), (10, 1000), (20, 2000), (7, 40)]:
        assert risk_upper_bound(errors, n, 0.05) == pytest.approx(
            clopper_pearson(errors, n, alpha=0.10)[1], abs=5e-5)


def test_upper_bound_edges_and_bad_input():
    assert risk_upper_bound(0, 0) == 1.0
    assert risk_upper_bound(4, 4) == 1.0
    with pytest.raises(ValueError):
        risk_upper_bound(0, 10, delta=0.0)
    with pytest.raises(ValueError):
        risk_upper_bound(11, 10)


# --- coverage_at_risk ------------------------------------------------------------------


def test_threshold_is_chosen_on_calibration_and_applied_to_test():
    cal_conf = [0.99] * 300 + [0.8] * 100
    cal_ok = [True] * 300 + [False] * 20 + [True] * 80
    test_conf = [0.995] * 10 + [0.99] * 150 + [0.8] * 50
    test_ok = [True] * 10 + [False] + [True] * 149 + [False] * 10 + [True] * 40
    res = coverage_at_risk(cal_conf, cal_ok, test_conf, test_ok, target_risk=0.02)
    # 0 of 300 bounds the risk at 1 - 0.05^(1/300) < 1 %; adding 20 errors in 100 fails
    assert res["threshold"] == 0.99
    assert res["calibration"] == {"n": 400, "covered": 300, "errors": 0, "coverage": 0.75,
                                  "risk_upper": round(1 - 0.05 ** (1 / 300), 4)}
    # a test confidence never seen in calibration (0.995) is above the threshold: covered
    assert (res["test"]["covered"], res["test"]["errors"], res["test"]["n"]) == (160, 1, 210)
    assert res["test"]["coverage"] == round(160 / 210, 4)


def test_nothing_is_automated_when_the_sample_cannot_certify_the_risk():
    # a perfect judge on 100 rows: zero errors bound the risk at 2.95 %, not below 2 %
    res = coverage_at_risk([0.9] * 100, [True] * 100, [0.9] * 50, [True] * 50, 0.02)
    assert res["threshold"] is None
    assert res["calibration"]["covered"] == 0 and res["calibration"]["risk_upper"] is None
    assert res["test"]["covered"] == 0 and res["test"]["risk"] is None


def test_min_rows_to_certify():
    assert min_rows_to_certify(0.01) == 299
    assert min_rows_to_certify(0.02) == 149
    assert min_rows_to_certify(0.05) == 59
    for r in (0.01, 0.02, 0.05, 0.1):
        n = min_rows_to_certify(r)
        assert risk_upper_bound(0, n) <= r < risk_upper_bound(0, n - 1)
    with pytest.raises(ValueError, match="delta"):
        min_rows_to_certify(0.05, delta=1.0)


def test_the_sequence_stops_at_the_first_cut_that_fails():
    # the top group (200 rows, 10 wrong) fails; the cumulative risk further down would
    # pass, but fixed-sequence testing never looks past the first failure
    cal_conf = [0.99] * 200 + [0.9] * 5000
    cal_ok = [False] * 10 + [True] * 190 + [True] * 5000
    assert risk_upper_bound(10, 5200) < 0.02 < risk_upper_bound(10, 200)
    res = coverage_at_risk(cal_conf, cal_ok, cal_conf, cal_ok, 0.02)
    assert res["threshold"] is None


def test_the_sequence_starts_where_a_cut_could_pass():
    # continuous confidences: the top cut holds one row, which can never certify 5 %;
    # the sequence starts at the first cut of at least 59 rows instead of failing there
    cal_conf = [0.999] + [0.95] * 70 + [0.6] * 30
    cal_ok = [False] + [True] * 70 + [False] * 30
    res = coverage_at_risk(cal_conf, cal_ok, cal_conf, cal_ok, 0.05)
    assert res["min_covered"] == 59
    # the first cut tested holds 71 rows with the one error: bound 6.5 % > 5 % -> fails
    assert res["threshold"] is None
    cal_ok[0] = True
    res = coverage_at_risk(cal_conf, cal_ok, cal_conf, cal_ok, 0.05)
    assert res["threshold"] == 0.95 and res["calibration"]["covered"] == 71


def test_coverage_at_risk_does_not_depend_on_row_order():
    conf, ok = _random_judge(600, seed=5, levels=8)
    expected = coverage_at_risk(conf[:300], ok[:300], conf[300:], ok[300:], 0.1)
    rows = list(zip(conf, ok, strict=True))
    cal, test = rows[:300], rows[300:]
    rng = random.Random(2)
    for _ in range(20):
        rng.shuffle(cal)
        rng.shuffle(test)
        got = coverage_at_risk([c for c, _ in cal], [o for _, o in cal],
                               [c for c, _ in test], [o for _, o in test], 0.1)
        assert got == expected


def test_coverage_at_risk_rejects_bad_input():
    with pytest.raises(ValueError, match="target_risk"):
        coverage_at_risk([0.9], [True], [0.9], [True], target_risk=0.0)
    with pytest.raises(ValueError, match="finite"):
        coverage_at_risk([math.inf], [True], [0.9], [True], 0.05)


# --- cross-fitting by distinct text ----------------------------------------------------


def test_split_keeps_every_text_on_one_side_and_is_seeded():
    groups = ["t1", "t1", "t2", "t3", "t3", "t3", "t4", "t5"]
    a, b = split_by_group(groups, seed=0)
    assert sorted(a + b) == list(range(len(groups)))
    assert not {groups[i] for i in a} & {groups[i] for i in b}
    assert split_by_group(groups, seed=0) == (a, b)
    assert len({groups[i] for i in a}) == 3          # 5 texts -> 3 and 2


def test_crossfit_pools_two_test_halves_that_cover_every_row_once():
    conf, ok = _random_judge(800, seed=9, levels=10)
    groups = [f"text{i // 2}" for i in range(800)]    # every text appears twice
    res = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0)
    fa, fb = res["folds"]
    assert fa["test"]["n"] + fb["test"]["n"] == 800
    assert fa["calibration"]["n"] == fb["test"]["n"]
    assert res["pooled"]["covered"] == fa["test"]["covered"] + fb["test"]["covered"]
    assert res["pooled"]["errors"] == fa["test"]["errors"] + fb["test"]["errors"]
    assert res["pooled"]["n"] == 800
    assert coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0) == res


# --- bootstrap of a statistic that can be undefined ------------------------------------


def test_bootstrap_defined_draws_the_same_resamples_as_bootstrap_ci():
    conf, ok = _random_judge(120, seed=4)
    rows = list(zip(conf, ok, strict=True))
    groups = [i // 3 for i in range(120)]

    def stat(rs):
        return sum(o for _, o in rs) / len(rs)

    res = bootstrap_defined(rows, stat, n_boot=300, seed=0, groups=groups)
    assert res.undefined == 0
    assert tuple(res.ci) == bootstrap_ci(rows, stat, n_boot=300, seed=0, groups=groups)


def test_auroc_interval_counts_the_resamples_with_no_error():
    # one wrong answer in 12: a resample that misses it has no AUROC
    conf = [0.9] * 6 + [0.8] * 5 + [0.6]
    ok = [True] * 11 + [False]
    res = failure_auroc_ci(conf, ok, n_boot=500, seed=0)
    assert res.undefined > 0
    assert res.ci is not None and res.ci[1] == 1.0
    assert failure_auroc_ci([], []) == (None, 0)


def test_aurc_interval_contains_its_point_on_a_large_sample():
    conf, ok = _random_judge(400, seed=12)
    res = aurc_ci(conf, ok, n_boot=400)
    assert res.undefined == 0 and res.ci[0] <= round(aurc(conf, ok), 4) <= res.ci[1]


# --- paired comparisons ----------------------------------------------------------------


def _accuracy(xs):
    return sum(xs) / len(xs)


def test_identical_judges_differ_by_exactly_zero():
    ok = [True, False, True, True] * 25
    res = paired_difference_ci(ok, ok, _accuracy, n_boot=200)
    assert tuple(res.ci) == (0.0, 0.0) and res.ci.degenerate


def test_a_real_difference_is_separated_and_antisymmetric():
    a = [True] * 100
    b = [True, False] * 50                           # A right on 50 rows B gets wrong
    ab = paired_difference_ci(a, b, _accuracy, n_boot=500)
    ba = paired_difference_ci(b, a, _accuracy, n_boot=500)
    assert ab.ci[0] > 0 and ab.ci[0] <= 0.5 <= ab.ci[1]
    assert ab.ci[0] == pytest.approx(-ba.ci[1]) and ab.ci[1] == pytest.approx(-ba.ci[0])


def test_paired_auroc_difference_uses_one_resample_for_both_judges():
    conf_a, ok = _random_judge(300, seed=21)
    rng = random.Random(0)
    conf_b = [rng.random() for _ in ok]              # B's confidence ignores correctness
    rows_a = list(zip(conf_a, ok, strict=True))
    rows_b = list(zip(conf_b, ok, strict=True))

    def auroc(rs):
        return failure_auroc([c for c, _ in rs], [o for _, o in rs])

    res = paired_difference_ci(rows_a, rows_b, auroc, n_boot=300)
    point = failure_auroc(conf_a, ok) - failure_auroc(conf_b, ok)
    assert res.ci[0] <= round(point, 4) <= res.ci[1]
    with pytest.raises(ValueError, match="rows"):
        paired_difference_ci(rows_a, rows_b[:-1], auroc)


def test_mcnemar_exact_on_hand_counts():
    a = [True] * 10 + [False] * 2 + [True] * 30 + [False] * 5
    b = [False] * 10 + [True] * 2 + [True] * 30 + [False] * 5
    res = mcnemar_exact(a, b)
    # 12 discordant rows, 10 favour A: p = 2 * (C(12,0)+C(12,1)+C(12,2)) / 2^12 = 158/4096
    assert (res["a_only"], res["b_only"]) == (10, 2)
    assert res["p_value"] == pytest.approx(158 / 4096)
    assert mcnemar_exact(b, a)["p_value"] == res["p_value"]
    assert mcnemar_exact([True, False], [True, False]) == {"a_only": 0, "b_only": 0,
                                                            "p_value": 1.0}
