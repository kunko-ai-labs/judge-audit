"""Calibration metrics: the honesty math. Stdlib only."""
from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Sequence
from typing import TypeVar

T = TypeVar("T")


EQUAL_WIDTH = "equal_width"
EQUAL_MASS = "equal_mass"


def expected_calibration_error(confidences: list[float], correct: list[bool],
                               n_bins: int = 10, binning: str = EQUAL_WIDTH) -> float:
    """ECE: the row-weighted gap between confidence and accuracy per bin. 0.0 = honest.

    `binning="equal_width"` (the default, and every ECE the repo publishes as "ECE") cuts
    [0, 1] into `n_bins` intervals of equal width. `binning="equal_mass"` cuts the rows,
    sorted by confidence, into `n_bins` groups of about equal size (`_equal_mass_bins`)
    — the robustness check for a judge whose confidences pile up in one or two bins.
    No rows: 0.0 under either binning (the published convention for an empty audit).
    """
    _require_finite(confidences)
    if binning == EQUAL_MASS:
        return _equal_mass_ece(confidences, correct, n_bins)
    if binning != EQUAL_WIDTH:
        raise ValueError(f"unknown binning {binning!r}: use {EQUAL_WIDTH!r} or {EQUAL_MASS!r}")
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


def _equal_mass_bins(sorted_conf: list[float], n_bins: int) -> list[int]:
    """Cut positions (0 … n) of equal-mass bins over confidences sorted ascending.

    The ideal cuts sit after rows i·n/n_bins. A cut may only fall between two different
    confidences — records with the same confidence always share a bin — so each ideal
    cut moves to the nearest edge of a group of tied confidences (the lower edge when
    both are equally near), and cuts that land on the same edge merge. Bins may
    therefore be unequal, and fewer than `n_bins`: a judge that says 1.0 on 125 of 200
    rows gets one bin of 125. The result depends only on the multiset of confidences,
    never on row order. Integer arithmetic (k·n_bins vs i·n) keeps it exact.
    """
    n = len(sorted_conf)
    edges = [0] + [k for k in range(1, n) if sorted_conf[k] != sorted_conf[k - 1]] + [n]
    cuts = {0, n}
    for i in range(1, n_bins):
        cuts.add(min(edges, key=lambda k: (abs(k * n_bins - i * n), k)))
    return sorted(cuts)


def _equal_mass_ece(confidences: list[float], correct: list[bool], n_bins: int) -> float:
    rows = sorted(zip(confidences, correct, strict=True), key=lambda r: r[0])
    n = len(rows)
    if n == 0:
        return 0.0
    cuts = _equal_mass_bins([c for c, _ in rows], n_bins)
    ece = 0.0
    for lo, hi in zip(cuts, cuts[1:], strict=False):
        b = rows[lo:hi]
        acc = sum(ok for _, ok in b) / len(b)
        avg_conf = math.fsum(c for c, _ in b) / len(b)   # exact: order-free, bit for bit
        ece += len(b) / n * abs(acc - avg_conf)
    return ece


def _binned_rows(confidences: list[float], correct: list[bool], n_bins: int,
                 binning: str) -> list[list[tuple[float, bool]]]:
    """The non-empty bins `expected_calibration_error` uses, as (confidence, correct) rows."""
    if binning == EQUAL_MASS:
        rows = sorted(zip(confidences, correct, strict=True), key=lambda r: r[0])
        cuts = _equal_mass_bins([c for c, _ in rows], n_bins)
        return [rows[lo:hi] for lo, hi in zip(cuts, cuts[1:], strict=False) if hi > lo]
    if binning != EQUAL_WIDTH:
        raise ValueError(f"unknown binning {binning!r}: use {EQUAL_WIDTH!r} or {EQUAL_MASS!r}")
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, correct, strict=True):
        bins[min(int(c * n_bins), n_bins - 1)].append((c, ok))
    return [b for b in bins if b]


