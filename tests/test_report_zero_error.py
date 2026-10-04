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
