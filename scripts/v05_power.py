"""Power analysis for the v0.5 study (#91): how many rows each claim needs. No API call.

Four questions, answered before any model is run so the pre-registration can fix n:

  A.  Certification at one cut (exact binomial). To state "error rate below r, with 95 %
      confidence" about a set of automated decisions, how many must it hold with 0, 1, 2 ...
      errors; and how many for an 80 % chance to certify one fixed set whose true error
      rate is r' < r. One fixed set's power is an upper bound on the procedure's in A2.
  A2. The procedure itself (simulated, P(certifies) exact). `metrics.selective.
      coverage_at_risk` (#98) walks the calibration half from the most confident row down
      and stops at the first cut that fails. How often does it certify, and how much does
      it automate on the test half, when half the rows are automatable at a true error rate
      r'? Once from #98's start (the cut zero errors could pass) and once from the plan's
      (D3: the cut START_ERRORS errors could pass), on the same calibration halves.
  B.  Paired AUROC (asymptotic, DeLong). Two confidence methods ranking the same decisions
      (H1: same model, verbalized against another method): the smallest AUROC difference
      a paired test detects with 80 % power at alpha 0.05, per n, accuracy, correlation and
      ties. Its variance comes from DeLong's placement values on one large simulated
      sample (100,000 rows), with that sample's Monte Carlo error printed; the gap
      it is compared with is computed exactly.
  C.  Paired ECE (simulated). The same for the difference in ECE between two judges on the
      same rows, with its Monte Carlo standard error.

A2, B and C rest on assumptions stated with each table (a binormal latent score, fixed
shares of tied confidence values, a constant calibration gap, a Gaussian copula between
outcomes). They are planning numbers. The pilot on the BANKING77 train sample
(examples/banking77/labels-pilot.jsonl) estimates accuracy, the agreement between methods
and the tie shares; the plan then edits the constants marked PILOT below in a reviewed
commit and regenerates this report before it is frozen. Every number in the prose is
derived from the tables, so it moves with them.

  python scripts/v05_power.py            # writes docs/v05-power.md and .json
  python scripts/v05_power.py --check    # exit 1 if either differs (CI)

Deterministic: every random draw comes from random.Random(seed).random(); normals are
drawn with Box-Muller from those, so the output does not depend on the Python version.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import random
import sys
from pathlib import Path
from statistics import NormalDist, median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.metrics.calibration import expected_calibration_error  # noqa: E402

OUT_MD = ROOT / "docs" / "v05-power.md"
OUT_JSON = ROOT / "docs" / "v05-power.json"
DELTA = 0.05                      # one-sided, as the certified bound in metrics.selective
POWER = 0.80
Z_ALPHA = NormalDist().inv_cdf(0.975)
Z_POWER = NormalDist().inv_cdf(POWER)
MDE_FACTOR = Z_ALPHA + Z_POWER
SEED = 2026
DATASETS = {"BANKING77 test": 3079, "CLINC150 subset": 1900}   # distinct texts (#99)
N_GRID = [950, 1540, 1900, 3079]  # a CLINC150 half, a BANKING77 half, CLINC150, BANKING77
HALVES = [950, 1540]

# PILOT: the pilot's estimates, from docs/v05-pilot-estimates.json (docs/v05-pilot.md §5, §5b).
ACCURACIES = [0.62, 0.64, 0.69]   # Qwen3-8B read-outs; 0.69 = Wilson upper bound of the highest
RHOS = [0.0, 0.4, 0.45]           # B: latent correlation of the two methods' noise
AUROC_A, AUROC_B = 0.65, 0.70     # latent (continuous) AUROCs of the two methods
# B's tied cells, per method (A: verbalized, B: self-consistency, the primary H1 pair),
# lowest value to highest; the report's "levels" wording is derived from their lengths.
# TIE_SHARES_B is the k = 10 run's, the k §5b's decision rule adopted (SC_SAMPLES).
TIE_SHARES_A = [0.032, 0.14, 0.597, 0.231]
TIE_SHARES_B = [0.013, 0.023, 0.026, 0.032, 0.039, 0.107, 0.76]
SC_SAMPLES = 10                   # method B: self-consistency, a vote over k samples (§5b)
CONF_VALUES = [0.8, 0.9, 0.95, 1.0]
CONF_WEIGHTS = [0.032, 0.14, 0.597, 0.231]
GAP_A, GAP_B = 0.05, 0.08         # judge A 5 points overconfident, judge B 8
# Design choices, not pilot estimates (docs/v05-pilot.md §5): C's copula links the outcomes
# of two different judges (H2), a different quantity from B's within-model RHOS.
RHOS_C = [0.3, 0.7]
AUTOMATABLE = 0.5                 # A2: share of rows in the automatable slice
REST_ERROR = 0.20                 # A2: error rate of the other rows

N_BIG = 100_000                   # B: rows of the large sample the variance comes from
REPS_A2 = 500
REPS_ECE = 800


# --- A. exact binomial ------------------------------------------------------------------


def binom_cdf(k: int, m: int, p: float) -> float:
    """P(Bin(m, p) <= k), summed in log space."""
    if k < 0:
        return 0.0
    if k >= m or p == 0:
        return 1.0
    if p == 1:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [math.lgamma(m + 1) - math.lgamma(i + 1) - math.lgamma(m - i + 1) + i * lp
             + (m - i) * lq for i in range(k + 1)]
    top = max(terms)
    return min(1.0, math.exp(top) * math.fsum(math.exp(t - top) for t in terms))


def binom_pmf(i: int, m: int, p: float) -> float:
    """P(Bin(m, p) = i), in log space."""
    if not 0 <= i <= m:
        return 0.0
    if p == 0 or p == 1:
        return 1.0 if i == (0 if p == 0 else m) else 0.0
    return math.exp(math.lgamma(m + 1) - math.lgamma(i + 1) - math.lgamma(m - i + 1)
                    + i * math.log(p) + (m - i) * math.log1p(-p))


def certifiable_errors(m: int, r: float, delta: float = DELTA) -> int:
    """The most errors among m rows that still certify risk <= r: the one-sided
    Clopper-Pearson upper bound is at most r exactly when P(Bin(m, r) <= k) <= delta, the
    rule `metrics.selective.risk_upper_bound` applies. -1 when even zero errors do not."""
    k = -1
    while k + 1 <= m and binom_cdf(k + 1, m, r) <= delta:
        k += 1
    return k


def certifiable_table(r: float, n_max: int, delta: float = DELTA) -> list[int]:
    """certifiable_errors(m, r) for m = 0 .. n_max, computed incrementally."""
    out, k = [-1], -1
    for m in range(1, n_max + 1):
        while k + 1 <= m and binom_cdf(k + 1, m, r) <= delta:
            k += 1
        out.append(k)
    return out


def rows_to_certify(r: float, errors: int, delta: float = DELTA) -> int:
    """Smallest m whose bound certifies risk <= r with `errors` errors among the m rows."""
    m = errors + 1
    while binom_cdf(errors, m, r) > delta:
        m += 1
    return m


def power_to_certify(m: int, r: float, r_true: float, delta: float = DELTA) -> float:
    """P(one fixed set of m rows certifies risk <= r) when their true error rate is
    r_true."""
    return binom_cdf(certifiable_errors(m, r, delta), m, r_true)


def rows_for_power(r: float, r_true: float, target: float = POWER, limit: int = 20000
                   ) -> int | None:
    """Smallest m from which the power stays at or above `target` (the power saw-tooths
    in m, since the number of errors allowed moves in steps): checked over [m, 2m]."""
    powers: list[float] = []            # powers[m - 1], computed as far as needed
    k = -1

    def power(m: int) -> float:
        nonlocal k
        while len(powers) < m:
            j = len(powers) + 1
            while k + 1 <= j and binom_cdf(k + 1, j, r) <= DELTA:
                k += 1
            powers.append(binom_cdf(k, j, r_true))
        return powers[m - 1]

    m = 1
    while m <= limit:
        bad = next((j for j in range(m, 2 * m + 1) if power(j) < target), None)
        if bad is None:
            return m
        m = bad + 1
    return None


RISKS = [0.01, 0.02, 0.05, 0.1]  # the plan's targets (D2): one table, none the headline
# r' = 0, a quarter and a half of each target
ALTERNATIVES = {r: [0.0, r / 4, r / 2] for r in RISKS}
ERRORS = [0, 1, 2, 5, 10]
START_ERRORS = 2                  # the plan's start (D3): the first cut 2 errors could pass
# A2's first version simulated these targets from the main stream; they keep drawing from it,
# in the same order, so their rows (and B and C after them) keep their published numbers.
# Everything A2 added later (the 10 % target, the plan's start) draws from its own stream.
RISKS_MAIN_STREAM = (0.01, 0.02, 0.05)
SEED_ADDED = SEED + 1


def section_a() -> dict:
    table = {f"{r:g}": {str(e): rows_to_certify(r, e) for e in ERRORS} for r in RISKS}
    power = {f"{r:g}": {f"{t:g}": rows_for_power(r, t) for t in ALTERNATIVES[r]}
             for r in RISKS}
    return {"rows_to_certify": table, "rows_for_80pct_power_one_cut": power}


# --- A2. the fixed-sequence procedure, simulated ------------------------------------------


def fixed_sequence_threshold(confidences: list[float], correct: list[bool], kstar: list[int],
                             n_min: int) -> float | None:
    """The threshold `metrics.selective.coverage_at_risk` chooses on a calibration split,
    with the pass rule precomputed (`kstar[m]`: the most errors m rows may hold). Walks
    whole groups of equal confidence from the top, starts at the first cut holding n_min
    rows, stops at the first failure. Tests check it against the library."""
    order = sorted(range(len(confidences)), key=lambda i: -confidences[i])
    threshold, rows, errors, i = None, 0, 0, 0
    while i < len(order):
        c = confidences[order[i]]
        while i < len(order) and confidences[order[i]] == c:
            rows += 1
            errors += not correct[order[i]]
            i += 1
        if rows < n_min:
            continue
        if errors > kstar[rows]:
            break
        threshold = c
    return threshold


def p_first_cut_passes(n_half: int, m: int, k: int, r_true: float) -> float:
    """Exact P(the procedure certifies) on a calibration half in A2's model, for a sequence
    that starts at m rows and lets them hold k errors (k = kstar[m]).

    With continuous confidences every cut adds one row, so the first cut tested holds
    exactly m rows, and the procedure certifies exactly when it passes (if it fails, the
    walk ends; if it passes, its threshold stands). The top m rows are the automatable
    rows (their number S ~ Bin(n_half, AUTOMATABLE)) first, then the others: min(S, m) rows
    erring at r_true and m - min(S, m) at REST_ERROR, all independent. Summed over S. A
    start past the half (m > n_half) certifies nothing."""
    if m > n_half or k < 0:
        return 0.0
    terms = []
    for s in range(n_half + 1):
        a = min(s, m)
        inside = math.fsum(binom_pmf(x, a, r_true) * binom_cdf(k - x, m - a, REST_ERROR)
                           for x in range(min(k, a) + 1))
        terms.append(binom_pmf(s, n_half, AUTOMATABLE) * inside)
    return min(1.0, math.fsum(terms))


def _true_risk_above(t: float, r_true: float) -> float:
    """The true error rate of the rows above threshold t in A2's model."""
    cut = 1.0 - AUTOMATABLE
    if t >= cut:
        return r_true
    return (AUTOMATABLE * r_true + (cut - t) * REST_ERROR) / (1.0 - t)


