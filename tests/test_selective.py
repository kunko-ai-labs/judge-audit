"""Discrimination, selective prediction at a target risk and paired comparisons, on inputs
whose answer is known by hand or by brute force."""
from __future__ import annotations

import itertools
import math
import random

import pytest

from judge_audit.metrics.calibration import bootstrap_ci, clopper_pearson
from judge_audit.metrics.selective import (
    aggregate_by_group,
    aurc,
    aurc_ci,
    bootstrap_defined,
    coverage_at_risk,
    coverage_at_risk_crossfit,
    failure_auroc,
    failure_auroc_ci,
    holm,
    mcnemar_exact,
    min_rows_to_certify,
    paired_difference_ci,
    paired_difference_test,
    percentile_p_value,
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


def _binom_cdf(k: int, n: int, p: float) -> float:
    return math.fsum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def test_upper_bound_inverts_the_binomial_cdf():
    # independent of the incomplete-beta code: at the bound u, P(X <= errors | n, u) = delta
    for errors, n in [(0, 59), (1, 71), (2, 500), (5, 1000), (10, 1000), (20, 2000), (7, 40)]:
        u = risk_upper_bound(errors, n, 0.05)
        assert _binom_cdf(errors, n, u) == pytest.approx(0.05, abs=1e-9)
    # and agrees with the two-sided exact interval at twice the level, to its 4 decimals
    assert risk_upper_bound(5, 1000) == pytest.approx(clopper_pearson(5, 1000, 0.10)[1],
                                                       abs=5e-5)


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


# the rows one set must hold to certify r with 0 / 1 / 2 / 5 / 10 errors (docs/v05-power.md
# § A, computed there from the binomial CDF, a different code path from the beta quantile)
ROWS_WITH_ERRORS = {0.01: (299, 473, 628, 1049, 1693), 0.02: (149, 236, 313, 523, 845),
                    0.05: (59, 93, 124, 208, 336), 0.1: (29, 46, 61, 103, 167)}


def test_min_rows_to_certify_with_errors():
    for r, counts in ROWS_WITH_ERRORS.items():
        for errors, n in zip((0, 1, 2, 5, 10), counts, strict=True):
            assert min_rows_to_certify(r, errors=errors) == n, (r, errors)
            # the smallest n: the binomial CDF at the target crosses delta between n - 1 and n
            assert _binom_cdf(errors, n, r) <= 0.05 < _binom_cdf(errors, n - 1, r)
    with pytest.raises(ValueError, match="errors"):
        min_rows_to_certify(0.05, errors=-1)


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


def test_start_errors_zero_is_the_98_procedure_byte_for_byte():
    """start_errors = 0 returns exactly what #98 returned: same keys, same values, same JSON."""
    import json

    cal_conf = [0.999] + [0.95] * 70 + [0.6] * 30
    cal_ok = [True] * 71 + [False] * 30
    expected = {"target_risk": 0.05, "delta": 0.05, "min_covered": 59, "threshold": 0.95,
                "calibration": {"n": 101, "covered": 71, "errors": 0,
                                "coverage": round(71 / 101, 4),
                                "risk_upper": round(1 - 0.05 ** (1 / 71), 4)},
                "test": {"n": 101, "covered": 71, "errors": 0,
                         "coverage": round(71 / 101, 4), "risk": 0.0,
                         "risk_upper": round(1 - 0.05 ** (1 / 71), 4)}}
    default = coverage_at_risk(cal_conf, cal_ok, cal_conf, cal_ok, 0.05)
    explicit = coverage_at_risk(cal_conf, cal_ok, cal_conf, cal_ok, 0.05, start_errors=0)
    assert json.dumps(default) == json.dumps(explicit) == json.dumps(expected)
    # and on random data with ties, every target, with and without a certification
    for seed in range(6):
        conf, ok = _random_judge(700, seed=seed, levels=9)
        for r in (0.02, 0.05, 0.1):
            old = coverage_at_risk(conf[:350], ok[:350], conf[350:], ok[350:], r)
            new = coverage_at_risk(conf[:350], ok[:350], conf[350:], ok[350:], r,
                                   start_errors=0)
            assert json.dumps(old) == json.dumps(new)
            assert set(new) == {"target_risk", "delta", "min_covered", "threshold",
                                "calibration", "test"}
    # a split too small to reach the start keeps #98's silent None: no key is added at 0
    small = coverage_at_risk([0.9] * 10, [True] * 10, [0.9], [True], 0.05, start_errors=0)
    assert "reason" not in small and small["threshold"] is None


def _continuous_fixture() -> tuple[list[float], list[bool]]:
    """100 distinct confidences 1.000, 0.999, ... 0.901; errors at ranks 5, 40 and 70."""
    conf = [(1000 - i) / 1000 for i in range(100)]
    ok = [i not in (4, 39, 69) for i in range(100)]
    return conf, ok


def test_the_2_error_start_certifies_where_the_98_start_stops():
    """At 10 %: 0 / 1 / 2 / 3 errors need 29 / 46 / 61 / 76 rows (ROWS_WITH_ERRORS and
    min_rows_to_certify). #98 tests 29 rows first, which hold the rank-5 error: the bound
    fails and the walk ends. From 1 error it tests 46 rows first, which hold 2 errors: it
    fails. From 2 errors it tests 61 rows with 2 errors: it passes, and so does every cut
    down to 69 rows; the cut of 70 rows holds 3 errors with fewer than 76 rows and fails."""
    conf, ok = _continuous_fixture()
    assert min_rows_to_certify(0.1, errors=3) == 76
    old = coverage_at_risk(conf, ok, conf, ok, 0.1)
    assert old["threshold"] is None and old["min_covered"] == 29
    one = coverage_at_risk(conf, ok, conf, ok, 0.1, start_errors=1)
    assert one["threshold"] is None and one["min_covered"] == 46
    two = coverage_at_risk(conf, ok, conf, ok, 0.1, start_errors=2)
    assert two["min_covered"] == 61 and two["start_errors"] == 2
    assert two["threshold"] == 0.932                  # rank 69: (1000 - 68) / 1000
    assert two["calibration"] == {"n": 100, "covered": 69, "errors": 2, "coverage": 0.69,
                                  "risk_upper": round(risk_upper_bound(2, 69), 4)}
    assert risk_upper_bound(2, 69) <= 0.1 < risk_upper_bound(3, 70)
    assert (two["test"]["covered"], two["test"]["errors"]) == (69, 2)
    assert "reason" not in two


def test_the_start_depends_on_row_counts_never_on_labels():
    conf, ok = _continuous_fixture()
    for labels in (ok, [True] * 100, [False] * 100):
        assert coverage_at_risk(conf, labels, conf, labels, 0.1,
                                start_errors=2)["min_covered"] == 61


def test_the_guarantee_holds_for_every_start_by_full_enumeration():
    """10 rows with distinct confidences, each wrong with probability 0.6, target 60 %:
    every one of the 1,024 labellings is run through the library and weighted by its
    probability. With continuous confidences the first cut tested decides, so the chance of
    certifying is P(Bin(n_e, 0.6) <= e) at the start n_e = 4 / 6 / 8 rows (0.0256, 0.0410,
    0.0498), at most delta for every start: the later start keeps the guarantee."""
    conf = [(100 - i) / 100 for i in range(10)]
    for start, n_e in ((0, 4), (1, 6), (2, 8)):
        assert min_rows_to_certify(0.6, errors=start) == n_e
        p = 0.0
        for bits in range(1 << 10):
            ok = [not (bits >> i) & 1 for i in range(10)]
            res = coverage_at_risk(conf, ok, conf, ok, 0.6, start_errors=start)
            if res["threshold"] is not None:
                wrong = 10 - sum(ok)
                p += 0.6 ** wrong * 0.4 ** (10 - wrong)
        assert p == pytest.approx(_binom_cdf(start, n_e, 0.6), abs=1e-12)
        assert p <= 0.05


def test_a_start_past_the_split_certifies_nothing_and_says_why():
    # 2 errors at 10 % need 61 rows; a calibration split of 50 cannot reach the start
    res = coverage_at_risk([0.9] * 50, [True] * 50, [0.9] * 20, [True] * 20, 0.1,
                           start_errors=2)
    assert res["threshold"] is None and res["test"]["covered"] == 0
    assert res["min_covered"] == 61
    assert "61" in res["reason"] and "50" in res["reason"]
    # one row more than the start is enough to be tested
    ok = coverage_at_risk([0.9] * 61, [True] * 61, [0.9], [True], 0.1, start_errors=2)
    assert ok["threshold"] == 0.9 and "reason" not in ok


def test_start_errors_rejects_bad_input():
    for bad in (-1, 1.5, True):
        with pytest.raises(ValueError, match="start_errors"):
            coverage_at_risk([0.9], [True], [0.9], [True], 0.05, start_errors=bad)


def test_crossfit_passes_the_start_through():
    conf, ok = _random_judge(800, seed=9, levels=10)
    groups = [f"text{i // 2}" for i in range(800)]
    base = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0)
    same = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0, start_errors=0)
    assert same == base and "start_errors" not in base
    res = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0, start_errors=2)
    assert res["start_errors"] == 2
    assert all(f["min_covered"] == 61 and f["start_errors"] == 2 for f in res["folds"])
    assert "reason" not in res
    # each half holds 200 texts: a 1 % target from 2 errors needs 628, so neither half can
    # start, and the pooled zero comes with its reason
    tiny = coverage_at_risk_crossfit(conf, ok, 0.01, groups=groups, seed=0, start_errors=2)
    assert tiny["pooled"]["covered"] == 0
    assert all("628" in f["reason"] for f in tiny["folds"])
    assert "628" in tiny["reason"]


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


