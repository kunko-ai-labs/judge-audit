"""The high-confidence error rate (#134): a reading of the coverage–risk curve at fixed
confidence cuts, on inputs whose answer is known by hand."""
from __future__ import annotations

import math

import pytest

from judge_audit.metrics.selective import HIGH_CONFIDENCE_CUTS, high_confidence_error
from judge_audit.report import high_confidence_lines, render_markdown
from judge_audit.runner import summarize


def test_the_cuts_are_the_issue_s_three():
    assert HIGH_CONFIDENCE_CUTS == (0.90, 0.95, 0.99)


def test_counts_errors_at_or_above_each_cut():
    # >= 0.90: 0.99, 0.99, 0.97, 0.95, 0.92, 0.90 -> 6 decisions, 2 wrong (0.95, 0.90)
    # >= 0.95: 0.99, 0.99, 0.97, 0.95 -> 4 decisions, 1 wrong
    # >= 0.99: 0.99, 0.99 -> 2 decisions, 0 wrong
    conf = [0.99, 0.99, 0.97, 0.95, 0.92, 0.90, 0.80, 0.50]
    ok = [True, True, True, False, True, False, False, True]
    levels = high_confidence_error(conf, ok)
    assert [(lv["confidence_at_least"], lv["n"], lv["errors"]) for lv in levels] == [
        (0.90, 6, 2), (0.95, 4, 1), (0.99, 2, 0)]
    assert [lv["error_rate"] for lv in levels] == [pytest.approx(2 / 6, abs=1e-4), 0.25, 0.0]


def test_the_bound_is_the_exact_one_sided_clopper_pearson_upper_bound():
    # 0 errors in n: the bound solves (1 - p)^n = delta, so p = 1 - 0.05^(1/n).
    # 1 error in 10: P(X <= 1 | p) = (1-p)^10 + 10 p (1-p)^9 = 0.05 at p = 0.3941633...
    conf = [0.99] * 3 + [0.95] * 10
    ok = [True] * 3 + [True] * 9 + [False]
    by_cut = {lv["confidence_at_least"]: lv for lv in high_confidence_error(conf, ok)}
    zero = by_cut[0.99]
    assert (zero["n"], zero["errors"]) == (3, 0)
    assert zero["risk_upper"] == pytest.approx(1 - 0.05 ** (1 / 3), abs=1e-6)
    one = by_cut[0.95]
    assert (one["n"], one["errors"]) == (13, 1)
    p = one["risk_upper"]
    assert (1 - p) ** 13 + 13 * p * (1 - p) ** 12 == pytest.approx(0.05, abs=1e-5)


def test_the_published_bound_is_rounded_up_never_down():
    conf, ok = [0.99] * 3, [True] * 3
    exact = 1 - 0.05 ** (1 / 3)                       # 0.6315968501...
    got = high_confidence_error(conf, ok)[-1]["risk_upper"]
    assert got >= exact and got - exact < 1e-6
    assert got == math.ceil(exact * 1e6) / 1e6


def test_a_tie_at_the_cut_is_included_whole():
    conf = [0.95, 0.95, 0.95, 0.94]
    ok = [True, False, True, False]
    lv = {x["confidence_at_least"]: x for x in high_confidence_error(conf, ok)}[0.95]
    assert (lv["n"], lv["errors"]) == (3, 1)


def test_no_decision_at_or_above_a_cut_bounds_nothing():
    lv = high_confidence_error([0.5, 0.6], [True, False])
    assert all(x["n"] == 0 and x["errors"] == 0 for x in lv)
    assert all(x["error_rate"] is None and x["risk_upper"] is None for x in lv)


def test_empty_input_and_all_wrong():
    assert all(x["n"] == 0 for x in high_confidence_error([], []))
    lv = high_confidence_error([0.99, 0.99], [False, False])[-1]
    assert (lv["n"], lv["errors"], lv["error_rate"], lv["risk_upper"]) == (2, 2, 1.0, 1.0)


def test_order_does_not_matter():
    conf = [0.99, 0.91, 0.96, 0.90, 0.97]
    ok = [True, False, True, True, False]
    a = high_confidence_error(conf, ok)
    b = high_confidence_error(conf[::-1], ok[::-1])
    assert a == b


def test_a_non_finite_confidence_is_refused():
    with pytest.raises(ValueError):
        high_confidence_error([float("nan")], [True])


