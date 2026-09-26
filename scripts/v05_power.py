"""Power analysis for the v0.5 study (#91): how many rows each claim needs. No API call.

Three questions, answered before any model is run so the pre-registration can fix n:

  A. Certification (exact binomial, no assumption). To state "error rate at most r, with
     95 % confidence" about the decisions a judge automates, how many automated decisions
     must a calibration or test half hold, with 0, 1, 2 ... errors among them; and, if the
     true error rate there is r' < r, how many for an 80 % chance to certify?
  B. Paired AUROC (simulation). Two confidence methods ranking the same decisions (H1:
     same model, verbalized against another method): the smallest AUROC difference a
     paired comparison resolves with 80 % power, per n, accuracy and correlation.
  C. Paired ECE (simulation). The same for the difference in ECE between two judges on
     the same rows.

B and C rest on stated assumptions (a binormal latent score, fixed shares of tied
confidence values, a constant calibration gap, a Gaussian copula between the two methods'
outcomes). They are the planning numbers; the pilot on the BANKING77 train sample
(examples/banking77/labels-pilot.jsonl, #99) replaces the assumed accuracies,
correlations and tie shares before the plan is frozen.

  python scripts/v05_power.py            # writes docs/v05-power.md and .json
  python scripts/v05_power.py --check    # exit 1 if either differs (CI)

Deterministic: every random draw comes from random.Random(seed).random(); normals are
drawn with Box-Muller from those, so the output does not depend on the Python version.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.metrics.calibration import expected_calibration_error  # noqa: E402

OUT_MD = ROOT / "docs" / "v05-power.md"
OUT_JSON = ROOT / "docs" / "v05-power.json"
DELTA = 0.05                      # one-sided, as the certified bound in metrics (#98)
POWER = 0.80
Z_ALPHA = NormalDist().inv_cdf(0.975)
Z_POWER = NormalDist().inv_cdf(POWER)
SEED = 2026
REPS = 200
N_GRID = [950, 1540, 3079]        # a CLINC150 half, a BANKING77 half, BANKING77 in full
DATASETS = {"BANKING77 test": 3079, "CLINC150 banking + credit + out-of-scope": 1900}


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
    """The most errors among m rows that still certify risk < r: the one-sided
    Clopper-Pearson upper bound is below r exactly when P(Bin(m, r) <= k) < delta.
    -1 when even zero errors do not."""
    k = -1
    while k + 1 <= m and binom_cdf(k + 1, m, r) < delta:
        k += 1
    return k


def rows_to_certify(r: float, errors: int, delta: float = DELTA) -> int:
    """Smallest m whose bound certifies risk < r with `errors` errors among the m rows."""
    m = errors + 1
    while binom_cdf(errors, m, r) >= delta:
        m += 1
    return m


def power_to_certify(m: int, r: float, r_true: float, delta: float = DELTA) -> float:
    """P(certify risk < r) when the m rows' true error rate is r_true."""
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
            while k + 1 <= j and binom_cdf(k + 1, j, r) < DELTA:
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


def section_a() -> dict:
    risks = [0.01, 0.02, 0.05]
    table = {f"{r:g}": {str(e): rows_to_certify(r, e) for e in (0, 1, 2, 5, 10)}
             for r in risks}
    alternatives = {0.01: [0.0, 0.0025, 0.005], 0.02: [0.0, 0.005, 0.01],
                    0.05: [0.0, 0.01, 0.025]}
    power = {f"{r:g}": {f"{t:g}": rows_for_power(r, t) for t in alternatives[r]}
             for r in risks}
    return {"rows_to_certify": table, "rows_for_80pct_power": power}


# --- shared simulation helpers ------------------------------------------------------------


def normal_pair(rng: random.Random, rho: float) -> tuple[float, float]:
    """Two standard normals with correlation rho (Box-Muller on rng.random())."""
    u1, u2 = 1.0 - rng.random(), rng.random()
    radius = math.sqrt(-2.0 * math.log(u1))
    z1, z2 = radius * math.cos(2 * math.pi * u2), radius * math.sin(2 * math.pi * u2)
    return z1, rho * z1 + math.sqrt(1 - rho * rho) * z2


