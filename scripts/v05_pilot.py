"""Estimates of the v0.5 pilot (#91, docs/v05-pilot.md §5), for scripts/v05_power.py. No model call.

Reads the four pilot checkpoints in docs/runs/v05-pilot/ (Laya; Qwen3-8B read three ways:
token log-probability, verbalized, self-consistency with k = 5) and the labels they judged,
examples/banking77/labels-pilot.jsonl, and writes docs/v05-pilot-estimates.md and .json:
every estimate §5 names, each with its n, and the values §5 says to feed back into the
power analysis's PILOT constants. The rules are the protocol's, fixed before any row was
seen; where the protocol leaves a detail open, the choice is stated next to the code.

  python scripts/v05_pilot.py            # writes docs/v05-pilot-estimates.md and .json
  python scripts/v05_pilot.py --check    # exit 1 if either differs; 2 if a checkpoint is missing

The pilot runs on 308 rows of the BANKING77 **train** split: nothing here is a result
about any judge, and nothing here tests H1 or H2.

Deterministic: the latent-rho mapping draws its one fixed sample of normal pairs with
v05_power's Box-Muller on random.Random(2026).random(); the bootstrap is the repository's
(`metrics.selective.bootstrap_defined`, seed 2026).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_resumable import load_checkpoint  # noqa: E402
from relabel import Z95, wilson_interval  # noqa: E402
from v05_power import (  # noqa: E402
    _cov,
    _placements,
    levels,
    normal_pair,
    population_auroc,
)

from judge_audit.metrics.calibration import interpolated_quantile  # noqa: E402
from judge_audit.metrics.selective import bootstrap_defined, failure_auroc  # noqa: E402
from judge_audit.runner import checkpoint_record, load_dataset, sha256_of  # noqa: E402

RUNS_DIR = ROOT / "docs" / "runs" / "v05-pilot"
LABELS = ROOT / "examples" / "banking77" / "labels-pilot.jsonl"
OUT_MD = ROOT / "docs" / "v05-pilot-estimates.md"
OUT_JSON = ROOT / "docs" / "v05-pilot-estimates.json"
SEED = 2026
N_SIM = 100_000            # the fixed sample of normal pairs behind every rho mapping
N_BOOT = 2000              # bootstrap resamples of the both-right rows
RHO_TOP, RHO_STEPS = 0.999, 40
MU_TOP, MU_STEPS = 8.0, 60
AUROC_CAP, DESIGN_GAP = 0.90, 0.05
POOL_BELOW = Fraction(1, 100)      # a verbalized level under 1 % of rows is pooled

VERB, SC, LP, LAYA = "llm-qwen3-8b", "llm-qwen3-8b-sc5", "logprob-qwen3-8b", "laya"
ORDER = [VERB, SC, LP, LAYA]
QWEN = [VERB, SC, LP]
PAIRS = [[VERB, SC], [VERB, LP], [SC, LP]]
H1_PAIRS = PAIRS[:2]               # verbalized against self-consistency and log-probability
NAMES = {VERB: "Qwen3-8B verbalized", SC: "Qwen3-8B self-consistency (k = 5)",
         LP: "Qwen3-8B token log-probability", LAYA: "Laya"}
ADAPTER = {VERB: "llm", SC: "llm", LP: "logprob", LAYA: "laya"}


class MissingCheckpoints(Exception):
    """One or more of the four checkpoints is not there yet."""


# --- reading the runs ------------------------------------------------------------------------


def load_run(slug: str, path: Path, rows: list[dict], labels_sha: str) -> dict:
    """{header, records} for one checkpoint: one record (runner.checkpoint_record) per
    labelled question, None where the checkpoint holds no answer to it."""
    done = load_checkpoint(path)
    if -1 not in done:
        raise SystemExit(f"{path}: no header line: cannot tell which judge or labels it holds")
    judge = done[-1]["run"].get("judge") or {}
    adapter = str(judge.get("name", "")).split(":")[0]
    if adapter != ADAPTER[slug]:
        raise SystemExit(f"{path}: judge {judge.get('name')!r}, expected the {ADAPTER[slug]} "
                         "adapter")
    samples = int(judge.get("samples") or 1)
    if slug == SC and samples < 2:
        raise SystemExit(f"{path}: not a self-consistency run (samples {samples})")
    if slug == VERB and samples != 1:
        raise SystemExit(f"{path}: a self-consistency run where the verbalized one belongs")
    recorded = (done[-1]["run"].get("dataset") or {}).get("sha256")
    if recorded != labels_sha:
        raise SystemExit(f"{path}: judged labels with sha256 {recorded}, not the labels "
                         f"given ({labels_sha})")
    records: dict[tuple[int, str], dict | None] = {}
    for idx, row in enumerate(rows):
        answered = {j["question"]: j for j in (done.get(idx) or {}).get("judgments", [])}
        for q, expected in row.get("labels", {}).items():
            j = answered.get(q)
            records[(idx, q)] = (None if j is None
                                 else checkpoint_record(idx, row, j, expected, done[-1]["run"]))
    return {"header": done[-1]["run"], "records": records}


def right(rec: dict | None) -> bool:
    """§5: a row with no answer, or whose decision carries no confidence, counts wrong."""
    return rec is not None and rec["parse_status"] == "parsed" and rec["correct"]


def scored(rec: dict | None) -> bool:
    """A row that enters tie shares, Spearman and AUROC: parsed, with a confidence."""
    return rec is not None and rec["parse_status"] == "parsed" and rec["confidence"] is not None


def tie_key(c: float) -> float:
    return round(float(c), 6)


# --- tie shares and the verbalized distribution ----------------------------------------------


def tie_levels(confidences: list[float]) -> list[tuple[float, int]]:
    """(value, rows) per distinct confidence rounded to 1e-6, lowest to highest."""
    counts: dict[float, int] = {}
    for c in confidences:
        counts[tie_key(c)] = counts.get(tie_key(c), 0) + 1
    return sorted(counts.items())


def milli(counts: list[int]) -> list[int]:
    """Shares of `counts` in thousandths (nearest, exact arithmetic), with the rounding
    remainder added to the largest so they sum to 1,000; a tie for the largest goes to the
    first (the lowest level)."""
    n = sum(counts)
    out = [round(Fraction(1000 * c, n)) for c in counts]
    top = max(range(len(out)), key=lambda i: (out[i], -i))
    out[top] += 1000 - sum(out)
    return out


def twentieth(c: float) -> int:
    """c rounded to the nearest 0.05, as a count of twentieths. A value exactly between two
    levels goes to the lower one (the protocol's tie rule for pooling, applied here too;
    exact because the decimal the checkpoint wrote is what is rounded)."""
    k20 = Fraction(repr(float(c))) * 20
    down = math.floor(k20)
    return down if k20 - down <= Fraction(1, 2) else down + 1


def pool_verbalized(confidences: list[float]) -> dict:
    """§5's verbalized distribution: levels of 0.05; a level under 1 % of rows joins the
    nearest kept level (a tie goes to the lower); weights to 0.001, summing to 1."""
    n = len(confidences)
    counts: dict[int, int] = {}
    for c in confidences:
        counts[twentieth(c)] = counts.get(twentieth(c), 0) + 1
    ks = sorted(counts)
    kept = [k for k in ks if Fraction(counts[k], n) >= POOL_BELOW]
    pooled = {k: 0 for k in kept}
    for k in ks:
        home = min(kept, key=lambda j: (abs(j - k), j))
        pooled[home] += counts[k]
    weights = milli([pooled[k] for k in kept]) if kept else []
    return {"n": n, "levels": [[k / 20, counts[k]] for k in ks],
            "pooled": [[k / 20, pooled[k]] for k in kept],
            "values": [k / 20 for k in kept], "weights": [w / 1000 for w in weights]}


# --- Spearman and the latent rho -------------------------------------------------------------


def _avg_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        for t in order[i:j]:
            ranks[t] = (i + 1 + j) / 2
        i = j
    return ranks


def _pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 2:
        return None
    mx, my = math.fsum(x) / n, math.fsum(y) / n
    sxx = math.fsum((a - mx) ** 2 for a in x)
    syy = math.fsum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return math.fsum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / math.sqrt(
        sxx * syy)


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman correlation with average ranks for ties (values compared at 1e-6). None
    with fewer than two rows or when either side holds one value only."""
    return _pearson(_avg_ranks([tie_key(v) for v in x]), _avg_ranks([tie_key(v) for v in y]))


