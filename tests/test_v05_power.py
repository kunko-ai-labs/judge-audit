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
    A = 2, 1 and B = 0.5, 0.2. A right answer's placement is the share of wrong answers
    below it, a wrong answer's the share of right answers above it: A right (1, 3/4, 3/4),
    B right (1, 3/4, 0); A wrong (2/3, 1), B wrong (1/2, 2/3). AUROC A = 5/6, B = 7/12;
    the differences' variances (n - 1) are s10 = 3/16 over right answers and s01 = 1/72
    over wrong."""
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

    shares = [0.05, 0.05, 0.10, 0.15, 0.25, 0.40]   # the design values, fixed here: the
    mu = math.sqrt(2) * NormalDist().inv_cdf(0.7)     # pilot will change the constants
    mu_b = math.sqrt(2) * NormalDist().inv_cdf(0.75)
    assert power.population_auroc(mu, 0.85, None) == pytest.approx(0.7)
    assert power.population_auroc(mu, 0.85, [1.0]) == pytest.approx(0.5)
    # recomputed independently (erfc, Newton quantiles, 1 - P(neg > pos) - P(tie) / 2)
    for m, acc, want in ((mu, 0.85, 0.687810), (mu_b, 0.85, 0.737178),
                         (mu, 0.93, 0.688883), (mu_b, 0.93, 0.738489)):
        assert power.population_auroc(m, acc, shares) == pytest.approx(want, abs=1e-5)
    rng = random.Random(5)
    ok = [rng.random() < 0.85 for _ in range(60000)]
    scores = power.levels([mu * o + rng.gauss(0, 1) for o in ok], shares)
    assert power.auroc(scores, ok) == pytest.approx(
        power.population_auroc(mu, 0.85, shares), abs=0.006)


def test_the_mde_monte_carlo_error_matches_reseeded_samples():
    """The delta-method SE of the paired SD, from one sample, matches the spread of that SD
    over independent samples of the same size."""
    import random
    import statistics

    rng = random.Random(7)
    acc, n_sample, n = 0.85, 4000, 1900

    def one():
        ok = [rng.random() < acc for _ in range(n_sample)]
        pairs = [power.normal_pair(rng, 0.5) for _ in range(n_sample)]
        comp = power.delong([0.74 * o + a for o, (a, _) in zip(ok, pairs, strict=True)],
                            [1.0 * o + b for o, (_, b) in zip(ok, pairs, strict=True)], ok)
        return (power.paired_auroc_sd(comp, n, acc),
                power.paired_auroc_sd_mc_se(comp, n, acc))

    runs = [one() for _ in range(60)]
    spread = statistics.stdev(sd for sd, _ in runs)
    assert statistics.fmean(se for _, se in runs) == pytest.approx(spread, rel=0.3)


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
    # a fixed 2 x 2 grid (8 cells at each n), independent of the PILOT constants
    monkeypatch.setattr(power, "ACCURACIES", [0.85, 0.93])
    monkeypatch.setattr(power, "RHOS", [0.3, 0.7])
    # and the design's positive gap (the pilot's ties make it negative)
    monkeypatch.setattr(power, "AUROC_A", 0.70)
    monkeypatch.setattr(power, "AUROC_B", 0.75)
    for name in ("TIE_SHARES_A", "TIE_SHARES_B"):
        monkeypatch.setattr(power, name, [0.05, 0.05, 0.10, 0.15, 0.25, 0.40])
    d = power.compute()
    md = power.markdown(d)
    cells = [r for r in d["b_paired_auroc"]["rows"] if r["n"] == 3079]
    lo, hi = min(r["mde"] for r in cells), max(r["mde"] for r in cells)
    assert f"At n = 3,079 the MDE is {lo:.4f} to {hi:.4f}" in md
    # B's verdict compares each cell's MDE with that cell's exact gap: 0.0003 above a tied
    # gap is still below the untied 0.05, so a single global gap would say 4 of 8
    for r in cells:
        r["mde"] = r["gap"] + 0.0003
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


def test_levels_wording_follows_each_methods_shares(monkeypatch):
    """B's "levels" wording comes from the lengths of the two methods' tie shares."""
    monkeypatch.setattr(power, "TIE_SHARES_A", [0.05, 0.05, 0.10, 0.15, 0.25, 0.40])
    monkeypatch.setattr(power, "TIE_SHARES_B", [0.05, 0.05, 0.10, 0.15, 0.25, 0.40])
    assert power.tie_label() == "6 levels" and power.tie_label_of("none") == "no ties"
    assert power.tie_values().startswith("each method says one of 6 values with shares")
    monkeypatch.setattr(power, "TIE_SHARES_B", [0.4, 0.2, 0.4])
    assert power.tie_label() == "6 and 3 levels"
    assert "method B one of 3 with shares [0.4, 0.2, 0.4]" in power.tie_values()


def test_b_cuts_each_method_by_its_own_shares_and_c_uses_rhos_c(monkeypatch):
    """One level for method B makes its tied AUROC a coin flip while A's is untouched; part
    C iterates over RHOS_C, not B's RHOS."""
    import random

    monkeypatch.setattr(power, "N_BIG", 2000)
    monkeypatch.setattr(power, "ACCURACIES", [0.85])
    monkeypatch.setattr(power, "RHOS", [0.5])
    monkeypatch.setattr(power, "AUROC_A", 0.70)
    monkeypatch.setattr(power, "AUROC_B", 0.75)
    monkeypatch.setattr(power, "TIE_SHARES_A", [0.05, 0.05, 0.10, 0.15, 0.25, 0.40])
    monkeypatch.setattr(power, "TIE_SHARES_B", [1.0])
    tied = [r for r in power.section_b(random.Random(1)) if r["ties"] == "tied"]
    assert all(r["auroc_b"] == 0.5 for r in tied)
    assert all(r["auroc_a"] == pytest.approx(0.6878, abs=1e-4) for r in tied)
    monkeypatch.setattr(power, "RHOS_C", [0.2])
    monkeypatch.setattr(power, "REPS_A2", 5)
    monkeypatch.setattr(power, "REPS_ECE", 3)
    monkeypatch.setattr(power, "N_GRID", [950])
    d = power.compute()
    assert [r["rho"] for r in d["c_paired_ece"]["rows"]] == [0.2]
    assert [r["rho"] for r in d["b_paired_auroc"]["rows"]] == [0.5, 0.5]
    assert d["b_paired_auroc"]["assumptions"]["tie_shares_b"] == [1.0]


