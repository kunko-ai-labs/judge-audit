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
    assert cert["unit"] == "decision" and cert["delta"] == 0.05 and cert["start_errors"] == 2
    (q,) = cert["questions"]
    assert q["question"] == "intent" and q["n"] == 200 and q["scored"] == 200
    assert [t["target_risk"] for t in q["targets"]] == list(DEFAULT_TARGETS)
    by = {t["target_risk"]: t for t in q["targets"]}
    assert by[0.05]["plain"] == "at most 1 in 20 automated decisions wrong"
    assert by[0.05]["coverage"] == 1.0 and by[0.01]["coverage"] == 0.0
    assert "628" in by[0.01]["reason"]
    json.dumps(cert)                                  # the result JSON can carry it


def test_repeats_are_decisions_and_the_per_text_check_counts_each_text_once():
    """Text t0 twice (0.99 right, 0.98 wrong) plus 198 single texts, all right: two hundred
    decisions with one error; per text, 199 texts with t0 wrong (any copy wrong)."""
    recs = [rec(0, 0.99, True), rec(1, 0.98, False)] + [
        rec(i + 2, c, True) for i, c in enumerate(desc(198))]
    groups = ["t0", "t0"] + [f"t{i + 1}" for i in range(198)]
    q = automation_certificate(recs, groups)["questions"][0]
    assert (q["n"], q["scored"], q["texts"]) == (200, 200, 199)
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert (t10["automated"], t10["errors"]) == (200, 1)
    assert t10["per_text"]["n"] == 199 and t10["per_text"]["errors"] == 1
    no_repeat = automation_certificate(recs[1:], groups[1:])["questions"][0]["targets"][3]
    assert "per_text" not in no_repeat


def test_a_text_repeated_and_always_wrong_counts_every_time():
    """The reviewer's case: one text copied 10 times, always wrong, among 190 right
    decisions: 10 errors among 200 decisions (5 %), never 1 among 191 texts."""
    recs = [rec(i, 0.9, False) for i in range(10)] + [
        rec(10 + i, 0.9, True) for i in range(190)]
    groups = ["same"] * 10 + [f"t{i}" for i in range(190)]
    q = automation_certificate(recs, groups)["questions"][0]
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert (t10["automated"], t10["errors"]) == (200, 10)
    assert t10["risk_upper"] == pytest.approx(risk_upper_bound(10, 200), abs=1e-6)


def test_the_per_text_check_keeps_the_highest_copy_and_any_error():
    """Three texts with copies at 0.5 (wrong) and 0.05 (right), below 300 right single
    texts: per text each unit sits at its highest copy, 0.5, and is wrong."""
    recs = [rec(i, 0.99 - i / 1000, True) for i in range(300)]
    groups = [f"s{i}" for i in range(300)]
    for k in range(3):
        recs += [rec(300 + 2 * k, 0.5, False), rec(301 + 2 * k, 0.05, True)]
        groups += [f"d{k}", f"d{k}"]
    q = automation_certificate(recs, groups)["questions"][0]
    pt = next(t for t in q["targets"] if t["target_risk"] == 0.10)["per_text"]
    assert (pt["n"], pt["threshold"], pt["errors"], pt["automated"]) == (303, 0.5, 3, 303)


def test_the_out_of_sample_split_does_not_depend_on_row_order():
    conf, ok = desc(400), [True] * 380 + [False] * 20
    recs = [rec(i, c, o) for i, (c, o) in enumerate(zip(conf, ok, strict=True))]
    groups = [f"t{i}" for i in range(400)]
    a = automation_certificate(recs, groups)["questions"][0]["targets"][3]["out_of_sample"]
    b = automation_certificate(recs[::-1], groups[::-1])["questions"][0]["targets"][3][
        "out_of_sample"]
    assert a == b and a["spread_seeds"] == [0, 9]
    assert a["spread_coverage"][0] <= a["coverage"] <= a["spread_coverage"][1]


def test_a_decision_without_confidence_is_never_automated_but_counts():
    recs = [rec(i, c, True) for i, c in enumerate(desc(150))] + [
        rec(150 + i, None, True) for i in range(50)]
    q = automation_certificate(recs, [f"t{i}" for i in range(200)])["questions"][0]
    assert q["n"] == 200 and q["scored"] == 150
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert t10["automated"] == 150 and t10["coverage"] == pytest.approx(0.75)


