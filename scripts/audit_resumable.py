"""Resumable audit driver: one row at a time, checkpointed to JSONL.

Long vendor audits hit rate limits and transient errors; re-running from
scratch wastes money and time. This driver appends each row's judgments to
a checkpoint file and skips rows already done, so an interrupted run resumes
where it left off.

Usage:
  python scripts/audit_resumable.py LABELS --judge jev --checkpoint CKPT.jsonl \
      --out docs/audit-jev-real.md --json docs/audit-jev-real.json [--html docs/audit-jev-real.html]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from judge_audit.cli import _judge  # noqa: E402
from judge_audit.judges.base import Question, QuestionType  # noqa: E402
from judge_audit.metrics.calibration import (  # noqa: E402
    accuracy_coverage,
    expected_calibration_error,
    reliability_bins,
    zero_error_coverage,
)
from judge_audit.report import render_html, render_markdown  # noqa: E402
from judge_audit.runner import AuditResult, _percentile, load_jsonl  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels")
    ap.add_argument("--judge", default="jev")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", default=None)
    args = ap.parse_args()

    rows = load_jsonl(args.labels)
    judge, tag = _judge(args.judge, rows)

    ckpt = Path(args.checkpoint)
    done: dict[int, list[dict]] = {}
    if ckpt.exists():
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["idx"]] = rec["judgments"]
    print(f"checkpoint: {len(done)}/{len(rows)} rows already done")

    with open(ckpt, "a", encoding="utf-8") as f:
        for idx, row in enumerate(rows):
            if idx in done:
                continue
            questions = [Question(name=q["name"],
                                  type=QuestionType(q.get("type", "choice")),
                                  instructions=q.get("instructions", ""),
                                  options=q.get("options", []))
                         for q in row["questions"]]
            # If the gateway's rate-limit window outlasts the adapter's backoff,
            # sleep it off and retry instead of losing the whole run.
            for attempt in range(4):
                try:
                    judgments = judge.decide(row["state"], questions)
                    break
                except Exception as e:
                    if "rate-limited" in str(e).lower() and attempt < 3:
                        wait = (attempt + 1) * 600
                        print(f"  rate-limited at row {idx}; sleeping {wait}s "
                              f"(attempt {attempt + 1}/3)", flush=True)
                        time.sleep(wait)
                    else:
                        raise
            rec = {"idx": idx,
                   "judgments": [{"question": j.question, "decision": j.decision,
                                  "confidence": j.confidence, "latency_s": j.latency_s,
                                  "cost_usd": j.cost_usd, "raw": j.raw}
                                 for j in judgments]}
            f.write(json.dumps(rec) + "\n")
            f.flush()
            done[idx] = rec["judgments"]
            if (idx + 1) % 10 == 0:
                print(f"  {idx + 1}/{len(rows)}", flush=True)

    confidences, correct, latencies = [], [], []
    cost, hits, total = 0.0, 0, 0
    for idx, row in enumerate(rows):
        labels = row.get("labels", {})
        for j in done[idx]:
            expected = labels.get(j["question"])
            if expected is None:
                continue
            ok = str(j["decision"]).strip().lower() == str(expected).strip().lower()
            confidences.append(max(0.0, min(1.0, j["confidence"])))
            correct.append(ok)
            latencies.append(j["latency_s"])
            cost += j["cost_usd"]
            hits += ok
            total += 1

    result = AuditResult(
        judge=judge.name, n=total,
        accuracy=round(hits / total, 4) if total else 0.0,
        ece=round(expected_calibration_error(confidences, correct), 4),
        reliability=reliability_bins(confidences, correct),
        curve=accuracy_coverage(confidences, correct),
        zero_error=zero_error_coverage(confidences, correct),
        total_cost_usd=cost,
        p50_latency_s=_percentile(latencies, 50),
        p99_latency_s=_percentile(latencies, 99),
    )
    md = render_markdown(result)
    if args.judge == "jev":
        md = ("> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway "
              "(not simulated).\n\n" + md)
    elif tag:
        md = f"> ⚠️ **{tag}**\n\n" + md
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.json).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_html(result), encoding="utf-8")
    print(f"judge={result.judge} n={result.n} accuracy={result.accuracy:.1%} "
          f"ece={result.ece:.4f} cost=${result.total_cost_usd:.4f} -> {args.out}")


if __name__ == "__main__":
    main()