def _false_certification_rate(texts: int, copies: int, risk: float, as_texts: bool) -> float:
    """Exact probability that one confidence group whose true risk is `risk` gets certified
    at target `risk`: each text is right or wrong for all of its `copies` rows at once."""
    rows = texts if as_texts else texts * copies
    per_error = 1 if as_texts else copies
    passing = [e for e in range(texts + 1)
               if rows >= min_rows_to_certify(risk)
               and risk_upper_bound(e * per_error, rows) <= risk]
    return math.fsum(math.comb(texts, e) * risk ** e * (1 - risk) ** (texts - e)
                     for e in passing)


def test_the_guarantee_needs_independent_units():
    # 300 texts, each present twice with one outcome (a temperature-0 judge), true risk at
    # the target: counted as 600 rows, a 5 % test certifies 12 % of the time; counted as
    # 300 texts it stays under delta
    assert _false_certification_rate(300, 2, 0.05, as_texts=False) > 0.10
    assert _false_certification_rate(300, 2, 0.05, as_texts=True) <= 0.05


def test_aggregation_counts_a_repeated_text_once():
    conf = [0.9, 0.9, 0.95, 0.8]
    ok = [True, True, True, False]
    groups = ["a", "a", "b", "b"]
    assert aggregate_by_group(conf, ok, groups) == ([0.9, 0.8], [True, False])
    # 100 texts x 2 copies, all right: 200 rows would certify 2 %, 100 texts cannot
    c, o = [0.9] * 200, [True] * 200
    g = [i // 2 for i in range(200)]
    assert coverage_at_risk(c, o, c, o, 0.02)["threshold"] == 0.9
    units = aggregate_by_group(c, o, g)
    assert coverage_at_risk(*units, *units, 0.02)["threshold"] is None


# --- cross-fitting by distinct text ----------------------------------------------------


def test_split_keeps_every_text_on_one_side_and_is_seeded():
    groups = ["t1", "t1", "t2", "t3", "t3", "t3", "t4", "t5"]
    a, b = split_by_group(groups, seed=0)
    assert sorted(a + b) == list(range(len(groups)))
    assert not {groups[i] for i in a} & {groups[i] for i in b}
    assert split_by_group(groups, seed=0) == (a, b)
    assert len({groups[i] for i in a}) == 3          # 5 texts -> 3 and 2


def test_crossfit_pools_two_test_halves_that_cover_every_text_once():
    conf, ok = _random_judge(800, seed=9, levels=10)
    groups = [f"text{i // 2}" for i in range(800)]    # every text appears twice
    res = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0)
    fa, fb = res["folds"]
    assert res["unit"] == "text"
    assert fa["test"]["n"] + fb["test"]["n"] == 400    # distinct texts, not rows
    assert fa["calibration"]["n"] == fb["test"]["n"]
    assert res["pooled"]["covered"] == fa["test"]["covered"] + fb["test"]["covered"]
    assert res["pooled"]["errors"] == fa["test"]["errors"] + fb["test"]["errors"]
    assert res["pooled"]["n"] == 400
    assert coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0) == res
    rows = coverage_at_risk_crossfit(conf, ok, 0.1, seed=0)
    assert rows["unit"] == "row" and rows["pooled"]["n"] == 800