def test_a_copy_without_confidence_is_one_decision_never_automated():
    recs = [rec(0, 0.99, True), rec(1, None, True)] + [
        rec(i + 2, c, True) for i, c in enumerate(desc(198))]
    groups = ["t0", "t0"] + [f"t{i + 1}" for i in range(198)]
    q = automation_certificate(recs, groups)["questions"][0]
    assert q["n"] == 200 and q["scored"] == 199
    t10 = next(t for t in q["targets"] if t["target_risk"] == 0.10)
    assert t10["automated"] == 199 and t10["coverage"] == pytest.approx(199 / 200)


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
    q = cert["questions"][0]
    assert cert["unit"] == "decision" and q["n"] == q["texts"] == 200


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


# --- primary target, scope, segments -----------------------------------------------------


def test_the_primary_target_is_marked_and_must_be_a_target():
    recs = [rec(i, c, True) for i, c in enumerate(desc(200))]
    cert = automation_certificate(recs, None, primary=0.10)
    assert cert["primary_target"] == 0.10 and cert["name"] == "safe automation rate"
    assert [t["primary"] for t in cert["questions"][0]["targets"]] == [False, False, False,
                                                                       True]
    with pytest.raises(ValueError):
        automation_certificate(recs, None, primary=0.2)


def test_the_scope_names_what_the_rate_is_valid_for_and_a_review_date():
    run = {"timestamp_utc": "2026-10-01T08:13:42+00:00",
           "judge": {"name": "llm:m", "model": "m", "prompt_sha256": "ab" * 32},
           "dataset": {"path": "x.jsonl", "sha256_rows": "cd" * 32},
           "served": {"versions": [{"model": "m-2026", "system_fingerprint": "fp1"}]}}
    cert = automation_certificate([rec(0, 0.9, True)], None, run=run)
    sc = cert["scope"]
    assert sc["judge"] == "llm:m" and sc["prompt_sha256"] == "ab" * 32
    assert sc["dataset_sha256"] == "cd" * 32 and sc["served"] == ["m-2026 (fp1)"]
    assert sc["measured_utc"] == "2026-10-01T08:13:42+00:00"
    assert sc["review_by"] == "2026-12-30"                      # 90 days later
    assert "not a conformity assessment" in cert["disclaimer"]
    assert automation_certificate([rec(0, 0.9, True)], None)["scope"]["review_by"] is None


def test_scope_changes_name_only_what_both_declare_and_differs():
    from judge_audit.certificate import scope_changes
    old = {"judge": "j", "prompt_sha256": "a", "model": None, "dataset_sha256": "d"}
    new = {"judge": "j", "prompt_sha256": "b", "model": "m", "dataset_sha256": "d"}
    assert scope_changes(old, new) == ["prompt_sha256: 'a' → 'b'"]


def _segmented(n=600):
    """600 decisions, labels a/b/c in turn; in the less confident half, every tenth text of
    label b is wrong (10 errors, all in b)."""
    recs = []
    for i, c in enumerate(desc(n)):
        label = "abc"[i % 3]
        wrong = label == "b" and i >= n // 2 and (i // 3) % 10 == 0
        recs.append({**rec(i, c, not wrong), "segment": label})
    return recs


def test_the_worst_segment_above_the_threshold_is_named():
    recs = _segmented()
    assert sum(not r["correct"] for r in recs) == 10
    cert = automation_certificate(recs, None, segment_by="label")
    t10 = next(t for t in cert["questions"][0]["targets"] if t["target_risk"] == 0.10)
    assert t10["threshold"] is not None and cert["segment_by"] == "label"
    w = t10["worst_segment"]
    by = {s["segment"]: s for s in t10["segments"]}
    assert w["segment"] == "b" and w["errors"] == by["b"]["errors"] == 10
    assert w["rate"] == pytest.approx(10 / w["automated"], abs=1e-4)
    assert w["risk_upper"] == pytest.approx(risk_upper_bound(10, w["automated"]), abs=1e-6)
    assert by["a"]["errors"] == by["c"]["errors"] == 0
    assert sum(s["automated"] for s in t10["segments"]) == t10["automated"]


