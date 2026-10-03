"""The automation certificate (US-003-004, #122; docs/automation-certificate-plan.md).

Hand-computable fixtures. Every expected bound below is the exact one-sided Clopper–Pearson
value at δ = 0.05, checked independently of the walk:
  0 errors in 200 → 1.49 %; 1 in 59 → 7.79 %; 1 in 124 → 3.77 %; 1 in 300 → 1.57 %;
  5 in 130 → 7.92 %; 9 in 159 → 9.67 %; 10 in 160 → 10.37 %.
Starting cuts: 59 / 124 units certify 5 % with 0 / 2 errors; 61 certify 10 % with 2; 628
certify 1 % with 2.
"""
from __future__ import annotations

import json
import math

import pytest

from judge_audit.certificate import (
    DEFAULT_TARGETS,
    automation_certificate,
    plain_reading,
)
from judge_audit.metrics.selective import certify_threshold, risk_upper_bound


def desc(n: int) -> list[float]:
    """n distinct confidences, highest first."""
    return [1.0 - i / (2 * n) for i in range(n)]


# --- certify_threshold: the deploy threshold on all labelled units ------------------------


def test_a_perfect_judge_certifies_everything_it_has_enough_units_for():
    conf = desc(200)
    r = certify_threshold(conf, [True] * 200, 0.05, start_errors=2)
    assert r["threshold"] == conf[-1] and r["covered"] == 200 and r["errors"] == 0
    assert r["coverage"] == 1.0
    assert r["risk_upper"] == pytest.approx(risk_upper_bound(0, 200))
    assert r["min_covered"] == 124 and r.get("reason") is None


def test_too_few_units_say_how_many_the_target_needs():
    r = certify_threshold(desc(200), [True] * 200, 0.01, start_errors=2)
    assert r["threshold"] is None and r["covered"] == 0 and r["coverage"] == 0.0
    assert r["min_covered"] == 628
    assert "628" in r["reason"] and "200" in r["reason"]


def test_the_start_decides_whether_one_early_error_ends_the_walk():
    """One error in the very top unit: from the zero-error start (59 units) the first cut
    tested already fails (1 in 59 → 7.79 % > 5 %); from the 2-error start (124) it passes
    and the walk continues to the bottom (1 in 300 → 1.57 %)."""
    conf, ok = desc(300), [False] + [True] * 299
    assert certify_threshold(conf, ok, 0.05, start_errors=0)["threshold"] is None
    r = certify_threshold(conf, ok, 0.05, start_errors=2)
    assert (r["threshold"], r["covered"], r["errors"]) == (conf[-1], 300, 1)
    assert r["risk_upper"] == pytest.approx(0.015714554891583965)


def test_the_walk_stops_at_the_first_cut_that_fails():
    """200 units, the 50 least confident wrong, target 10 %: 9 errors in 159 pass (9.67 %),
    10 in 160 fail (10.37 %)."""
    conf, ok = desc(200), [True] * 150 + [False] * 50
    r = certify_threshold(conf, ok, 0.10, start_errors=2)
    assert (r["threshold"], r["covered"], r["errors"]) == (conf[158], 159, 9)
    assert r["coverage"] == pytest.approx(159 / 200)


def test_a_tie_is_one_threshold():
    """130 units at one confidence, 5 wrong: the first cut is the whole tie (5 in 130 →
    7.92 %), never the 124 the start asks for."""
    r = certify_threshold([0.9] * 130, [True] * 125 + [False] * 5, 0.05, start_errors=2)
    assert r["threshold"] is None and r["covered"] == 0
    assert "first cut" in r["reason"] and "130" in r["reason"]


def test_certify_threshold_refuses_what_it_cannot_measure():
    with pytest.raises(ValueError):
        certify_threshold([0.9, math.nan], [True, True], 0.05)
    with pytest.raises(ValueError):
        certify_threshold([0.9], [True, False], 0.05)
    with pytest.raises(ValueError):
        certify_threshold([0.9], [True], 1.5)


# --- automation_certificate: per question, one unit per text, out-of-sample check --------


def rec(i, conf, ok, q="intent"):
    return {"idx": i, "question": q, "confidence": conf, "correct": ok}


def test_the_certificate_has_every_default_target_with_its_plain_reading():
    recs = [rec(i, c, True) for i, c in enumerate(desc(200))]
    cert = automation_certificate(recs, [f"t{i}" for i in range(200)])
    assert cert["unit"] == "text" and cert["delta"] == 0.05 and cert["start_errors"] == 2
    (q,) = cert["questions"]
    assert q["question"] == "intent" and q["n"] == 200 and q["scored"] == 200
    assert [t["target_risk"] for t in q["targets"]] == list(DEFAULT_TARGETS)
    by = {t["target_risk"]: t for t in q["targets"]}
    assert by[0.05]["plain"] == "at most 1 in 20 automated decisions wrong"
    assert by[0.05]["coverage"] == 1.0 and by[0.01]["coverage"] == 0.0
    assert "628" in by[0.01]["reason"]
    json.dumps(cert)                                  # the result JSON can carry it


