"""Resumable audit driver: one row at a time, checkpointed to JSONL.

Long vendor audits hit rate limits and transient errors; re-running from
scratch wastes money and time. This driver appends each row's judgments to
a checkpoint file and skips rows already done, so an interrupted run resumes
where it left off. The checkpoint IS the raw evidence: commit it under
docs/runs/ next to the report so anyone can re-derive every number.

Usage:
  python scripts/audit_resumable.py LABELS --judge jev --checkpoint docs/runs/NAME.ckpt.jsonl \\
      --out docs/audit-NAME.md --json docs/audit-NAME.json [--html docs/audit-NAME.html]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from judge_audit import __version__  # noqa: E402
from judge_audit.cli import _judge  # noqa: E402
from judge_audit.ground_truth import parse_ground_truth  # noqa: E402
from judge_audit.judges.simulated import SIMULATED_TAG  # noqa: E402
from judge_audit.report import render_html, render_markdown  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    is_correct,
    load_dataset,
    questions_of,
    run_metadata,
    summarize,
)

REAL_BANNER = ("> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway (not simulated). "
               "Raw per-row responses: see the checkpoint file named in the provenance line.\n\n")


def load_checkpoint(path: Path) -> dict[int, dict]:
    done: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["idx"]] = rec
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels")
    ap.add_argument("--judge", default="jev")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", default=None)
    args = ap.parse_args()

    rows, dataset_meta = load_dataset(args.labels)
    ckpt = Path(args.checkpoint)
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    done = load_checkpoint(ckpt)
    n_done = sum(k >= 0 for k in done)
    print(f"checkpoint: {n_done}/{len(rows)} rows already done")

    if n_done >= len(rows):
        # Complete checkpoint: recompute only. No key, no judge, no API call.
        judge, tag = None, ("" if args.judge == "jev" else SIMULATED_TAG)
        started = {"judge": {"name": args.judge, "model": "typesafe-ai/jev", "backend": "gateway"}
                   if args.judge == "jev" else {"name": args.judge},
                   "judge_audit_version": __version__,
                   "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    else:
        judge, tag = _judge(args.judge, rows)
        started = run_metadata(judge, args.labels, len(rows), dataset_meta)

    with open(ckpt, "a", encoding="utf-8") as f:
        if not done:
            # First line of a fresh checkpoint: how this run was produced.
            f.write(json.dumps({"idx": -1, "run": started}) + "\n")
        for idx, row in enumerate(rows):
            if idx in done:
                continue
            # If the gateway's rate-limit window outlasts the adapter's backoff,
            # or a call stalls (timeout), sleep it off and retry instead of
            # losing the whole run.
            for attempt in range(4):
                try:
                    judgments = judge.decide(row["state"], questions_of(row))
                    break
                except Exception as e:
                    transient = ("rate-limited" in str(e).lower()
                                 or "timeout" in type(e).__name__.lower()
                                 or "timed out" in str(e).lower())
                    if transient and attempt < 3:
                        wait = (attempt + 1) * 600
                        print(f"  transient error at row {idx} "
                              f"({type(e).__name__}); sleeping {wait}s "
                              f"(attempt {attempt + 1}/3)", flush=True)
                        time.sleep(wait)
                    else:
                        raise
            rec = {"idx": idx,
                   "judgments": [{"question": j.question, "decision": j.decision,
                                  "confidence": j.confidence, "latency_s": j.latency_s,
                                  "cost_usd": j.cost_usd, "raw": j.raw}
                                 for j in judgments]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            done[idx] = rec
            if (idx + 1) % 10 == 0:
                print(f"  {idx + 1}/{len(rows)}", flush=True)

    if -1 in done:
        run = done[-1]["run"]
    else:
        # Checkpoint predates run headers: say so instead of inventing a timestamp.
        run = {k: v for k, v in started.items() if k != "timestamp_utc"}
        run["recomputed_utc"] = started["timestamp_utc"]
        run["note"] = "original run time not recorded in this checkpoint"
    run["checkpoint"] = str(ckpt)
    # The tier is a property of the dataset, not of the run: read it from the labels
    # file so a checkpoint that predates ground-truth headers still reports it.
    run.setdefault("dataset", {})["ground_truth"] = parse_ground_truth(
        dataset_meta.get("ground_truth")).to_dict()
    records = []
    for idx, row in enumerate(rows):
        labels = row.get("labels", {})
        for j in done[idx]["judgments"]:
            expected = labels.get(j["question"])
            if expected is None:
                continue
            records.append({
                "idx": idx, "question": j["question"], "expected": str(expected),
                "decision": str(j["decision"]),
                "correct": is_correct(j["decision"], expected),
                "confidence": max(0.0, min(1.0, float(j["confidence"]))),
                "latency_s": j.get("latency_s", 0.0), "cost_usd": j.get("cost_usd", 0.0),
                "meta": row.get("_meta", {}), "raw": j.get("raw", {}),
            })

    result = summarize(args.judge, records, run)
    md = render_markdown(result)
    if args.judge == "jev":
        md = REAL_BANNER + md
    elif tag:
        md = f"> ⚠️ **{tag}**\n\n" + md
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.json).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_html(result, tag=tag), encoding="utf-8")
    print(f"judge={result.judge} n={result.n} accuracy={result.accuracy:.1%} "
          f"ece={result.ece:.4f} gt={run['dataset']['ground_truth']['tier']} "
          f"cost=${result.total_cost_usd:.4f} -> {args.out}")


if __name__ == "__main__":
    main()
