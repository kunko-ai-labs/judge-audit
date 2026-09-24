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
    lines += [f"Judge {_judge_line(run)}", "",
              "| n | confidence known | accuracy | ground truth | ECE | zero-error coverage | cost | p50 | p99 |",
              "|---|---|---|---|---|---|---|---|---|",
              f"| {_md(result.get('n', 0))} | {confidence['known']}/{confidence['total']} | "
              f"{result.get('accuracy', 0):.1%} | {gt_cell} | "
              f"{_metric(result.get('ece'), '.4f')} | "
              f"{_metric(zec.get('coverage'), '.1%')} "
              f"(n={_md(zec.get('n', 0))}, conf ≥ {_md(zec.get('threshold'))}) | "
              f"{('$' + format(result['total_cost_usd'], '.4f')) if result.get('total_cost_usd') is not None else 'unknown'} | "
              f"{result.get('p50_latency_s', 0)} s | {result.get('p99_latency_s', 0)} s |", "",
              f"_{gt_line}_", ""]
    if drift is not None:
        base = _md(drift.get("baseline", "baseline"))
        if drift.get("ok"):
            lines += [f"✅ **No drift** vs `{base}` "
                      f"(ECE drift ≤ {_md(drift.get('max_ece_drift'))}, "
                      f"accuracy drop ≤ {_md(drift.get('max_acc_drop'))})."]
        else:
            lines += [f"❌ **Drift detected** vs `{base}`:", ""]
            lines += [f"- {_md(f)}" for f in drift.get("failures", [])]
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