def worst_calibration_bin(confidences: list[float], correct: list[bool], n_bins: int = 10,
                          binning: str = EQUAL_WIDTH) -> dict:
    """The bin with the largest |accuracy − confidence|: its gap, row count, mean
    confidence and accuracy (the lowest-confidence bin wins a tie). The gap is the MCE."""
    _require_finite(confidences)
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    if not confidences:
        raise ValueError("maximum_calibration_error of no rows is undefined")
    outside = next((c for c in confidences if not 0.0 <= c <= 1.0), None)
    if outside is not None:
        # a confidence below 0 would land in a bin from the top by Python's negative index
        raise ValueError(f"confidence must lie in [0, 1], got {outside!r}")
    worst: dict = {}
    for b in _binned_rows(confidences, correct, n_bins, binning):
        acc = sum(ok for _, ok in b) / len(b)
        avg_conf = math.fsum(c for c, _ in b) / len(b)
        gap = abs(acc - avg_conf)
        if not worst or gap > worst["gap"]:
            worst = {"gap": gap, "n": len(b), "avg_confidence": avg_conf, "accuracy": acc}
    return worst


def maximum_calibration_error(confidences: list[float], correct: list[bool],
                              n_bins: int = 10, binning: str = EQUAL_WIDTH) -> float:
    """MCE: the largest gap between confidence and accuracy in any non-empty bin.

    The worst bin rather than the row-weighted average (Naeini, Cooper & Hauskrecht, AAAI
    2015; Guo et al. 2017): an ECE of 0.03 can hide one confidence range that is wrong
    half the time. Same bins as `expected_calibration_error` under either `binning`. A
    maximum over bins of different sizes can be decided by a bin of one row, so read it
    with that bin's count (`worst_calibration_bin`). Proposed here as evidence for the
    documentation an auditor asks for, not as a legal requirement. No rows → raises.
    """
    return worst_calibration_bin(confidences, correct, n_bins, binning)["gap"]


def brier_score(confidences: list[float], correct: list[bool]) -> float:
    """Top-label Brier score: mean of (confidence − correct)², 0 = certain and right.

    The proper scoring rule that needs no bins: it rewards being right and being honest
    about it at once, so it is not a calibration number alone — a more accurate judge
    scores better at equal honesty. A mean of no rows is undefined and raises."""
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    if not confidences:
        raise ValueError("brier_score of no rows is undefined")
    _require_finite(confidences)
    return math.fsum((c - float(ok)) ** 2 for c, ok in zip(confidences, correct, strict=True)
                     ) / len(confidences)


def negative_log_likelihood(confidences: list[float], correct: list[bool]) -> float:
    """Top-label negative log-likelihood (log loss): mean of −ln p(outcome), where p is the
    stated confidence when right and 1 − confidence when wrong. Nothing is clipped: a judge
    that states 1.0 and is wrong (or 0.0 and is right) has an infinite loss, and this
    returns `math.inf` rather than a number built on a confidence it never gave.

    The other proper scoring rule next to Brier; it punishes confident mistakes far harder
    (a wrong 0.99 costs 4.6, a wrong 0.6 costs 0.92). A mean of no rows raises."""
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    if not confidences:
        raise ValueError("negative_log_likelihood of no rows is undefined")
    _require_finite(confidences)
    if nll_infinite(confidences, correct):
        return math.inf
    return math.fsum(-math.log(c if ok else 1.0 - c)
                     for c, ok in zip(confidences, correct, strict=True)) / len(confidences)


def nll_infinite(confidences: Sequence[float], correct: Sequence[bool]) -> int:
    """Rows whose declared confidence gives the outcome probability 0: stated certain, wrong."""
    _require_finite(confidences)
    return sum(1 for c, ok in zip(confidences, correct, strict=True)
               if (c if ok else 1.0 - c) <= 0.0)


def reliability_bins(confidences: list[float], correct: list[bool],
                     n_bins: int = 10) -> list[dict]:
    """Per-bin (avg confidence, accuracy, count) for the reliability diagram."""
    out: list[dict] = []
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


def _require_finite(confidences: Sequence[float]) -> None:
    """Refuse NaN and ±inf: a group walk cannot advance past a value unequal to itself.

    Unknown confidence is reported, never imputed — so it is not silently dropped or
    clamped here either; the caller decides what an unknown confidence means.
    """
    for i, c in enumerate(confidences):
        if not math.isfinite(c):
            raise ValueError(f"confidence must be a finite number, got {c!r} at row {i}")