def simulate_fixed_sequence(n_half: int, r: float, r_true: float, rng: random.Random,
                            kstar: list[int], n_min: int,
                            later: tuple[int, random.Random] | None = None) -> dict:
    """Both halves draw continuous confidences uniformly on [0, 1]. Rows above
    1 - AUTOMATABLE err at r_true, the others at REST_ERROR. The threshold is chosen on
    the calibration half and applied to the test half. A violation is a threshold whose
    true error rate above it exceeds r (the guarantee says at most DELTA of the time).

    `later` = (n_start, rng_later): the same calibration halves are also walked from the
    plan's later start (the first cut of n_start rows), whose test halves are drawn from
    rng_later, so `rng` is consumed exactly as without it."""
    cut = 1.0 - AUTOMATABLE
    certified = violations = 0
    coverages: list[float] = []                 # test coverage of the runs that certify
    late_certified = late_violations = 0
    late_coverages: list[float] = []
    for _ in range(REPS_A2):
        conf = [rng.random() for _ in range(n_half)]
        ok = [rng.random() >= (r_true if c >= cut else REST_ERROR) for c in conf]
        if later is not None:
            n_start, rng_later = later
            t_late = fixed_sequence_threshold(conf, ok, kstar, n_start)
            if t_late is not None:
                late_certified += 1
                late_coverages.append(
                    sum(1 for _ in range(n_half) if rng_later.random() >= t_late) / n_half)
                late_violations += _true_risk_above(t_late, r_true) > r
        t = fixed_sequence_threshold(conf, ok, kstar, n_min)
        if t is None:
            continue
        certified += 1
        coverages.append(sum(1 for _ in range(n_half) if rng.random() >= t) / n_half)
        violations += _true_risk_above(t, r_true) > r
    row = {"n_half": n_half, "target": r, "true_rate": r_true,
           # exact: see p_first_cut_passes (#98's start: kstar[n_min] = 0 errors allowed)
           "p_certify_exact": round(p_first_cut_passes(n_half, n_min, kstar[n_min], r_true),
                                    3),
           "p_certify_simulated": round(certified / REPS_A2, 3),
           "median_coverage_if_certified": (round(median(coverages), 3) if coverages
                                            else None),
           "mean_coverage": round(math.fsum(coverages) / REPS_A2, 3),
           "violation_rate": round(violations / REPS_A2, 3)}
    if later is not None:
        n_start = later[0]
        row["plan_start"] = {
            "start_errors": START_ERRORS, "start_rows": n_start,
            "p_certify_exact": round(p_first_cut_passes(n_half, n_start,
                                                        kstar[min(n_start, n_half)],
                                                        r_true), 3),
            "p_certify_simulated": round(late_certified / REPS_A2, 3),
            "median_coverage_if_certified": (round(median(late_coverages), 3)
                                             if late_coverages else None),
            "mean_coverage": round(math.fsum(late_coverages) / REPS_A2, 3),
            "violation_rate": round(late_violations / REPS_A2, 3)}
    return row


