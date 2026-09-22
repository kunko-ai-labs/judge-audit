"""Calibration metrics: the honesty math. Stdlib only."""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Sequence
from typing import TypeVar

T = TypeVar("T")


def expected_calibration_error(confidences: list[float], correct: list[bool],
                               n_bins: int = 10) -> float:
    """ECE with equal-width bins. 0.0 = perfectly honest."""
    bins: list[list[bool]] = [[] for _ in range(n_bins)]
    conf_bins: list[list[float]] = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, correct, strict=True):
        i = min(int(c * n_bins), n_bins - 1)
        bins[i].append(ok)
        conf_bins[i].append(c)
    ece = 0.0
    n = len(correct)
    for b, cb in zip(bins, conf_bins, strict=True):
        if not b:
            continue
        acc = sum(b) / len(b)
        avg_conf = math.fsum(cb) / len(cb)  # exact: identical on every Python version
        ece += len(b) / n * abs(acc - avg_conf)
    return ece


def reliability_bins(confidences: list[float], correct: list[bool],
                     n_bins: int = 10) -> list[dict]:
    """Per-bin (avg confidence, accuracy, count) for the reliability diagram."""
    out = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        idx = [j for j, c in enumerate(confidences) if lo <= c < hi or (hi == 1.0 and c == 1.0)]
        if not idx:
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "avg_confidence": None,
                        "accuracy": None, "n": 0})
            continue
        cs = [confidences[j] for j in idx]
        oks = [correct[j] for j in idx]
        out.append({"bin": f"{lo:.1f}-{hi:.1f}",
                    "avg_confidence": round(math.fsum(cs) / len(cs), 4),
                    "accuracy": round(sum(oks) / len(oks), 4), "n": len(idx)})
    return out


def accuracy_coverage(confidences: list[float], correct: list[bool],
                      steps: int = 20) -> list[dict]:
    """Selective prediction: sort by confidence desc, accuracy at each coverage level.

    Answers the business question: 'what share can I automate at what error rate?'
    """
    order = sorted(range(len(confidences)), key=lambda j: confidences[j], reverse=True)
    curve = []
    for s in range(1, steps + 1):
        k = max(1, int(len(order) * s / steps))
        top = order[:k]
        acc = sum(correct[j] for j in top) / k
        curve.append({"coverage": round(k / len(order), 4),
                      "accuracy": round(acc, 4), "n": k,
                      "min_confidence": round(confidences[top[-1]], 4)})
    return curve


def zero_error_coverage(confidences: list[float], correct: list[bool]) -> dict:
    """Largest most-confident prefix with zero observed errors (nikhilmudholkar metric).

    Order-independent: rows are walked from the top in groups of equal confidence and a
    group counts only when every row in it is correct and no error was seen above it. A
    tie is one threshold — you cannot automate half of the rows that say 0.9 — so the
    prefix is cut at whole groups and shuffling the input never changes the result.
    `threshold` is the lowest confidence in the covered prefix (None when it is empty).
    """
    if not confidences:
        return {"coverage": 0.0, "n": 0, "threshold": None}
    order = sorted(range(len(confidences)), key=lambda j: confidences[j], reverse=True)
    k, threshold = 0, None
    i, n = 0, len(order)
    while i < n:
        c = confidences[order[i]]
        end, clean = i, True  # the group is the contiguous run of rows at confidence c
        while end < n and confidences[order[end]] == c:
            clean = clean and correct[order[end]]
            end += 1
        if not clean:
            break
        k, threshold, i = end, c, end
    return {"coverage": round(k / n, 4), "n": k,
            "threshold": round(threshold, 4) if k else None}


