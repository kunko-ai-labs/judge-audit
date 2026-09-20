"""CLI: run audits, write reports, gate CI on drift.

Exit codes: 0 ok · 1 drift detected (check) · 2 usage / configuration error.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import NoReturn

from . import __version__
from .judges.jev import JevJudge
from .judges.llm import LLMJudge
from .judges.simulated import SIMULATED_TAG, SimulatedJudge
from .report import check_drift, render_html, render_markdown
from .runner import load_jsonl, run_audit, write_judgments

JUDGES = ("jev", "llm", "simulated")


def _die(msg: str) -> NoReturn:
    print(f"judge-audit: {msg}", file=sys.stderr)
    sys.exit(2)


def _judge(name: str, rows: list | None = None):
    if name == "jev":
        return JevJudge(), ""
    if name == "llm":
        return LLMJudge(), ""
    if name == "simulated":
        return SimulatedJudge(rows or []), SIMULATED_TAG
    _die(f"unknown judge '{name}' (available: {', '.join(JUDGES)})")


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="judge-audit",
        description="Independent calibration audits for AI judges.")
    ap.add_argument("--version", action="version", version=f"judge-audit {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="audit a judge against a labeled JSONL file")
    r.add_argument("labels", help="JSONL: {state, questions:[...], labels:{...}}")
    r.add_argument("--judge", default="jev", choices=JUDGES,
                   help="jev: AI_GATEWAY_API_KEY (or JEV_ENDPOINT) · llm: any chat model, "
                        "see docs/judges.md · simulated: nothing")
    r.add_argument("--format", choices=["md", "html"], default="md")
    r.add_argument("--out", default=None, help="report path (default audit-report.md|html)")
    r.add_argument("--json", default="audit-result.json", help="metrics + run metadata")
    r.add_argument("--judgments", default="audit-judgments.jsonl",
                   help="per-decision evidence (JSONL); pass '' to skip")

    c = sub.add_parser("check", help="CI gate: fail if drifted vs baseline")
    c.add_argument("labels")
    c.add_argument("--judge", default="jev", choices=JUDGES)
    c.add_argument("--baseline", required=True, help="audit-result.json of a previous run")
    c.add_argument("--max-ece-drift", type=float, default=0.02)
    c.add_argument("--max-acc-drop", type=float, default=0.01)
    c.add_argument("--out", default=None, help="also write the markdown report here")
    c.add_argument("--json", default=None, help="also write metrics + run metadata here")
    c.add_argument("--drift", default=None,
                   help="write the verdict here: {ok, failures, ece, accuracy, baseline}")
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    try:
        rows = load_jsonl(args.labels)
    except (OSError, ValueError) as e:
        _die(f"cannot read {args.labels}: {e}")
    if not rows:
        _die(f"{args.labels} has no rows")
    tag = ""
    try:
        judge, tag = _judge(args.judge, rows)
    except (RuntimeError, ValueError) as e:
        _die(f"judge '{args.judge}' is not configured: {e}")

    result = run_audit(judge, rows, labels_path=args.labels)

    if args.cmd == "run":
        fmt = args.format
        out = args.out or f"audit-report.{fmt}"
        if fmt == "html":
            try:
                content = render_html(result, tag=tag)
            except RuntimeError as e:
                _die(str(e))
        else:
            content = render_markdown(result)
            if tag:
                content = f"> ⚠️ **{tag}**\n\n" + content
        with open(out, "w", encoding="utf-8") as f:
            f.write(content)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        if args.judgments:
            write_judgments(result, args.judgments)
        print(f"judge={result.judge} n={result.n} accuracy={result.accuracy:.1%} "
              f"ece={result.ece:.4f} cost=${result.total_cost_usd:.4f} -> {out}")
    else:
        failures: list[str] = []
        try:
            failures = check_drift(result, args.baseline,
                                   args.max_ece_drift, args.max_acc_drop)
        except (OSError, ValueError, KeyError) as e:
            _die(f"cannot use baseline {args.baseline}: {e}")
        if args.out:
            content = render_markdown(result)
            if tag:
                content = f"> ⚠️ **{tag}**\n\n" + content
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(content)
        if args.json:
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        if args.drift:
            with open(args.drift, "w", encoding="utf-8") as f:
                json.dump({"ok": not failures, "failures": failures, "ece": result.ece,
                           "accuracy": result.accuracy, "n": result.n,
                           "baseline": args.baseline,
                           "max_ece_drift": args.max_ece_drift,
                           "max_acc_drop": args.max_acc_drop}, f, indent=2)
        if failures:
            print("DRIFT DETECTED:", file=sys.stderr)
            for fl in failures:
                print(f"  - {fl}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: no drift (ece={result.ece:.4f}, accuracy={result.accuracy:.1%})")


if __name__ == "__main__":
    main()