def auroc(scores: list[float], correct: list[bool]) -> float:
    """P(a right answer outranks a wrong one), ties one half: the definition of
    metrics.selective.failure_auroc (#98), by mid-ranks."""
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


# --- B. paired AUROC ----------------------------------------------------------------------

AUROC_A, AUROC_B = 0.70, 0.75     # latent (continuous) AUROCs of the two methods
# Tie regimes. "none": continuous scores. "tied": each method says one of 6 values, the top
# one for 40 % of the rows (a verbalized number at 0.95, a unanimous 5-sample vote).
TIES = {"none": None, "tied": [0.05, 0.05, 0.10, 0.15, 0.25, 0.40]}


def simulate_auroc(n: int, accuracy: float, rho: float, ties: str, rng: random.Random
                   ) -> dict:
    mu_a = math.sqrt(2) * NormalDist().inv_cdf(AUROC_A)
    mu_b = math.sqrt(2) * NormalDist().inv_cdf(AUROC_B)
    diffs, a_vals, b_vals = [], [], []
    for _ in range(REPS):
        correct = [rng.random() < accuracy for _ in range(n)]
        if all(correct) or not any(correct):
            continue
        sa, sb = [], []
        for ok in correct:
            ea, eb = normal_pair(rng, rho)
            sa.append(mu_a * ok + ea)
            sb.append(mu_b * ok + eb)
        shares = TIES[ties]
        a = auroc(levels(sa, shares) if shares else sa, correct)
        b = auroc(levels(sb, shares) if shares else sb, correct)
        a_vals.append(a)
        b_vals.append(b)
        diffs.append(b - a)
    s = sd(diffs)
    return {"n": n, "accuracy": accuracy, "rho": rho, "ties": ties,
            "errors_expected": round(n * (1 - accuracy)),
            "auroc_a": round(math.fsum(a_vals) / len(a_vals), 3),
            "auroc_b": round(math.fsum(b_vals) / len(b_vals), 3),
            "sd_difference": round(s, 4), "mde": round((Z_ALPHA + Z_POWER) * s, 3)}


# --- C. paired ECE ------------------------------------------------------------------------

# verbalized-style confidence values and how often a judge says each
CONF_VALUES = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]
CONF_WEIGHTS = [0.03, 0.05, 0.10, 0.12, 0.25, 0.30, 0.15]
GAP_A, GAP_B = 0.05, 0.08         # judge A 5 points overconfident, judge B 8


def _draw_conf(rng: random.Random) -> float:
    u, acc = rng.random(), 0.0
    for v, w in zip(CONF_VALUES, CONF_WEIGHTS, strict=True):
        acc += w
        if u < acc:
            return v
    return CONF_VALUES[-1]


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def simulate_ece(n: int, rho: float, rng: random.Random) -> dict:
    diffs, ea, eb = [], [], []
    for _ in range(REPS):
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
    true_a = math.fsum(w * min(v, GAP_A) for v, w in zip(CONF_VALUES, CONF_WEIGHTS,
                                                         strict=True))
    true_b = math.fsum(w * min(v, GAP_B) for v, w in zip(CONF_VALUES, CONF_WEIGHTS,
                                                         strict=True))
    return {"n": n, "rho": rho, "true_ece_a": round(true_a, 3), "true_ece_b": round(true_b, 3),
            "mean_ece_a": round(math.fsum(ea) / REPS, 3),
            "mean_ece_b": round(math.fsum(eb) / REPS, 3),
            "sd_difference": round(s, 4), "mde": round((Z_ALPHA + Z_POWER) * s, 3)}


# --- report -------------------------------------------------------------------------------


