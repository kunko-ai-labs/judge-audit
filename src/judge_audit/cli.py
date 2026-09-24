"""CLI: run audits, write reports, gate CI on drift.

Exit codes: 0 ok · 1 drift detected (check) · 2 usage / configuration error.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from typing import NoReturn

from . import __version__
from .ground_truth import ground_truth_of
from .judges.finetuned import FinetunedJudge
from .judges.jev import JevJudge
from .judges.llm import LLMJudge
from .judges.nli import NLIJudge
from .judges.simulated import SIMULATED_TAG, SimulatedJudge
from .report import (
    IncompatibleBaseline,
    check_drift,
    fmt4,
    interval,
    render_html,
    render_markdown,
)
from .runner import load_dataset, run_audit, write_judgments

JUDGES = ("jev", "llm", "nli", "finetuned", "simulated")


def _die(msg: str) -> NoReturn:
    print(f"judge-audit: {msg}", file=sys.stderr)
    sys.exit(2)


def _write_atomic(path: str, content: str) -> None:
    """Write through a temp file in the same directory, then rename.

    A CI gate that dies mid-write must not leave a half-written report behind for the
    next run to compare against: either the old file or the new one, never a prefix.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".judge-audit-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on POSIX and Windows
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _write_json(path: str, obj: dict) -> None:
    _write_atomic(path, json.dumps(obj, indent=2))


def _judge(name: str, rows: list | None = None):
    if name == "jev":
        return JevJudge(), ""
    if name == "llm":
        return LLMJudge(), ""
    if name == "nli":
        return NLIJudge(), ""
    if name == "finetuned":
        return FinetunedJudge(), ""
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
                   help="jev: AI_GATEWAY_API_KEY (or JEV_ENDPOINT) · llm: any chat model · "
                        "nli: local zero-shot encoder (control) · finetuned: your own "
                        "classifier, FINETUNED_MODEL_DIR · see docs/judges.md · simulated: nothing")
    r.add_argument("--format", choices=["md", "html"], default="md")
    r.add_argument("--out", default=None, help="report path (default audit-report.md|html)")
    r.add_argument("--json", default="audit-result.json", help="metrics + run metadata")
    r.add_argument("--judgments", default="audit-judgments.jsonl",
                   help="per-decision evidence (JSONL); pass '' to skip")
    r.add_argument("--no-ci", action="store_true",
                   help="skip the bootstrap confidence intervals (also JUDGE_AUDIT_BOOTSTRAP=0)")

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
    c.add_argument("--allow-incompatible", action="store_true",
                   help="compare even when the baseline measured another dataset, judge "
                        "or n (refused with exit 2 otherwise)")
    c.add_argument("--no-ci", action="store_true",
                   help="skip the bootstrap confidence intervals (also JUDGE_AUDIT_BOOTSTRAP=0)")
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    rows: list[dict] = []
    dataset_meta: dict = {}
    try:
        rows, dataset_meta = load_dataset(args.labels)
    except (OSError, ValueError) as e:
        _die(f"cannot read {args.labels}: {e}")
    if not rows:
        _die(f"{args.labels} has no rows")
    judge, tag = None, ""
    try:
        judge, tag = _judge(args.judge, rows)
    except (RuntimeError, ValueError) as e:
        _die(f"judge '{args.judge}' is not configured: {e}")
    lead = f"{tag} · " if tag else ""  # the line that gets copied says it is simulated

    result = run_audit(judge, rows, labels_path=args.labels, dataset_meta=dataset_meta,
                       ci=False if args.no_ci else None)

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
        _write_atomic(out, content)
        _write_json(args.json, result.to_dict())
        if args.judgments:
            write_judgments(result, args.judgments)
        confidence = result.confidence
        cost = (f"${result.total_cost_usd:.4f}" if result.total_cost_usd is not None
                else "unknown")
        print(f"{lead}judge={result.judge} n={result.n} "
              f"accuracy={result.accuracy:.1%}{interval(result.accuracy_ci, pct=True)} "
              f"confidence_known={confidence['known']}/{confidence['total']} "
              f"ece={fmt4(result.ece)}{interval(result.ece_ci)} "
              f"ece_equal_mass={fmt4(result.ece_equal_mass)}"
              f"{interval(result.ece_equal_mass_ci)} "
              f"brier={fmt4(result.brier)}{interval(result.brier_ci)} "
              f"nll={'inf' if result.nll_infinite else fmt4(result.nll)}"
              f"{interval(result.nll_ci)} "
              f"gt={ground_truth_of(result.run).tier} "
              f"cost={cost} -> {out}")
    else:
        failures: list[str] = []
        try:
            failures = check_drift(result, args.baseline,
                                   args.max_ece_drift, args.max_acc_drop,
                                   allow_incompatible=args.allow_incompatible)
        except IncompatibleBaseline as e:
            _die(str(e))
        except (OSError, ValueError, KeyError) as e:
            _die(f"cannot use baseline {args.baseline}: {e}")
        if args.out:
            content = render_markdown(result)
            if tag:
                content = f"> ⚠️ **{tag}**\n\n" + content
            _write_atomic(args.out, content)
        if args.json:
            _write_json(args.json, result.to_dict())
        if args.drift:
            _write_json(args.drift,
                        {"ok": not failures, "failures": failures, "ece": result.ece,
                         "accuracy": result.accuracy, "n": result.n,
                         "baseline": args.baseline,
                         "max_ece_drift": args.max_ece_drift,
                         "max_acc_drop": args.max_acc_drop})
        if failures:
            print(f"{lead}DRIFT DETECTED:", file=sys.stderr)
            for fl in failures:
                print(f"  - {fl}", file=sys.stderr)
            sys.exit(1)
        ece = fmt4(result.ece)
        print(f"{lead}OK: no drift (ece={ece}, accuracy={result.accuracy:.1%}, "
              f"gt={ground_truth_of(result.run).tier})")


if __name__ == "__main__":
    main()
