"""Discrimination, selective prediction at a target risk, and paired comparisons. Stdlib only.

Calibration asks whether a confidence of 0.9 is right 90 % of the time. The questions here
are the ones a deployment asks next (docs/judges.md § Discrimination and selective
prediction, § Paired comparisons):

- does the confidence rank the judge's errors below its right answers? (`failure_auroc`)
- how much risk does the judge carry across every automation threshold? (`aurc`)
- how much can be automated at a target risk, with the threshold chosen on one split and
  checked on another? (`coverage_at_risk`, `coverage_at_risk_crossfit`)
- is judge A better than judge B on the same rows? (`paired_difference_ci`,
  `paired_difference_test` with its percentile p-value, `holm` across a family of such
  tests, `mcnemar_exact`)

Every point estimate here treats a tie as one threshold, as `zero_error_coverage` does:
rows with the same confidence are never split by the order they happen to arrive in, and no
point estimate depends on row order. The intervals use the repository's seeded bootstrap,
which draws texts in first-appearance order: like every interval published here, an
interval is reproducible for a given file, not invariant to reordering it. A confidence
that is not a finite number is refused, never imputed.
"""
from __future__ import annotations

import functools
import math
import random
from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any, NamedTuple, TypeVar

from .calibration import (
    BOOTSTRAP,
    CI_LEVEL,
    N_BOOT,
    Interval,
    _beta_quantile,
    _require_finite,
    interpolated_quantile,
)

T = TypeVar("T")


def _groups_desc(confidences: Sequence[float],
                 correct: Sequence[bool]) -> list[tuple[float, int, int]]:
    """(confidence, rows, errors) per group of equal confidence, most confident first."""
    counts: dict[float, list[int]] = {}
    for c, ok in zip(confidences, correct, strict=True):
        slot = counts.setdefault(c, [0, 0])
        slot[0] += 1
        slot[1] += 0 if ok else 1
    return [(c, m, e) for c, (m, e) in sorted(counts.items(), key=lambda kv: kv[0], reverse=True)]


# --- discrimination --------------------------------------------------------------------


def failure_auroc(confidences: Sequence[float], correct: Sequence[bool]) -> float | None:
    """AUROC of the confidence as a predictor of a correct answer.

    The probability that a right answer, drawn at random, carries a higher confidence than
    a wrong answer drawn at random; a tie counts one half. 1.0 = every right answer is
    more confident than every wrong one, 0.5 = the confidence says nothing about which is
    which. It measures ranking only: a judge can rank perfectly and still be miscalibrated.
    None when every answer is right or every answer is wrong — there is nothing to rank,
    and no number is imputed.

    Mann–Whitney U with mid-ranks for ties, in integer arithmetic (doubled ranks) so the
    value is exact and identical on every Python version.
    """
    _require_finite(confidences)
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    n_ok = sum(1 for ok in correct if ok)
    n_err = len(correct) - n_ok
    if n_ok == 0 or n_err == 0:
        return None
    order = sorted(range(len(confidences)), key=lambda j: confidences[j])
    doubled_rank_sum = 0          # sum over right answers of 2 x (mid-rank)
    i, n = 0, len(order)
    while i < n:
        j = i
        while j < n and confidences[order[j]] == confidences[order[i]]:
            j += 1
        doubled_mid_rank = i + 1 + j  # ranks i+1 … j share (i+1+j)/2
        doubled_rank_sum += doubled_mid_rank * sum(1 for k in order[i:j] if correct[k])
        i = j
    return (doubled_rank_sum - n_ok * (n_ok + 1)) / (2 * n_ok * n_err)