def _level_ranks(values: list[float], shares: list[float] | None) -> list[float]:
    """Average ranks of `values` after `levels` cuts them into the given shares; an uncut
    (continuous) coordinate keeps its order, which has no ties."""
    if shares is None:
        ranks = [0.0] * len(values)
        for pos, i in enumerate(sorted(range(len(values)), key=values.__getitem__)):
            ranks[i] = pos + 1.0
        return ranks
    lv = levels(values, shares)
    counts = [0] * len(shares)
    for v in lv:
        counts[int(v)] += 1
    mid, below = [], 0
    for c in counts:
        mid.append(below + (c + 1) / 2)
        below += c
    return [mid[int(v)] for v in lv]


class RankMap:
    """rho -> the Spearman correlation of one fixed sample of normal pairs (z1, z2) after
    mixing the second as rho z1 + sqrt(1 - rho^2) z2 and cutting each coordinate into its
    method's tie shares (None: continuous, not cut). The sample is fixed, so the map is
    a deterministic, monotone function of rho (common random numbers)."""

    def __init__(self, base: list[tuple[float, float]], shares_x: list[float] | None,
                 shares_y: list[float] | None):
        self.z1 = [a for a, _ in base]
        self.z2 = [b for _, b in base]
        self.rx = _level_ranks(self.z1, shares_x)
        self.shares_y = shares_y
        self.cache: dict[float, float] = {}

    def __call__(self, rho: float) -> float:
        if rho not in self.cache:
            w = math.sqrt(1 - rho * rho)
            y = [rho * a + w * b for a, b in zip(self.z1, self.z2, strict=True)]
            self.cache[rho] = _pearson(self.rx, _level_ranks(y, self.shares_y)) or 0.0
        return self.cache[rho]


def latent_rho(observed: float | None, f: RankMap) -> float | None:
    """The rho whose simulated Spearman equals `observed`: bisection on [0, 0.999] for 40
    steps; a value at or below the rho = 0 one maps to 0."""
    if observed is None:
        return None
    if observed <= f(0.0):
        return 0.0
    lo, hi = 0.0, RHO_TOP
    for _ in range(RHO_STEPS):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < observed else (lo, mid)
    return (lo + hi) / 2


