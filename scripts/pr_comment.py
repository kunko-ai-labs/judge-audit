"""Build the sticky pull-request comment for the judge-audit GitHub Action.

Reads the audit result JSON (from `judge-audit run|check --json`) and, in check
mode, the drift verdict JSON (`judge-audit check --drift`). Stdlib only.

  python scripts/pr_comment.py audit-result.json [--drift audit-drift.json]
      [--artifact-url URL] [--marker "<!-- judge-audit -->"] > comment.md
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

MARKER = "<!-- judge-audit -->"

# Markdown metacharacters that can forge structure inside a comment: code spans, table
# cells, emphasis, headings, quotes, links and images.
_SPECIAL = set("\\`*_[]()<>#|~!")


def _md(value: object) -> str:
    """Escape a string that came from the dataset or the run before it is interpolated.

    A caveat, a model name or a dataset path is *data*, not markup: it must not be able
    to open a table row, a heading, a link, an image or a verdict in the comment a human
    reads. Every newline (and every run of blanks) collapses to a single space, so one
    value stays one cell, and every metacharacter is backslash-escaped. Values are still
    shown inside backticks where that reads better; a hostile backtick can end that code
    span early, but what follows is escaped text, not markup.
    """
    text = " ".join(str(value).split())
    out = "".join("\\" + c if c in _SPECIAL else c for c in text)
    return "\\" + out if out[:1] in ("-", "+", "=") else out


def _judge_line(run: dict) -> str:
    j = run.get("judge", {}) if isinstance(run, dict) else {}
    parts = [f"`{_md(j.get('name', '?'))}`"]
    if j.get("model"):
        parts.append(f"model `{_md(j['model'])}`")
    if j.get("backend"):
        parts.append(f"backend `{_md(j['backend'])}`")
    if j.get("confidence_method"):
        parts.append(_md(j["confidence_method"]))
    ds = run.get("dataset", {}) if isinstance(run, dict) else {}
    if ds.get("path"):
        parts.append(f"dataset `{_md(ds['path'])}` ({_md(ds.get('rows', '?'))} rows, "
                     f"sha256 `{_md(str(ds.get('sha256', ''))[:12])}…`)")
    return " · ".join(parts)


def _ground_truth(run: dict) -> tuple[str, str]:
    """(cell next to accuracy, full line) from run.dataset.ground_truth; GT-0 when absent.

    Mirrors GroundTruth.report_line() in src/judge_audit/ground_truth.py without
    importing it: this script runs with the stdlib only.
    """
    ds = run.get("dataset", {}) if isinstance(run, dict) else {}
    gt = ds.get("ground_truth") or {}
    tier, label = gt.get("tier", "GT-0"), gt.get("label", "unknown")
    cell = f"{_md(tier)} {_md(label)}"
    if tier == "GT-0":
        tail = "declare it with a dataset header line (see docs/ground-truth.md)"
    else:
        caveats = gt.get("caveats") or []
        tail = "; ".join(_md(x) for x in [gt.get("meaning", ""), *caveats])
    return cell, f"Ground truth: {cell} — {tail}"


TABLE_HEADER = ("| error target | in plain words | validated on held-out decisions | "
                + "deploy at confidence ≥ | on all labelled decisions |")
TABLE_RULE = "|---|---|---|---|---|"
OBSERVED = "Observed on all rows, no bound — not a basis for deployment"


def _pct(x: float) -> str:
    return f"{x * 100:g}%"


def _up(x: object) -> str:
    """A bound as printed: rounded **up** to 0.1 %, never below the exact value."""
    return f"{math.ceil(float(x) * 1000 - 1e-9) / 10:.1f}%"  # type: ignore[arg-type]


def _bound(x: object, level: float) -> str:
    return f"{level:.0%} upper bound on the error rate: {_up(x)}"


def _threshold(t: object) -> str:
    """A deployment threshold as printed (mirrors `report.threshold_text`): exact when short;
    when a float has many digits, rounded **up** to 6 significant digits and marked `↑` so a
    caller using the printed number is never less selective than the tested cut."""
    exact = repr(float(t))  # type: ignore[arg-type]
    if len(exact) <= 8:
        return _md(exact)
    d = Decimal(exact)
    q = Decimal(1).scaleb(d.adjusted() - 5)
    up = d.quantize(q, rounding=ROUND_CEILING)
    return _md(f"{up.normalize():f}↑")


def _status(t: dict) -> str:
    """`none`, `unrecorded`, `too_few`, `not_met` or `met` (mirrors
    `report.held_out_status`): only `met` is called validated."""
    o = t.get("out_of_sample")
    if t.get("threshold") is None:
        return "none"
    if not o:
        return "unrecorded"
    if o.get("reason") and not o.get("automated"):
        return "too_few"
    if "risk_upper" not in o:
        return "unrecorded"
    ru = o.get("risk_upper")
    return "not_met" if ru is None or float(ru) > float(t["target_risk"]) else "met"


def _held_out(o: dict, unit: str, level: float, bound: bool = True) -> str:
    """The held-out share's counts, bound and range over split seeds (not the share)."""
    parts = [f"{int(o.get('automated') or 0):,} of {int(o.get('n') or 0):,} {unit}s; "
             f"{int(o.get('errors') or 0)} wrong"
             + (f": {float(o['risk']):.1%}" if o.get("risk") is not None else "")]
    if bound and o.get("risk_upper") is not None:
        parts.append(_bound(o["risk_upper"], level))
    spread, seeds = o.get("spread_coverage") or [], o.get("spread_seeds") or []
    if len(spread) == 2 and len(seeds) == 2:
        parts.append(f"seeds {_md(seeds[0])}–{_md(seeds[1])}: "
                     f"{float(spread[0]):.1%}–{float(spread[1]):.1%}")
    return "; ".join(parts)