def accuracy_coverage(confidences: list[float], correct: list[bool],
                      steps: int = 20) -> list[dict]:
    """Selective prediction: sort by confidence desc, accuracy at each coverage level.

    Answers the business question: 'what share can I automate at what error rate?'

    Order-independent, like `zero_error_coverage`: rows are walked from the top in groups
    of equal confidence, and a coverage point is only reported at a cut that includes a
    whole group. A tie is one threshold — you cannot automate half of the rows that say
    0.9 — so each of the `steps` target coverage levels snaps *up* to the end of the group
    it falls inside instead of splitting it; several targets that land inside the same
    group collapse to that group's single point instead of repeating it. `min_confidence`
    is the covered group's own confidence, which is what makes it a valid threshold.
    """
    _require_finite(confidences)
    n = len(confidences)
    if not n:
        return []
    order = sorted(range(n), key=lambda j: confidences[j], reverse=True)
    boundaries: list[tuple[int, float]] = []  # (k, confidence) after each whole group
    i = 0
    while i < n:
        c = confidences[order[i]]
        j = i
        while j < n and confidences[order[j]] == c:
            j += 1
        boundaries.append((j, c))
        i = j

    curve = []
    last_k = None
    for s in range(1, steps + 1):
        target = max(1, int(n * s / steps))
        k, conf = next((b for b in boundaries if b[0] >= target), boundaries[-1])
        if k == last_k:
            continue  # several targets snapped to the same group boundary
        last_k = k
        top = order[:k]
        acc = sum(correct[j] for j in top) / k
        curve.append({"coverage": round(k / n, 4), "accuracy": round(acc, 4), "n": k,
                      "min_confidence": round(conf, 4)})
    return curve


def zero_error_coverage(confidences: list[float], correct: list[bool]) -> dict:
    """Largest most-confident prefix with zero observed errors (nikhilmudholkar metric).

    Order-independent: rows are walked from the top in groups of equal confidence and a
    group counts only when every row in it is correct and no error was seen above it. A
    tie is one threshold — you cannot automate half of the rows that say 0.9 — so the
    prefix is cut at whole groups and shuffling the input never changes the result.
    `threshold` is the lowest confidence in the covered prefix (None when it is empty).
    """
    _require_finite(confidences)
    if not confidences:
        return {"coverage": 0.0, "n": 0, "threshold": None}
    order = sorted(range(len(confidences)), key=lambda j: confidences[j], reverse=True)
    k, threshold = 0, None  # type: tuple[int, float | None]
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
            "threshold": round(threshold, 4) if k and threshold is not None else None}


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

BOOTSTRAP = "bootstrap"            # percentile bootstrap, clustered when groups are given
EXACT = "clopper-pearson"          # exact binomial, used where the bootstrap degenerates


class Interval(tuple):
    """A published `(lo, hi)` that remembers which method produced it.

    It *is* the two-element tuple every report already formats and serialises — the
    extra `.method` (and the derived `.degenerate`) only lets a table mark the
    interval whose meaning differs from the bootstrap default.
    """

    method: str

    def __new__(cls, lo: float, hi: float, method: str) -> Interval:
        obj = super().__new__(cls, (round(lo, 4), round(hi, 4)))
        obj.method = method
        return obj

    @property
    def degenerate(self) -> bool:
        """Zero width out of the bootstrap: every resample gave the same value."""
        return self.method == BOOTSTRAP and self[0] == self[1]


# --- exact binomial interval ----------------------------------------------------------
#
# The percentile bootstrap collapses to a point when the statistic cannot move: 10 rows
# all correct resample to 10 correct every time, so the interval reads [1.0, 1.0] — a
# claim of certainty from ten observations. At that boundary we publish the Clopper-
# Pearson exact interval instead: the Beta quantiles that invert the binomial test,
# [Beta(k, n-k+1)_{a/2}, Beta(k+1, n-k)_{1-a/2}], with the closed-form ends 0 and 1.
# It assumes independent rows, so where texts repeat it is a LOWER BOUND on the width.


