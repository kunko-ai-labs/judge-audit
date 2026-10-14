"""#185: every surface leads with the validated share (held out, bounded, with its range over
split seeds); a share without a bound appears only under "Observed on all rows, no bound —
not a basis for deployment"; no result claim says "at most", "guaranteed", "certified" or
"compliant". Wording and order only: the numbers are the certificate's own."""
from __future__ import annotations

import importlib.util
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit.certificate import _up, automation_certificate, plain_reading
from judge_audit.metrics.selective import risk_upper_bound
from judge_audit.report import (
    _key_figures,
    bound_text,
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


def up(x: float) -> str:
    """A bound as every surface prints it: rounded **up** to 0.1 %, never below the exact."""
    return f"{math.ceil(x * 1000 - 1e-9) / 10:.1f}%"


MET, NOT_MET = 25, 15          # wrong_every: held-out bound 3.03 % / 6.58 % at the 5 % target


def test_a_printed_bound_is_rounded_up_never_to_nearest():
    """2 errors in 199: the exact bound is 3.1297 %, so it prints 3.2 %, not 3.1 %."""
    exact = risk_upper_bound(2, 199)
    assert exact == pytest.approx(0.031297, abs=1e-6)
    assert bound_text(exact) == "95% upper bound on the error rate: 3.2%"
    assert _pr_comment()._bound(exact, 0.95) == "95% upper bound on the error rate: 3.2%"


def test_the_report_headline_is_the_validated_share_with_bound_and_range():
    res = _result(wrong_every=MET)
    p, md = _primary(res), render_markdown(res)
    o = p["out_of_sample"]
    assert o["risk_upper"] <= 0.05
    lo, hi = o["spread_coverage"]
    section = md[md.index("## Can I automate this?"):]
    head = section.split("\n\n")[1]
    assert head.startswith(f"**Validated on held-out decisions, at a 5% error target: "
                           f"{o['coverage']:.1%}**")
    assert f"95% upper bound on the error rate: {up(o['risk_upper'])}" in head
    assert f"seeds 0–9: {lo:.1%}–{hi:.1%}" in head
    # the deployed share on all rows comes after, with its own bound
    assert head.index(f"{o['coverage']:.1%}") < head.index(f"{p['coverage']:.1%}")
    assert f"95% upper bound on the error rate: {up(p['risk_upper'])}" in head
    assert "| error target | in plain words | validated on held-out decisions |" in section


def test_a_held_out_bound_above_the_target_is_not_met_on_every_surface():
    """6 errors in 177 held out: the bound (6.58 %) is above the 5 % target, so the held-out
    share is never presented as validated: report, HTML card, PR comment, CLI line."""
    res = _result(wrong_every=NOT_MET)
    p = _primary(res)
    o, d = p["out_of_sample"], res.to_dict()
    assert o["risk_upper"] > 0.05
    md = render_markdown(res)
    head = md[md.index("## Can I automate this?"):].split("\n\n")[1]
    assert head.startswith("**Validated on held-out decisions, at a 5% error target: not met** "
                           f"(95% upper bound on the error rate {up(o['risk_upper'])}, above "
                           "the 5% target).")
    assert f"Held out: {o['coverage']:.1%} of the labelled decisions" in head
    assert "Not validated: to deploy, confidence ≥" in head
    cell = (f"| 5% (primary) | a target of 1 wrong in every 20 automated decisions | not met at "
            f"the 5% target (95% upper bound {up(o['risk_upper'])}): {o['coverage']:.1%} held "
            "out (")
    assert cell in md
    shown = f"target: {o['coverage']:.1%}"
    cards = _key_figures(d, "", "")
    lead = cards[cards.index('class="kpi lead"'):cards.index('<div class="kpi">')]
    assert '<div class="kpi-value">not met</div>' in lead
    comment = _pr_comment().build(d)
    assert ("**Validated on held-out decisions, at a 5% error target: not met** (95% upper "
            f"bound on the error rate {up(o['risk_upper'])}, above the 5% target)") in comment
    assert cell in comment
    for text in (md, certificate_html(d), lead, comment):
        assert shown not in text
    assert certificate_summary(d) == (f"safe_automation@5%=not_met({o['coverage']:.1%} "
                                      f"bound={up(o['risk_upper'])}) "
                                      f"all_rows={p['coverage']:.1%}")


def test_too_few_decisions_say_so_in_plain_words():
    recs = [{"idx": i, "question": "intent", "confidence": 1 - i / 400, "correct": i < 190,
             "latency_s": 0.1, "cost_usd": 0.0, "expected": "a", "meta": {}}
            for i in range(200)]
    res = summarize("demo", recs, RUN, groups=[f"t{i}" for i in range(200)], ci=False)
    p = _primary(res)
    assert p["out_of_sample"]["reason"] == ("too few decisions to check on held-out data "
                                            "(each half needs 124, the larger has 100)")
    md = render_markdown(res)
    head = md[md.index("## Can I automate this?"):].split("\n\n")[1]
    assert head.startswith("**Validated on held-out decisions, at a 5% error target: too few "
                           "decisions to check** with 200 decisions. The check splits the "
                           "decisions into two halves and needs 124 scored decisions in a half "
                           "(about 248 in all); the larger half has 100. Not validated: to "
                           "deploy, confidence ≥")
    assert "not checkable" not in md
    assert "too few decisions to check on held-out data (each half needs 124" in md
    comment = _pr_comment().build(res.to_dict())
    assert "too few decisions to check** with 200 decisions" in comment
    assert certificate_summary(res.to_dict()).startswith("safe_automation@5%=too_few ")


def test_no_threshold_passing_reads_with_the_one_bound_wording():
    recs = [{"question": "q", "confidence": 1 - i / 2000, "correct": i % 10 != 9}
            for i in range(1000)]
    cert = automation_certificate(recs, [i % 700 for i in range(1000)])
    two = next(t for t in cert["questions"][0]["targets"] if t["target_risk"] == 0.02)
    fc = two["first_cut"]
    want = (f"no threshold passes: the first cut tested holds {fc['units']} decisions with "
            f"{fc['errors']} errors (95% upper bound on the error rate {up(fc['risk_upper'])}, "
            "above the 2% target)")
    assert two["reason"] == want
    pt = two["per_text"]
    assert pt["reason"] == want.replace(f"{fc['units']} decisions",
                                        f"{pt['first_cut']['units']} texts").replace(
        f"{fc['errors']} errors", f"{pt['first_cut']['errors']} errors").replace(
        up(fc["risk_upper"]), up(pt["first_cut"]["risk_upper"]))


@pytest.mark.parametrize("path, target", [
    ("docs/runs/arena/deberta-nli/email-clean.md", "10%"),
    ("docs/runs/jury/router-described/claude-sonnet-4.5.r2.md", "10%"),
    ("docs/runs/jury/router-described/llama-3.3-70b.r2.md", "10%"),
])
def test_published_rows_whose_held_out_bound_fails_read_not_met(path, target):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert f"not met at the {target} target (95% upper bound" in text


def test_the_readme_quickstart_line_reads_not_met():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # the exact held-out bound is 16.5x %: printed rounded up
    assert "safe_automation@10%=not_met(75.0% bound=16.6%) all_rows=65.5%" in readme


def test_a_share_without_a_bound_appears_only_in_the_observed_section():
    md = render_markdown(_result())
    assert md.count(f"## {OBSERVED}") == 1
    observed = md.index(f"## {OBSERVED}")
    assert md.index("## Can I automate this?") < observed
    assert md.index("## When it says ≥ 90 / 95 / 99 %") < observed
    for unbounded in ("Zero observed errors", "| coverage | accuracy | min confidence | n |"):
        assert md.index(unbounded) > observed


@pytest.mark.parametrize("wrong_every", [MET, NOT_MET])
def test_no_banned_phrasing_in_the_markdown_html_pr_comment_or_gate(wrong_every):
    res = _result(wrong_every=wrong_every)
    d = res.to_dict()
    texts = [render_markdown(res), certificate_html(d), _key_figures(d, "", ""),
             _pr_comment().build(d), certificate_summary(d),
             *check_safe_rate(res.certificate, [(0.05, 0.99), (0.01, 0.5)])]
    for text in texts:
        assert not BANNED.search(text), BANNED.search(text)


def test_the_html_lead_card_is_the_validated_share():
    res = _result(wrong_every=MET)
    o = _primary(res)["out_of_sample"]
    cards = _key_figures(res.to_dict(), "", "")
    lead = cards[cards.index('class="kpi lead"'):cards.index('<div class="kpi">')]
    assert "Validated on held-out decisions" in lead and "5% error target" in lead
    assert f'<div class="kpi-value">{o["coverage"]:.1%}</div>' in lead
    assert f"95% upper bound on the error rate: {up(o['risk_upper'])}" in lead


def test_the_pr_comment_leads_with_the_validated_share_and_moves_zero_error_coverage():
    res = _result(wrong_every=MET)
    o = _primary(res)["out_of_sample"]
    md = _pr_comment().build(res.to_dict())
    assert (f"**Validated on held-out decisions, at a 5% error target: {o['coverage']:.1%}**"
            in md)
    assert md.index("**Validated on held-out") < md.index("| error target |")
    table = md[md.index("| n | confidence known"):].split("\n\n")[0]
    assert "zero-error" not in table
    assert md.index(OBSERVED) > md.index("| n | confidence known")


def test_the_cli_summary_leads_with_the_validated_share():
    res = _result(wrong_every=MET)
    p = _primary(res)
    o = p["out_of_sample"]
    lo, hi = o["spread_coverage"]
    line = certificate_summary({"certificate": res.certificate})
    assert line == (f"safe_automation@5%={o['coverage']:.1%} [{lo:.1%}–{hi:.1%}] "
                    f"bound={up(o['risk_upper'])} all_rows={p['coverage']:.1%}")


# --- the docs and the Action ---------------------------------------------------------------


@pytest.mark.parametrize("path", ["README.md", "action.yml", "docs/integrations.md",
                                  "docs/audit-jev-real.md", "docs/audit-jev-router-ablation.md",
                                  "docs/results/v0.5.md"])
def test_no_at_most_claim_in_the_readme_action_or_published_prose(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    assert not BANNED.search(text), BANNED.search(text)


def test_the_cli_help_says_target_not_at_most():
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "check", "--help"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and "at most" not in r.stdout
    assert "error target" in " ".join(r.stdout.split())