def _not_met(t: dict, level: float) -> str:
    ru = (t.get("out_of_sample") or {}).get("risk_upper")
    if ru is None:
        return "no held-out decision reached the threshold chosen on the other half"
    return (f"{level:.0%} upper bound on the error rate {_up(ru)}, above the "
            f"{_pct(float(t['target_risk']))} target")


def _too_few(t: dict, unit: str) -> str:
    o = t.get("out_of_sample") or {}
    need = t.get("min_units")
    has = re.search(r"the larger has (\d+)", str(o.get("reason") or ""))
    if need is None or has is None:
        return f"{_md(o.get('reason') or 'the check could not be made')}."
    return (f"The check splits the {unit}s into two halves and needs {int(need):,} scored "
            f"{unit}s in a half (about {2 * int(need):,} in all); the larger half has "
            f"{int(has.group(1)):,}.")


def _cells(t: dict, unit: str, level: float = 0.95) -> tuple[str, str, str]:
    """(held-out check, threshold, on all labelled decisions) for one target, escaped: the
    held-out column first, a share in it only when validated (#185)."""
    if t.get("threshold") is None:
        return f"none: {_md(t.get('reason') or 'no threshold passes')}", "—", "—"
    o, status = t.get("out_of_sample") or {}, _status(t)
    if status == "unrecorded":
        held = "not recorded: this result predates the held-out check"
    elif status == "too_few":
        held = _md(o.get("reason") or "too few decisions to check on held-out data")
    elif status == "not_met":
        ru = o.get("risk_upper")
        why = f"{level:.0%} upper bound {_up(ru)}" if ru is not None else (
            "no held-out decision automated")
        held = (f"not met at the {_pct(float(t['target_risk']))} target ({why}): "
                f"{float(o.get('coverage') or 0):.1%} held out "
                f"({_held_out(o, unit, level, False)})")
    else:
        held = f"{float(o.get('coverage') or 0):.1%} ({_held_out(o, unit, level)})"
    bound = (f", {_bound(t['risk_upper'], level)}" if t.get("risk_upper") is not None else "")
    rows = (f"{float(t['coverage']):.1%} ({int(t['automated']):,} of {int(t['n']):,} {unit}s; "
            f"{int(t['errors'])} wrong{bound})")
    return held, _threshold(t["threshold"]), rows