def test_the_model_limits_are_printed_next_to_their_tables(monkeypatch):
    monkeypatch.setattr(power, "REPS_A2", 5)
    monkeypatch.setattr(power, "REPS_ECE", 3)
    monkeypatch.setattr(power, "N_BIG", 2000)
    md = power.markdown(power.compute())
    b, c = md.index("## B."), md.index("## C.")
    assert b < md.index(power.LIMIT_B) < c < md.index(power.LIMIT_C)
    assert "one shared set of decisions" in power.LIMIT_B
    assert "independently" in power.LIMIT_C


def test_the_pilot_constants_are_the_estimates_proposed():
    """Every PILOT constant is exactly what docs/v05-pilot-estimates.json proposes: a change
    to either without the other fails here."""
    import json

    proposed = json.loads((ROOT / "docs" / "v05-pilot-estimates.json").read_text(
        encoding="utf-8"))["proposed_constants"]
    for name in ("ACCURACIES", "RHOS", "AUROC_A", "AUROC_B", "TIE_SHARES_A", "TIE_SHARES_B",
                 "CONF_VALUES", "CONF_WEIGHTS"):
        assert getattr(power, name) == proposed[name]["value"], name
    # §5b: the k whose tie shares TIE_SHARES_B holds, as the prose names it
    assert power.SC_SAMPLES == proposed["SC_K"]["value"]


def _small(monkeypatch):
    monkeypatch.setattr(power, "REPS_A2", 5)
    monkeypatch.setattr(power, "REPS_ECE", 3)
    monkeypatch.setattr(power, "N_BIG", 3000)
    return power.compute()


def test_resolvable_means_mde_at_most_the_absolute_gap(monkeypatch):
    """The paired test is two-sided: a gap of -0.06 against an MDE of 0.05 is resolvable."""
    d = _small(monkeypatch)
    cells = [r for r in d["b_paired_auroc"]["rows"] if r["n"] == 3079]
    for r in cells:
        r["mde"], r["gap"] = 0.05, 0.01
    cells[0]["gap"] = -0.06
    assert f"is resolvable in 1 of {len(cells)} cells: " in power.markdown(d)


def test_the_plan_bullet_states_a_negative_tied_gap_from_the_table(monkeypatch):
    d = _small(monkeypatch)
    rows = d["b_paired_auroc"]["rows"]
    tied = [r for r in rows if r["ties"] == "tied"]
    for i, r in enumerate(tied):
        r["gap"], r["mde"] = -0.0138 - 0.001 * (i % 3), 0.03
    md = power.markdown(d)
    bullet = next(line for line in md.splitlines() if line.startswith("- **Smallest"))
    assert "in every tied cell the exact gap is negative (-0.0158 to -0.0138" in bullet
    assert f"smaller than the MDE in {len(tied)} of {len(tied)}" in bullet
    tied[0]["gap"] = 0.02
    bullet = next(line for line in power.markdown(d).splitlines()
                  if line.startswith("- **Smallest"))
    assert "in every tied cell the exact gap is negative" not in bullet
    # all positive but all below the MDE: said too, with the range, computed
    for i, r in enumerate(tied):
        r["gap"], r["mde"] = 0.0028 + 0.001 * (i % 3), 0.03
    bullet = next(line for line in power.markdown(d).splitlines()
                  if line.startswith("- **Smallest"))
    assert ("in every tied cell the exact gap is 0.0028 to 0.0048, below the MDE in "
            f"{len(tied)} of {len(tied)}") in bullet
    tied[0]["mde"] = 0.001                  # one cell resolvable: no blanket statement
    bullet = next(line for line in power.markdown(d).splitlines()
                  if line.startswith("- **Smallest"))
    assert "in every tied cell" not in bullet


def test_b_prose_explains_the_coarsening_and_c_takes_only_the_distribution(monkeypatch):
    monkeypatch.setattr(power, "TIE_SHARES_B", [0.003, 0.013, 0.055, 0.107, 0.822])
    md = power.markdown(_small(monkeypatch))
    assert "verbalized 0.95" not in md
    assert "82 % at its top level" in md and "coarsening" in md
    assert "B and C take their accuracy" not in md
    assert "C takes only its confidence distribution" in md
