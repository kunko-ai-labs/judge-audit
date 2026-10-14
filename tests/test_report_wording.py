"""#185: every surface leads with the validated share (held out, bounded, with its range over
split seeds); a share without a bound appears only under "Observed on all rows, no bound —
not a basis for deployment"; no result claim says "at most", "guaranteed", "certified" or
"compliant". Wording and order only: the numbers are the certificate's own."""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit.certificate import _up, automation_certificate, plain_reading
from judge_audit.metrics.selective import risk_upper_bound
from judge_audit.report import (
    _key_figures,
    certificate_html,
    certificate_summary,
    check_safe_rate,
    render_markdown,
)
from judge_audit.runner import summarize

ROOT = Path(__file__).resolve().parent.parent
RUN = {"timestamp_utc": "2026-10-01T08:13:42+00:00",
       "judge": {"name": "demo", "model": "demo-1", "prompt_sha256": "ab" * 32},
       "dataset": {"path": "x.jsonl", "sha256_rows": "cd" * 32}}
BANNED = re.compile(r"(?i)\bat most\b|guarantee|\bcertified\b|\bcompliant\b|at ≤")
OBSERVED = "Observed on all rows, no bound — not a basis for deployment"


def _result(n=600, wrong_every=15):
    """Big enough that each half (300 texts) clears the 5 % start (124 decisions)."""
    recs = [{"idx": i, "question": "intent", "confidence": 1 - i / (2 * n),
             "correct": i % wrong_every != wrong_every - 1 or i < 200, "latency_s": 0.1,
             "cost_usd": 0.0, "expected": "abcd"[i % 4], "meta": {}}
            for i in range(n)]
    return summarize("demo", recs, RUN, groups=[f"t{i}" for i in range(n)], ci=False)


def _primary(res):
    return next(t for t in res.certificate["questions"][0]["targets"] if t["primary"])


