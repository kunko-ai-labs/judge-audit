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
