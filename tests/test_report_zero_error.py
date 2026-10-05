"""The zero-error sentence never prints a missing threshold as "None"."""
from judge_audit.report import zero_error_sentence, zero_error_tail


def test_an_empty_prefix_says_why_instead_of_none():
    d = {"zero_error_coverage": {"coverage": 0.0, "n": 0, "threshold": None}}
    s = zero_error_sentence(d)
    assert "None" not in s
    assert "the most confident group of decisions already holds an error" in s
    assert "**0.0%**" in s


def test_a_covered_prefix_keeps_its_count_and_threshold():
    d = {"zero_error_coverage": {"coverage": 0.25, "n": 50, "threshold": 0.97}}
    assert zero_error_sentence(d).endswith("(50 decisions, confidence ≥ 0.97).")


def test_unknown_confidence_is_unchanged():
    d = {"zero_error_coverage": {"coverage": None, "n": 0, "threshold": None}}
    assert "unknown" in zero_error_sentence(d)


def test_the_html_uses_the_same_tail():
    assert zero_error_tail({"coverage": 0.0, "n": 0, "threshold": None}) == (
        "(none: the most confident group of decisions already holds an error)")


# --- the HTML report's inline markdown ----------------------------------------------------
import pytest  # noqa: E402

from judge_audit.report import _key_figures, _md_inline  # noqa: E402


def test_markdown_from_the_data_never_becomes_markup():
    assert _md_inline("_judge `<script>x</script>` · **b** · *lower bound*_") == (
        "judge <code>&lt;script&gt;x&lt;/script&gt;</code> · <b>b</b> · <em>lower bound</em>")


@pytest.mark.parametrize("name", ["<img src=x onerror=alert(1)>"])
def test_a_hostile_question_name_is_escaped_in_the_key_figures(name):
    t = {"target_risk": 0.05, "plain": "at most 1 in 20 automated decisions wrong",
         "primary": True, "threshold": None, "reason": "too few", "coverage": 0.0}
    q = {"question": name, "targets": [t]}
    d = {"n": 10, "accuracy": 0.5, "ece": 0.1, "total_cost_usd": None, "p50_latency_s": 0.1,
         "p99_latency_s": 0.2, "certificate": {"unit": "decision", "questions": [q, q]}}
    out = _key_figures(d, "", "")
    assert "<img" not in out and "&lt;img" in out


def test_code_spans_are_verbatim_and_values_cannot_close_them():
    assert _md_inline("model `m'x'**y**&lt;b&gt;` · **bold**") == (
        "model <code>m&#x27;x&#x27;**y**&amp;lt;b&amp;gt;</code> · <b>bold</b>")
    from judge_audit.report import provenance_lines
    line = provenance_lines({"judge": {"name": "j", "model": "m`x`**y**"},
                             "dataset": {"path": "<h>`x`*y*", "rows": 1, "sha256": "ab"}})
    html_lines = [_md_inline(x) for x in line]
    assert "<b>" not in "".join(html_lines) and "<em>" not in "".join(html_lines)
    assert "&lt;h&gt;&#x27;x&#x27;*y*" in "".join(html_lines)


def test_cards_say_interval_only_when_there_is_one():
    d = {"n": 10, "accuracy": 0.5, "ece": None, "total_cost_usd": None, "p50_latency_s": 0.1,
         "p99_latency_s": 0.2, "certificate": {}}
    out = _key_figures(d, "", "")
    assert "interval" not in out and "n = 10" in out


def test_several_decision_types_are_announced_on_the_cover():
    t = {"target_risk": 0.05, "plain": "at most 1 in 20 automated decisions wrong",
         "primary": True, "threshold": None, "reason": "too few", "coverage": 0.0}
    qs = [{"question": f"q{i}", "targets": [t]} for i in range(3)]
    d = {"n": 10, "accuracy": 0.5, "ece": 0.1, "total_cost_usd": None, "p50_latency_s": 0.1,
         "p99_latency_s": 0.2, "certificate": {"unit": "decision", "questions": qs}}
    assert "2 more decision types in section 1" in _key_figures(d, "", "")


def test_the_footer_claims_a_checkpoint_only_for_a_regenerated_report():
    pytest.importorskip("matplotlib")


    from judge_audit.judges.simulated import SimulatedJudge
    from judge_audit.report import render_html
    from judge_audit.runner import load_dataset, run_audit
    rows, meta = load_dataset("examples/email-routing/labels.jsonl")
    res = run_audit(SimulatedJudge(rows), rows, labels_path="examples/email-routing/labels.jsonl",
                    dataset_meta=meta)
    assert "checkpoint named above" not in render_html(res)
    res.regenerated = {"utc": "2026-10-04T10:00:00+00:00", "checkpoint": "c.ckpt.jsonl",
                       "script": "scripts/runs_report.py", "judge_audit_version": "0.5.0"}
    assert "checkpoint named above" in render_html(res)
