"""Build the sticky pull-request comment for the judge-audit GitHub Action.

Reads the audit result JSON (from `judge-audit run|check --json`) and, in check
mode, the drift verdict JSON (`judge-audit check --drift`). Stdlib only.

  python scripts/pr_comment.py audit-result.json [--drift audit-drift.json]
      [--artifact-url URL] [--marker "<!-- judge-audit -->"] > comment.md
"""
from __future__ import annotations

import argparse
import json
import sys
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


def _pct(x: float) -> str:
    return f"{x * 100:g}%"


def _cells(t: dict, unit: str) -> tuple[str, str, str]:
    """(safe automation rate, threshold, out of sample) for one target, escaped."""
    if t.get("threshold") is None:
        return f"none: {_md(t.get('reason') or 'no threshold passes')}", "—", "—"
    o = t.get("out_of_sample") or {}
    if o.get("reason") and not o.get("automated"):
        oos = f"not checkable: {_md(o['reason'])}"
    else:
        spread = o.get("spread_coverage") or []
        oos = f"{float(o.get('coverage') or 0):.1%} automated" + (
            f", {float(o['risk']):.1%} wrong" if o.get("risk") is not None else "") + (
            f" (seeds: {float(spread[0]):.1%}–{float(spread[1]):.1%})"
            if len(spread) == 2 else "")
    bound = (f", error bound {float(t['risk_upper']):.1%}"
             if t.get("risk_upper") is not None else "")
    rate = (f"{float(t['coverage']):.1%} ({int(t['automated']):,} of {int(t['n']):,} {unit}s; "
            f"{int(t['errors'])} wrong{bound})")
    return rate, _md(t["threshold"]), oos


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
    lines = ["### Can I automate this?", ""]
    for q in questions:
        if len(questions) > 1:
            lines += [f"**`{_md(q.get('question', '?'))}`**", ""]
        targets = q.get("targets", [])
        p = next((t for t in targets if t.get("primary")), targets[0] if targets else None)
        if p is not None:
            rate, thr, oos = _cells(p, unit)
            head = f"Safe automation rate at ≤ {_pct(float(p['target_risk']))} error"
            if p.get("threshold") is None:
                lines += [f"**{head}: {rate}**", ""]
            else:
                lines += [f"**{head}: {float(p['coverage']):.1%}** of the labelled {unit}s "
                          f"({int(p['automated']):,} of {int(p['n']):,}; {int(p['errors'])} "
                          f"wrong, error bound {float(p['risk_upper']):.1%}), deploying at "
                          f"confidence ≥ {thr}; out of sample: {oos}.", ""]
            pt = p.get("per_text")
            if pt:
                lines += [f"The labelled set repeats texts ({int(q.get('n', 0)):,} decisions, "
                          f"{int(q.get('texts', 0)):,} texts); counting each text once: "
                          + (f"{float(pt['coverage']):.1%} of the texts."
                             if pt.get("threshold") is not None else
                             f"none ({_md(pt.get('reason') or 'no threshold passes')})."), ""]
            w = p.get("worst_segment")
            if w:
                lines += [f"Worst segment above that threshold: `{_md(w.get('segment'))}`, "
                          f"{int(w['errors'])} of {int(w['automated'])} automated wrong "
                          f"({float(w['rate']):.1%}; its own error bound "
                          f"{float(w['risk_upper']):.1%})."
                          + (f" {int(p['errors_in_small_segments'])} of the "
                             f"{int(p['errors'])} errors sit in segments too small to rank."
                             if p.get("errors_in_small_segments") else ""), ""]
        lines += ["| at most this error | in plain words | safe automation rate | "
                  "deploy at confidence ≥ | checked out of sample |",
                  "|---|---|---|---|---|"]
        for t in targets:
            rate, thr, oos = _cells(t, unit)
            mark = " (primary)" if t.get("primary") else ""
            plain = _md(str(t.get("plain", "")))
            lines.append(f"| {_pct(float(t['target_risk']))}{mark} | {plain} | {rate} | "
                         f"{thr} | {oos} |")
        lines.append("")
    s = c.get("scope") or {}
    valid = " · ".join(x for x in (
        f"judge `{_md(s['judge'])}`" if s.get("judge") else "",
        f"prompt `{_md(str(s['prompt_sha256'])[:8])}…`" if s.get("prompt_sha256") else "",
        f"data sha256 `{_md(str(s['dataset_sha256'])[:12])}…`" if s.get("dataset_sha256") else "",
        f"review by {_md(s['review_by'])}" if s.get("review_by") else "") if x)
    level = 1 - float(c.get("delta", 0.05))
    lines += [f"_Valid only for {valid or 'this run'}, on traffic drawn like these labelled "
              f"{unit}s (a random sample of it) with the labels taken as right; "
              f"{level:.0%} confidence per row; out of sample = threshold chosen on half the "
              f"{unit}s, applied to the other half. {_md(c.get('disclaimer', ''))}_", ""]
    return lines


def _metric(value: object, spec: str) -> str:
    return "unknown" if value is None else format(value, spec)


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
    zec_cell = ("unknown" if zec.get("coverage") is None else
                f"{_metric(zec.get('coverage'), '.1%')} "
                f"(n={_md(zec.get('n', 0))}, conf ≥ {_md(zec.get('threshold'))})")
    lines += [*_certificate(result)]
    lines += [f"Judge {_judge_line(run)}", "",
              "| n | confidence known | accuracy | ground truth | ECE | zero-error coverage | cost | p50 | p99 | slowest |",
              "|---|---|---|---|---|---|---|---|---|---|",
              f"| {_md(result.get('n', 0))} | {confidence['known']}/{confidence['total']} | "
              f"{result.get('accuracy', 0):.1%} | {gt_cell} | "
              f"{_metric(result.get('ece'), '.4f')} | "
              f"{zec_cell} | "
              f"{('$' + format(result['total_cost_usd'], '.4f')) if result.get('total_cost_usd') is not None else 'unknown'} | "
              f"{result.get('p50_latency_s', 0)} s | {result.get('p99_latency_s', 0)} s | "
              f"{_md(result['max_latency_s']) + ' s' if result.get('max_latency_s') is not None else '—'} |", "",
              f"_{gt_line}_", ""]
    if drift is not None:
        base = _md(drift.get("baseline", "baseline"))
        if drift.get("ok"):
            mins = "".join(
                f", safe automation rate at ≤ {_pct(float(m['risk']))} error ≥ "
                f"{float(m['share']):.1%}" for m in drift.get("min_safe_rate") or [])
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
    lines.append("_ECE 0 = perfectly honest confidence. Zero-error coverage = the most-confident "
                 "share of decisions with no observed error, retrospective on this dataset._")
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