def test_a_repeated_text_is_one_unit_wrong_if_any_copy_is():
    """Text t0 appears twice (0.99 right, 0.98 wrong): one unit at 0.98, wrong."""
    recs = [rec(0, 0.99, True), rec(1, 0.98, False)] + [
        rec(i + 2, c, True) for i, c in enumerate(desc(198))]
    groups = ["t0", "t0"] + [f"t{i + 1}" for i in range(198)]
    q = automation_certificate(recs, groups)["questions"][0]
    assert q["n"] == 199 and q["scored"] == 199
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert t10["errors"] == 1 and t10["automated"] == 199


def test_a_decision_without_confidence_is_never_automated_but_counts():
    recs = [rec(i, c, True) for i, c in enumerate(desc(150))] + [
        rec(150 + i, None, True) for i in range(50)]
    q = automation_certificate(recs, [f"t{i}" for i in range(200)])["questions"][0]
    assert q["n"] == 200 and q["scored"] == 150
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert t10["automated"] == 150 and t10["coverage"] == pytest.approx(0.75)


def test_a_text_with_one_copy_lacking_confidence_is_not_automated():
    recs = [rec(0, 0.99, True), rec(1, None, True)] + [
        rec(i + 2, c, True) for i, c in enumerate(desc(198))]
    groups = ["t0", "t0"] + [f"t{i + 1}" for i in range(198)]
    q = automation_certificate(recs, groups)["questions"][0]
    assert q["n"] == 199 and q["scored"] == 198


def test_each_question_is_certified_on_its_own():
    recs = []
    for i, c in enumerate(desc(200)):
        recs += [rec(i, c, True, "category"), rec(i, c, i % 2 == 0, "priority")]
    groups = [f"t{r['idx']}" for r in recs]
    cert = automation_certificate(recs, groups)
    by = {q["question"]: q for q in cert["questions"]}
    assert list(by) == ["category", "priority"]
    cat10 = next(t for t in by["category"]["targets"] if t["target_risk"] == 0.10)
    pri10 = next(t for t in by["priority"]["targets"] if t["target_risk"] == 0.10)
    assert cat10["coverage"] == 1.0 and pri10["coverage"] == 0.0


def test_the_out_of_sample_check_is_the_cross_fit_on_the_same_units():
    conf, ok = desc(400), [True] * 380 + [False] * 20
    recs = [rec(i, c, o) for i, (c, o) in enumerate(zip(conf, ok, strict=True))]
    cert = automation_certificate(recs, [f"t{i}" for i in range(400)], seed=7)
    t10 = next(t for t in cert["questions"][0]["targets"] if t["target_risk"] == 0.10)
    oos = t10["out_of_sample"]
    assert cert["seed"] == 7 and oos["n"] == 400
    assert 0 < oos["automated"] <= 400 and oos["errors"] <= oos["automated"]
    assert oos["coverage"] == pytest.approx(oos["automated"] / 400)


def test_without_groups_every_row_is_its_own_unit():
    recs = [rec(i, c, True) for i, c in enumerate(desc(200))]
    cert = automation_certificate(recs, None)
    assert cert["unit"] == "row" and cert["questions"][0]["n"] == 200


def test_custom_targets_and_start_are_recorded():
    recs = [rec(i, c, True) for i, c in enumerate(desc(100))]
    cert = automation_certificate(recs, None, targets=(0.05,), start_errors=0)
    (t,) = cert["questions"][0]["targets"]
    assert cert["start_errors"] == 0 and t["min_units"] == 59 and t["coverage"] == 1.0


def test_no_records_no_certificate():
    assert automation_certificate([], None)["questions"] == []


@pytest.mark.parametrize("r, text", [
    (0.01, "at most 1 in 100 automated decisions wrong"),
    (0.10, "at most 1 in 10 automated decisions wrong"),
    (0.03, "at most 3 % of automated decisions wrong"),
    (0.025, "at most 1 in 40 automated decisions wrong"),
])
def test_plain_reading(r, text):
    assert plain_reading(r) == text


# --- the surfaces: report, HTML, CLI gate, PR comment, Action ----------------------------

import importlib.util  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from judge_audit.report import (  # noqa: E402
    check_coverage,
    parse_min_coverage,
    render_html,
    render_markdown,
)
from judge_audit.runner import summarize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _result(n=200, wrong_from=180, question="intent"):
    recs = [{"idx": i, "question": question, "confidence": 1 - i / (2 * n),
             "correct": i < wrong_from, "latency_s": 0.1, "cost_usd": 0.0}
            for i in range(n)]
    return summarize("demo", recs, groups=[f"t{i}" for i in range(n)], ci=False)