def test_crossfit_does_not_depend_on_row_order():
    conf, ok = _random_judge(1000, seed=13, levels=10)
    groups = [f"text{i // 2}" for i in range(1000)]
    expected = coverage_at_risk_crossfit(conf, ok, 0.1, groups=groups, seed=0)
    rows = list(zip(conf, ok, groups, strict=True))
    rng = random.Random(4)
    for _ in range(10):
        rng.shuffle(rows)
        got = coverage_at_risk_crossfit([c for c, _, _ in rows], [o for _, o, _ in rows],
                                        0.1, groups=[g for _, _, g in rows], seed=0)
        assert got == expected


def test_split_does_not_depend_on_row_order():
    groups = ["t1", "t1", "t2", "t3", "t3", "t3", "t4", "t5"]
    a, _ = split_by_group(groups, seed=0)
    rev = groups[::-1]
    a_rev, _ = split_by_group(rev, seed=0)
    assert {groups[i] for i in a} == {rev[i] for i in a_rev}


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


# --- the percentile p-value and Holm (docs/v05-plan.md § 6) --------------------------------


def test_percentile_p_value_by_hand():
    # B = 4, none <= 0: 2 x min(1 + 0, 1 + 4) / 5
    assert percentile_p_value([1.0, 2.0, 3.0, 4.0]) == pytest.approx(0.4)
    # B = 9, one <= 0: 2 x min(2, 10) / 10
    assert percentile_p_value([-0.5, 1, 2, 3, 4, 5, 6, 7, 8]) == pytest.approx(0.4)
    # a zero counts on both sides: #{<= 0} = 2, #{>= 0} = 4 -> 2 x 3 / 6 = 1
    assert percentile_p_value([-1.0, 0.0, 1.0, 2.0, 3.0]) == 1.0
    # symmetric in the sign of the differences
    assert percentile_p_value([-1.0, -2.0, -3.0, -4.0]) == pytest.approx(0.4)
    # all zero: 2 x (B + 1) / (B + 1) = 2, capped at 1
    assert percentile_p_value([0.0] * 7) == 1.0
    # B = 99, all positive: the smallest p it can give is 2 / (B + 1)
    assert percentile_p_value([0.1] * 99) == pytest.approx(0.02)
    assert percentile_p_value([]) is None