def test_a_segment_below_the_minimum_is_counted_not_ranked():
    recs = _segmented()
    recs[0] = {**recs[0], "segment": "rare"}                    # one decision, one segment
    t10 = next(t for t in automation_certificate(recs, None)["questions"][0]["targets"]
               if t["target_risk"] == 0.10)
    assert t10["segments_too_small"] == 1 and t10["worst_segment"]["segment"] == "b"


def test_no_segments_without_a_threshold_or_a_segment_key():
    recs = [rec(i, c, True) for i, c in enumerate(desc(200))]
    cert = automation_certificate(recs, None)
    assert cert["segment_by"] is None
    assert all(t["segments"] == [] and t["worst_segment"] is None
               for t in cert["questions"][0]["targets"])


# --- the surfaces: report, HTML, CLI gate, PR comment, Action ----------------------------

import importlib.util  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

from judge_audit.report import (  # noqa: E402
    check_safe_rate,
    parse_min_safe_rate,
    render_html,
    render_markdown,
)
from judge_audit.runner import summarize  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RUN = {"timestamp_utc": "2026-10-01T08:13:42+00:00",
       "judge": {"name": "demo", "model": "demo-1", "prompt_sha256": "ab" * 32},
       "dataset": {"path": "x.jsonl", "sha256_rows": "cd" * 32}}


def _result(n=200, wrong_from=180, question="intent", run=None):
    recs = [{"idx": i, "question": question, "confidence": 1 - i / (2 * n),
             "correct": i < wrong_from, "latency_s": 0.1, "cost_usd": 0.0,
             "expected": "abcd"[i % 4], "meta": {"lang": "en" if i % 2 else "de"}}
            for i in range(n)]
    return summarize("demo", recs, run or RUN, groups=[f"t{i}" for i in range(n)], ci=False)


def test_the_report_opens_with_the_rate_its_scope_and_its_conditions():
    md = render_markdown(_result())
    section = md[md.index("## Can I automate this?"):md.index("## Accuracy vs coverage")]
    assert section.index("**Safe automation rate at ≤ 5% error: 92.0%**") < section.index(
        "| at most this error |")
    assert "deploying at confidence ≥ 0.5425" in section
    assert ("| 5% (primary) | at most 1 in 20 automated decisions wrong | 92.0% (184 of 200 "
            "decisions") in section
    assert "Worst segment above that threshold (true label): `" in section
    assert "none: needs 628 decisions with a confidence" in section  # never an unexplained 0
    assert "Valid only for: judge `demo` · model `demo-1` · prompt `abababab…`" in section
    assert "Review by 2026-12-30" in section
    assert "not a conformity assessment" in section
    assert "not checkable: a half holds at most 100 decisions" in section
    assert "Label errors cut both ways" in section and "at least 80%" in section
    assert section.index("| 1% |") < section.index("Zero observed errors")


def test_the_html_report_carries_the_same_section_escaped():
    r = _result(question="<script>x</script>")
    r.certificate["questions"].append(dict(r.certificate["questions"][0]))
    page = render_html(r)
    assert "safe automation rate" in page and "<script>x" not in page
    assert "&lt;script&gt;x&lt;/script&gt;" in page and "<b>Safe automation rate" in page


def test_a_result_written_before_the_certificate_still_renders():
    r = _result()
    r.certificate = {}
    md = render_markdown(r)
    assert "## Can I automate this?" in md and "safe automation rate" not in md


@pytest.mark.parametrize("spec", ["0.05", "0.05:", "x:0.4", "0:0.4", "1:0.4", "0.05:1.5",
                                  "nan:0.4"])
def test_a_malformed_minimum_is_refused(spec):
    with pytest.raises(ValueError):
        parse_min_safe_rate(spec)


def test_the_gate_names_the_question_the_rate_and_the_reason():
    cert = _result().certificate
    assert parse_min_safe_rate("0.10:0.96") == (0.10, 0.96)
    assert check_safe_rate(cert, [(0.10, 0.96)]) == []
    (msg,) = check_safe_rate(cert, [(0.10, 0.97)])
    assert "≤ 10% error: 96.0% of `intent`" in msg and "minimum 97.0%" in msg
    (msg,) = check_safe_rate(cert, [(0.01, 0.10)])
    assert "needs 628 decisions" in msg
    with pytest.raises(ValueError):
        check_safe_rate(cert, [(0.2, 0.1)])