# --- uncertainty: percentile bootstrap over rows or over groups of rows ----------------
#
# Every headline number is a statistic of n rows; the interval says how much it would
# move on another sample of the same size. Rows (or whole groups of rows) are resampled
# with replacement and the statistic recomputed on each resample; the 2.5th and 97.5th
# percentiles of those values are the 95 % interval. Pure Python, seeded, identical on
# every Python version: `random.Random(seed).choices` and linear interpolation between
# order statistics.
#
# Groups exist because the datasets repeat texts: the router has 61 distinct states in
# 120 rows (14 in the 40 hard rows), the adversarial emails 189 in 200. Two rows with the
# same text are not two independent observations of the judge, so the published interval
# resamples distinct texts (a cluster bootstrap); `groups=None` is the row-i.i.d. version.

N_BOOT = 2000
CI_LEVEL = 0.95


def _percentile(sorted_values: list[float], q: float) -> float:
    """q-th quantile (0..1) by linear interpolation between order statistics — the
    same cut as `statistics.quantiles(method="inclusive")`."""
    pos = q * (len(sorted_values) - 1)
    i = int(pos)
    if i + 1 >= len(sorted_values):
        return sorted_values[-1]
    frac = pos - i
    return sorted_values[i] + (sorted_values[i + 1] - sorted_values[i]) * frac


def bootstrap_ci(values: Sequence[T], statistic: Callable[[list[T]], float],
                 n_boot: int = N_BOOT, seed: int = 0, level: float = CI_LEVEL,
                 groups: Sequence[Hashable] | None = None) -> tuple[float, float] | None:
    """Percentile bootstrap interval of `statistic(values)`.

    `values` is one entry per row (a bool, a (confidence, correct) pair, …) and
    `statistic` maps a list of them to a number. With `groups` (one key per row, e.g.
    the row's text) whole groups are resampled with replacement and their rows
    concatenated — the unit of independence is the group; without it every row is its
    own group. Returns (lo, hi) rounded to 4 decimals, deterministic for a seed; None
    when there are no rows."""
    n = len(values)
    if n == 0:
        return None
    if groups is None:
        units: list[list[T]] = [[v] for v in values]
    else:
        if len(groups) != n:
            raise ValueError(f"{len(groups)} group keys for {n} rows")
        by_key: dict[Hashable, list[T]] = {}
        for key, v in zip(groups, values, strict=True):
            by_key.setdefault(key, []).append(v)          # first-appearance order
        units = list(by_key.values())
    rng = random.Random(seed)
    idx = range(len(units))
    stats = sorted(statistic([v for i in rng.choices(idx, k=len(units)) for v in units[i]])
                   for _ in range(n_boot))
    tail = (1 - level) / 2
    return round(_percentile(stats, tail), 4), round(_percentile(stats, 1 - tail), 4)


def accuracy_ci(correct: Sequence[bool], n_boot: int = N_BOOT, seed: int = 0,
                groups: Sequence[Hashable] | None = None) -> tuple[float, float] | None:
    """95 % interval of the share of correct rows."""
    return bootstrap_ci(list(correct), lambda ok: sum(ok) / len(ok), n_boot, seed,
                        groups=groups)


def ece_ci(confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10,
           n_boot: int = N_BOOT, seed: int = 0,
           groups: Sequence[Hashable] | None = None) -> tuple[float, float] | None:
    """95 % interval of `expected_calibration_error`, bins recomputed on every resample."""
    rows = list(zip(confidences, correct, strict=True))
    return bootstrap_ci(rows, lambda rs: expected_calibration_error(
        [c for c, _ in rs], [ok for _, ok in rs], n_bins), n_boot, seed, groups=groups)


def zero_error_coverage_ci(confidences: Sequence[float], correct: Sequence[bool],
                           n_boot: int = N_BOOT, seed: int = 0,
                           groups: Sequence[Hashable] | None = None) -> tuple[float, float] | None:
    """95 % interval of `zero_error_coverage(...)["coverage"]`."""
    rows = list(zip(confidences, correct, strict=True))
    return bootstrap_ci(rows, lambda rs: zero_error_coverage(
        [c for c, _ in rs], [ok for _, ok in rs])["coverage"], n_boot, seed, groups=groups)