def _replayed_differences(a, b, statistic, n_boot, seed):
    """The resamples of `bootstrap_defined` without groups, written out: `random.Random(seed)`
    draws n rows with replacement, n_boot times."""
    rng = random.Random(seed)
    n = len(a)
    out, undefined = [], 0
    for _ in range(n_boot):
        idx = rng.choices(range(n), k=n)
        sa, sb = statistic([a[i] for i in idx]), statistic([b[i] for i in idx])
        if sa is None or sb is None:
            undefined += 1
        else:
            out.append(sa - sb)
    return out, undefined


def _auroc_of(rs):
    return failure_auroc([c for c, _ in rs], [o for _, o in rs])


def test_paired_test_uses_the_intervals_resamples_and_counts_the_undefined():
    # 2 wrong answers in 40: a resample that misses both has no AUROC for either method
    ok = [True] * 38 + [False] * 2
    rng = random.Random(8)
    a = [(rng.random(), o) for o in ok]
    b = [(rng.random(), o) for o in ok]
    res = paired_difference_test(a, b, _auroc_of, n_boot=400, seed=3)
    diffs, undefined = _replayed_differences(a, b, _auroc_of, 400, 3)
    assert res.undefined == undefined > 0
    assert res.n_defined == len(diffs) == 400 - undefined
    assert res.p_value == pytest.approx(percentile_p_value(diffs))
    assert res.difference == pytest.approx(_auroc_of(a) - _auroc_of(b))
    # the interval is paired_difference_ci's, from the same draws
    assert res.ci == paired_difference_ci(a, b, _auroc_of, n_boot=400, seed=3).ci
    assert paired_difference_test(a, b, _auroc_of, n_boot=400, seed=3) == res


