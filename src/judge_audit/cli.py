"""CLI: run audits, write reports, gate CI on drift.

Exit codes: 0 ok · 1 drift detected (check) · 2 usage / configuration error.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import json
import os
import re
import sys
import tempfile
from typing import NoReturn

from . import __version__
from .certificate import DEFAULT_TARGETS, PRIMARY_TARGET, scope_changes
from .ground_truth import ground_truth_of
from .judges.clef import ClefJudge
from .judges.decider import DeciderJudge
from .judges.decision2 import Decision2Judge
from .judges.finetuned import FinetunedJudge
from .judges.hosted import ClefHostedJudge, OpenAIDecisionsJudge
from .judges.jev import JevJudge
from .judges.laya import LayaJudge
from .judges.llm import LLMJudge
from .judges.logprob import LogprobJudge
from .judges.nli import NLIJudge
from .judges.simulated import SIMULATED_TAG, SimulatedJudge
from .judges.strands import StrandsJudge
from .report import (
    IncompatibleBaseline,
    certificate_summary,
    check_drift,
    check_safe_rate,
    fmt4,
    interval,
    parse_min_safe_rate,
    render_html,
    render_markdown,
)
from .runner import (
    IncompleteAnswers,
    certificate_of,
    display_path,
    groups_of,
    load_dataset,
    run_audit,
    scrub,
    write_judgments,
)

JUDGES = ("jev", "llm", "nli", "finetuned", "laya", "decision2", "decider", "strands", "clef",
          "openai-decisions", "clef-hosted", "logprob", "simulated")


def _die(msg: str) -> NoReturn:
    # errors reach CI logs and an Action's output: paths named as provenance names them
    print(f"judge-audit: {scrub(msg)}", file=sys.stderr)
    sys.exit(2)


def _write_or_die(write, path: str, *args) -> None:
    """`write(path, *args)`, or a clear exit 2 naming the path as provenance names it: an
    output that cannot be written is the caller's to fix, not a traceback."""
    try:
        write(path, *args)
    except OSError as e:
        _die(f"cannot write {display_path(path)}: {e.strerror or type(e).__name__}")


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
    if name == "logprob":
        return LogprobJudge(), ""
    if name == "laya":
        return LayaJudge(), ""
    if name == "decision2":
        return Decision2Judge(), ""
    if name == "decider":
        return DeciderJudge(), ""
    if name == "strands":
        return StrandsJudge(), ""
    if name == "clef":
        return ClefJudge(), ""
    if name == "openai-decisions":
        return OpenAIDecisionsJudge(), ""
    if name == "clef-hosted":
        return ClefHostedJudge(), ""
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
                        "classifier, FINETUNED_MODEL_DIR · laya: open judgment model, local · "
                        "decision2 / decider / strands / clef: open decision models, local, "
                        "pinned revision · openai-decisions: the OpenAI Decisions API, "
                        "OPENAI_API_KEY · clef-hosted: Clef / Clef-flash on Workers AI, "
                        "CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID · "
                        "logprob: an open model's own option probabilities, MLX · see "
                        "docs/judges.md · simulated: nothing")
    r.add_argument("--format", choices=["md", "html"], default="md")
    r.add_argument("--out", default=None, help="report path (default audit-report.md|html)")
    r.add_argument("--json", default="audit-result.json", help="metrics + run metadata")
    r.add_argument("--judgments", default="audit-judgments.jsonl",
                   help="per-decision evidence (JSONL); pass '' to skip")
    r.add_argument("--no-ci", action="store_true",
                   help="skip the bootstrap confidence intervals (also JUDGE_AUDIT_BOOTSTRAP=0)")
    _rate_options(r)

    c = sub.add_parser("check", help="CI gate: fail if drifted vs baseline")
    c.add_argument("labels")
    c.add_argument("--judge", default="jev", choices=JUDGES)
    c.add_argument("--baseline", required=True, help="audit-result.json of a previous run")
    c.add_argument("--max-ece-drift", type=float, default=0.02)
    c.add_argument("--max-acc-drop", type=float, default=0.01)
    c.add_argument("--min-safe-rate", action="append", default=[], metavar="RISK:SHARE",
                   help="fail when the safe automation rate at an error of at most RISK is "
                        "below SHARE (e.g. 0.05:0.40); repeatable; see the report's 'Can I "
                        "automate this?'")
    c.add_argument("--out", default=None, help="also write the markdown report here")
    c.add_argument("--json", default=None, help="also write metrics + run metadata here")
    c.add_argument("--drift", default=None,
                   help="write the verdict here: {ok, failures, ece, accuracy, baseline}")
    c.add_argument("--allow-incompatible", action="store_true",
                   help="compare even when the baseline measured another dataset, judge "
                        "or n (refused with exit 2 otherwise)")
    c.add_argument("--no-ci", action="store_true",
                   help="skip the bootstrap confidence intervals (also JUDGE_AUDIT_BOOTSTRAP=0)")
    _rate_options(c)
    return ap


def _rate_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--target", type=float, default=PRIMARY_TARGET, metavar="RISK",
                   help="the error rate the safe automation rate is headlined at, chosen "
                        f"before the run (default {PRIMARY_TARGET}); 1, 2, 5 and 10 %% are "
                        "always shown as context")
    p.add_argument("--segment-by", default="label", metavar="label|meta.FIELD|none",
                   help="segments the deployed threshold is checked on, to name the worst: "
                        "the true label (default), a field of the rows' _meta, or none")


