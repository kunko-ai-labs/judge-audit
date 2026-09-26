"""Power analysis for the v0.5 study (#91): how many rows each claim needs. No API call.

Four questions, answered before any model is run so the pre-registration can fix n:

  A.  Certification at one cut (exact binomial). To state "error rate below r, with 95 %
      confidence" about a set of automated decisions, how many must it hold with 0, 1, 2 ...
      errors; and how many for an 80 % chance to certify one fixed set whose true error
      rate is r' < r. One fixed set's power is an upper bound on the procedure's in A2.
  A2. The procedure itself (simulated). `metrics.selective.coverage_at_risk` (#98) walks
      the calibration half from the most confident row down and stops at the first cut
      that fails. How often does it certify, and how much does it automate on the test
      half, when half the rows are automatable at a true error rate r'?
  B.  Paired AUROC (asymptotic, DeLong). Two confidence methods ranking the same decisions
      (H1: same model, verbalized against another method): the smallest AUROC difference
      a paired test detects with 80 % power at alpha 0.05, per n, accuracy, correlation and
      ties. Its variance comes from DeLong's placement values on one large simulated
      sample (100,000 rows); the gap it is compared with is computed exactly.
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

# PILOT: replaced by the pilot's estimates before the plan is frozen.
ACCURACIES = [0.85, 0.93]
RHOS = [0.3, 0.7]                 # latent correlation of the two methods' noise
AUROC_A, AUROC_B = 0.70, 0.75     # latent (continuous) AUROCs of the two methods
TIE_SHARES = [0.05, 0.05, 0.10, 0.15, 0.25, 0.40]   # 6 values, the top one for 40 %
CONF_VALUES = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]
CONF_WEIGHTS = [0.03, 0.05, 0.10, 0.12, 0.25, 0.30, 0.15]
GAP_A, GAP_B = 0.05, 0.08         # judge A 5 points overconfident, judge B 8
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


RISKS = [0.01, 0.02, 0.05]
# r' = 0, a quarter and a half of each target
ALTERNATIVES = {r: [0.0, r / 4, r / 2] for r in (0.01, 0.02, 0.05)}
ERRORS = [0, 1, 2, 5, 10]


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


def simulate_fixed_sequence(n_half: int, r: float, r_true: float, rng: random.Random,
                            kstar: list[int], n_min: int) -> dict:
    """Both halves draw continuous confidences uniformly on [0, 1]. Rows above
    1 - AUTOMATABLE err at r_true, the others at REST_ERROR. The threshold is chosen on
    the calibration half and applied to the test half. A violation is a threshold whose
    true error rate above it exceeds r (the guarantee says at most DELTA of the time)."""
    cut = 1.0 - AUTOMATABLE
    certified = violations = 0
    coverages: list[float] = []                 # test coverage of the runs that certify
    for _ in range(REPS_A2):
        conf = [rng.random() for _ in range(n_half)]
        ok = [rng.random() >= (r_true if c >= cut else REST_ERROR) for c in conf]
        t = fixed_sequence_threshold(conf, ok, kstar, n_min)
        if t is None:
            continue
        certified += 1
        coverages.append(sum(1 for _ in range(n_half) if rng.random() >= t) / n_half)
        above = 1.0 - t
        true_risk = (r_true if t >= cut else
                     (AUTOMATABLE * r_true + (cut - t) * REST_ERROR) / above)
        violations += true_risk > r
    return {"n_half": n_half, "target": r, "true_rate": r_true,
            # continuous confidences: the first cut holds exactly n_min rows, all in the
            # automatable slice, and passes only with no error, so this is exact
            "p_certify_exact": round((1 - r_true) ** n_min, 3),
            "p_certify_simulated": round(certified / REPS_A2, 3),
            "median_coverage_if_certified": (round(median(coverages), 3) if coverages
                                             else None),
            "mean_coverage": round(math.fsum(coverages) / REPS_A2, 3),
            "violation_rate": round(violations / REPS_A2, 3)}


def max_safe_coverage(r: float, r_true: float) -> float:
    """The largest share of rows whose true error rate is still at most r, in A2's model:
    the automatable slice, then as many of the other rows as the budget allows."""
    if r_true > r:
        return 0.0
    return min(1.0, AUTOMATABLE * (REST_ERROR - r_true) / (REST_ERROR - r))


def section_a2(rng: random.Random) -> list[dict]:
    rows = []
    for r in RISKS:
        kstar = certifiable_table(r, max(HALVES))
        n_min = rows_to_certify(r, 0)
        for n_half in HALVES:
            for t in ALTERNATIVES[r]:
                rows.append(simulate_fixed_sequence(n_half, r, t, rng, kstar, n_min))
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


def delong(score_a: list[float], score_b: list[float], correct: list[bool]) -> dict:
    """AUROCs of two methods on the same rows and the per-row variance components of their
    difference: Var(AUROC_A - AUROC_B) = s10 / n_right + s01 / n_wrong (DeLong, DeLong &
    Clarke-Pearson 1988)."""
    a10, a01 = _placements(score_a, correct)
    b10, b01 = _placements(score_b, correct)
    d10 = [x - y for x, y in zip(a10, b10, strict=True)]
    d01 = [x - y for x, y in zip(a01, b01, strict=True)]
    return {"auroc_a": math.fsum(a10) / len(a10), "auroc_b": math.fsum(b10) / len(b10),
            "s10": _cov(d10, d10), "s01": _cov(d01, d01)}


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
                    sa, sb = levels(sa, TIE_SHARES), levels(sb, TIE_SHARES)
                comp = delong(sa, sb, correct)
                shares = TIE_SHARES if ties == "tied" else None
                pop_a = population_auroc(mu_a, acc, shares)
                pop_b = population_auroc(mu_b, acc, shares)
                for n in N_GRID:
                    s = paired_auroc_sd(comp, n, acc)
                    rows.append({"ties": ties, "accuracy": acc, "rho": rho, "n": n,
                                 "errors_expected": round(n * (1 - acc)),
                                 "auroc_a": round(pop_a, 4), "auroc_b": round(pop_b, 4),
                                 "gap": round(pop_b - pop_a, 4),
                                 "sd_difference": round(s, 5),
                                 "mde": round(MDE_FACTOR * s, 4)})
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
    return {"seed": SEED, "delta": DELTA, "power": POWER,
            "a_certification": section_a(),
            "a2_fixed_sequence": {"assumptions": {
                "automatable_share": AUTOMATABLE, "rest_error": REST_ERROR,
                "reps": REPS_A2, "confidences": "continuous, uniform on [0, 1]"},
                "rows": section_a2(rng)},
            "b_paired_auroc": {"assumptions": {
                "latent_auroc": [AUROC_A, AUROC_B], "tie_shares": TIE_SHARES,
                "rows_in_large_sample": N_BIG,
                "model": "binormal latent score per method, errors N(0,1), right answers "
                         "N(mu,1); the two methods' noise correlated rho; ties: cut into "
                         "6 levels; variance from DeLong placement values"},
                "rows": section_b(rng)},
            "c_paired_ece": {"assumptions": {
                "confidence_values": CONF_VALUES, "weights": CONF_WEIGHTS,
                "gaps": [GAP_A, GAP_B], "bins": 10, "reps": REPS_ECE,
                "model": "each judge draws its confidence independently; P(right) = "
                         "confidence - gap; outcomes linked by a Gaussian copula rho"},
                "rows": [simulate_ece(n, rho, rng) for rho in RHOS for n in N_GRID]}}


def _pct(x: float) -> str:
    """A rate as the repository writes it: '1 %', '0.25 %', '2.5 %'."""
    return f"{round(x * 100, 4):g} %"


def _share(x: float) -> str:
    return f"{round(x * 100)} %"


TIE_LABEL = {"none": "no ties", "tied": "6 levels"}


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
         "table: they are planning numbers. The pilot on the BANKING77 train sample estimates "
         "accuracy, the agreement between methods and the tie shares; the plan edits the "
         "script's PILOT constants to those estimates in a reviewed commit and regenerates "
         "this page before `docs/v05-plan.md` fixes n. Every figure in the prose below is "
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
              "(1 − r′)^rows, exactly; the simulated share is printed next to it as a check. "
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
               "Starting the sequence at a later, pre-registered cut keeps the guarantee and "
               "should certify more often when the slice is not error-free; that choice, and "
               "its effect in this simulation, belong in the plan."), "",
              "## B. Paired AUROC: the smallest difference resolved", "",
              (f"Two confidence methods on the same decisions, latent AUROCs {AUROC_A} and "
               f"{AUROC_B}. Ties \"none\": continuous scores; \"tied\": each method says one of "
               f"6 values with shares {TIE_SHARES}, lowest to highest (the top one like a "
               "verbalized 0.95 or a unanimous 5-sample vote). ρ is the latent correlation of "
               "the two methods' noise; the pilot measures the rank agreement of the two "
               "methods and ρ is set to reproduce it. The standard deviation of the paired "
               "difference comes from DeLong's placement values on one sample of "
               f"{N_BIG:,} rows per cell, scaled to n; MDE = (z₀.₉₇₅ + z₀.₈) × SD, the "
               "smallest true difference a paired test at α = 0.05 detects with 80 % power. "
               "The AUROC columns and their gap are exact population values after ties, "
               "not sample estimates."), "",
              "| ties | accuracy | ρ | n | errors | AUROC A | AUROC B | gap | SD(Δ) | MDE |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in b:
        lines.append(f"| {TIE_LABEL[r['ties']]} | {_share(r['accuracy'])} | {r['rho']} | "
                     f"{r['n']:,} | "
                     f"{r['errors_expected']:,} | {r['auroc_a']:.4f} | {r['auroc_b']:.4f} | "
                     f"{r['gap']:.4f} | {r['sd_difference']:.5f} | **{r['mde']:.4f}** |")
    for n in (big, clinc):
        cells = [r for r in b if r["n"] == n]
        ok = [r for r in cells if r["mde"] <= r["gap"]]
        tied_gaps = [r["gap"] for r in cells if r["ties"] == "tied"]
        lines += ["", f"At n = {n:,} the MDE is {_span([r['mde'] for r in cells], 4)}; the exact "
                  f"gap between the two methods ({AUROC_B - AUROC_A:.4f} without ties, "
                  f"{_span(tied_gaps, 4)} with 6 levels) is resolvable in {len(ok)} of "
                  f"{len(cells)} cells"
                  + (": " + "; ".join(f"{TIE_LABEL[r['ties']]}, accuracy "
                                      f"{_share(r['accuracy'])}, ρ {r['rho']}" for r in ok)
                     if ok else "") + "."]
    lines += ["", ("What drives it is the number of **errors**, not rows: at "
               f"{_share(ACCURACIES[-1])} accuracy {big:,} rows hold about "
               f"{round(big * (1 - ACCURACIES[-1])):,}."), "",
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
    b_big = [r["mde"] for r in b if r["n"] == big]
    b_clinc = [r["mde"] for r in b if r["n"] == clinc]
    c_big = [r["mde"] for r in c if r["n"] == big]
    c_clinc = [r["mde"] for r in c if r["n"] == clinc]
    lines += ["", "## What the plan takes from this (proposals for `docs/v05-plan.md`)", "",
              (f"- **n**: every distinct text, {big:,} for BANKING77 and {clinc:,} for "
               "CLINC150; paired comparisons use all of them, certification uses halves."),
              (f"- **Certification**: at {_pct(RISKS[0])} zero errors certify from {first:,} "
               f"automated rows and each further error costs about {inc_lo}–{inc_hi} more; the "
               "table in A2 shows how often the procedure succeeds at each target. The plan "
               "states which targets are primary per dataset on that basis, and where the "
               "fixed sequence starts."),
              (f"- **Smallest differences stated before the runs**: paired AUROC "
               f"{_span(b_big)} on BANKING77 and {_span(b_clinc)} on CLINC150; ECE "
               f"{_span(c_big)} and {_span(c_clinc)} (80 % power, α = 0.05). The plan "
               "states the MDE of the cell the pilot matches; a smaller observed difference "
               "is reported as not resolved, not as no difference."),
              ("- **Caveat**: A2, B and C assume the shapes above; the pilot's estimates "
               "replace them before the plan is frozen."), ""]
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