def _pr_comment():
    spec = importlib.util.spec_from_file_location("pr_comment_185",
                                                  ROOT / "scripts" / "pr_comment.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the certificate: the held-out share carries its own exact bound ----------------------


def test_the_held_out_share_carries_its_exact_one_sided_bound():
    cert = _result().certificate
    for t in cert["questions"][0]["targets"]:
        o = t["out_of_sample"]
        want = _up(risk_upper_bound(o["errors"], o["automated"], cert["delta"])) \
            if o["automated"] else None
        assert o["risk_upper"] == want


def test_the_held_out_bound_matches_a_hand_computed_clopper_pearson_value():
    """A perfect judge on 400 distinct texts: each half (200) clears the 5 % start (124), and
    the held-out check automates 399 of them (the least confident text of one half sits just
    under the other half's threshold) with 0 errors. The exact one-sided 95 % bound for 0
    errors in m is 1 − 0.05^(1/m) in closed form: 0.74800 % for m = 399."""
    recs = [{"question": "q", "confidence": 1 - i / 800, "correct": True} for i in range(400)]
    cert = automation_certificate(recs, None)
    o = next(t for t in cert["questions"][0]["targets"]
             if t["target_risk"] == 0.05)["out_of_sample"]
    assert (o["automated"], o["errors"]) == (399, 0)
    hand = 1 - 0.05 ** (1 / 399)
    assert hand == pytest.approx(0.0074800, abs=1e-7)
    assert o["risk_upper"] == pytest.approx(hand, abs=1e-6) and o["risk_upper"] >= hand


def test_a_held_out_half_with_nothing_automated_has_no_bound():
    recs = [{"question": "q", "confidence": 1 - i / 400, "correct": True} for i in range(200)]
    cert = automation_certificate(recs, None)
    five = next(t for t in cert["questions"][0]["targets"] if t["target_risk"] == 0.05)
    assert five["out_of_sample"]["automated"] == 0 and five["out_of_sample"]["risk_upper"] is None


@pytest.mark.parametrize(("r", "text"), [
    (0.05, "a target of 1 wrong in every 20 automated decisions"),
    (0.03, "a target of 3 % of automated decisions wrong"),
])
def test_the_plain_reading_states_a_target_not_a_promise(r, text):
    assert plain_reading(r) == text


# --- the report: validated first, bounded before observed ---------------------------------


def test_the_report_headline_is_the_validated_share_with_bound_and_range():
    res = _result()
    p, md = _primary(res), render_markdown(res)
    o = p["out_of_sample"]
    lo, hi = o["spread_coverage"]
    section = md[md.index("## Can I automate this?"):]
    head = section.split("\n\n")[1]
    assert head.startswith(f"**Validated on held-out decisions, at a 5% error target: "
                           f"{o['coverage']:.1%}**")
    assert f"95% upper bound on the error rate: {o['risk_upper']:.1%}" in head
    assert f"seeds 0–9: {lo:.1%}–{hi:.1%}" in head
    # the deployed share on all rows comes after, with its own bound
    assert head.index(f"{o['coverage']:.1%}") < head.index(f"{p['coverage']:.1%}")
    assert f"95% upper bound on the error rate: {p['risk_upper']:.1%}" in head
    assert "| error target | in plain words | validated on held-out decisions |" in section


def test_a_share_without_a_bound_appears_only_in_the_observed_section():
    md = render_markdown(_result())
    assert md.count(f"## {OBSERVED}") == 1
    observed = md.index(f"## {OBSERVED}")
    assert md.index("## Can I automate this?") < observed
    assert md.index("## When it says ≥ 90 / 95 / 99 %") < observed
    for unbounded in ("Zero observed errors", "| coverage | accuracy | min confidence | n |"):
        assert md.index(unbounded) > observed


def test_no_banned_phrasing_in_the_markdown_html_pr_comment_or_gate():
    res = _result()
    d = res.to_dict()
    texts = [render_markdown(res), certificate_html(d), _key_figures(d, "", ""),
             _pr_comment().build(d), certificate_summary(d),
             *check_safe_rate(res.certificate, [(0.05, 0.99), (0.01, 0.5)])]
    for text in texts:
        assert not BANNED.search(text), BANNED.search(text)


def test_the_html_lead_card_is_the_validated_share():
    res = _result()
    o = _primary(res)["out_of_sample"]
    cards = _key_figures(res.to_dict(), "", "")
    lead = cards[cards.index('class="kpi lead"'):cards.index('<div class="kpi">')]
    assert "Validated on held-out decisions" in lead and "5% error target" in lead
    assert f'<div class="kpi-value">{o["coverage"]:.1%}</div>' in lead
    assert f"95% upper bound on the error rate: {o['risk_upper']:.1%}" in lead


def test_the_pr_comment_leads_with_the_validated_share_and_moves_zero_error_coverage():
    res = _result()
    o = _primary(res)["out_of_sample"]
    md = _pr_comment().build(res.to_dict())
    assert (f"**Validated on held-out decisions, at a 5% error target: {o['coverage']:.1%}**"
            in md)
    assert md.index("**Validated on held-out") < md.index("| error target |")
    table = md[md.index("| n | confidence known"):].split("\n\n")[0]
    assert "zero-error" not in table
    assert md.index(OBSERVED) > md.index("| n | confidence known")


def test_the_cli_summary_leads_with_the_validated_share():
    p = _primary(_result())
    o = p["out_of_sample"]
    lo, hi = o["spread_coverage"]
    line = certificate_summary({"certificate": _result().certificate})
    assert line == (f"safe_automation@5%={o['coverage']:.1%} [{lo:.1%}–{hi:.1%}] "
                    f"bound={o['risk_upper']:.1%} all_rows={p['coverage']:.1%}")


# --- the docs and the Action ---------------------------------------------------------------


@pytest.mark.parametrize("path", ["README.md", "action.yml", "docs/integrations.md"])
def test_no_at_most_claim_in_the_readme_action_or_integrations(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert "at most" not in text and "at ≤" not in text


def test_the_cli_help_says_target_not_at_most():
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "check", "--help"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and "at most" not in r.stdout
    assert "error target" in " ".join(r.stdout.split())