def _cli(*args, cwd):
    return subprocess.run([sys.executable, "-m", "judge_audit.cli", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_the_cli_line_and_the_check_gate(labels_path, tmp_path):
    r = _cli("run", str(labels_path), "--judge", "simulated", "--json", "base.json",
             cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "safe_automation@5%=0.0%" in r.stdout
    base = ["check", str(labels_path), "--judge", "simulated", "--baseline", "base.json"]
    ok = _cli(*base, "--min-safe-rate", "0.10:0", "--drift", "d.json", cwd=tmp_path)
    assert ok.returncode == 0, ok.stderr
    drift = json.loads((tmp_path / "d.json").read_text())
    assert drift["min_safe_rate"] == [{"risk": 0.10, "share": 0.0}]
    assert drift["certificate"]["questions"] and drift["baseline_rate_stale"] == []
    bad = _cli(*base, "--min-safe-rate", "0.10:0.5", cwd=tmp_path)
    assert bad.returncode == 1 and "Safe automation rate at ≤ 10% error: 0.0%" in bad.stderr
    extra = _cli(*base, "--min-safe-rate", "0.2:0", "--target", "0.3", "--segment-by",
                 "none", "--json", "r.json", cwd=tmp_path)
    assert extra.returncode == 0, extra.stderr
    res = json.loads((tmp_path / "r.json").read_text())
    assert res["certificate"]["targets"] == [0.01, 0.02, 0.05, 0.1, 0.2, 0.3]
    assert res["certificate"]["primary_target"] == 0.3
    assert res["certificate"]["segment_by"] is None
    for args in (("--min-safe-rate", "five:percent"), ("--target", "1.5"),
                 ("--segment-by", "lang")):
        usage = _cli(*base, *args, cwd=tmp_path)
        assert usage.returncode == 2, args


def test_check_says_when_the_baselines_rate_no_longer_applies(labels_path, tmp_path):
    _cli("run", str(labels_path), "--judge", "simulated", "--json", "base.json", cwd=tmp_path)
    base = json.loads((tmp_path / "base.json").read_text())
    base["certificate"]["scope"].update(judge="old-judge", review_by="2000-01-01")
    (tmp_path / "old.json").write_text(json.dumps(base))
    r = _cli("check", str(labels_path), "--judge", "simulated", "--baseline", "old.json",
             "--drift", "d.json", cwd=tmp_path)
    stale = json.loads((tmp_path / "d.json").read_text())["baseline_rate_stale"]
    assert any("no longer applies (judge: 'old-judge' → 'simulated')" in s for s in stale)
    assert any("due for review by 2000-01-01" in s for s in stale)
    assert "due for review by 2000-01-01" in r.stderr


def _pr_comment():
    spec = importlib.util.spec_from_file_location("pr_comment_cert",
                                                  ROOT / "scripts" / "pr_comment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_pr_comment_opens_with_the_safe_automation_rate():
    res = _result().to_dict()
    md = _pr_comment().build(res)
    assert md.index("### Can I automate this?") < md.index("Judge `")
    assert "**Safe automation rate at ≤ 5% error: 92.0%** of the labelled decisions" in md
    assert ("| 10% | at most 1 in 10 automated decisions wrong | 96.0% (192 of 200 "
            "decisions") in md
    assert "none: needs 628 decisions" in md
    assert "review by 2026-12-30" in md and "not a conformity assessment" in md
    ok = _pr_comment().build(res, {"ok": True, "failures": [], "baseline": "b.json",
                                   "max_ece_drift": 0.02, "max_acc_drop": 0.01,
                                   "min_safe_rate": [{"risk": 0.05, "share": 0.4}],
                                   "baseline_rate_stale": ["prompt changed"]})
    assert "safe automation rate at ≤ 5% error ≥ 40.0%" in ok and "⚠️ prompt changed" in ok


def test_the_pr_comment_escapes_what_the_certificate_quotes():
    res = _result(question="x | **forged** |").to_dict()
    res["certificate"]["questions"].append(res["certificate"]["questions"][0])
    t = res["certificate"]["questions"][0]["targets"][2]
    t["worst_segment"] = {**(t["worst_segment"] or {}), "segment": "![i](http://e/x) |",
                          "errors": 1, "automated": 40, "rate": 0.025, "risk_upper": 0.1}
    md = _pr_comment().build(res)
    assert "**forged**" not in md and "\\*\\*forged\\*\\*" in md
    assert "![i](" not in md