def shares_of(values: list[float]) -> list[float] | None:
    """Exact tie shares of `values`, or None when no two are equal. §5 does not cut "a
    continuous method"; the test is made on the rows themselves, so a coordinate is cut
    exactly when the observed ranks it is matched to hold ties (the log-probability read-out
    is not cut unless its rows tie, a tied read-out without a tie on these rows is not either:
    its observed ranks are then those of a continuous score)."""
    lv = tie_levels(values)
    if all(c == 1 for _, c in lv):
        return None
    return [c / len(values) for _, c in lv]


def rank_agreement(runs: dict, keys: list, a: str, b: str, base: list, n_boot: int) -> dict:
    ra, rb = runs[a]["records"], runs[b]["records"]
    both = [k for k in keys if right(ra[k]) and right(rb[k])]
    wrong = [k for k in keys if not right(ra[k]) and not right(rb[k])]
    xs = [ra[k]["confidence"] for k in both]
    ys = [rb[k]["confidence"] for k in both]
    rho_s = spearman(xs, ys)
    out = {"pair": [a, b], "both_right": len(both), "levels": [None, None], "spearman": None,
           "spearman_95": None, "undefined_resamples": None, "rho_at_zero": None, "rho": None,
           "rho_95": None, "both_wrong": len(wrong),
           "spearman_both_wrong": _r4(spearman(
               [ra[k]["confidence"] for k in wrong if scored(ra[k]) and scored(rb[k])],
               [rb[k]["confidence"] for k in wrong if scored(ra[k]) and scored(rb[k])]))}
    if not both:
        return out
    sx, sy = shares_of(xs), shares_of(ys)
    out["levels"] = [len(sx) if sx else None, len(sy) if sy else None]
    if rho_s is None:
        return out
    f = RankMap(base, sx, sy)
    boot = bootstrap_defined(list(zip(xs, ys, strict=True)),
                             lambda rs: spearman([x for x, _ in rs], [y for _, y in rs]),
                             n_boot=n_boot, seed=SEED)
    out.update({"spearman": _r4(rho_s), "rho_at_zero": _r4(f(0.0)),
                "rho": _r4(latent_rho(rho_s, f)), "undefined_resamples": boot.undefined})
    if boot.ci is not None:
        out["spearman_95"] = list(boot.ci)
        out["rho_95"] = [_r4(latent_rho(boot.ci[0], f)), _r4(latent_rho(boot.ci[1], f))]
    return out


# --- AUROC and the latent AUROC --------------------------------------------------------------


def auroc_delong(confidences: list[float], correct: list[bool]) -> dict:
    """AUROC of confidence for correctness (ties one half, `failure_auroc`) with DeLong's
    95 % interval, AUROC +- z sqrt(s10 / n_right + s01 / n_wrong), clipped to [0, 1]. The
    interval needs two right and two wrong answers (a variance from one row is undefined)."""
    n_right = sum(correct)
    out = {"n": len(correct), "right": n_right, "wrong": len(correct) - n_right,
           "value": None, "delong_95": None}
    if not confidences:
        return out
    value = failure_auroc(confidences, correct)
    out["value"] = _r4(value)
    if value is None or out["right"] < 2 or out["wrong"] < 2:
        return out
    v10, v01 = _placements(confidences, correct)
    se = math.sqrt(_cov(v10, v10) / len(v10) + _cov(v01, v01) / len(v01))
    out["delong_95"] = [round(max(0.0, value - Z95 * se), 4), round(min(1.0, value + Z95 * se), 4)]
    return out


def latent_auroc(observed: float | None, accuracy: float, shares: list[float] | None
                 ) -> dict | None:
    """§5's AUROC_A: the mu with population_auroc(mu, accuracy, shares) equal to the
    observed AUROC (bisection on [0, 8], 60 steps; at or below the mu = 0 value, 0.5, it is
    0), then Phi(mu / sqrt 2) rounded to 0.05 and capped at 0.90."""
    if observed is None or shares is None:
        return None
    if observed <= population_auroc(0.0, accuracy, shares):
        mu = 0.0
    else:
        lo, hi = 0.0, MU_TOP
        for _ in range(MU_STEPS):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if population_auroc(mid, accuracy, shares) < observed else (lo, mid)
        mu = (lo + hi) / 2
    latent = NormalDist().cdf(mu / math.sqrt(2))
    rounded = round(latent * 20) / 20
    return {"observed": observed, "accuracy": round(accuracy, 4), "tie_shares": shares,
            "mu": round(mu, 6), "latent": round(latent, 6), "rounded": rounded,
            "auroc_a": min(AUROC_CAP, rounded), "capped": rounded > AUROC_CAP}


# --- tetrachoric -----------------------------------------------------------------------------