def _beta_cf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz), stdlib only."""
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _beta_inc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b) = P(Beta(a, b) <= x)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x <= (a + 1.0) / (a + b + 2.0):   # <=: x = 1 - x would recurse forever
        return front * _beta_cf(a, b, x) / a
    return 1.0 - _beta_inc(b, a, 1.0 - x)


def _beta_quantile(q: float, a: float, b: float) -> float:
    """x with I_x(a, b) = q, by bisection — 200 halvings of [0, 1] is exact to 1e-15."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _beta_inc(a, b, mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson(successes: int, n: int, alpha: float = 0.05) -> Interval:
    """Exact binomial (Clopper-Pearson) interval for `successes` out of `n` rows.

    The conservative inversion of the binomial test: 0/10 -> [0.0, 0.3085],
    10/10 -> [0.6915, 1.0], 8/10 -> [0.4439, 0.9748]. Rows are assumed independent.
    """
    if n <= 0:
        raise ValueError(f"n must be positive, got {n}")
    if not 0 <= successes <= n:
        raise ValueError(f"{successes} successes out of {n} rows")
    lo = 0.0 if successes == 0 else _beta_quantile(alpha / 2, successes, n - successes + 1)
    hi = 1.0 if successes == n else _beta_quantile(1 - alpha / 2, successes + 1, n - successes)
    return Interval(lo, hi, EXACT)


def interpolated_quantile(sorted_values: list[float], q: float) -> float:
    """q-th quantile (0..1) by linear interpolation between order statistics —
    Hyndman–Fan type 7, numpy's default and `statistics.quantiles(method="inclusive")`."""
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
    return (round(interpolated_quantile(stats, tail), 4),
            round(interpolated_quantile(stats, 1 - tail), 4))


def proportion_ci(successes: int, values: Sequence[T], statistic: Callable[[list[T]], float],
                  n_boot: int = N_BOOT, seed: int = 0,
                  groups: Sequence[Hashable] | None = None) -> Interval | None:
    """Interval of a proportion: the clustered bootstrap, exact where it degenerates.

    The bootstrap is always run first, because it is the one that honours the clusters.
    Only when it comes back with **zero width** — every resample gave the same value, as
    when every row is correct — is the exact binomial interval of `successes` out of
    `len(values)` published instead. A statistic that *can* move keeps its bootstrap even
    at 0 % or 100 %: a judge whose zero-error coverage is 0 % because one confident error
    sits at the top has a wide interval, and replacing it with the exact one would claim
    a precision the resamples deny.
    """
    n = len(values)
    if n == 0:
        return None
    ci = bootstrap_ci(list(values), statistic, n_boot, seed, groups=groups)
    if ci is None:
        return None
    if ci[0] == ci[1]:
        return clopper_pearson(successes, n, alpha=1 - CI_LEVEL)
    return Interval(ci[0], ci[1], BOOTSTRAP)


def ci_fields(name: str, ci: Interval | None, point: float | None = None) -> dict:
    """The two published keys of an interval: `<name>_ci` and `<name>_ci_method`.

    Reports are rendered from JSON, so the method has to travel next to the pair —
    a table cannot mark an exact interval it cannot recognise. Given the `point`
    estimate, a third key `<name>_ci_point_outside: true` is added when the point lies
    outside its own percentile interval (a statistic whose resamples are biased away
    from it on this sample), so the report can say so instead of printing a range that
    silently excludes the number next to it.
    """
    if ci is None:
        return {f"{name}_ci": None, f"{name}_ci_method": None}
    if ci[0] == ci[1]:
        # A zero-width 95 % interval is not a narrow interval, it is no interval:
        # every resample returned the same value. Say that instead of publishing [x, x].
        return {f"{name}_ci": None, f"{name}_ci_method": "degenerate-" + ci.method}
    out: dict = {f"{name}_ci": [ci[0], ci[1]], f"{name}_ci_method": ci.method}
    if point is not None and not ci[0] <= round(point, 4) <= ci[1]:
        out[f"{name}_ci_point_outside"] = True
    return out


def accuracy_ci(correct: Sequence[bool], n_boot: int = N_BOOT, seed: int = 0,
                groups: Sequence[Hashable] | None = None) -> Interval | None:
    """95 % interval of the share of correct rows."""
    ok = list(correct)
    return proportion_ci(sum(bool(x) for x in ok), ok, lambda xs: sum(xs) / len(xs),
                         n_boot, seed, groups=groups)


