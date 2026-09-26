"""scripts/v05_power.py: the exact binomial part by hand, the simulation helpers on
fixtures. The report itself is regenerated and diffed in CI."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("v05_power", ROOT / "scripts" / "v05_power.py")
power = importlib.util.module_from_spec(spec)
sys.modules["v05_power"] = power
spec.loader.exec_module(power)


def test_binomial_cdf_equals_the_sum_written_out():
    for m, p in ((10, 0.3), (40, 0.01), (7, 0.5)):
        for k in range(m + 1):
            brute = sum(math.comb(m, i) * p ** i * (1 - p) ** (m - i) for i in range(k + 1))
            assert power.binom_cdf(k, m, p) == pytest.approx(brute, abs=1e-12)


def test_zero_errors_need_the_textbook_row_counts():
    # (1 - r)^m < 0.05: m > ln(0.05) / ln(1 - r)
    assert power.rows_to_certify(0.01, 0) == 299       # 0.99^298 = 0.0501, 0.99^299 = 0.0496
    assert power.rows_to_certify(0.02, 0) == 149
    assert power.rows_to_certify(0.05, 0) == 59
    m = power.rows_to_certify(0.01, 1)
    assert power.binom_cdf(1, m, 0.01) <= 0.05 < power.binom_cdf(1, m - 1, 0.01)


def test_certifiable_errors_and_power():
    assert power.certifiable_errors(298, 0.01) == -1 and power.certifiable_errors(299, 0.01) == 0
    assert power.power_to_certify(299, 0.01, 0.0) == 1.0
    assert power.power_to_certify(100, 0.01, 0.0) == 0.0     # too few rows to certify at all
    m = power.rows_for_power(0.05, 0.01)
    assert all(power.power_to_certify(j, 0.05, 0.01) >= 0.8 for j in range(m, 2 * m + 1))
    assert power.power_to_certify(m - 1, 0.05, 0.01) < 0.8


def test_auroc_counts_ties_one_half():
    # right answers score 3, 2, 2; wrong ones 2, 1: pairs (3>2, 3>1, 2=2, 2>1, 2=2, 2>1)
    assert power.auroc([3, 2, 2, 2, 1], [True, True, True, False, False]) == pytest.approx(5 / 6)


def test_levels_cut_the_sorted_rows_into_the_given_shares():
    out = power.levels([0.9, 0.1, 0.5, 0.7, 0.3, 0.2, 0.8, 0.6, 0.4, 1.0], [0.2, 0.3, 0.5])
    assert out == [2.0, 0.0, 1.0, 2.0, 1.0, 0.0, 2.0, 2.0, 1.0, 2.0]


def test_normal_pairs_have_the_asked_correlation():
    import random

    rng = random.Random(0)
    pairs = [power.normal_pair(rng, 0.7) for _ in range(20000)]
    xs, ys = zip(*pairs, strict=True)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in pairs) / len(pairs)
    vx = sum((x - mx) ** 2 for x in xs) / len(xs)
    vy = sum((y - my) ** 2 for y in ys) / len(ys)
    assert cov / math.sqrt(vx * vy) == pytest.approx(0.7, abs=0.02)


def test_the_power_window_skips_the_saw_tooth():
    """At 1 % with a true 0.5 %, one fixed set first reaches 80 % power at 1,941 rows but
    dips below it 105 times before 2,185; the window rule answers 2,185, a naive "first
    crossing" would answer 1,941."""
    assert power.rows_for_power(0.01, 0.005) == 2185
    assert power.power_to_certify(1941, 0.01, 0.005) >= 0.8
    dips = [m for m in range(1941, 2185) if power.power_to_certify(m, 0.01, 0.005) < 0.8]
    assert len(dips) == 105 and dips[-1] == 2184


def test_the_pass_rule_is_the_librarys_at_every_size():
    """`certifiable_table` must allow exactly the errors `risk_upper_bound` allows, at every
    size the report uses, for every target it reports."""
    from judge_audit.metrics.selective import risk_upper_bound

    for r in power.RISKS:
        kstar = power.certifiable_table(r, max(power.HALVES))
        for m in range(1, max(power.HALVES) + 1):
            k = kstar[m]
            if k >= 0:
                assert risk_upper_bound(k, m) <= r
            if k + 1 <= m:
                assert risk_upper_bound(k + 1, m) > r


