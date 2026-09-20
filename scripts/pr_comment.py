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


def _judge_line(run: dict) -> str:
    j = run.get("judge", {}) if isinstance(run, dict) else {}
    parts = [f"`{j.get('name', '?')}`"]
    if j.get("model"):
        parts.append(f"model `{j['model']}`")
    if j.get("backend"):
        parts.append(f"backend `{j['backend']}`")
    if j.get("confidence_method"):
        parts.append(j["confidence_method"])
    ds = run.get("dataset", {}) if isinstance(run, dict) else {}
    if ds.get("path"):
        parts.append(f"dataset `{ds['path']}` ({ds.get('rows', '?')} rows, "
                     f"sha256 `{str(ds.get('sha256', ''))[:12]}…`)")
    return " · ".join(parts)


def build(result: dict, drift: dict | None = None, artifact_url: str = "",
          marker: str = MARKER) -> str:
    run = result.get("run", {}) or {}
    tag = (run.get("judge") or {}).get("tag")
    zec = result.get("zero_error_coverage", {}) or {}
    lines = [marker, "## judge-audit", ""]
    if tag:
        lines += [f"> ⚠️ **{tag}**", ""]
    lines += [f"Judge {_judge_line(run)}", "",
              "| n | accuracy | ECE | zero-error coverage | cost | p50 | p99 |",
              "|---|---|---|---|---|---|---|",
              f"| {result.get('n', 0)} | {result.get('accuracy', 0):.1%} | "
              f"{result.get('ece', 0):.4f} | {zec.get('coverage', 0):.1%} "
              f"(n={zec.get('n', 0)}, conf ≥ {zec.get('threshold')}) | "
              f"${result.get('total_cost_usd', 0):.4f} | {result.get('p50_latency_s', 0)} s | "
              f"{result.get('p99_latency_s', 0)} s |", ""]
    if drift is not None:
        base = drift.get("baseline", "baseline")
        if drift.get("ok"):
            lines += [f"✅ **No drift** vs `{base}` (ECE drift ≤ {drift.get('max_ece_drift')}, "
                      f"accuracy drop ≤ {drift.get('max_acc_drop')})."]
        else:
            lines += [f"❌ **Drift detected** vs `{base}`:", ""]
            lines += [f"- {f}" for f in drift.get("failures", [])]
        lines.append("")
    if artifact_url:
        lines += [f"Full report and per-decision evidence: [run artifacts]({artifact_url}).", ""]
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