def ece_ci(confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10,
           n_boot: int = N_BOOT, seed: int = 0,
           groups: Sequence[Hashable] | None = None,
           binning: str = EQUAL_WIDTH) -> Interval | None:
    """95 % interval of `expected_calibration_error`, bins recomputed on every resample.

    ECE is not a proportion, so it keeps the clustered bootstrap even when the interval
    comes back with zero width; `.degenerate` marks that case for the reports. With
    `binning="equal_mass"` the equal-mass bins are rebuilt on each resample too.
    """
    rows = list(zip(confidences, correct, strict=True))
    ci = bootstrap_ci(rows, lambda rs: expected_calibration_error(
        [c for c, _ in rs], [ok for _, ok in rs], n_bins, binning), n_boot, seed,
        groups=groups)
    return None if ci is None else Interval(ci[0], ci[1], BOOTSTRAP)


def mce_ci(confidences: Sequence[float], correct: Sequence[bool], n_bins: int = 10,
           n_boot: int = N_BOOT, seed: int = 0,
           groups: Sequence[Hashable] | None = None,
           binning: str = EQUAL_WIDTH) -> Interval | None:
    """95 % interval of `maximum_calibration_error`, bins rebuilt on every resample, by the
    same clustered bootstrap as `ece_ci`. A maximum over bins tends to rise on resamples, so the
    point estimate can sit near the bottom of its interval or below it (`ci_fields` marks
    that ◊)."""
    rows = list(zip(confidences, correct, strict=True))
    ci = bootstrap_ci(rows, lambda rs: maximum_calibration_error(
        [c for c, _ in rs], [ok for _, ok in rs], n_bins, binning), n_boot, seed,
        groups=groups)
    return None if ci is None else Interval(ci[0], ci[1], BOOTSTRAP)


def brier_ci(confidences: Sequence[float], correct: Sequence[bool],
             n_boot: int = N_BOOT, seed: int = 0,
             groups: Sequence[Hashable] | None = None) -> Interval | None:
    """95 % interval of `brier_score`: the same clustered bootstrap as the ECE interval
    (same resampling unit, same seed, same number of resamples). Not a proportion, so a
    zero-width result stays a bootstrap and is flagged `.degenerate`."""
    rows = list(zip(confidences, correct, strict=True))
    ci = bootstrap_ci(rows, lambda rs: brier_score([c for c, _ in rs], [ok for _, ok in rs]),
                      n_boot, seed, groups=groups)
    return None if ci is None else Interval(ci[0], ci[1], BOOTSTRAP)


def nll_ci(confidences: Sequence[float], correct: Sequence[bool],
           n_boot: int = N_BOOT, seed: int = 0,
           groups: Sequence[Hashable] | None = None) -> Interval | None:
    """95 % interval of `negative_log_likelihood`, by the same clustered bootstrap as Brier;
    None when a row makes it infinite (every resample that keeps the row is infinite)."""
    if nll_infinite(confidences, correct):
        return None
    rows = list(zip(confidences, correct, strict=True))
    ci = bootstrap_ci(rows, lambda rs: negative_log_likelihood([c for c, _ in rs],
                                                               [ok for _, ok in rs]),
                      n_boot, seed, groups=groups)
    return None if ci is None else Interval(ci[0], ci[1], BOOTSTRAP)


def zero_error_coverage_ci(confidences: Sequence[float], correct: Sequence[bool],
                           n_boot: int = N_BOOT, seed: int = 0,
                           groups: Sequence[Hashable] | None = None) -> Interval | None:
    """95 % interval of `zero_error_coverage(...)["coverage"]`.

    A coverage of 0 or 1 is a 0/n or n/n proportion of automatable rows, and there the
    bootstrap degenerates; the exact binomial interval is published instead.
    """
    rows = list(zip(confidences, correct, strict=True))
    covered = zero_error_coverage(list(confidences), list(correct))["n"]
    return proportion_ci(covered, rows, lambda rs: zero_error_coverage(
        [c for c, _ in rs], [ok for _, ok in rs])["coverage"], n_boot, seed, groups=groups)