def _certificate(result: dict) -> list[str]:
    """The "Can I automate this?" section from `audit-result.json`'s certificate: the
    safe automation rate at the primary target, the worst segment, the other targets, what
    it is valid for (mirrors `report.certificate_lines` without importing it: stdlib
    only). [] without one."""
    c = result.get("certificate") or {}
    questions = c.get("questions") or []
    if not questions:
        return []
    unit = _md(c.get("unit", "text"))
    level = 1 - float(c.get("delta", 0.05))
    lines = ["### Can I automate this?", ""]
    for q in questions:
        if len(questions) > 1:
            lines += [f"**`{_md(q.get('question', '?'))}`**", ""]
        targets = q.get("targets", [])
        p = next((t for t in targets if t.get("primary")), targets[0] if targets else None)
        if p is not None:
            held, thr, rows = _cells(p, unit, level)
            head = (f"Validated on held-out {unit}s, at a {_pct(float(p['target_risk']))} "
                    "error target")
            o, status = p.get("out_of_sample") or {}, _status(p)
            deploy = (f"to deploy, confidence ≥ {thr}; on all labelled {unit}s it automates "
                      f"{rows}.")
            if status == "none":
                lines += [f"**{head}: {held}**", ""]
            elif status == "not_met":
                lines += [f"**{head}: not met** ({_not_met(p, level)}). Held out: "
                          f"{float(o.get('coverage') or 0):.1%} of the labelled {unit}s "
                          f"({_held_out(o, unit, level, False)}), with the threshold chosen "
                          f"on one half and applied to the other. Not validated: {deploy}", ""]
            elif status == "too_few":
                lines += [f"**{head}: too few {unit}s to check** with {int(p['n']):,} "
                          f"{unit}s. {_too_few(p, unit)} Not validated: {deploy}", ""]
            elif status == "unrecorded":
                lines += [f"**{head}: not recorded** (this result predates the held-out "
                          f"check). Not validated: {deploy}", ""]
            else:
                lines += [f"**{head}: {float(o.get('coverage') or 0):.1%}** of the labelled "
                          f"{unit}s ({_held_out(o, unit, level)}), with the threshold chosen "
                          f"on one half and applied to the other. To deploy: confidence ≥ "
                          f"{thr}; on all labelled {unit}s it automates {rows}.", ""]
            pt = p.get("per_text")
            if pt:
                head_pt = (f"The labelled set repeats texts ({int(q.get('n', 0)):,} decisions, "
                           f"{int(q.get('texts', 0)):,} texts); counting each text once")
                if pt.get("threshold") is None:
                    lines += [f"{head_pt}: none "
                              f"({_md(pt.get('reason') or 'no threshold passes')}).", ""]
                else:
                    lines += [f"{head_pt}: {float(pt['coverage']):.1%} of the texts "
                              f"({int(pt['automated']):,} of {int(pt['n']):,}; "
                              f"{int(pt['errors'])} counted wrong, "
                              f"{_bound(pt['risk_upper'], level)}), at confidence ≥ "
                              f"{_threshold(pt['threshold'])}.", ""]
            w = p.get("worst_segment")
            if w:
                lines += [f"Worst segment above that threshold: `{_md(w.get('segment'))}`, "
                          f"{int(w['errors'])} of {int(w['automated'])} automated wrong "
                          f"({float(w['rate']):.1%}; its own "
                          f"{_bound(w['risk_upper'], level)})."
                          + (f" {int(p['errors_in_small_segments'])} of the "
                             f"{int(p['errors'])} errors sit in segments too small to rank."
                             if p.get("errors_in_small_segments") else ""), ""]
        lines += [TABLE_HEADER, TABLE_RULE]
        for t in targets:
            held, thr, rows = _cells(t, unit, level)
            mark = " (primary)" if t.get("primary") else ""
            plain = _md(str(t.get("plain", "")))
            lines.append(f"| {_pct(float(t['target_risk']))}{mark} | {plain} | {held} | "
                         f"{thr} | {rows} |")
        lines.append("")
    s = c.get("scope") or {}
    valid = " · ".join(x for x in (
        f"judge `{_md(s['judge'])}`" if s.get("judge") else "",
        f"prompt `{_md(str(s['prompt_sha256'])[:8])}…`" if s.get("prompt_sha256") else "",
        f"data sha256 `{_md(str(s['dataset_sha256'])[:12])}…`" if s.get("dataset_sha256") else "",
        f"review by {_md(s['review_by'])}" if s.get("review_by") else "") if x)
    lines += [f"_Valid only for {valid or 'this run'}, on traffic drawn like these labelled "
              f"{unit}s (a random sample of it) with the labels taken as right; "
              f"{level:.0%} confidence per row; validated on held-out {unit}s = threshold "
              f"chosen on half the {unit}s, applied to the other half. "
              f"{_md(c.get('disclaimer', ''))}_", ""]
    return lines