def max_safe_coverage(r: float, r_true: float) -> float:
    """The largest share of rows whose true error rate is still at most r, in A2's model:
    the automatable slice, then as many of the other rows as the budget allows."""
    if r_true > r:
        return 0.0
    return min(1.0, AUTOMATABLE * (REST_ERROR - r_true) / (REST_ERROR - r))


def section_a2(rng: random.Random, rng_added: random.Random) -> list[dict]:
    """Every cell walked from #98's start and from the plan's (START_ERRORS); see
    RISKS_MAIN_STREAM for which stream each draw comes from."""
    rows = []
    for r in RISKS:
        kstar = certifiable_table(r, max(HALVES))
        n_min = rows_to_certify(r, 0)
        n_start = rows_to_certify(r, START_ERRORS)
        stream = rng if r in RISKS_MAIN_STREAM else rng_added
        for n_half in HALVES:
            for t in ALTERNATIVES[r]:
                rows.append(simulate_fixed_sequence(n_half, r, t, stream, kstar, n_min,
                                                    later=(n_start, rng_added)))
    return rows


# --- shared helpers -----------------------------------------------------------------------


def normal_pair(rng: random.Random, rho: float) -> tuple[float, float]:
    """Two standard normals with correlation rho (Box-Muller on rng.random())."""
    u1, u2 = 1.0 - rng.random(), rng.random()
    radius = math.sqrt(-2.0 * math.log(u1))
    z1, z2 = radius * math.cos(2 * math.pi * u2), radius * math.sin(2 * math.pi * u2)
    return z1, rho * z1 + math.sqrt(1 - rho * rho) * z2


def auroc(scores: list[float], correct: list[bool]) -> float:
    """P(a right answer outranks a wrong one), ties one half: the definition of
    metrics.selective.failure_auroc, by mid-ranks."""
    order = sorted(range(len(scores)), key=scores.__getitem__)
    n_ok = sum(correct)
    n_err = len(correct) - n_ok
    rank_sum, i = 0.0, 0
    while i < len(order):
        j = i
        while j < len(order) and scores[order[j]] == scores[order[i]]:
            j += 1
        mid = (i + 1 + j) / 2
        rank_sum += mid * sum(1 for t in order[i:j] if correct[t])
        i = j
    return (rank_sum - n_ok * (n_ok + 1) / 2) / (n_ok * n_err)


def levels(scores: list[float], shares: list[float]) -> list[float]:
    """Replace each score by its level (0, 1, ...) when the rows, sorted by score, are cut
    into consecutive groups of the given shares: a judge that says one of a few values."""
    order = sorted(range(len(scores)), key=scores.__getitem__)
    out = [0.0] * len(scores)
    bounds, acc = [], 0.0
    for s in shares:
        acc += s
        bounds.append(round(acc * len(scores)))
    level = 0
    for pos, i in enumerate(order):
        while level < len(bounds) - 1 and pos >= bounds[level]:
            level += 1
        out[i] = float(level)
    return out


def sd(xs: list[float]) -> float:
    mean = math.fsum(xs) / len(xs)
    return math.sqrt(math.fsum((x - mean) ** 2 for x in xs) / (len(xs) - 1))


# --- B. paired AUROC, DeLong ----------------------------------------------------------------


def _placements(scores: list[float], correct: list[bool]) -> tuple[list[float], list[float]]:
    """DeLong's placement values: for each right answer, the share of wrong answers it
    outranks (ties one half); for each wrong answer, the share of right answers that
    outrank it. Their means are both the AUROC."""
    pos = [s for s, ok in zip(scores, correct, strict=True) if ok]
    neg = [s for s, ok in zip(scores, correct, strict=True) if not ok]
    sp, sn = sorted(pos), sorted(neg)
    v10 = [(bisect.bisect_left(sn, x) + 0.5 * (bisect.bisect_right(sn, x)
                                               - bisect.bisect_left(sn, x))) / len(sn)
           for x in pos]
    v01 = [(len(sp) - bisect.bisect_right(sp, y) + 0.5 * (bisect.bisect_right(sp, y)
                                                          - bisect.bisect_left(sp, y)))
           / len(sp) for y in neg]
    return v10, v01


def _cov(x: list[float], y: list[float]) -> float:
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    return math.fsum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / (len(x) - 1)


def _variance_of_variance(d: list[float], var: float) -> float:
    """Sampling variance of a variance estimate: (fourth central moment - var^2) / n."""
    m = math.fsum(d) / len(d)
    return (math.fsum((x - m) ** 4 for x in d) / len(d) - var * var) / len(d)


def delong(score_a: list[float], score_b: list[float], correct: list[bool]) -> dict:
    """AUROCs of two methods on the same rows and the per-row variance components of their
    difference: Var(AUROC_A - AUROC_B) = s10 / n_right + s01 / n_wrong (DeLong, DeLong &
    Clarke-Pearson 1988). var_s10 and var_s01 are the sampling variances of those two
    estimates, for the Monte Carlo error of anything computed from one sample."""
    a10, a01 = _placements(score_a, correct)
    b10, b01 = _placements(score_b, correct)
    d10 = [x - y for x, y in zip(a10, b10, strict=True)]
    d01 = [x - y for x, y in zip(a01, b01, strict=True)]
    s10, s01 = _cov(d10, d10), _cov(d01, d01)
    return {"auroc_a": math.fsum(a10) / len(a10), "auroc_b": math.fsum(b10) / len(b10),
            "s10": s10, "s01": s01, "var_s10": _variance_of_variance(d10, s10),
            "var_s01": _variance_of_variance(d01, s01)}