def _stale_baseline(path: str, current: dict) -> list[str]:
    """Why the baseline's safe automation rate no longer applies: its scope differs from
    this run's, or its review date has passed. [] when it still applies or it has none."""
    try:
        with open(path, encoding="utf-8") as f:
            old = (json.load(f).get("certificate") or {}).get("scope") or {}
    except (OSError, ValueError, AttributeError):
        return []
    notes = []
    changes = scope_changes(old, current.get("scope") or {})
    if changes:
        notes.append("the baseline's safe automation rate no longer applies (" +
                     "; ".join(changes) + "); this run's rate replaces it")
    review = old.get("review_by")
    if review and review < datetime.date.today().isoformat():
        notes.append(f"the baseline's safe automation rate was due for review by {review}")
    return notes


def _audit(judge, rows: list[dict], args, dataset_meta: dict):
    """run_audit, or exit 2 when the answers or the dataset would leave it incomplete."""
    try:
        return run_audit(judge, rows, labels_path=args.labels, dataset_meta=dataset_meta,
                         ci=False if args.no_ci else None)
    except IncompleteAnswers as e:
        _die(f"the audit would not be complete: {e}")


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

    minimums: list[tuple[float, float]] = []
    for spec in getattr(args, "min_safe_rate", []):
        try:
            minimums.append(parse_min_safe_rate(spec))
        except ValueError as e:
            _die(str(e))
    if not 0 < args.target < 1:
        _die(f"--target must be between 0 and 1, got {args.target}")
    segment_by = None if args.segment_by == "none" else args.segment_by
    if segment_by not in (None, "label") and not re.fullmatch(r"meta\.[A-Za-z0-9_]+",
                                                              segment_by):
        _die(f"--segment-by expects label, meta.FIELD or none, got {args.segment_by!r}")
    result = _audit(judge, rows, args, dataset_meta)
    done = result.completeness
    wanted = [args.target, *(r for r, _ in minimums)]
    extra = [r for r in wanted if not any(abs(r - t) < 1e-12 for t in DEFAULT_TARGETS)]
    if extra or args.target != PRIMARY_TARGET or segment_by != "label":
        # a target, a gate or segments the default certificate does not carry
        result.certificate = certificate_of(
            result.records, groups_of(result.records, rows),
            targets=sorted({*DEFAULT_TARGETS, *extra}), run=result.run,
            primary=args.target, segment_by=segment_by)

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
        _write_or_die(_write_atomic, out, content)
        _write_or_die(_write_json, args.json, result.to_dict())
        if args.judgments:
            _write_or_die(lambda path: write_judgments(result, path), args.judgments)
        confidence = result.confidence
        cost = (f"${result.total_cost_usd:.4f}" if result.total_cost_usd is not None
                else "unknown")
        print(f"{lead}judge={result.judge} n={result.n} "
              f"accuracy={result.accuracy:.1%}{interval(result.accuracy_ci, pct=True)} "
              f"{certificate_summary(result.to_dict())} "
              f"answered={done['answered']}/{done['expected']} "
              f"{'unexpected=' + str(done['unexpected']) + ' ' if done['unexpected'] else ''}"
              f"{'not_sent=' + str(result.not_sent) + ' ' if result.not_sent else ''}"
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
        gate_failures = check_safe_rate(result.certificate, minimums)
        stale = _stale_baseline(args.baseline, result.certificate)
        for note in stale:
            print(f"{lead}note: {note}", file=sys.stderr)
        if args.out:
            content = render_markdown(result)
            if tag:
                content = f"> ⚠️ **{tag}**\n\n" + content
            _write_or_die(_write_atomic, args.out, content)
        if args.json:
            _write_or_die(_write_json, args.json, result.to_dict())
        if args.drift:
            _write_or_die(_write_json, args.drift,
                        {"ok": not failures and not gate_failures, "failures": failures,
                         "gate_failures": gate_failures, "ece": result.ece,
                         "accuracy": result.accuracy, "n": result.n,
                         "baseline": display_path(args.baseline),
                         "max_ece_drift": args.max_ece_drift,
                         "max_acc_drop": args.max_acc_drop,
                         "min_safe_rate": [{"risk": r, "share": sh} for r, sh in minimums],
                         "baseline_rate_stale": stale,
                         "certificate": result.certificate})
        if failures or gate_failures:
            if failures:
                print(f"{lead}DRIFT DETECTED:", file=sys.stderr)
                for fl in failures:
                    print(f"  - {fl}", file=sys.stderr)
            if gate_failures:
                print(f"{lead}BELOW THE MINIMUM (no drift involved; the gate you set):",
                      file=sys.stderr)
                for fl in gate_failures:
                    print(f"  - {fl}", file=sys.stderr)
            sys.exit(1)
        ece = fmt4(result.ece)
        print(f"{lead}OK: no drift (ece={ece}, accuracy={result.accuracy:.1%}, "
              f"{certificate_summary(result.to_dict())}, "
              f"gt={ground_truth_of(result.run).tier})")


if __name__ == "__main__":
    main()