def compute() -> dict:
    rng = random.Random(SEED)
    b = [simulate_auroc(n, acc, rho, ties, rng) for ties in TIES for acc in (0.85, 0.93)
         for rho in (0.3, 0.7) for n in N_GRID]
    c = [simulate_ece(n, rho, rng) for rho in (0.3, 0.7) for n in N_GRID]
    return {"seed": SEED, "reps": REPS, "delta": DELTA, "power": POWER,
            "a_certification": section_a(),
            "b_paired_auroc": {"assumptions": {
                "latent_auroc": [AUROC_A, AUROC_B], "tie_shares": TIES,
                "model": "binormal latent score per method, errors N(0,1), right answers "
                         "N(mu,1); the two methods' noise correlated rho; then cut into "
                         "tied levels"}, "rows": b},
            "c_paired_ece": {"assumptions": {
                "confidence_values": CONF_VALUES, "weights": CONF_WEIGHTS,
                "gaps": [GAP_A, GAP_B], "bins": 10,
                "model": "P(right) = confidence - gap; the two judges' outcomes linked by a "
                         "Gaussian copula rho"}, "rows": c}}


def markdown(d: dict) -> str:
    a = d["a_certification"]
    lines = [
        "# v0.5 power analysis (pre-registration input, #91)", "",
        "Generated by `scripts/v05_power.py` (seed "
        f"{d['seed']}, {d['reps']} simulated datasets per cell); CI regenerates it. "
        "**No model was called.** Part A is exact. Parts B and C rest on the assumptions "
        "stated with each table. They are planning numbers: the pilot on the BANKING77 train "
        "sample replaces the assumed accuracies, correlations and tie shares before "
        "`docs/v05-plan.md` fixes n.", "",
        "## A. Certifying an error rate on automated decisions (exact)", "",
        "One-sided 95 % Clopper-Pearson bound, as in the selective metrics (#98). Rows needed "
        "among the **automated** decisions of one half (calibration or test) so that the "
        "observed errors still certify \"error rate below r\":", "",
        "| target risk r | 0 errors | 1 | 2 | 5 | 10 |", "|---|---:|---:|---:|---:|---:|"]
    for r, row in a["rows_to_certify"].items():
        lines.append(f"| {float(r):.0%} | " + " | ".join(f"{row[e]:,}" for e in
                                                          ("0", "1", "2", "5", "10")) + " |")
    lines += ["", "Rows needed for an 80 % chance to certify r when the true error rate of "
              "those rows is r′ (the power saw-tooths in n; the number given is where it "
              "stays at or above 80 % up to twice that n):", "",
              "| target risk r | r′ | rows for 80 % power |", "|---|---|---:|"]
    for r, row in a["rows_for_80pct_power"].items():
        for t, m in row.items():
            lines.append(f"| {float(r):.0%} | {float(t):.2%} | "
                         f"{m:,} |" if m else f"| {float(r):.0%} | {float(t):.2%} | > 20,000 |")
    lines += ["", "Each half of a cross-fitted split must hold those rows **in its automated "
              "slice**: a judge that automates a share c of the rows needs about 2 × rows ÷ c "
              "distinct texts in all. For the datasets drafted in #99:", "",
              "| dataset | distinct texts | per half | automated rows per half at c = 30 % "
              "| 50 % | 80 % |", "|---|---:|---:|---:|---:|---:|"]
    for name, n in DATASETS.items():
        half = n // 2
        lines.append(f"| {name} | {n:,} | {half:,} | {round(0.3 * half):,} | "
                     f"{round(0.5 * half):,} | {round(0.8 * half):,} |")
    lines += ["", "Read together: **1 % is certifiable only with zero errors in about 300 "
              "automated rows per half**, and with 80 % power only when the true error rate "
              "there is essentially zero; a judge whose automated slice truly errs 0.5 % needs "
              "thousands. On CLINC150's 950 rows per half, 1 % needs a judge that automates at "
              "least about a third of them with no error. 2 % and 5 % are the realistic "
              "targets at these sizes; the plan must say which r it tests on which dataset.",
              "", "## B. Paired AUROC: the smallest difference resolved", "",
              f"Two confidence methods on the same decisions, latent AUROCs {AUROC_A} and "
              f"{AUROC_B}. Ties \"none\": continuous scores; \"tied\": each method says one "
              f"of 6 values, with shares {TIES['tied']} from lowest to highest (the top value "
              "for 40 % of the rows, like a verbalized 0.95 or a unanimous 5-sample vote). ρ "
              "is the correlation of the two methods' noise (same model, same prompt: high). "
              "MDE = (z₀.₉₇₅ + z₀.₈) × SD of the paired difference: the smallest true "
              "difference a paired test at α = 0.05 detects with 80 % power. The AUROC "
              "columns are the simulated means.", "",
              "| ties | accuracy | ρ | n | errors | AUROC A | AUROC B | SD(Δ) | MDE |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in d["b_paired_auroc"]["rows"]:
        lines.append(f"| {r['ties']} | {r['accuracy']:.0%} | {r['rho']} | {r['n']:,} | "
                     f"{r['errors_expected']:,} | {r['auroc_a']:.3f} | {r['auroc_b']:.3f} | "
                     f"{r['sd_difference']:.4f} | **{r['mde']:.3f}** |")
    lines += ["", "What drives it is the number of **errors**, not rows: at 93 % accuracy "
              "BANKING77's full test split holds about 216. With these tie shares both AUROCs "
              "drop by about 0.01 to 0.015 and the gap between them barely moves; heavier ties "
              "(a vote unanimous on most rows) would cost more, and the pilot measures the "
              "real shares. A gap of 0.05 is resolvable on BANKING77's full split, and on a "
              "half only with strongly correlated noise; on a CLINC150 half (950 rows) the "
              "MDE is 0.05 to 0.11. Each SD comes from "
              f"{REPS} simulated datasets, so it is known to about ±5 %.", "",
              "## C. Paired ECE: the smallest difference resolved", "",
              f"Two judges on the same rows, overconfident by {GAP_A} and {GAP_B}; confidence "
              f"values {CONF_VALUES} said with weights {CONF_WEIGHTS}; 10 equal-width bins; "
              "outcomes linked by a Gaussian copula ρ. True ECE is the average gap; the mean "
              "estimate shows the small upward bias of binned ECE (under 0.005 here).", "",
              "| ρ | n | true ECE A | mean ECE A | true ECE B | mean ECE B | SD(Δ) | MDE |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in d["c_paired_ece"]["rows"]:
        lines.append(f"| {r['rho']} | {r['n']:,} | {r['true_ece_a']:.3f} | "
                     f"{r['mean_ece_a']:.3f} | {r['true_ece_b']:.3f} | {r['mean_ece_b']:.3f} "
                     f"| {r['sd_difference']:.4f} | **{r['mde']:.3f}** |")
    lines += ["", "## What the plan takes from this (proposals for `docs/v05-plan.md`)", "",
              "- **n**: every distinct text of BANKING77's test split (3,079) and of the "
              "CLINC150 subset (1,900); subsampling them loses power the study needs. "
              "Certification at 2 % and 5 % is the primary target; 1 % is reachable only for "
              "a judge with zero errors in about 300 automated rows per half, so it is "
              "reported as exploratory.",
              "- **Smallest differences stated before the runs**: on BANKING77's full split, "
              "paired AUROC differences below about 0.03 to 0.06 and ECE differences below "
              "about 0.02 to 0.025 are not resolvable (80 % power, α = 0.05); on 950 rows, "
              "about 0.05 to 0.11 and 0.04. The plan states the MDE of the cell the pilot "
              "matches; a smaller observed difference is reported as not resolved, not as "
              "no difference.",
              "- **Caveat**: B and C assume the shapes above. The pilot estimates accuracy, "
              "the correlation between methods and the tie shares; the plan reruns this "
              "script with those values before it is frozen.", ""]
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