def population_auroc(mu: float, accuracy: float, shares: list[float] | None) -> float:
    """The exact AUROC of one method in B's model: right answers score N(mu, 1), wrong ones
    N(0, 1). With ties, scores are cut at the quantiles of their mixture into levels with the
    given shares (what `levels` does to a sample), and a tie counts one half."""
    norm = NormalDist()
    if shares is None:
        return norm.cdf(mu / math.sqrt(2))

    def mixture(x: float) -> float:
        return accuracy * norm.cdf(x - mu) + (1 - accuracy) * norm.cdf(x)

    cuts, total = [], 0.0
    for share in shares[:-1]:
        total += share
        lo, hi = -12.0, 12.0 + mu
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if mixture(mid) < total else (lo, mid)
        cuts.append((lo + hi) / 2)
    edges = [-math.inf, *cuts, math.inf]

    def mass(shift: float, i: int) -> float:
        return norm.cdf(edges[i + 1] - shift) - norm.cdf(edges[i] - shift)

    auc, below = 0.0, 0.0
    for i in range(len(shares)):
        neg = mass(0.0, i)
        auc += mass(mu, i) * (below + 0.5 * neg)
        below += neg
    return auc


def paired_auroc_sd(components: dict, n: int, accuracy: float) -> float:
    return math.sqrt(components["s10"] / (n * accuracy)
                     + components["s01"] / (n * (1 - accuracy)))


def paired_auroc_sd_mc_se(components: dict, n: int, accuracy: float) -> float:
    """Monte Carlo standard error of `paired_auroc_sd` when s10 and s01 come from one
    simulated sample (delta method: SE(SD) = SE(Var) / 2 SD)."""
    n1, n0 = n * accuracy, n * (1 - accuracy)
    se_var = math.sqrt(components["var_s10"] / n1 ** 2 + components["var_s01"] / n0 ** 2)
    return se_var / (2 * paired_auroc_sd(components, n, accuracy))


def section_b(rng: random.Random) -> list[dict]:
    """One large sample per cell, common random numbers across cells."""
    base = [normal_pair(rng, 0.0) for _ in range(N_BIG)]
    uniforms = [rng.random() for _ in range(N_BIG)]
    mu_a = math.sqrt(2) * NormalDist().inv_cdf(AUROC_A)
    mu_b = math.sqrt(2) * NormalDist().inv_cdf(AUROC_B)
    rows = []
    for ties in ("none", "tied"):
        for acc in ACCURACIES:
            correct = [u < acc for u in uniforms]
            for rho in RHOS:
                w = math.sqrt(1 - rho * rho)
                sa = [mu_a * ok + z1 for ok, (z1, _) in zip(correct, base, strict=True)]
                sb = [mu_b * ok + rho * z1 + w * z2
                      for ok, (z1, z2) in zip(correct, base, strict=True)]
                if ties == "tied":
                    sa, sb = levels(sa, TIE_SHARES_A), levels(sb, TIE_SHARES_B)
                comp = delong(sa, sb, correct)
                tied = ties == "tied"
                pop_a = population_auroc(mu_a, acc, TIE_SHARES_A if tied else None)
                pop_b = population_auroc(mu_b, acc, TIE_SHARES_B if tied else None)
                for n in N_GRID:
                    s = paired_auroc_sd(comp, n, acc)
                    rows.append({"ties": ties, "accuracy": acc, "rho": rho, "n": n,
                                 "errors_expected": round(n * (1 - acc)),
                                 "auroc_a": round(pop_a, 4), "auroc_b": round(pop_b, 4),
                                 "gap": round(pop_b - pop_a, 4),
                                 "sd_difference": round(s, 5),
                                 "mde": round(MDE_FACTOR * s, 4),
                                 "mde_mc_se": round(
                                     MDE_FACTOR * paired_auroc_sd_mc_se(comp, n, acc), 4)})
    return rows


# --- C. paired ECE --------------------------------------------------------------------------


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _draw_conf(rng: random.Random) -> float:
    u, acc = rng.random(), 0.0
    for v, w in zip(CONF_VALUES, CONF_WEIGHTS, strict=True):
        acc += w
        if u < acc:
            return v
    return CONF_VALUES[-1]


def simulate_ece(n: int, rho: float, rng: random.Random) -> dict:
    """Two judges on the same n rows. Each draws its confidence independently from
    CONF_VALUES; P(right) = confidence - gap; the two outcomes are linked by a Gaussian
    copula rho (a hard row is hard for both)."""
    diffs, ea, eb = [], [], []
    for _ in range(REPS_ECE):
        ca, cb, oka, okb = [], [], [], []
        for _ in range(n):
            a, b = _draw_conf(rng), _draw_conf(rng)
            za, zb = normal_pair(rng, rho)
            ca.append(a)
            cb.append(b)
            oka.append(phi(za) < min(max(a - GAP_A, 0.0), 1.0))
            okb.append(phi(zb) < min(max(b - GAP_B, 0.0), 1.0))
        x, y = expected_calibration_error(ca, oka), expected_calibration_error(cb, okb)
        ea.append(x)
        eb.append(y)
        diffs.append(y - x)
    s = sd(diffs)
    se_sd = s / math.sqrt(2 * (REPS_ECE - 1))       # Monte Carlo SE of an SD
    true_a = math.fsum(w * min(v, GAP_A) for v, w in zip(CONF_VALUES, CONF_WEIGHTS,
                                                         strict=True))
    true_b = math.fsum(w * min(v, GAP_B) for v, w in zip(CONF_VALUES, CONF_WEIGHTS,
                                                         strict=True))
    return {"n": n, "rho": rho, "true_ece_a": round(true_a, 3), "true_ece_b": round(true_b, 3),
            "mean_ece_a": round(math.fsum(ea) / REPS_ECE, 4),
            "mean_ece_b": round(math.fsum(eb) / REPS_ECE, 4),
            "sd_difference": round(s, 4), "mde": round(MDE_FACTOR * s, 3),
            "mde_mc_se": round(MDE_FACTOR * se_sd, 4)}


# --- report ---------------------------------------------------------------------------------