def _q(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def bvn_upper(h: float, k: float, rho: float, steps: int = 4000) -> float:
    """P(X > h, Y > k) for standard normals with correlation rho (|rho| < 1): Simpson's rule
    on the integral of phi(x) Q((k - rho x) / sqrt(1 - rho^2)) over x > h."""
    top = max(h, 0.0) + 10.0
    if h >= top:
        return 0.0
    s = math.sqrt(1 - rho * rho)
    width = (top - h) / steps

    def g(x: float) -> float:
        return math.exp(-x * x / 2) / math.sqrt(2 * math.pi) * _q((k - rho * x) / s)

    total = g(h) + g(top)
    total += 4 * math.fsum(g(h + (2 * i - 1) * width) for i in range(1, steps // 2 + 1))
    total += 2 * math.fsum(g(h + 2 * i * width) for i in range(1, steps // 2))
    return total * width / 3


def tetrachoric(a: list[bool], b: list[bool]) -> dict:
    """The latent correlation of two binary outcomes: thresholds from each margin, then the
    rho whose bivariate normal reproduces the share right on both (bisection). Undefined
    when a margin is 0 or 1; +-1 (flagged `boundary`) when an empty cell puts the share at
    the bound it can reach only at |rho| = 1."""
    n = len(a)
    cells = {"both_right": sum(x and y for x, y in zip(a, b, strict=True)),
             "first_only": sum(x and not y for x, y in zip(a, b, strict=True)),
             "second_only": sum(y and not x for x, y in zip(a, b, strict=True)),
             "both_wrong": sum(not x and not y for x, y in zip(a, b, strict=True))}
    out = {"n": n, "cells": cells, "value": None, "boundary": False}
    pa, pb = Fraction(sum(a), n) if n else 0, Fraction(sum(b), n) if n else 0
    if not 0 < pa < 1 or not 0 < pb < 1:
        return out
    p11 = Fraction(cells["both_right"], n)
    if p11 >= min(pa, pb) or p11 <= max(Fraction(0), pa + pb - 1):
        out.update(value=1.0 if p11 >= min(pa, pb) else -1.0, boundary=True)
        return out
    h, k = NormalDist().inv_cdf(1 - float(pa)), NormalDist().inv_cdf(1 - float(pb))
    lo, hi = -1.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bvn_upper(h, k, mid) < float(p11) else (lo, mid)
    out["value"] = round((lo + hi) / 2, 4)
    return out


# --- the rest --------------------------------------------------------------------------------


def _r4(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def accuracy_of(recs: list) -> dict:
    k, n = sum(right(r) for r in recs), len(recs)
    lo, hi = wilson_interval(k, n)
    return {"right": k, "n": n, "value": round(k / n, 4), "wilson_95": [round(lo, 4), round(hi, 4)]}


def throughput(slug: str, recs: list) -> dict:
    """Rows per minute from the judges' own latency fields (a row without one, a missing
    answer, is left out), and tokens per call where the checkpoint records them (the chat
    read-outs; a self-consistency row is k calls)."""
    timed = [r["latency_s"] for r in recs if r is not None and r.get("latency_s") is not None]
    secs = math.fsum(timed)
    out = {"rows_timed": len(timed),
           "seconds_per_row": round(secs / len(timed), 4) if timed else None,
           "rows_per_minute": round(60 * len(timed) / secs, 2) if secs > 0 else None,
           "calls": None, "input_tokens_per_call": None, "output_tokens_per_call": None}
    usages = []
    for r in recs:
        raw = (r or {}).get("raw") or {}
        if slug == SC:
            usages += [s.get("usage") or {} for s in raw.get("samples") or []]
        elif slug == VERB and isinstance(raw.get("usage"), dict):
            usages.append(raw["usage"])
    if usages:
        out["calls"] = len(usages)
        for side in ("input", "output"):
            vals = [u.get(f"{side}_tokens") for u in usages if u.get(f"{side}_tokens") is not None]
            out[f"{side}_tokens_per_call"] = (round(math.fsum(vals) / len(vals), 2)
                                              if vals else None)
    return out


def run_summary(slug: str, run: dict) -> dict:
    recs = list(run["records"].values())
    have = [r for r in recs if scored(r)]
    confs = [r["confidence"] for r in have]
    ok = [r["correct"] for r in have]
    lv = tie_levels(confs)
    judge = run["header"].get("judge") or {}
    over = None
    if have:
        mean_c, acc = math.fsum(confs) / len(have), sum(ok) / len(have)
        over = {"n": len(have), "mean_confidence": round(mean_c, 4), "accuracy": round(acc, 4),
                "value": round(mean_c - acc, 4)}
    return {
        "judge": judge.get("name"), "model": judge.get("model"),
        "decisions": len(recs), "in_checkpoint": sum(r is not None for r in recs),
        "missing": sum(r is None for r in recs),
        "no_answer": sum(r is not None and r["parse_status"] == "no_answer" for r in recs),
        "no_confidence": sum(r is not None and r["parse_status"] == "no_confidence"
                             for r in recs),
        "no_confidence_decision_right": sum(r is not None and r["parse_status"] == "no_confidence"
                                            and r["correct"] for r in recs),
        "accuracy": accuracy_of(recs), "overconfidence": over,
        "tie_shares": {"n": len(confs), "levels": [[v, c, round(c / len(confs), 6)]
                                                   for v, c in lv]},
        "auroc": auroc_delong(confs, ok), "throughput": throughput(slug, recs)}


def sc_samples(run: dict) -> dict:
    """Failed samples: a sample that voted for nothing (`llm.vote`: no answer, or a null
    decision) counts in k, so k minus the votes cast."""
    total = failed = rows = 0
    for r in run["records"].values():
        if r is None:
            continue
        raw = r.get("raw") or {}
        k = len(raw.get("samples") or [])
        miss = k - sum((raw.get("votes") or {}).values())
        total, failed, rows = total + k, failed + miss, rows + (miss > 0)
    return {"samples": total, "failed": failed, "rows_with_a_failed_sample": rows}


def quartiles(values: list[float]) -> dict:
    v = sorted(values)
    if not v:
        return {"n": 0, "min": None, "q1": None, "median": None, "q3": None, "max": None}
    return {"n": len(v), "min": round(v[0], 6),
            "q1": round(interpolated_quantile(v, 0.25), 6),
            "median": round(interpolated_quantile(v, 0.5), 6),
            "q3": round(interpolated_quantile(v, 0.75), 6), "max": round(v[-1], 6)}


def laya_temperatures(run: dict, rows: list[dict]) -> dict:
    t = (run["header"].get("judge") or {}).get("softmax_temperature") or {}
    shipped = (t.get("shipped") or {}).get("by_options") or {}
    applied = (t.get("applied") or {}).get("by_options") or {}
    return {"clamped": [{"entry": e, "shipped": _r4(shipped.get(e)), "applied": _r4(applied.get(e))}
                        for e in t.get("clamped_by_options") or []],
            "options_in_question": max((len(q.get("options") or []) for r in rows
                                        for q in r["questions"]), default=0),
            "device": (run["header"].get("judge") or {}).get("device")}


# --- the constants §5 feeds back -------------------------------------------------------------


def _to(x: float, step: float) -> float:
    """x rounded to the nearest multiple of step (0.01 or 0.05), as the repository prints it."""
    return round(round(x / step) * step, 2)


def tie_shares_constant(levels: list) -> list[float] | None:
    """A run's tie shares as a PILOT constant: to 0.001 (§5 fixes no precision for them;
    the rule of the verbalized weights is used), the remainder on the largest."""
    return [m / 1000 for m in milli([c for _, c, _ in levels])] if levels else None


def proposed(d: dict) -> dict:
    runs = d["runs"]
    out: dict[str, dict] = {}

    accs = [runs[s]["accuracy"] for s in QWEN]
    best = max(accs, key=lambda a: a["right"] / a["n"])
    values = sorted({_to(a["right"] / a["n"], 0.01) for a in accs} | {_to(best["wilson_95"][1],
                                                                          0.01)})
    clipped = sorted({min(0.99, max(0.01, v)) for v in values})
    out["ACCURACIES"] = {
        "value": clipped,
        "rule": "the distinct accuracies of the three Qwen3 read-outs to 0.01, plus the "
                "Wilson upper bound of the highest",
        "note": ("" if clipped == values else
                 "clipped to [0.01, 0.99]: the power model needs right and wrong answers")}

    for name, slug in (("TIE_SHARES_A", VERB), ("TIE_SHARES_B", SC)):
        lv = runs[slug]["tie_shares"]["levels"]
        out[name] = {"value": tie_shares_constant(lv),
                     "values": [v for v, _, _ in lv],
                     "rule": f"the shares of each distinct confidence of the {NAMES[slug]} run, "
                             "lowest to highest, to 0.001 with the remainder on the largest"}

    v = d["verbalized_distribution"]
    out["CONF_VALUES"] = {"value": v["values"] or None,
                          "rule": "the verbalized confidences to 0.05, levels under 1 % pooled "
                                  "into the nearest kept one (ties down)"}
    out["CONF_WEIGHTS"] = {"value": v["weights"] or None,
                           "rule": "their shares to 0.001, the remainder on the largest"}

    h1 = [r for r in d["rank_agreement"] if r["pair"] in H1_PAIRS]
    points = [r for r in h1 if r["rho"] is not None]
    rhos = {_to(r["rho"], 0.05) for r in points}
    note = [f"{r['pair'][0]}–{r['pair'][1]}: not estimable" for r in h1 if r["rho"] is None]
    if points:
        smaller = min(points, key=lambda r: r["rho"])
        if smaller["rho_95"] is not None and smaller["rho_95"][0] is not None:
            rhos.add(_to(smaller["rho_95"][0], 0.05))
        else:
            note.append("no interval for the smaller point estimate")
    out["RHOS"] = {"value": sorted(rhos),
                   "rule": "the latent rho of verbalized–self-consistency and "
                           "verbalized–log-probability to 0.05, plus the lower interval bound "
                           "of the smaller",
                   "note": "; ".join(note)}

    la = d["latent_auroc_a"]
    a = la["auroc_a"] if la else None
    out["AUROC_A"] = {"value": a,
                      "rule": "the latent AUROC reproducing the verbalized run's observed AUROC "
                              "with TIE_SHARES_A, to 0.05, capped at 0.90",
                      "note": "" if la else "not estimable: keep the design value"}
    out["AUROC_B"] = {"value": round(a + DESIGN_GAP, 2) if a is not None else None,
                      "rule": "AUROC_A + 0.05 (the design gap)"}
    return out


# --- compute ---------------------------------------------------------------------------------


def compute(runs_dir: Path = RUNS_DIR, labels: Path = LABELS, n_sim: int | None = None,
            n_boot: int | None = None) -> dict:
    n_sim = N_SIM if n_sim is None else n_sim
    n_boot = N_BOOT if n_boot is None else n_boot
    paths = {s: Path(runs_dir) / f"{s}.ckpt.jsonl" for s in ORDER}
    missing = [p for p in paths.values() if not p.exists()]
    if missing:
        raise MissingCheckpoints(", ".join(_shown(p) for p in missing))
    rows, _ = load_dataset(str(labels))
    sha = sha256_of(str(labels))
    runs = {s: load_run(s, paths[s], rows, sha) for s in ORDER}
    keys = list(runs[VERB]["records"])

    d: dict = {"seed": SEED, "labels": {"path": _shown(Path(labels)), "sha256": sha,
                                        "rows": len(rows), "decisions": len(keys)},
               "checkpoints": {s: _shown(paths[s]) for s in ORDER},
               "runs": {s: run_summary(s, runs[s]) for s in ORDER}}

    agree = []
    for a, b in PAIRS:
        ra, rb = runs[a]["records"], runs[b]["records"]
        same = sum(bool(ra[k] is not None and rb[k] is not None and ra[k]["decision"].strip()
                        and ra[k]["decision"].strip().casefold()
                        == rb[k]["decision"].strip().casefold()) for k in keys)
        same_ok = sum(right(ra[k]) == right(rb[k]) for k in keys)
        agree.append({"pair": [a, b], "n": len(keys), "same_decision": same,
                      "same_decision_share": round(same / len(keys), 4),
                      "same_correctness": same_ok,
                      "same_correctness_share": round(same_ok / len(keys), 4)})
    d["decision_agreement"] = agree

    d["verbalized_distribution"] = pool_verbalized(
        [r["confidence"] for r in runs[VERB]["records"].values() if scored(r)])

    rng = random.Random(SEED)
    base = [normal_pair(rng, 0.0) for _ in range(n_sim)]
    d["rank_agreement"] = [rank_agreement(runs, keys, a, b, base, n_boot) for a, b in PAIRS]
    d["rank_agreement_method"] = {"normal_pairs": n_sim, "bisection_steps": RHO_STEPS,
                                  "rho_range": [0.0, RHO_TOP], "bootstrap_resamples": n_boot}

    d["tetrachoric"] = [
        {"pair": [LAYA, s], **tetrachoric([right(runs[LAYA]["records"][k]) for k in keys],
                                          [right(runs[s]["records"][k]) for k in keys])}
        for s in QWEN]
    d["self_consistency_samples"] = sc_samples(runs[SC])
    d["option_mass"] = quartiles([r["raw"]["option_mass"] for r in runs[LP]["records"].values()
                                  if r is not None and isinstance((r.get("raw") or {})
                                                                  .get("option_mass"),
                                                                  (int, float))])
    d["laya_softmax_temperature"] = laya_temperatures(runs[LAYA], rows)

    # AUROC_A inverts population_auroc with the proposed TIE_SHARES_A, at the accuracy of
    # the rows those shares and the AUROC are measured on (the scored rows)
    v = d["runs"][VERB]
    shares_a = tie_shares_constant(v["tie_shares"]["levels"])
    acc_scored = v["auroc"]["right"] / v["auroc"]["n"] if v["auroc"]["n"] else 0.0
    d["latent_auroc_a"] = latent_auroc(v["auroc"]["value"], acc_scored, shares_a)
    d["proposed_constants"] = proposed(d)
    return d


def _shown(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


# --- report ----------------------------------------------------------------------------------


def _pct(x: float | None, digits: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{digits}f} %"


def _num(x: float | None, digits: int = 4) -> str:
    return "—" if x is None else f"{x:.{digits}f}"


def _iv(iv: list | None, digits: int = 4) -> str:
    return "—" if not iv or iv[0] is None else f"[{iv[0]:.{digits}f}, {iv[1]:.{digits}f}]"


def _levels_text(levels: list) -> str:
    if not levels:
        return "no rows with a confidence"
    if len(levels) <= 12:
        return ", ".join(f"{v:g}: {100 * s:.1f} % ({c})" for v, c, s in levels)
    top = max(levels, key=lambda x: x[1])
    return (f"{len(levels)} distinct values (all in the JSON); the most frequent, {top[0]:g}, "
            f"holds {100 * top[2]:.1f} % ({top[1]})")


def markdown(d: dict) -> str:
    runs = d["runs"]
    n = d["labels"]["decisions"]
    lines = [
        "# v0.5 pilot estimates (planning inputs, #91)", "",
        (f"Generated by `scripts/v05_pilot.py` (seed {d['seed']}) from the four pilot "
         "checkpoints in `docs/runs/v05-pilot/` and `" + d["labels"]["path"] + "` "
         f"(sha256 `{d['labels']['sha256'][:12]}…`, {n} decisions); CI regenerates it. **No "
         "model was called.** The rules are those of [the pilot protocol](v05-pilot.md) §5, "
         "fixed before any row was seen."), "",
        ("**This is not a result about any judge.** The rows are BANKING77 **train** queries, "
         "public since 2020 and probably in the judges' pretraining data, with about 14 % "
         "possibly mislabelled (Ying & Thomas 2022; not measured here). The accuracies are "
         "planning inputs for `scripts/v05_power.py`, not scores; nothing here tests H1 or "
         "H2. Laya runs with budgets raised beyond what its checkpoint shipped with and is "
         "near chance zero-shot by its own README: its row measures that configuration."), "",
        "## Runs", "",
        ("A row with no answer, or whose decision carries no confidence, counts as wrong in "
         "accuracy and is left out of the tie shares, the rank correlations and the AUROC; a "
         "row missing from a checkpoint counts as no answer. Accuracy with a Wilson 95 % "
         "interval over every labelled decision; overconfidence = mean confidence − accuracy "
         "on the rows with a confidence."), "",
        "| run | judge | n | in checkpoint | no answer (incl. missing) | no confidence | "
        "accuracy [Wilson 95 %] | overconfidence (n) |",
        "|---|---|---:|---:|---:|---:|---|---:|"]
    for s in ORDER:
        r = runs[s]
        a = r["accuracy"]
        over = r["overconfidence"]
        no_conf = f"{r['no_confidence']:,}" + (
            f" ({r['no_confidence_decision_right']} naming the label)"
            if r["no_confidence_decision_right"] else "")
        lines.append(
            f"| {NAMES[s]} | `{r['judge']}` | {a['n']:,} | {r['in_checkpoint']:,} | "
            f"{r['no_answer'] + r['missing']:,}"
            + (f" ({r['missing']:,} missing)" if r["missing"] else "")
            + f" | {no_conf} | {a['right']:,} = "
            f"{_pct(a['value'])} {_iv(a['wilson_95'], 3)} | "
            + (f"{over['value']:+.4f} ({over['n']:,})" if over else "—") + " |")
    lines += ["", "## Decision agreement between the Qwen3 read-outs", "",
              ("Share of the decisions on which two read-outs give the same decision (case "
               "ignored; a missing answer agrees with nothing) and the same correctness. Not "
               "fed back: it says how far the power model's one shared set of decisions "
               "(part B) is from this design, where each read-out decides for itself."), "",
              "| pair | n | same decision | same correctness |", "|---|---:|---:|---:|"]
    for r in d["decision_agreement"]:
        lines.append(f"| {NAMES[r['pair'][0]]} – {NAMES[r['pair'][1]]} | {r['n']:,} | "
                     f"{r['same_decision']:,} = {_pct(r['same_decision_share'])} | "
                     f"{r['same_correctness']:,} = {_pct(r['same_correctness_share'])} |")
    lines += ["", "## Tie shares", "",
              "Share of the rows with a confidence at each distinct value (to 1e-6), lowest to "
              "highest.", ""]
    for s in ORDER:
        t = runs[s]["tie_shares"]
        lines.append(f"- **{NAMES[s]}** (n = {t['n']:,}): {_levels_text(t['levels'])}.")
    v = d["verbalized_distribution"]
    lines += ["", "## Verbalized distribution (part C)", "",
              (f"The verbalized confidences (n = {v['n']:,}) to the nearest 0.05 (a value exactly "
               "between two levels goes down); a level under 1 % of rows joins the nearest kept "
               "level (a tie goes to the lower); weights to 0.001, the remainder on the "
               "largest."), "",
              "| level | rows | pooled rows | weight |", "|---:|---:|---:|---:|"]
    pooled = {x: c for x, c in v["pooled"]}
    weight = dict(zip(v["values"], v["weights"], strict=True))
    for x, c in v["levels"]:
        lines.append(f"| {x:g} | {c:,} | {pooled[x]:,} | {weight[x]:.3f} |" if x in pooled
                     else f"| {x:g} | {c:,} | pooled | — |")
    m = d["rank_agreement_method"]
    lines += ["", "## Rank agreement and the latent ρ (part B)", "",
              ("Spearman correlation (average ranks) of two read-outs' confidences on the rows "
               "**both** got right. ρ is the latent correlation that reproduces it: one fixed "
               f"sample of {m['normal_pairs']:,} standard normal pairs (seed {d['seed']}), the "
               "second coordinate mixed as ρ·z₁ + √(1−ρ²)·z₂, each cut into its method's tie "
               "shares on those same rows (a method with no ties is not cut), bisection on "
               f"ρ ∈ [0, {m['rho_range'][1]}] for {m['bisection_steps']} steps; a correlation at "
               "or below the ρ = 0 value maps to 0. Interval: the 2.5 % and 97.5 % percentiles "
               f"of {m['bootstrap_resamples']:,} bootstrap resamples (seed {d['seed']}) of those "
               "rows, each mapped the same way (resamples where the correlation is undefined "
               "are counted, not used). The rows both got wrong are reported, not used."), "",
              "| pair | both right | levels | Spearman [95 %] | ρ at 0 | latent ρ [95 %] | "
              "both wrong (Spearman) |", "|---|---:|---|---|---:|---|---:|"]
    for r in d["rank_agreement"]:
        lv = " / ".join("continuous" if x is None else str(x) for x in r["levels"])
        und = (f", {r['undefined_resamples']} undefined" if r["undefined_resamples"] else "")
        lines.append(f"| {NAMES[r['pair'][0]]} – {NAMES[r['pair'][1]]} | {r['both_right']:,} | "
                     f"{lv if r['both_right'] else '—'} | {_num(r['spearman'])} "
                     f"{_iv(r['spearman_95'])}{und} | {_num(r['rho_at_zero'])} | "
                     f"{_num(r['rho'])} {_iv(r['rho_95'])} | {r['both_wrong']:,} "
                     f"({_num(r['spearman_both_wrong'])}) |")
    la = d["latent_auroc_a"]
    lines += ["", "## AUROC", "",
              ("AUROC of the confidence for a right answer (ties one half) on the rows with a "
               "confidence, with DeLong's 95 % interval (it needs two right and two wrong "
               "answers)."), "",
              "| run | n | right | wrong | AUROC [DeLong 95 %] |", "|---|---:|---:|---:|---|"]
    for s in ORDER:
        a = runs[s]["auroc"]
        lines.append(f"| {NAMES[s]} | {a['n']:,} | {a['right']:,} | {a['wrong']:,} | "
                     f"{_num(a['value'])} {_iv(a['delong_95'])} |")
    lines.append("")
    if la:
        lines.append(
            f"Latent AUROC of the verbalized run: the μ with `population_auroc(μ, "
            f"{la['accuracy']}, TIE_SHARES_A)` (the accuracy of the rows with a confidence, "
            f"where the AUROC and the tie shares are measured) equal to its observed "
            f"{la['observed']:.4f} is "
            f"{la['mu']:.4f}, so Φ(μ/√2) = {la['latent']:.4f}, {la['rounded']:.2f} to the "
            "nearest 0.05" + (f", capped at {AUROC_CAP:.2f}" if la["capped"] else "")
            + ". The latent value is the one the power model cuts into ties itself, so the "
              "ties are not counted twice.")
    else:
        lines.append("The verbalized run's AUROC is undefined, so no latent AUROC is estimated.")
    lines += ["", "## Correctness correlation between Laya and each Qwen3 read-out", "",
              ("Tetrachoric correlation of right/wrong over every decision. **Not fed back**: "
               "part C's copula links two *different* judges and keeps its design values "
               "(`RHOS_C`); Laya near chance zero-shot is not a stand-in for the judges the "
               "study compares."), "",
              "| pair | both right | Laya only | Qwen3 only | both wrong | tetrachoric |",
              "|---|---:|---:|---:|---:|---:|"]
    for r in d["tetrachoric"]:
        c = r["cells"]
        val = ("undefined (a margin of 0 or 1)" if r["value"] is None
               else f"{r['value']:+.4f}" + (" (an empty cell: at the bound)"
                                            if r["boundary"] else ""))
        lines.append(f"| Laya – {NAMES[r['pair'][1]]} | {c['both_right']:,} | "
                     f"{c['first_only']:,} | {c['second_only']:,} | {c['both_wrong']:,} | "
                     f"{val} |")
    s = d["self_consistency_samples"]
    om = d["option_mass"]
    t = d["laya_softmax_temperature"]
    lines += ["", "## Also reported (not fed back)", "",
              (f"- **Self-consistency samples**: {s['samples']:,} drawn, {s['failed']:,} failed "
               f"(no answer or a null decision: they count in k and vote for nothing), in "
               f"{s['rows_with_a_failed_sample']:,} rows."),
              (f"- **`option_mass`** of the log-probability run (the probability the model put "
               f"on the listed options before normalising; n = {om['n']:,}): minimum "
               f"{_num(om['min'])}, quartiles {_num(om['q1'])} / {_num(om['median'])} / "
               f"{_num(om['q3'])}, maximum {_num(om['max'])}."),
              ("- **Laya's softmax temperatures** clamped by the library: "
               + ("; ".join(f"`{x['entry']}` shipped {_num(x['shipped'])}, applied "
                            f"{_num(x['applied'])}" for x in t["clamped"]) or "none")
               + f" (the question has {t['options_in_question']} options; device "
               f"{t['device'] or 'not recorded'})."), "",
              "| run | rows timed | s per row | rows per minute | calls | tokens per call (in / out) |",
              "|---|---:|---:|---:|---:|---|"]
    for sl in ORDER:
        tp = runs[sl]["throughput"]
        tok = ("not recorded" if tp["input_tokens_per_call"] is None
               else f"{tp['input_tokens_per_call']:,.1f} / {tp['output_tokens_per_call']:,.1f}")
        lines.append(f"| {NAMES[sl]} | {tp['rows_timed']:,} | {_num(tp['seconds_per_row'], 3)} "
                     f"| {_num(tp['rows_per_minute'], 1)} | "
                     f"{tp['calls'] if tp['calls'] is not None else '—'} | {tok} |")
    lines += ["", ("Latency is each judge's own per-decision field on one Apple M4 (16 GB), one "
                   "model in memory at a time; it excludes loading.")]

    c = d["proposed_constants"]
    lines += ["", "## Proposed PILOT constants", "",
              ("The values §5 says to feed back into `scripts/v05_power.py`. They are changed "
               "there in one reviewed commit that cites this file; `GAP_A`, `GAP_B`, `RHOS_C`, "
               "`AUTOMATABLE`, `REST_ERROR` and the grid of n stay as they are (design "
               "choices, not pilot measurements)."), "", "```python",
              "# PILOT: from docs/v05-pilot-estimates.json (docs/v05-pilot.md §5)"]
    for name in ("ACCURACIES", "RHOS"):
        lines.append(f"{name} = {c[name]['value']}")
    lines.append(f"AUROC_A, AUROC_B = {c['AUROC_A']['value']}, {c['AUROC_B']['value']}")
    for name in ("TIE_SHARES_A", "TIE_SHARES_B", "CONF_VALUES", "CONF_WEIGHTS"):
        lines.append(f"{name} = {c[name]['value']}")
    lines += ["```", "", "| constant | rule | note |", "|---|---|---|"]
    for name, x in c.items():
        extra = x.get("note") or ""
        if name.startswith("TIE_SHARES") and x.get("values"):
            extra = (f"values {x['values']}; {len(x['values'])} levels"
                     + (f"; {extra}" if extra else ""))
        lines.append(f"| `{name}` | {x['rule']} | {extra or '—'} |")
    lines += ["", ("Two limits of the power model stay and are printed with its tables: part B "
                   "scores both methods on one shared set of decisions (here each read-out "
                   "decides for itself; the decision agreement above says by how much), and "
                   "part C draws each judge's confidence independently."), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--runs", type=Path, default=RUNS_DIR, help="directory of the checkpoints")
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    args = ap.parse_args(argv)
    try:
        d = compute(args.runs, args.labels)
    except MissingCheckpoints as e:
        print(f"missing checkpoint(s): {e}. The pilot runs (docs/v05-pilot.md §4) must finish "
              "and be committed before the estimates exist.", file=sys.stderr)
        return 2
    md, js = markdown(d), json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        stale = [p for p, text in ((args.out_md, md), (args.out_json, js))
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"differs: {_shown(p)}")
        return 1 if stale else 0
    args.out_md.write_text(md, encoding="utf-8")
    args.out_json.write_text(js, encoding="utf-8")
    print(f"wrote {_shown(args.out_md)} and {_shown(args.out_json)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