def _metric(value: object, spec: str) -> str:
    return "unknown" if value is None else format(value, spec)


def _latency(result: dict, key: str, absent: str = "unknown") -> str:
    """`0.407 s`; `unknown` when the judge answered nothing (null, #80), never `0 s`.
    `absent` is for a key an older result does not carry."""
    if key not in result:
        return absent
    value = result[key]
    return "unknown" if value is None else f"{_md(value)} s"


def build(result: dict, drift: dict | None = None, artifact_url: str = "",
          marker: str = MARKER) -> str:
    run = result.get("run", {}) or {}
    tag = (run.get("judge") or {}).get("tag")
    zec = result.get("zero_error_coverage", {}) or {}
    lines = [marker, "## judge-audit", ""]
    if tag:
        lines += [f"> ⚠️ **{_md(tag)}**", ""]
    gt_cell, gt_line = _ground_truth(run)
    confidence = result.get("confidence") or {"known": result.get("n", 0),
                                               "total": result.get("n", 0)}
    if zec.get("coverage") is None:
        zec_text = "unknown"
    elif not zec.get("n") or zec.get("threshold") is None:
        zec_text = (f"{_metric(zec.get('coverage'), '.1%')} "
                    "(none: the most confident group of decisions already holds an error)")
    else:
        zec_text = (f"{_metric(zec.get('coverage'), '.1%')} "
                    f"(n={_md(zec.get('n', 0))}, conf ≥ {_md(zec.get('threshold'))})")
    lines += [*_certificate(result)]
    lines += [f"Judge {_judge_line(run)}", "",
              "| n | confidence known | accuracy | ground truth | ECE | cost | p50 | p99 | slowest |",
              "|---|---|---|---|---|---|---|---|---|",
              f"| {_md(result.get('n', 0))} | {confidence['known']}/{confidence['total']} | "
              f"{result.get('accuracy', 0):.1%} | {gt_cell} | "
              f"{_metric(result.get('ece'), '.4f')} | "
              f"{('$' + format(result['total_cost_usd'], '.4f')) if result.get('total_cost_usd') is not None else 'unknown'} | "
              f"{_latency(result, 'p50_latency_s')} | {_latency(result, 'p99_latency_s')} | "
              f"{_latency(result, 'max_latency_s', absent='—')} |", "",
              f"_{gt_line}_", "",
              f"**{OBSERVED}:** zero-error coverage {zec_text}, the most confident share of "
              "decisions with no observed error, retrospective on this dataset.", ""]
    if drift is not None:
        base = _md(drift.get("baseline", "baseline"))
        if drift.get("ok"):
            mins = "".join(
                f", safe automation rate at a {_pct(float(m['risk']))} error target on all "
                f"labelled decisions ≥ {float(m['share']):.1%}"
                for m in drift.get("min_safe_rate") or [])
            lines += [f"✅ **No drift** vs `{base}` "
                      f"(ECE drift ≤ {_md(drift.get('max_ece_drift'))}, "
                      f"accuracy drop ≤ {_md(drift.get('max_acc_drop'))}{mins})."]
        else:
            if drift.get("failures"):
                lines += [f"❌ **Drift detected** vs `{base}`:", ""]
                lines += [f"- {_md(f)}" for f in drift["failures"]]
            if drift.get("gate_failures"):
                lines += ["", "❌ **Below the minimum you set** (no drift involved):", ""]
                lines += [f"- {_md(f)}" for f in drift["gate_failures"]]
        for note in drift.get("baseline_rate_stale") or []:
            lines += ["", f"⚠️ {_md(note)}"]
        lines.append("")
    if artifact_url:
        lines += [f"Full report and per-decision evidence: [run artifacts]({_md(artifact_url)}).", ""]
    lines.append("_ECE 0 = perfectly honest confidence._")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("result", help="audit-result.json")
    ap.add_argument("--drift", default=None, help="audit-drift.json from `check --drift`")
    ap.add_argument("--artifact-url", default="")
    ap.add_argument("--marker", default=MARKER)
    args = ap.parse_args(argv)
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    drift = json.loads(Path(args.drift).read_text(encoding="utf-8")) if args.drift else None
    sys.stdout.write(build(result, drift, args.artifact_url, args.marker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