def test_the_fast_walk_is_the_library_procedure():
    """A2 simulates `coverage_at_risk` through a precomputed pass rule; on random data with
    ties it must choose the same threshold as the library, including when it certifies."""
    import random

    from judge_audit.metrics.selective import coverage_at_risk

    rng = random.Random(7)
    certified = 0
    for r in (0.01, 0.02, 0.05):
        kstar = power.certifiable_table(r, 1500)
        n_min = power.rows_to_certify(r, 0)
        for _ in range(40):
            n = rng.randint(n_min, 1500)
            err = rng.choice([0.0, r / 4, r, 4 * r])
            conf = [round(rng.random(), rng.choice([1, 2, 3])) for _ in range(n)]
            ok = [rng.random() >= (err if c >= 0.5 else 0.3) for c in conf]
            ours = power.fixed_sequence_threshold(conf, ok, kstar, n_min)
            lib = coverage_at_risk(conf, ok, conf, ok, target_risk=r)["threshold"]
            assert ours == lib
            certified += ours is not None
    assert certified >= 30          # the comparison is not only None against None


def test_delong_by_hand():
    """Five rows: right answers A = 0.9, 0.8, 0.3 and B = 0.9, 0.2, 0.7; wrong answers
    A = 0.5, 0.1 and B = 0.95, 0.1. Placements: A right (1, 1, 1/2), B right (1/2, 1/2,
    1/2); A wrong (2/3, 1), B wrong (0, 1). AUROC A = 5/6, B = 1/2; the paired
    differences' variances are s10 = 1/12 over right answers and s01 = 2/9 over wrong."""
    comp = power.delong([0.9, 0.8, 0.3, 0.5, 0.1], [0.9, 0.2, 0.7, 0.95, 0.1],
                        [True, True, True, False, False])
    assert comp["auroc_a"] == pytest.approx(5 / 6) and comp["auroc_b"] == pytest.approx(0.5)
    assert comp["s10"] == pytest.approx(1 / 12) and comp["s01"] == pytest.approx(2 / 9)
    # n = 10 rows at 60 % accuracy: 6 right, 4 wrong
    assert power.paired_auroc_sd(comp, 10, 0.6) == pytest.approx(
        math.sqrt((1 / 12) / 6 + (2 / 9) / 4))


def test_delong_with_ties_by_hand():
    """Ties count one half. Right answers A = 3, 2, 2 and B = 0.9, 0.5, 0.1; wrong answers
    A = 2, 1 and B = 0.5, 0.2. Placements: A right (1, 3/4, 3/4), B right (1, 3/4, 0);
    A wrong (1/3, 0), B wrong (2/3, 1/3). AUROC A = 5/6, B = 7/12; s10 = 3/16 over right
    answers, s01 = 1/72 over wrong."""
    comp = power.delong([3, 2, 2, 2, 1], [0.9, 0.5, 0.1, 0.5, 0.2],
                        [True, True, True, False, False])
    assert comp["auroc_a"] == pytest.approx(5 / 6) and comp["auroc_b"] == pytest.approx(7 / 12)
    assert comp["s10"] == pytest.approx(3 / 16) and comp["s01"] == pytest.approx(1 / 72)


def test_max_safe_coverage():
    assert power.max_safe_coverage(0.01, 0.0) == pytest.approx(0.5 * 0.2 / 0.19)
    assert power.max_safe_coverage(0.01, 0.02) == 0.0


def test_a2_certification_probability_is_exact(monkeypatch):
    """With continuous confidences the first cut of the sequence holds exactly n_min rows,
    all automatable, and passes only with no error: (1 - r')^n_min, and the simulation
    agrees within its binomial error."""
    import random

    monkeypatch.setattr(power, "REPS_A2", 400)
    r, r_true, n_min = 0.01, 0.0025, power.rows_to_certify(0.01, 0)
    out = power.simulate_fixed_sequence(950, r, r_true, random.Random(3),
                                        power.certifiable_table(r, 950), n_min)
    exact = (1 - r_true) ** n_min
    assert out["p_certify_exact"] == round(exact, 3) == 0.473
    assert abs(out["p_certify_simulated"] - exact) < 3 * math.sqrt(exact * (1 - exact) / 400)