def test_the_result_excludes_and_counts_unknown_confidence():
    records = [
        {"confidence": 0.99, "correct": True, "latency_s": 0.1, "cost_usd": 0.0},
        {"confidence": 0.96, "correct": False, "latency_s": 0.1, "cost_usd": 0.0},
        {"confidence": None, "correct": False, "latency_s": 0.1, "cost_usd": 0.0},
        {"confidence": 1.5, "correct": True, "latency_s": 0.1, "cost_usd": 0.0},
    ]
    d = summarize("x", records, ci=False).to_dict()
    hc = d["high_confidence_error"]
    assert hc["unknown_confidence"] == 2           # None and the out-of-range 1.5
    assert hc["delta"] == 0.05
    assert [(x["confidence_at_least"], x["n"], x["errors"]) for x in hc["levels"]] == [
        (0.90, 2, 1), (0.95, 2, 1), (0.99, 1, 0)]


def test_no_known_confidence_has_empty_counts_not_zero_error():
    records = [{"confidence": None, "correct": False, "cost_usd": 0.0}]
    hc = summarize("x", records, ci=False).to_dict()["high_confidence_error"]
    assert hc["unknown_confidence"] == 1
    assert all(x["n"] == 0 and x["error_rate"] is None for x in hc["levels"])


def test_the_existing_fields_are_unchanged():
    records = [{"confidence": c, "correct": ok, "latency_s": 0.1, "cost_usd": 0.0}
               for c, ok in [(0.99, True), (0.95, False), (0.7, True)]]
    d = summarize("x", records, ci=False).to_dict()
    without = {k: v for k, v in d.items() if k != "high_confidence_error"}
    assert "high_confidence_error" in d
    assert without["zero_error_coverage"] == {"coverage": 0.3333, "n": 1, "threshold": 0.99}


def test_the_report_reads_it_as_the_curve_not_a_score():
    records = [{"confidence": c, "correct": ok, "latency_s": 0.1, "cost_usd": 0.0}
               for c, ok in [(0.99, True), (0.96, False), (0.92, True), (None, False)]]
    res = summarize("x", records, ci=False)
    lines = high_confidence_lines(res.to_dict())
    text = "\n".join(lines)
    assert "coverage" in text and "not a new score" in text
    assert "| ≥ 0.90 | 3 | 1 | 33.3% |" in text
    assert "| ≥ 0.99 | 1 | 0 | 0.0% |" in text
    assert "1 decision without a known confidence" in text
    assert "When it says" in render_markdown(res)


def test_a_cut_with_no_decision_prints_a_dash():
    res = summarize("x", [{"confidence": 0.5, "correct": True, "cost_usd": 0.0}], ci=False)
    assert "| ≥ 0.99 | 0 | 0 | — | — |" in "\n".join(high_confidence_lines(res.to_dict()))


def test_a_result_written_before_the_field_renders_without_it():
    assert high_confidence_lines({"n": 1}) == []


def test_the_html_report_carries_the_same_table():
    pytest.importorskip("matplotlib")
    from judge_audit.report import render_html
    records = [{"confidence": c, "correct": ok, "latency_s": 0.1, "cost_usd": 0.0}
               for c, ok in [(0.99, True), (0.96, False), (0.92, True)]]
    page = render_html(summarize("x", records, ci=False))
    assert "how often is it wrong?</h2>" in page
    assert "<td>≥ 0.95</td><td>2</td><td>1</td><td>50.0%</td>" in page


def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space."""
    return math.fsum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                              + i * math.log(p) + (n - i) * math.log1p(-p))
                     for i in range(k + 1))


def _cp_upper(k: int, n: int, delta: float = 0.05) -> float:
    """Exact one-sided Clopper–Pearson upper bound by bisection: the p at which
    P(X <= k) = delta. Independent of the library's beta quantile."""
    lo, hi = k / n, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _binom_cdf(k, n, mid) > delta:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def test_a_published_row_matches_an_independent_bound():
    # docs/runs/arena/claude-sonnet-4.5/email-adversarial.json, confidence >= 0.90:
    # 187 decisions, 5 wrong; the published bound is the exact one rounded up to 6 decimals.
    import json
    from pathlib import Path
    path = (Path(__file__).resolve().parent.parent
            / "docs/runs/arena/claude-sonnet-4.5/email-adversarial.json")
    row = json.loads(path.read_text(encoding="utf-8"))["high_confidence_error"]["levels"][0]
    assert (row["confidence_at_least"], row["n"], row["errors"]) == (0.90, 187, 5)
    exact = _cp_upper(5, 187)
    assert row["risk_upper"] == math.ceil(exact * 1e6 - 1e-9) / 1e6
    assert row["error_rate"] == round(5 / 187, 4)