def compute() -> dict:
    rng = random.Random(SEED)
    rng_added = random.Random(SEED_ADDED)
    return {"seed": SEED, "delta": DELTA, "power": POWER,
            "a_certification": section_a(),
            "a2_fixed_sequence": {"assumptions": {
                "automatable_share": AUTOMATABLE, "rest_error": REST_ERROR,
                "reps": REPS_A2, "confidences": "continuous, uniform on [0, 1]",
                "plan_start_errors": START_ERRORS, "seed_added": SEED_ADDED},
                "rows": section_a2(rng, rng_added)},
            "b_paired_auroc": {"assumptions": {
                "latent_auroc": [AUROC_A, AUROC_B], "tie_shares_a": TIE_SHARES_A,
                "tie_shares_b": TIE_SHARES_B, "rows_in_large_sample": N_BIG,
                "model": "binormal latent score per method, errors N(0,1), right answers "
                         "N(mu,1); the two methods' noise correlated rho; ties: cut into "
                         f"{tie_label()}; variance from DeLong placement values",
                "limit": LIMIT_B},
                "rows": section_b(rng)},
            "c_paired_ece": {"assumptions": {
                "confidence_values": CONF_VALUES, "weights": CONF_WEIGHTS,
                "gaps": [GAP_A, GAP_B], "bins": 10, "reps": REPS_ECE,
                "model": "each judge draws its confidence independently; P(right) = "
                         "confidence - gap; outcomes linked by a Gaussian copula rho",
                "limit": LIMIT_C},
                "rows": [simulate_ece(n, rho, rng) for rho in RHOS_C for n in N_GRID]}}


def _pct(x: float) -> str:
    """A rate as the repository writes it: '1 %', '0.25 %', '2.5 %'."""
    return f"{round(x * 100, 4):g} %"


def _share(x: float) -> str:
    return f"{round(x * 100)} %"


def tie_label() -> str:
    """'6 levels' when both methods say one of 6 values, '6 and 4 levels' otherwise."""
    a, b = len(TIE_SHARES_A), len(TIE_SHARES_B)
    return f"{a} levels" if a == b else f"{a} and {b} levels"


def tie_label_of(ties: str) -> str:
    return "no ties" if ties == "none" else tie_label()


def tie_values() -> str:
    """How B's tied methods are described: one sentence when both share their shares."""
    if TIE_SHARES_A == TIE_SHARES_B:
        return f"each method says one of {len(TIE_SHARES_A)} values with shares {TIE_SHARES_A}"
    return (f"method A says one of {len(TIE_SHARES_A)} values with shares {TIE_SHARES_A}, "
            f"method B one of {len(TIE_SHARES_B)} with shares {TIE_SHARES_B}")




def coarsening() -> str:
    """B's prose: what the vote's levels do to its observed AUROC."""
    return (f"The tied cells use self-consistency at k = {SC_SAMPLES} (the k adopted under "
            f"docs/v05-pilot.md §5b): method B's levels are those of a {SC_SAMPLES}-sample "
            "vote; with "
            f"{_share(TIE_SHARES_B[-1])} at its top level (unanimous), that coarsening caps "
            "its observed AUROC below what its latent AUROC alone would give. ")


def tied_gap_finding(b: list[dict]) -> str:
    """The plan bullet's finding about the tied cells, computed from B's table: said when
    every tied cell's exact gap is negative, or when every one is positive and below its
    MDE (the vote's coarsening leaves less than the study can resolve)."""
    tied = [r for r in b if r["ties"] == "tied"]
    if not tied:
        return ""
    below = sum(abs(r["gap"]) < r["mde"] for r in tied)
    if all(r["gap"] > 0 for r in tied) and below == len(tied):
        return (f" At the pilot's ties, in every tied cell the exact gap is "
                f"{_span([r['gap'] for r in tied], 4)}, below the MDE in {below} of "
                f"{len(tied)}: the {SC_SAMPLES}-sample vote's coarsening shrinks the assumed "
                f"latent advantage of +{AUROC_B - AUROC_A:.2f} (a design value, not a "
                "measurement) to less than the study can resolve.")
    if any(r["gap"] >= 0 for r in tied):
        return ""
    return (f" At the pilot's ties, in every tied cell the exact gap is negative "
            f"({_span([r['gap'] for r in tied], 4)}), its size smaller than the MDE in {below} "
            f"of {len(tied)}: the {SC_SAMPLES}-sample vote coarsens self-consistency so much "
            f"that its assumed latent advantage of +{AUROC_B - AUROC_A:.2f} becomes an observed "
            "deficit.")


# The two limits of the power model that the pilot does not remove (docs/v05-pilot.md §5),
# printed next to the tables they qualify.
LIMIT_B = ("Part B scores both methods on one shared set of decisions; in the study each "
           "read-out makes its own decisions, and the pilot's decision agreement says how far "
           "apart they are")
LIMIT_C = ("Part C draws each judge's confidence independently of the other's; only their "
           "outcomes are linked")


def _span(values: list[float], digits: int = 3) -> str:
    lo, hi = min(values), max(values)
    return f"{lo:.{digits}f}" if lo == hi else f"{lo:.{digits}f} to {hi:.{digits}f}"


def per_error_increment(table: dict, r: str) -> tuple[int, int]:
    """Smallest and largest number of further rows one more error costs, over the table's
    columns, at target r."""
    cols = [int(e) for e in table[r]]
    steps = [(table[r][str(b)] - table[r][str(a)]) / (b - a)
             for a, b in zip(cols, cols[1:], strict=False)]
    return round(min(steps)), round(max(steps))


def _p_range(values: list[float]) -> str:
    lo, hi = _share(min(values)), _share(max(values))
    return lo if lo == hi else f"{lo} to {hi}"


def _p_dash(values: list[float]) -> str:
    """'17–23 %': a range inside a sentence that already says 'from … to …'."""
    lo, hi = round(min(values) * 100), round(max(values) * 100)
    return f"{lo} %" if lo == hi else f"{lo}–{hi} %"


def blocked(row: dict) -> bool:
    """The plan's start holds more rows than a half can automate at a true error rate of at
    most r in A2's model, even with no error in the slice (r' = 0, the most it can): a
    certification there would be a violation, and it (almost) never happens. A property of
    the (target, half) cell, whatever r'."""
    return (row["plan_start"]["start_rows"]
            > max_safe_coverage(row["target"], 0.0) * row["n_half"])