def aurc(confidences: Sequence[float], correct: Sequence[bool]) -> float:
    """Area under the risk–coverage curve (Geifman, Uziel & El-Yaniv, ICLR 2019).

    Sort the answers from the most confident down; after the first k, the risk is the
    share of those k that are wrong. AURC is the mean of that risk over k = 1 … n: the
    average error rate across every automation threshold. Lower is better; it rewards
    accuracy as well as ranking, so read it next to accuracy and `failure_auroc`.

    Ties: inside a group of equal confidence the rows have no order, so the risk at a cut
    inside the group is its expectation over every order of the group — errors above the
    group plus j·e/m errors after j of its m rows (e of them wrong). The result is the
    expected AURC under a random order of ties, and does not depend on row order.
    A mean over no rows is undefined and raises.
    """
    _require_finite(confidences)
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    if not confidences:
        raise ValueError("aurc of no rows is undefined")
    terms: list[float] = []
    rows_above = errors_above = 0
    for _, m, e in _groups_desc(confidences, correct):
        for j in range(1, m + 1):
            terms.append((errors_above + j * e / m) / (rows_above + j))
        rows_above += m
        errors_above += e
    return math.fsum(terms) / len(terms)


# --- selective prediction at a target risk ---------------------------------------------


def risk_upper_bound(errors: int, n: int, delta: float = 0.05) -> float:
    """One-sided exact (Clopper–Pearson) upper bound on an error rate, at level 1 − delta.

    The largest error rate at which seeing `errors` or fewer out of `n` still has
    probability at least `delta`: Beta(errors + 1, n − errors) at 1 − delta. Zero errors
    give 1 − delta^(1/n) (0 of 299 → 0.99 %); no rows bound nothing (1.0). Not rounded,
    because a decision is taken on it. Rows are assumed independent.
    """
    if not 0 < delta < 1:
        raise ValueError(f"delta must be in (0, 1), got {delta}")
    if n < 0 or not 0 <= errors <= n:
        raise ValueError(f"{errors} errors out of {n} rows")
    if n == 0 or errors == n:
        return 1.0
    if errors == 0:
        return 1.0 - delta ** (1.0 / n)
    return _beta_quantile(1.0 - delta, errors + 1, n - errors)