def test_paired_test_with_groups_matches_the_clustered_interval():
    conf_a, ok = _random_judge(240, seed=31)
    conf_b = [min(1.0, c + 0.05) if o else c for c, o in zip(conf_a, ok, strict=True)]
    a, b = list(zip(conf_a, ok, strict=True)), list(zip(conf_b, ok, strict=True))
    groups = [i // 4 for i in range(240)]
    res = paired_difference_test(b, a, _auroc_of, n_boot=300, seed=1, groups=groups)
    assert res.ci == paired_difference_ci(b, a, _auroc_of, n_boot=300, seed=1,
                                          groups=groups).ci
    assert res.n_defined + res.undefined == 300


def test_paired_test_degenerate_cases():
    ok = [True, False, True, True] * 25
    same = paired_difference_test(ok, ok, _accuracy, n_boot=200)
    assert same.difference == 0.0 and same.p_value == 1.0 and same.n_defined == 200
    # A right on 50 rows B gets wrong: every resample favours A, p = 2 / (B + 1)
    a, b = [True] * 100, [True, False] * 50
    ab = paired_difference_test(a, b, _accuracy, n_boot=499)
    assert ab.p_value == pytest.approx(2 / 500) and ab.difference == 0.5
    assert paired_difference_test(b, a, _accuracy, n_boot=499).p_value == ab.p_value
    # never defined: no p-value, the resamples counted
    never = paired_difference_test([(0.9, True)] * 5, [(0.8, True)] * 5, _auroc_of,
                                   n_boot=50)
    assert (never.p_value, never.ci, never.n_defined, never.undefined) == (None, None, 0, 50)
    assert never.difference is None
    empty = paired_difference_test([], [], _accuracy)
    assert (empty.p_value, empty.ci, empty.n_defined, empty.undefined) == (None, None, 0, 0)
    with pytest.raises(ValueError, match="rows"):
        paired_difference_test([True], [True, False], _accuracy)


def test_holm_by_hand():
    """Four tests. Sorted: T4 0.005 x 4 = 0.02; T1 0.01 x 3 = 0.03; T3 0.03 x 2 = 0.06;
    T2 0.04 x 1 = 0.04, raised to 0.06 because an adjusted p never falls down the order.
    T2 alone at 0.04 would pass; after T3 fails, Holm stops."""
    res = holm({"T1": 0.01, "T2": 0.04, "T3": 0.03, "T4": 0.005})
    adjusted = {k: v["p_adjusted"] for k, v in res.items()}
    assert adjusted == pytest.approx({"T1": 0.03, "T2": 0.06, "T3": 0.06, "T4": 0.02})
    assert {k for k, v in res.items() if v["resolved"]} == {"T1", "T4"}
    assert res["T2"]["p"] == 0.04 and list(res) == ["T1", "T2", "T3", "T4"]


def test_holm_caps_at_one_and_edges():
    res = holm({"a": 0.3, "b": 0.5, "c": 0.9})
    assert [res[k]["p_adjusted"] for k in "abc"] == pytest.approx([0.9, 1.0, 1.0])
    assert holm({"only": 0.04}) == {"only": {"p": 0.04, "p_adjusted": 0.04, "resolved": True}}
    assert holm({}) == {}
    # tied p-values get the same adjusted p whatever their order
    tied = holm({"x": 0.01, "y": 0.01, "z": 0.2})
    assert tied["x"]["p_adjusted"] == tied["y"]["p_adjusted"] == pytest.approx(0.03)
    # "below alpha": an adjusted p equal to alpha does not resolve
    assert holm({"a": 0.025, "b": 0.5})["a"] == {"p": 0.025, "p_adjusted": 0.05,
                                                  "resolved": False}
    assert holm({"a": 0.02}, alpha=0.01)["a"]["resolved"] is False
    for bad in ({"a": -0.1}, {"a": 1.5}, {"a": math.nan}, {"a": None}):
        with pytest.raises(ValueError, match="p-value"):
            holm(bad)
    with pytest.raises(ValueError, match="alpha"):
        holm({"a": 0.01}, alpha=0.0)


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
    # as many rows favour each judge: 2 * P(X <= 3 | 6, 1/2) = 84/64, capped at 1
    even = mcnemar_exact([True] * 3 + [False] * 3, [False] * 3 + [True] * 3)
    assert (even["a_only"], even["b_only"], even["p_value"]) == (3, 3, 1.0)