def test_the_report_opens_with_the_certificate_and_its_conditions():
    md = render_markdown(_result())
    section = md[md.index("## Can I automate this?"):md.index("## Accuracy vs coverage")]
    assert md.index("## Can I automate this?") < md.index("## Accuracy vs coverage")
    assert "| 5% | 1 in 20 automated decisions wrong | 92.0% (184 of 200 texts; 4 wrong" in section
    assert "needs 628 texts with a confidence" in section            # never an unexplained 0
    assert "same mix, same judge version" in section and "Each row is its own 95%" in section
    assert "not checkable: a half holds at most 100 texts" in section
    assert section.index("| 1% |") < section.index("Zero observed errors")


def test_the_html_report_carries_the_same_table_escaped():
    r = _result(question="<script>x</script>")
    r.certificate["questions"].append(dict(r.certificate["questions"][0]))
    page = render_html(r)
    assert "automate (certified)" in page and "<script>x" not in page
    assert "&lt;script&gt;x&lt;/script&gt;" in page


def test_a_result_written_before_the_certificate_still_renders():
    r = _result()
    r.certificate = {}
    md = render_markdown(r)
    assert "## Can I automate this?" in md and "automate (certified)" not in md


@pytest.mark.parametrize("spec", ["0.05", "0.05:", "x:0.4", "0:0.4", "1:0.4", "0.05:1.5",
                                  "nan:0.4"])
def test_a_malformed_minimum_is_refused(spec):
    with pytest.raises(ValueError):
        parse_min_coverage(spec)


def test_the_gate_names_the_question_the_share_and_the_reason():
    cert = _result().certificate
    assert parse_min_coverage("0.10:0.96") == (0.10, 0.96)
    assert check_coverage(cert, [(0.10, 0.96)]) == []
    (msg,) = check_coverage(cert, [(0.10, 0.97)])
    assert "at most 10%" in msg and "96.0% of `intent`" in msg and "minimum 97.0%" in msg
    (msg,) = check_coverage(cert, [(0.01, 0.10)])
    assert "needs 628 texts" in msg
    with pytest.raises(ValueError):
        check_coverage(cert, [(0.2, 0.1)])


def _cli(*args, cwd):
    return subprocess.run([sys.executable, "-m", "judge_audit.cli", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_the_cli_line_and_the_check_gate(labels_path, tmp_path):
    r = _cli("run", str(labels_path), "--judge", "simulated", "--json", "base.json",
             cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "certified=1%:0.0%,2%:0.0%,5%:0.0%,10%:0.0%" in r.stdout
    base = ["check", str(labels_path), "--judge", "simulated", "--baseline", "base.json"]
    ok = _cli(*base, "--min-coverage", "0.10:0", "--drift", "d.json", cwd=tmp_path)
    assert ok.returncode == 0, ok.stderr
    drift = json.loads((tmp_path / "d.json").read_text())
    assert drift["min_coverage"] == [{"risk": 0.10, "share": 0.0}]
    assert drift["certificate"]["questions"]
    bad = _cli(*base, "--min-coverage", "0.10:0.5", cwd=tmp_path)
    assert bad.returncode == 1 and "can automate 0.0%" in bad.stderr
    extra = _cli(*base, "--min-coverage", "0.2:0", "--json", "r.json", cwd=tmp_path)
    assert extra.returncode == 0, extra.stderr
    res = json.loads((tmp_path / "r.json").read_text())
    assert res["certificate"]["targets"] == [0.01, 0.02, 0.05, 0.1, 0.2]
    usage = _cli(*base, "--min-coverage", "five:percent", cwd=tmp_path)
    assert usage.returncode == 2 and "RISK:SHARE" in usage.stderr


def _pr_comment():
    spec = importlib.util.spec_from_file_location("pr_comment_cert",
                                                  ROOT / "scripts" / "pr_comment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_pr_comment_opens_with_the_certificate():
    res = _result().to_dict()
    md = _pr_comment().build(res)
    assert md.index("### Can I automate this?") < md.index("Judge `")
    assert "| 10% | 1 in 10 automated decisions wrong | **96.0%** (192 of 200 texts" in md
    assert "not certified: needs 628 texts" in md
    ok = _pr_comment().build(res, {"ok": True, "failures": [], "baseline": "b.json",
                                   "max_ece_drift": 0.02, "max_acc_drop": 0.01,
                                   "min_coverage": [{"risk": 0.05, "share": 0.4}]})
    assert "certified share at ≤ 5% error ≥ 40.0%" in ok


def test_the_pr_comment_escapes_what_the_certificate_quotes():
    res = _result(question="x | **forged** |").to_dict()
    res["certificate"]["questions"].append(res["certificate"]["questions"][0])
    md = _pr_comment().build(res)
    assert "**forged**" not in md and "\\*\\*forged\\*\\*" in md