def plan_start_gain(a2: list[dict]) -> str:
    """The plan bullet's one-line summary of A2's second table."""
    rows = [r for r in a2 if not blocked(r) and r["true_rate"] == r["target"] / 4]
    text = (f"{_p_range([r['plan_start']['p_certify_exact'] for r in rows])} of the time at a "
            f"quarter of the target, where #98's start certifies "
            f"{_p_range([r['p_certify_exact'] for r in rows])}")
    stuck = sorted({(r["target"], r["n_half"]) for r in a2 if blocked(r)})
    if stuck:
        text += "; it cannot usefully start on " + " or ".join(
            f"a {n:,}-row half at {_pct(t)}" for t, n in stuck)
    return text


def plan_start_section(a2: list[dict], reps: int, se_violation: float) -> list[str]:
    """A2's second table and its reading: the same calibration halves walked from the plan's
    start (D3), next to #98's P(certifies). Every figure is computed from the rows."""
    starts = {r["target"]: r["plan_start"]["start_rows"] for r in a2}
    lines = [
        (f"**From the plan's start (D3).** The same calibration halves, walked from the first "
         f"cut holding the rows that certify r with {START_ERRORS} errors ("
         + " / ".join(f"{n:,}" for n in starts.values()) + " rows at "
         + " / ".join(_pct(r) for r in starts) + ") instead of zero. The start depends on "
         "the row counts only, never on which rows are wrong, so the guarantee is the same "
         "(`coverage_at_risk(..., start_errors="
         f"{START_ERRORS})`). P(certifies) is exact by the same argument: the first cut "
         f"tested holds the start's rows, may hold {START_ERRORS} errors, and decides; when "
         "the half's automatable rows are fewer than the start, the rest of the cut comes "
         f"from rows that err at {_share(REST_ERROR)} (the sum over the slice's size is in "
         "`p_first_cut_passes`). The simulated runs use the calibration halves above; their "
         f"test halves come from a second stream (seed {SEED_ADDED}), as do all the "
         f"{_pct(RISKS[-1])} runs, so the rows published before keep their numbers. "
         f"{reps} runs per cell."), "",
        ("| r | r′ | rows per half | start (rows) | P(certifies), #98 start | P(certifies), "
         "plan start, exact | simulated | coverage if certified (median) | mean coverage | "
         "violations |"),
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in a2:
        ps = row["plan_start"]
        cov = ps["median_coverage_if_certified"]
        lines.append(f"| {_pct(row['target'])} | "
                     f"{_pct(row['true_rate']) if row['true_rate'] else '0'} | "
                     f"{row['n_half']:,} | {ps['start_rows']:,} | "
                     f"{_share(row['p_certify_exact'])} | **{_share(ps['p_certify_exact'])}** | "
                     f"{_share(ps['p_certify_simulated'])} | "
                     f"{_share(cov) if cov is not None else '—'} | "
                     f"{_share(ps['mean_coverage'])} | {ps['violation_rate'] * 100:.1f} % |")
    usable = [r for r in a2 if not blocked(r)]
    stuck = [r for r in a2 if blocked(r)]

    def compare(frac: float) -> tuple[str, str, str, str]:
        rows = [r for r in usable if r["true_rate"] == r["target"] * frac]
        return (_p_range([r["plan_start"]["p_certify_exact"] for r in rows]),
                _p_range([r["p_certify_exact"] for r in rows]),
                _p_dash([r["plan_start"]["mean_coverage"] for r in rows]),
                _p_dash([r["mean_coverage"] for r in rows]))

    q_new, q_old, qm_new, qm_old = compare(0.25)
    h_new, h_old, hm_new, hm_old = compare(0.5)
    c_new, c_old, _, _ = compare(0.0)
    worst = max(r["plan_start"]["violation_rate"] for r in a2)
    verdict = ("is consistent with" if worst <= DELTA + 2 * se_violation else "**exceeds**")
    text = (f"**Read it this way.** With a true error rate a quarter of the target the plan's "
            f"start certifies {q_new} of the time, against {q_old} from #98's start, and its "
            f"mean coverage (a run that certifies nothing counts 0) goes from {qm_old} to "
            f"{qm_new}; at half the target it certifies {h_new} ({h_old}), mean coverage "
            f"{hm_old} → {hm_new}; with no error in the slice, {c_new} ({c_old}). A few errors "
            "no longer end the walk before it reaches the rows that could absorb them. ")
    if stuck:
        cells = sorted({(r["target"], r["n_half"]) for r in stuck})
        where = "; ".join(
            f"at {_pct(t)} on a {n:,}-row half the start ({starts[t]:,} rows) is more than "
            f"the {math.floor(max_safe_coverage(t, 0.0) * n):,} rows it can automate at a "
            f"true error rate of at most {_pct(t)} even when r′ = 0"
            for t, n in cells)
        p_stuck = _p_range([r["plan_start"]["p_certify_exact"] for r in stuck])
        p_stuck_old = _p_range([r["p_certify_exact"] for r in stuck])
        text += (f"What it costs: {where}, so there it certifies {p_stuck} of the time "
                 f"(#98's start: {p_stuck_old}), because of where the sequence starts, not "
                 "because of the judge. ")
    text += (f"The largest violation rate from the plan's start is {worst * 100:.1f} %, "
             f"which {verdict} the {_pct(DELTA)} allowed.")
    return [*lines, "", text]


def markdown(d: dict) -> str:
    a = d["a_certification"]
    table = a["rows_to_certify"]
    first = table[f"{RISKS[0]:g}"]["0"]
    inc_lo, inc_hi = per_error_increment(table, f"{RISKS[0]:g}")
    a2 = d["a2_fixed_sequence"]["rows"]
    b = d["b_paired_auroc"]["rows"]
    c = d["c_paired_ece"]["rows"]
    big, clinc = DATASETS["BANKING77 test"], DATASETS["CLINC150 subset"]

    lines = [
        "# v0.5 power analysis (pre-registration input, #91)", "",
        (f"Generated by `scripts/v05_power.py` (seed {d['seed']}); CI regenerates it. **No model "
         "was called.** Part A is exact. A2, B and C rest on the assumptions stated with each "
         "table: they are planning numbers. Accuracy, the agreement between methods, the AUROC "
         "level and the tie shares are the pilot's estimates on the BANKING77 train sample "
         "([docs/v05-pilot-estimates.md](v05-pilot-estimates.md), rules fixed in "
         "[docs/v05-pilot.md](v05-pilot.md) §5), set in the script's PILOT constants before "
         "`docs/v05-plan.md` fixes n. Every figure in the prose below is "
         "computed from the tables."), "",
        "## A. Certifying one set of automated decisions (exact)", "",
        ("One-sided 95 % Clopper-Pearson bound, the rule `metrics.selective` applies. Rows a "
         "set of automated decisions must hold so that its errors still certify \"error rate "
         "at most r\":"), "",
        "| target risk r | " + " | ".join(f"{e} errors" if i == 0 else str(e)
                                           for i, e in enumerate(ERRORS)) + " |",
        "|---|" + "---:|" * len(ERRORS)]
    for r, row in table.items():
        lines.append(f"| {_pct(float(r))} | "
                     + " | ".join(f"{row[str(e)]:,}" for e in ERRORS) + " |")
    lines += ["", (f"At {_pct(RISKS[0])}, zero errors certify from {first:,} rows, and each "
               f"further error costs about {inc_lo}–{inc_hi} more rows."), "",
              ("Rows one **fixed** set needs for an 80 % chance to certify r when its true "
               "error rate is r′ (the power saw-tooths in n; the number is where it stays at "
               "or above 80 % up to twice that n). The procedure in A2 chooses its set from the "
               "data and stops at the first cut that fails, so this power is an upper bound on "
               "its power, and these row counts are a lower bound on the rows it needs:"), "", "| target risk r | r′ | rows for 80 % power, one fixed set |",
              "|---|---|---:|"]
    for r, row in a["rows_for_80pct_power_one_cut"].items():
        for t, m in row.items():
            lines.append(f"| {_pct(float(r))} | {_pct(float(t)) if float(t) else '0'} | "
                         + (f"{m:,} |" if m else "> 20,000 |"))

    reps = d["a2_fixed_sequence"]["assumptions"]["reps"]
    lines += ["", "## A2. The certification procedure itself (simulated)", "",
              f"`coverage_at_risk` (#98) on a calibration half, applied to a test half of the "
              f"same size. Confidences are continuous; the top {_share(AUTOMATABLE)} of rows "
              f"err at r′, the rest at {_share(REST_ERROR)}. The most a half can automate with a "
              "true error rate still at most r is the slice plus as many other rows as r "
              "allows: "
              + ", ".join(f"{_share(max_safe_coverage(r, 0.0))} at {_pct(r)}" for r in RISKS)
              + " when r′ = 0. With continuous confidences the first cut the procedure tests "
              f"holds exactly the rows zero errors need ({first:,} at {_pct(RISKS[0])}), all "
              "inside the slice, and passes only if they hold no error, so P(certifies) = "
              "(1 − r′)^rows (the exact column sums over the slice's size, "
              "`p_first_cut_passes`, which differs only if a half's slice could hold fewer "
              "rows than the cut); the simulated share is printed next to it as a check. "
              f"{reps} simulated datasets per cell (Monte Carlo SE of a share: at most "
              f"{100 * math.sqrt(0.25 / reps):.1f} points). Coverage is on the test half, "
              "given that the procedure certified; mean coverage counts a run that "
              "certified nothing as 0. *Violation* = a threshold whose true error rate above "
              f"it exceeds r; the guarantee allows it {_pct(DELTA)} of the time.", "",
              ("| r | r′ | rows per half | P(certifies), exact | simulated | coverage if "
               "certified (median) | mean coverage | violations |"),
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for row in a2:
        cov = row["median_coverage_if_certified"]
        lines.append(f"| {_pct(row['target'])} | "
                     f"{_pct(row['true_rate']) if row['true_rate'] else '0'} | "
                     f"{row['n_half']:,} | {_share(row['p_certify_exact'])} | "
                     f"{_share(row['p_certify_simulated'])} | "
                     f"{_share(cov) if cov is not None else '—'} | "
                     f"{_share(row['mean_coverage'])} | {row['violation_rate'] * 100:.1f} % |")
    worst_violation = max(row["violation_rate"] for row in a2)
    clean = [row for row in a2 if row["true_rate"] == 0]
    quarter = [row for row in a2 if row["true_rate"] == row["target"] / 4]
    half = [row for row in a2 if row["true_rate"] == row["target"] / 2]

    def p_range(rows: list[dict]) -> str:
        lo = min(r["p_certify_exact"] for r in rows)
        hi = max(r["p_certify_exact"] for r in rows)
        return _share(lo) if _share(lo) == _share(hi) else f"{_share(lo)} to {_share(hi)}"

    def cov_range(rows: list[dict]) -> str:
        vals = [r["median_coverage_if_certified"] for r in rows
                if r["median_coverage_if_certified"] is not None]
        if not vals:
            return "nothing"
        lo, hi = _share(min(vals)), _share(max(vals))
        return lo if lo == hi else f"{lo} to {hi}"

    se_violation = math.sqrt(DELTA * (1 - DELTA) / reps)
    guarantee = ("is consistent with" if worst_violation <= DELTA + 2 * se_violation
                 else "**exceeds**")
    lines += ["", ("**Read it this way.** With no error in the automatable slice the procedure "
               f"certifies {p_range(clean)} of the time and then automates "
               f"{cov_range(clean)} of a half (median). With a true error rate a quarter of "
               f"the target it certifies {p_range(quarter)} of the time, and at half the target "
               f"{p_range(half)}; when it does certify there, it automates {cov_range(half)}. "
               "The reason is where the sequence starts: #98 starts at the smallest cut that "
               f"could pass ({first:,} rows at {_pct(RISKS[0])}, where it must hold zero "
               "errors), and with continuous confidences one error among those rows ends the "
               "walk before any larger cut is tried. The largest violation rate in the table "
               f"is {worst_violation * 100:.1f} %, which {guarantee} the {_pct(DELTA)} allowed "
               f"(each rate is one simulated estimate, standard error about "
               f"{se_violation * 100:.1f} points). "
               "The plan starts the sequence at a later, pre-registered cut (D3); the next "
               "table shows what that changes."), "",
              *plan_start_section(a2, reps, se_violation), "",
              "## B. Paired AUROC: the smallest difference resolved", "",
              (f"Two confidence methods on the same decisions, latent AUROCs {AUROC_A} and "
               f"{AUROC_B}. Ties \"none\": continuous scores; \"tied\": {tie_values()}, "
               f"lowest to highest. {coarsening()}ρ is the latent correlation of "
               "the two methods' noise; the pilot measures the rank agreement of the two "
               "methods and ρ is set to reproduce it (the largest ρ, verbalized against "
               "token log-probability, is lower when the pilot's confidences are compared "
               "exactly rather than to 1e-6: see the sensitivity section of "
               "[the estimates](v05-pilot-estimates.md)). The standard deviation of the paired "
               "difference comes from DeLong's placement values on one sample of "
               f"{N_BIG:,} rows per cell, scaled to n; MDE = (z₀.₉₇₅ + z₀.₈) × SD, the "
               "smallest true difference a paired test at α = 0.05 detects with 80 % power. "
               "That one sample makes each MDE an estimate: the ± after it is its Monte "
               "Carlo standard error (delta method from the fourth moments of the placement "
               "differences). The AUROC columns and their gap are exact population values "
               "after ties, not sample estimates."), "",
              "| ties | accuracy | ρ | n | errors | AUROC A | AUROC B | gap | SD(Δ) | MDE |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in b:
        lines.append(f"| {tie_label_of(r['ties'])} | {_share(r['accuracy'])} | {r['rho']} | "
                     f"{r['n']:,} | "
                     f"{r['errors_expected']:,} | {r['auroc_a']:.4f} | {r['auroc_b']:.4f} | "
                     f"{r['gap']:.4f} | {r['sd_difference']:.5f} | **{r['mde']:.4f}** ± "
                     f"{r['mde_mc_se']:.4f} |")
    for n in (big, clinc):
        cells = [r for r in b if r["n"] == n]
        ok = [r for r in cells if r["mde"] <= abs(r["gap"])]      # the test is two-sided
        tied_gaps = [r["gap"] for r in cells if r["ties"] == "tied"]
        lines += ["", f"At n = {n:,} the MDE is {_span([r['mde'] for r in cells], 4)}; the exact "
                  f"gap between the two methods ({AUROC_B - AUROC_A:.4f} without ties, "
                  f"{_span(tied_gaps, 4)} with {tie_label()}) is resolvable in {len(ok)} of "
                  f"{len(cells)} cells"
                  + (": " + "; ".join(f"{tie_label_of(r['ties'])}, accuracy "
                                      f"{_share(r['accuracy'])}, ρ {r['rho']}" for r in ok)
                     if ok else "") + "."]
        close = min(cells, key=lambda r: abs(r["mde"] - abs(r["gap"])) / r["mde_mc_se"])
        lines[-1] += (f" The closest call is {tie_label_of(close['ties'])}, accuracy "
                      f"{_share(close['accuracy'])}, ρ {close['rho']}: MDE "
                      f"{close['mde']:.4f} ± {close['mde_mc_se']:.4f} against a gap of "
                      f"{close['gap']:.4f}, "
                      f"{abs(close['mde'] - abs(close['gap'])) / close['mde_mc_se']:.1f} standard "
                      "errors apart.")
    lines += ["", ("What drives it is the number of **errors**, not rows: at "
               f"{_share(ACCURACIES[-1])} accuracy {big:,} rows hold about "
               f"{round(big * (1 - ACCURACIES[-1])):,}."), "",
              f"**Limit of this model.** {LIMIT_B}.", "",
              "## C. Paired ECE: the smallest difference resolved", "",
              (f"Two judges on the same rows, overconfident by {GAP_A} and {GAP_B}. Each draws "
               f"its confidence independently from {CONF_VALUES} with weights "
               f"{CONF_WEIGHTS}; 10 equal-width bins; outcomes linked by a Gaussian copula ρ. "
               f"{REPS_ECE} simulated datasets per cell; the ± is the Monte Carlo standard "
               "error of the MDE."), "",
              "| ρ | n | true ECE A | mean ECE A | true ECE B | mean ECE B | SD(Δ) | MDE |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in c:
        lines.append(f"| {r['rho']} | {r['n']:,} | {r['true_ece_a']:.3f} | "
                     f"{r['mean_ece_a']:.4f} | {r['true_ece_b']:.3f} | {r['mean_ece_b']:.4f} "
                     f"| {r['sd_difference']:.4f} | **{r['mde']:.3f}** ± {r['mde_mc_se']:.4f} |")
    bias = [abs(r[f"mean_ece_{j}"] - r[f"true_ece_{j}"]) for r in c for j in ("a", "b")]
    lines += ["", (f"The binned ECE's bias against the true gap is at most {max(bias):.4f} "
               "here.")]
    for n in (big, clinc):
        cells = [r for r in c if r["n"] == n]
        lines.append(f"At n = {n:,} the ECE MDE is {_span([r['mde'] for r in cells])}.")
    lines += ["", f"**Limit of this model.** {LIMIT_C}."]
    b_big = [r["mde"] for r in b if r["n"] == big]
    b_clinc = [r["mde"] for r in b if r["n"] == clinc]
    c_big = [r["mde"] for r in c if r["n"] == big]
    c_clinc = [r["mde"] for r in c if r["n"] == clinc]
    lines += ["", "## What the plan takes from this (proposals for `docs/v05-plan.md`)", "",
              (f"- **n**: every distinct text, {big:,} for BANKING77 and {clinc:,} for "
               "CLINC150; paired comparisons use all of them, certification uses halves."),
              (f"- **Certification**: at {_pct(RISKS[0])} zero errors certify from {first:,} "
               f"automated rows and each further error costs about {inc_lo}–{inc_hi} more. "
               "The maintainer's decisions for the plan: certify at "
               + ", ".join(_pct(r) for r in RISKS[:-1]) + f" and {_pct(RISKS[-1])} in one "
               f"table (D2), and start the fixed sequence at the {START_ERRORS}-error cut (D3), "
               "which A2's second table shows certifying "
               + plan_start_gain(a2) + "."),
              (f"- **Smallest differences stated before the runs**: paired AUROC "
               f"{_span(b_big)} on BANKING77 and {_span(b_clinc)} on CLINC150; ECE "
               f"{_span(c_big)} and {_span(c_clinc)} (80 % power, α = 0.05)."
               + tied_gap_finding(b) + " The plan "
               "states the MDE of the cell the pilot matches. The MDE sizes the study; the "
               "paired test judges each observed difference, and a difference it does not "
               "resolve is reported as not resolved, not as no difference."),
              ("- **Caveat**: A2, B and C assume the shapes above. B takes its accuracy, ρ, "
               "AUROC level and ties, and C takes only its confidence distribution, from a "
               "308-row pilot on train queries with one open model (Qwen3-8B, 4-bit), not from "
               "the judges or the test split the study scores; C's ρ (`RHOS_C`) and "
               "overconfidence gaps, and A2's slice, are design values, not pilot "
               "estimates."), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    d = compute()
    md, js = markdown(d), json.dumps(d, indent=1) + "\n"
    if args.check:
        stale = [p for p, text in ((OUT_MD, md), (OUT_JSON, js))
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"differs: {p.relative_to(ROOT)}")
        return 1 if stale else 0
    OUT_MD.write_text(md, encoding="utf-8")
    OUT_JSON.write_text(js, encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(ROOT)} and {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