def _check_count(name: str, value: object) -> int:
    """A non-negative int (a bool is refused: True is not a number of errors)."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def min_rows_to_certify(target_risk: float, delta: float = 0.05, errors: int = 0) -> int:
    """The fewest rows whose error rate `risk_upper_bound` can certify at `target_risk`
    with `errors` errors among them: the smallest n whose bound is at or below the target.
    At delta = 0.05, zero errors need 299 rows for 1 %, 149 for 2 %, 59 for 5 % and 29 for
    10 %; two errors need 628, 313, 124 and 61. With zero errors, a set with fewer rows
    cannot pass however few errors it holds."""
    if not 0 < target_risk < 1:
        raise ValueError(f"target_risk must be in (0, 1), got {target_risk}")
    if not 0 < delta < 1:
        raise ValueError(f"delta must be in (0, 1), got {delta}")
    _check_count("errors", errors)
    return _min_rows(target_risk, delta, errors)


@functools.lru_cache(maxsize=256)
def _min_rows(target_risk: float, delta: float, errors: int) -> int:
    """`min_rows_to_certify` on checked input, cached: each call bisects on beta quantiles,
    and the cross-fit and the simulations ask for the same few targets many times."""
    if errors == 0:
        n = max(1, math.ceil(math.log(delta) / math.log1p(-target_risk)))
        while n > 1 and risk_upper_bound(0, n - 1, delta) <= target_risk:
            n -= 1
        while risk_upper_bound(0, n, delta) > target_risk:
            n += 1
        return n
    # the bound falls as n grows with the errors fixed: bracket, then bisect
    lo, hi = errors, 2 * (errors + 1)           # lo fails (n = errors bounds nothing)
    while risk_upper_bound(errors, hi, delta) > target_risk:
        lo, hi = hi, 2 * hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if risk_upper_bound(errors, mid, delta) <= target_risk else (mid, hi)
    return hi


def coverage_at_risk(cal_confidences: Sequence[float], cal_correct: Sequence[bool],
                     test_confidences: Sequence[float], test_correct: Sequence[bool],
                     target_risk: float, delta: float = 0.05, start_errors: int = 0) -> dict:
    """The share of decisions a judge can automate at a target risk, chosen on one split
    and checked on another.

    **Choosing the threshold (calibration split).** Walk the calibration rows from the most
    confident down, one whole group of equal confidence at a time. At each cut, test
    "the error rate of the rows above this cut exceeds `target_risk`" with the exact
    binomial bound (`risk_upper_bound`): the cut passes when the one-sided 1 − `delta`
    upper bound is at most `target_risk`. Stop at the first cut that fails; the threshold
    is the confidence of the last cut that passed. The sequence starts at the first cut
    holding at least `min_rows_to_certify(target_risk, delta)` rows: a smaller cut fails
    whatever its rows, and testing it first would end the sequence before any cut that
    could pass (a judge with continuous confidences has one row in its top cut). This is
    fixed-sequence testing (Learn then Test; Angelopoulos, Bates, Candès, Jordan & Lei,
    Annals of Applied Statistics 2025): the order of the tests and where they start are
    set by the confidences, the target and delta, never by which rows are wrong, so no
    correction for the number of cuts is needed. Selective classification
    with a guaranteed risk is Geifman & El-Yaniv (NeurIPS 2017); Jung, Brahman & Choi
    (ICLR 2025) apply the same idea to LLM judges. With probability at least 1 − `delta`
    over the calibration draw, the true error rate above the threshold is at most
    `target_risk` — **provided the calibration rows are independent draws**, and the test
    rows come from the same distribution. The binomial bound counts every row as one
    independent trial: two copies of a text that a judge answers the same way are one
    observation counted twice, and the bound is then too tight (on 300 texts each
    present twice, a 5 % test certifies 12 % of the time at a true risk of 5 %). With
    repeated texts, pass one unit per text (`aggregate_by_group`), as
    `coverage_at_risk_crossfit` does when given `groups`.

    **A later, pre-registered start (`start_errors`).** Starting where zero errors could
    pass means that, with continuous confidences, one error among the first
    `min_rows_to_certify` rows ends the walk: the procedure certifies with probability
    (1 − r′)^299 at 1 %, about 47 % when the true rate r′ is a quarter of the target.
    With `start_errors = k` the sequence starts instead at the first cut holding
    `min_rows_to_certify(target_risk, delta, errors=k)` rows (628 for 1 %, 313 for 2 %,
    124 for 5 %, 61 for 10 % with k = 2), and the walk and its stopping rule are otherwise
    the same. The start depends only on the target, delta, k and the row counts of the
    confidence groups, never on which rows are wrong, so the guarantee above is
    unchanged; k must be fixed before the labels are seen (pre-registered), since choosing
    it after looking would make it depend on them. What it costs: cuts above the start are
    never tested, so a judge whose top rows are error-free cannot be certified on fewer
    rows than the start. `start_errors = 0` (the default) is the #98 procedure and returns
    exactly its result. With k > 0 the result also carries `start_errors`, and when the
    calibration split holds fewer rows than the start, nothing can be tested: `threshold`
    is None and `reason` says so, rather than a coverage of 0 with no explanation.

    **Checking it (test split).** The threshold is applied to the test rows unchanged:
    their coverage, errors, observed risk and its own one-sided bound are reported. No
    test row influences the threshold.

    Nothing passes → `threshold` is None and nothing is automated: on few rows even a
    perfect judge cannot certify a small risk (zero errors in 100 rows bound the risk
    at 2.95 %, not below 2 %). `min_covered` is the fewest rows the first cut tested may
    hold: that cut is the first whole group of equal confidence that reaches it, so ties
    can make it larger.
    """
    return _coverage_at_risk(cal_confidences, cal_correct, test_confidences, test_correct,
                             target_risk, delta, start_errors, unit="rows")


def certify_threshold(confidences: Sequence[float], correct: Sequence[bool],
                      target_risk: float, delta: float = 0.05, start_errors: int = 0) -> dict:
    """The threshold to deploy: `coverage_at_risk`'s walk on every labelled unit, with
    nothing held out.

    The walk is the one documented there (fixed-sequence exact binomial tests from the
    most confident unit down, whole tie groups, starting at the cut holding
    `min_rows_to_certify(target_risk, delta, start_errors)` units, stopping at the first
    failure). Its guarantee: with probability at least 1 − `delta` over the draw of these
    units, the true error rate among decisions at or above `threshold` is at most
    `target_risk` — for traffic drawn like them, with independent units (pass one per
    text, `aggregate_by_group`). `coverage` is the share of these units the threshold
    covers: in-sample, so `coverage_at_risk_crossfit` is the out-of-sample estimate of it.

    Returns {target_risk, delta, start_errors, min_covered, threshold, n, covered,
    errors, coverage, risk_upper, reason, first_cut}: `threshold` None and `covered` 0 when
    nothing passes, with `reason` saying why — too few units for the start, or the first
    cut tested already over the bound. In the second case `first_cut` is that cut as data,
    {units, errors, risk_upper} (the exact bound `reason` rounds), so a reader need not
    parse the sentence; it is None when a threshold passes or the walk could not start
    (`n < min_covered`). Raises on a non-finite confidence, mismatched lengths
    or a target outside (0, 1)."""
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    r = _coverage_at_risk(confidences, correct, [], [], target_risk, delta, start_errors,
                          unit="units")
    cal, n = r["calibration"], len(confidences)
    out: dict[str, Any] = {
        "target_risk": target_risk, "delta": delta, "start_errors": start_errors,
        "min_covered": r["min_covered"], "threshold": r["threshold"], "n": n,
        "covered": cal["covered"], "errors": cal["errors"],
        "coverage": round(cal["covered"] / n, 4) if n else 0.0,
        "risk_upper": (risk_upper_bound(cal["errors"], cal["covered"], delta)
                       if cal["covered"] else None),
        "reason": None, "first_cut": None,
    }
    if r["threshold"] is None:
        if n < r["min_covered"]:
            out["reason"] = (f"needs {r['min_covered']} units with a confidence to bound the "
                             f"error at {target_risk * 100:g}%; has {n}")
        else:
            rows = errs = 0
            for _, m, e in _groups_desc(confidences, correct):
                rows, errs = rows + m, errs + e
                if rows >= r["min_covered"]:
                    break
            bound = risk_upper_bound(errs, rows, delta)
            out["first_cut"] = {"units": rows, "errors": errs, "risk_upper": bound}
            out["reason"] = (f"no threshold passes: the first cut tested holds {rows} units "
                             f"with {errs} errors (bound {bound:.1%} > {target_risk * 100:g}%)")
    return out


def _coverage_at_risk(cal_confidences: Sequence[float], cal_correct: Sequence[bool],
                      test_confidences: Sequence[float], test_correct: Sequence[bool],
                      target_risk: float, delta: float, start_errors: int,
                      unit: str) -> dict:
    """`coverage_at_risk`, with the unit its `reason` counts in ("rows", or "texts" when
    the cross-fit has reduced each half to one unit per text)."""
    _check_count("start_errors", start_errors)
    n_min = min_rows_to_certify(target_risk, delta, errors=start_errors)
    _require_finite(cal_confidences)
    _require_finite(test_confidences)
    if len(cal_confidences) != len(cal_correct) or len(test_confidences) != len(test_correct):
        raise ValueError("each split needs one outcome per confidence")

    threshold: float | None = None
    cal_covered = cal_errors = 0
    cal_upper: float | None = None
    rows = errors = 0
    for c, m, e in _groups_desc(cal_confidences, cal_correct):
        rows, errors = rows + m, errors + e
        if rows < n_min:
            continue                      # before the pre-registered start: not tested
        upper = risk_upper_bound(errors, rows, delta)
        if upper > target_risk:
            break
        threshold, cal_covered, cal_errors, cal_upper = c, rows, errors, upper

    covered = [ok for c, ok in zip(test_confidences, test_correct, strict=True)
               if threshold is not None and c >= threshold]
    t_covered, t_errors = len(covered), sum(1 for ok in covered if not ok)
    n_cal, n_test = len(cal_confidences), len(test_confidences)
    result: dict[str, Any] = {
        "target_risk": target_risk, "delta": delta, "min_covered": n_min,
        "threshold": threshold,
        "calibration": {"n": n_cal, "covered": cal_covered, "errors": cal_errors,
                        "coverage": round(cal_covered / n_cal, 4) if n_cal else None,
                        "risk_upper": round(cal_upper, 4) if cal_upper is not None else None},
        "test": {"n": n_test, "covered": t_covered, "errors": t_errors,
                 "coverage": round(t_covered / n_test, 4) if n_test else None,
                 "risk": round(t_errors / t_covered, 4) if t_covered else None,
                 "risk_upper": (round(risk_upper_bound(t_errors, t_covered, delta), 4)
                                if t_covered else None)},
    }
    if start_errors:                      # only a non-default start adds keys (#98 unchanged)
        result["start_errors"] = start_errors
        if n_min > n_cal:
            result["reason"] = (
                f"the sequence starts at the first cut holding {n_min} {unit} (the {unit} "
                f"that certify {_pct(target_risk)} with {start_errors} errors); the "
                f"calibration split holds {n_cal} {unit}, so nothing can be certified")
    return result


def _pct(x: float) -> str:
    return f"{round(x * 100, 4):g} %"


def _key_order(key: Hashable) -> tuple[str, str]:
    return type(key).__name__, repr(key)


def split_by_group(groups: Sequence[Hashable], seed: int = 0) -> tuple[list[int], list[int]]:
    """Two halves of the row indices, whole groups on one side: the distinct keys are put in
    a fixed order (sorted), shuffled with `random.Random(seed)`, and the first half of them
    (rounded up) goes to fold A. The partition depends on the keys and the seed, never on
    the order of the rows."""
    keys: list[Hashable] = sorted(set(groups), key=_key_order)
    random.Random(seed).shuffle(keys)
    fold_a = set(keys[:(len(keys) + 1) // 2])
    a = [i for i, g in enumerate(groups) if g in fold_a]
    b = [i for i, g in enumerate(groups) if g not in fold_a]
    return a, b


def aggregate_by_group(confidences: Sequence[float], correct: Sequence[bool],
                       groups: Sequence[Hashable]) -> tuple[list[float], list[bool]]:
    """One unit per distinct group (text): its lowest confidence, and whether every one of
    its rows is right. A text is then above a threshold only when all of its rows are, and
    wrong when any of them is — the conservative reading that makes texts, not rows, the
    independent draws `risk_upper_bound` assumes. Units come out in a fixed (sorted-key)
    order, so the result does not depend on row order."""
    if not len(confidences) == len(correct) == len(groups):
        raise ValueError("one confidence, one outcome and one group key per row")
    lowest: dict[Hashable, float] = {}
    all_right: dict[Hashable, bool] = {}
    for c, ok, g in zip(confidences, correct, groups, strict=True):
        lowest[g] = min(c, lowest.get(g, c))
        all_right[g] = all_right.get(g, True) and bool(ok)
    keys = sorted(lowest, key=_key_order)
    return [lowest[k] for k in keys], [all_right[k] for k in keys]


def coverage_at_risk_crossfit(confidences: Sequence[float], correct: Sequence[bool],
                              target_risk: float, delta: float = 0.05,
                              groups: Sequence[Hashable] | None = None,
                              seed: int = 0, start_errors: int = 0) -> dict:
    """`coverage_at_risk` both ways over two halves of one dataset, split by distinct text.

    The rows are split in two by `split_by_group` (every row of a text on the same side;
    without `groups` each row is its own group). With `groups`, each half is reduced to one
    unit per text (`aggregate_by_group`) before testing, so a text that repeats counts
    once, and coverage and risk are shares of texts (`unit: "text"`); without it they are
    shares of rows. Fold A chooses a threshold that fold B checks, then the roles swap.
    `pooled` adds the two test halves together: every unit is judged once, against a
    threshold it did not help choose. The two thresholds can differ; both are reported.
    The split depends on `seed`: pre-register it, or report the spread over seeds.
    `start_errors` is passed to both folds (see `coverage_at_risk`); when it is not 0 the
    result carries it, and a `reason` when either calibration half is smaller than the
    start, so a pooled coverage of 0 is never left unexplained.
    """
    if len(confidences) != len(correct):
        raise ValueError(f"{len(confidences)} confidences for {len(correct)} outcomes")
    keys: Sequence[Hashable] = groups if groups is not None else list(range(len(confidences)))
    if len(keys) != len(confidences):
        raise ValueError(f"{len(keys)} group keys for {len(confidences)} rows")
    a, b = split_by_group(keys, seed)

    def part(idx: list[int]) -> tuple[list[float], list[bool]]:
        conf, ok = [confidences[i] for i in idx], [correct[i] for i in idx]
        if groups is None:
            return conf, ok
        return aggregate_by_group(conf, ok, [groups[i] for i in idx])

    folds = [_coverage_at_risk(*part(cal), *part(test), target_risk, delta, start_errors,
                               unit="rows" if groups is None else "texts")
             for cal, test in ((a, b), (b, a))]
    covered = sum(f["test"]["covered"] for f in folds)
    errs = sum(f["test"]["errors"] for f in folds)
    n = sum(f["test"]["n"] for f in folds)
    result = {
        "target_risk": target_risk, "delta": delta, "seed": seed,
        "unit": "row" if groups is None else "text",
        "folds": folds,
        "pooled": {"n": n, "covered": covered, "errors": errs,
                   "coverage": round(covered / n, 4) if n else None,
                   "risk": round(errs / covered, 4) if covered else None},
    }
    if start_errors:
        result["start_errors"] = start_errors
        reasons = [f"calibrated on half {name}: {f['reason']}"
                   for name, f in zip("AB", folds, strict=True) if "reason" in f]
        if reasons:
            result["reason"] = "; ".join(reasons)
    return result


# --- uncertainty on statistics that can be undefined, and paired comparisons -----------


class BootstrapResult(NamedTuple):
    """A percentile interval and how many resamples left the statistic undefined.

    AUROC has no value on a resample without a wrong answer; such resamples are left out
    of the percentiles and counted here, so a report can say how many there were instead
    of hiding them."""

    ci: Interval | None
    undefined: int


def bootstrap_defined(values: Sequence[T], statistic: Callable[[list[T]], float | None],
                      n_boot: int = N_BOOT, seed: int = 0,
                      groups: Sequence[Hashable] | None = None) -> BootstrapResult:
    """`calibration.bootstrap_ci` for a statistic that may be undefined (None).

    Same resampling unit, seed and draws as `bootstrap_ci`, so resample i is the same set of
    texts for every metric; the percentiles are taken over the resamples where the
    statistic is defined. No rows, or no defined resample → `ci` None."""
    stats, undefined = _resampled(values, statistic, n_boot, seed, groups)
    return BootstrapResult(_percentile_interval(stats), undefined)


def _resampled(values: Sequence[T], statistic: Callable[[list[T]], float | None],
               n_boot: int, seed: int, groups: Sequence[Hashable] | None
               ) -> tuple[list[float], int]:
    """The statistic on each resample where it is defined, in draw order, and how many
    resamples left it undefined. The one resampling loop every interval and test here
    shares: `random.Random(seed)`, texts (or rows) drawn with replacement in
    first-appearance order."""
    n = len(values)
    if n == 0:
        return [], 0
    if groups is None:
        units: list[list[T]] = [[v] for v in values]
    else:
        if len(groups) != n:
            raise ValueError(f"{len(groups)} group keys for {n} rows")
        by_key: dict[Hashable, list[T]] = {}
        for key, v in zip(groups, values, strict=True):
            by_key.setdefault(key, []).append(v)
        units = list(by_key.values())
    rng = random.Random(seed)
    idx = range(len(units))
    stats: list[float] = []
    undefined = 0
    for _ in range(n_boot):
        s = statistic([v for i in rng.choices(idx, k=len(units)) for v in units[i]])
        if s is None:
            undefined += 1
        else:
            stats.append(s)
    return stats, undefined


def _percentile_interval(stats: list[float]) -> Interval | None:
    if not stats:
        return None
    ordered = sorted(stats)
    tail = (1 - CI_LEVEL) / 2
    return Interval(interpolated_quantile(ordered, tail),
                    interpolated_quantile(ordered, 1 - tail), BOOTSTRAP)


def failure_auroc_ci(confidences: Sequence[float], correct: Sequence[bool],
                     n_boot: int = N_BOOT, seed: int = 0,
                     groups: Sequence[Hashable] | None = None) -> BootstrapResult:
    """95 % interval of `failure_auroc`: the clustered bootstrap of the other metrics, with
    the resamples that hold no wrong (or no right) answer counted as undefined."""
    rows = list(zip(confidences, correct, strict=True))
    return bootstrap_defined(rows, lambda rs: failure_auroc([c for c, _ in rs],
                                                            [ok for _, ok in rs]),
                             n_boot, seed, groups)


def aurc_ci(confidences: Sequence[float], correct: Sequence[bool],
            n_boot: int = N_BOOT, seed: int = 0,
            groups: Sequence[Hashable] | None = None) -> BootstrapResult:
    """95 % interval of `aurc`, same bootstrap (never undefined on a non-empty resample)."""
    rows = list(zip(confidences, correct, strict=True))
    return bootstrap_defined(rows, lambda rs: aurc([c for c, _ in rs], [ok for _, ok in rs]),
                             n_boot, seed, groups)


def paired_difference_ci(values_a: Sequence[T], values_b: Sequence[T],
                         statistic: Callable[[list[T]], float | None],
                         n_boot: int = N_BOOT, seed: int = 0,
                         groups: Sequence[Hashable] | None = None) -> BootstrapResult:
    """95 % interval of statistic(A) − statistic(B), two judges on the same rows.

    `values_a[i]` and `values_b[i]` are the two judges' entries for row i (a bool for
    accuracy, a (confidence, correct) pair for a calibration or ranking metric). Each
    resample draws texts once and scores **both** judges on it, so what the two share —
    the same easy and hard rows — cancels out of the difference. That is why a paired
    interval is narrower than two separate intervals, and why two separate intervals that
    overlap do not show that the judges are indistinguishable (Schenker & Gentleman, The
    American Statistician 2001). An interval that excludes 0 separates them on this data.
    A resample where either statistic is undefined is counted, not used."""
    pairs, diff = _paired(values_a, values_b, statistic)
    return bootstrap_defined(pairs, diff, n_boot, seed, groups)


def _paired(values_a: Sequence[T], values_b: Sequence[T],
            statistic: Callable[[list[T]], float | None]
            ) -> tuple[list[tuple[T, T]], Callable[[list[tuple[T, T]]], float | None]]:
    if len(values_a) != len(values_b):
        raise ValueError(f"{len(values_a)} rows for judge A, {len(values_b)} for judge B")
    pairs = list(zip(values_a, values_b, strict=True))

    def diff(rs: list[tuple[T, T]]) -> float | None:
        sa = statistic([a for a, _ in rs])
        sb = statistic([b for _, b in rs])
        return None if sa is None or sb is None else sa - sb

    return pairs, diff


def percentile_p_value(differences: Sequence[float]) -> float | None:
    """Two-sided percentile p-value of "no difference" from bootstrap differences Δ*:
    min(1, 2 × min(1 + #{Δ* ≤ 0}, 1 + #{Δ* ≥ 0}) / (B + 1)), B = len(differences).

    The +1s count the observed data as one of the resamples (Davison & Hinkley, Bootstrap
    Methods and Their Application, 1997, ch. 4), so the smallest p it can give is
    2 / (B + 1), never 0; a Δ* of exactly 0 counts on both sides. Up to that +1 and the
    interpolation between resamples, the p-value is below α when the equal-tailed
    percentile interval at level 1 − α excludes 0: the same evidence as
    `paired_difference_ci`, read at a level a multiple-testing correction chooses.
    No differences → None."""
    if not differences:
        return None
    b = len(differences)
    below = sum(1 for d in differences if d <= 0)
    above = sum(1 for d in differences if d >= 0)
    return min(1.0, 2 * min(1 + below, 1 + above) / (b + 1))


class PairedTest(NamedTuple):
    """`paired_difference_ci`'s interval and the percentile p-value from the same resamples.

    `difference` is statistic(A) − statistic(B) on all the rows (None when either is
    undefined there); `n_defined` is B, the resamples where both statistics are defined, on
    which the interval and the p-value are computed; `undefined` counts the others."""

    difference: float | None
    ci: Interval | None
    p_value: float | None
    n_defined: int
    undefined: int


def paired_difference_test(values_a: Sequence[T], values_b: Sequence[T],
                           statistic: Callable[[list[T]], float | None],
                           n_boot: int = N_BOOT, seed: int = 0,
                           groups: Sequence[Hashable] | None = None) -> PairedTest:
    """A two-sided test of statistic(A) = statistic(B), two methods on the same rows.

    The resamples are exactly those `paired_difference_ci` draws with the same arguments
    (same seed, same clustering by `groups`): each resample draws texts once and scores both
    methods on it; the interval returned is that function's. The p-value is
    `percentile_p_value` over the B resamples where both statistics are defined; the
    resamples where either is undefined are counted in `undefined`, not used. Deterministic
    for a given seed and row order. For AUROC, pass (confidence, correct) pairs and a
    statistic that scores each method on its own correctness (docs/v05-plan.md § 6)."""
    pairs, diff = _paired(values_a, values_b, statistic)
    stats, undefined = _resampled(pairs, diff, n_boot, seed, groups)
    return PairedTest(diff(pairs) if pairs else None, _percentile_interval(stats),
                      percentile_p_value(stats), len(stats), undefined)


def holm(p_values: Mapping[str, float], alpha: float = 0.05) -> dict[str, dict]:
    """Holm's step-down adjustment (Scandinavian Journal of Statistics 1979) of a family of
    tests: the family-wise error rate stays at most `alpha` under any dependence between
    the tests, as far as the p-values are accurate (bootstrap p-values are approximate).

    Sort the m p-values ascending; the i-th smallest (i = 1 … m) is multiplied by
    m − i + 1, each adjusted p is raised to the largest adjusted p before it (so it never
    falls down the order) and capped at 1. A test is `resolved` when its adjusted p is
    below `alpha` — the rule of docs/v05-plan.md § 6, which also requires the difference to
    have the predicted sign; that check is the caller's. Tied p-values get the same
    adjusted p whatever their order. The result keeps the order of `p_values`:
    {name: {"p", "p_adjusted", "resolved"}}. A missing (None), non-finite or out-of-range
    p-value is refused: a test that was not run is left out of the family by the caller,
    and saying so is the report's job."""
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    for name, p in p_values.items():
        if not isinstance(p, (int, float)) or isinstance(p, bool) or not 0 <= p <= 1:
            raise ValueError(f"p-value of {name!r} must be a number in [0, 1], got {p!r}")
    m = len(p_values)
    adjusted: dict[str, float] = {}
    running = 0.0
    for i, (name, p) in enumerate(sorted(p_values.items(), key=lambda kv: kv[1])):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[name] = running
    return {name: {"p": p, "p_adjusted": adjusted[name], "resolved": adjusted[name] < alpha}
            for name, p in p_values.items()}


def mcnemar_exact(correct_a: Sequence[bool], correct_b: Sequence[bool]) -> dict:
    """Exact McNemar test of equal accuracy for two judges on the same rows.

    Only the discordant rows carry information: `a_only` rows where A is right and B wrong,
    `b_only` the reverse. Under equal accuracy each discordant row is a fair coin, so the
    two-sided p-value is min(1, 2·P(X ≤ min(a_only, b_only))) for X ~ Binomial(a_only +
    b_only, ½), computed exactly with integers. It treats rows as independent; on a dataset
    that repeats texts, read it next to the clustered `paired_difference_ci`."""
    if len(correct_a) != len(correct_b):
        raise ValueError(f"{len(correct_a)} rows for judge A, {len(correct_b)} for judge B")
    a_only = sum(1 for x, y in zip(correct_a, correct_b, strict=True) if x and not y)
    b_only = sum(1 for x, y in zip(correct_a, correct_b, strict=True) if y and not x)
    n = a_only + b_only
    if n == 0:
        return {"a_only": 0, "b_only": 0, "p_value": 1.0}
    tail = sum(math.comb(n, i) for i in range(min(a_only, b_only) + 1))
    return {"a_only": a_only, "b_only": b_only, "p_value": min(1.0, 2 * tail / 2 ** n)}