def test_population_auroc():
    """Without ties the binormal AUROC is Phi(mu / sqrt 2); cut into levels it is what a large
    sample cut the same way gives; and one level for everything is a coin flip."""
    import random
    from statistics import NormalDist

    mu = math.sqrt(2) * NormalDist().inv_cdf(0.7)
    assert power.population_auroc(mu, 0.85, None) == pytest.approx(0.7)
    assert power.population_auroc(mu, 0.85, [1.0]) == pytest.approx(0.5)
    rng = random.Random(5)
    ok = [rng.random() < 0.85 for _ in range(60000)]
    scores = power.levels([mu * o + rng.gauss(0, 1) for o in ok], power.TIE_SHARES)
    assert power.auroc(scores, ok) == pytest.approx(
        power.population_auroc(mu, 0.85, power.TIE_SHARES), abs=0.006)


def test_delong_matches_the_simulated_paired_sd():
    """The asymptotic SD of the paired AUROC difference equals the spread of simulated
    differences at a small n."""
    import random

    rng = random.Random(11)
    acc, rho, n = 0.85, 0.5, 400
    mu_a, mu_b = 0.74, 1.0

    def sample(k):
        ok = [rng.random() < acc for _ in range(k)]
        pairs = [power.normal_pair(rng, rho) for _ in range(k)]
        return ([mu_a * o + a for o, (a, _) in zip(ok, pairs, strict=True)],
                [mu_b * o + b for o, (_, b) in zip(ok, pairs, strict=True)], ok)

    comp = power.delong(*sample(40000))
    predicted = power.paired_auroc_sd(comp, n, acc)
    diffs = []
    for _ in range(400):
        a, b, ok = sample(n)
        diffs.append(power.auroc(b, ok) - power.auroc(a, ok))
    assert power.sd(diffs) == pytest.approx(predicted, rel=0.12)


def test_prose_ranges_are_computed_from_the_tables(monkeypatch):
    """Every range in the prose moves with the tables: change one MDE and the sentence
    that quotes BANKING77's range changes too."""
    monkeypatch.setattr(power, "REPS_A2", 20)
    monkeypatch.setattr(power, "REPS_ECE", 8)
    monkeypatch.setattr(power, "N_BIG", 3000)
    d = power.compute()
    md = power.markdown(d)
    cells = [r for r in d["b_paired_auroc"]["rows"] if r["n"] == 3079]
    lo, hi = min(r["mde"] for r in cells), max(r["mde"] for r in cells)
    assert f"At n = 3,079 the MDE is {lo:.4f} to {hi:.4f}" in md
    # B's verdict compares each cell's MDE with that cell's exact gap
    for r in cells:
        r["mde"] = r["gap"] + 0.001
    assert "is resolvable in 0 of 8 cells." in power.markdown(d)
    cells[0]["mde"] = cells[0]["gap"]
    assert "is resolvable in 1 of 8 cells: " in power.markdown(d)
    cells[1]["mde"] = 0.999
    assert "to 0.9990" in power.markdown(d)
    first = d["a_certification"]["rows_to_certify"]["0.01"]["0"]
    assert f"zero errors certify from {first:,} rows" in md
    # the A2 verdicts follow their rows too
    a2 = d["a2_fixed_sequence"]["rows"]
    assert "which is consistent with the 5 % allowed" in md
    a2[0]["violation_rate"] = 0.20          # 20 runs here: 2 SE above 5 % is 14.7 %
    clean = next(r for r in a2 if r["true_rate"] == 0)
    clean["p_certify_exact"] = 0.9
    md2 = power.markdown(d)
    assert "20.0 %, which **exceeds** the 5 % allowed" in md2
    assert "certifies 90 % to 100 % of the time" in md2
