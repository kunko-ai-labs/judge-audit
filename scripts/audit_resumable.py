"""Resumable audit driver: one row at a time, checkpointed to JSONL.

Long vendor audits hit rate limits and transient errors; re-running from
scratch wastes money and time. This driver appends each row's judgments to
a checkpoint file and skips rows already done, so an interrupted run resumes
where it left off. The checkpoint IS the raw evidence: commit it under
docs/runs/ next to the report so anyone can re-derive every number.

Usage:
  python scripts/audit_resumable.py LABELS --judge jev --checkpoint docs/runs/NAME.ckpt.jsonl \\
      --out docs/audit-NAME.md --json docs/audit-NAME.json [--html docs/audit-NAME.html]

`--rows examples/<dataset>/split-heldout.json:heldout` judges only the row
indices that part of a pre-registered split names; the checkpoint header then
records the split file, its sha256, the part and its size under `rows_subset`,
and the report's n is the subset's. A run without `--rows` judges every row.
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
from judge_audit.report import fmt4, render_html, render_markdown  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    AuditResult,
    checkpoint_record,
    display_path,
    groups_of,
    load_dataset,
    questions_of,
    run_metadata,
    sha256_of,
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


def rows_subset(spec: str | None, n_rows: int) -> tuple[list[int], dict | None]:
    """Row indices to judge from `<split.json>:<part>`; (all rows, None) without a spec."""
    if not spec:
        return list(range(n_rows)), None
    path, sep, part = spec.rpartition(":")
    if not sep or not part:
        raise SystemExit(f"--rows expects <split.json>:<part>, got {spec!r}")
    split = json.loads(Path(path).read_text(encoding="utf-8"))
    if part not in split or not isinstance(split[part], list):
        raise SystemExit(f"{path}: no row list named {part!r}")
    idx = sorted(int(i) for i in split[part])
    if idx and (idx[0] < 0 or idx[-1] >= n_rows):
        raise SystemExit(f"{path}:{part} names rows outside 0..{n_rows - 1}")
    return idx, {"split": path, "sha256": sha256_of(path), "part": part, "n": len(idx)}


def build_result(judge_name: str, rows: list[dict], dataset_meta: dict, wanted: list[int],
                 done: dict[int, dict], ckpt: Path, started: dict,
                 subset: dict | None, cluster_rows: list[dict] | None = None) -> AuditResult:
    """The report of a complete checkpoint: pure function of the checkpoint and the labels.

    `scripts/runs_report.py` calls this same function to regenerate every committed
    per-run report, so a fresh run and a regeneration write the same bytes.
    `cluster_rows` supplies the bootstrap's cluster texts when they are not the judged
    rows' own: a deliberation dataset clusters on the original texts, as jury_report does.
    """
    if -1 in done:
        run = dict(done[-1]["run"])
    else:
        # Checkpoint predates run headers: say so instead of inventing a timestamp.
        run = {k: v for k, v in started.items() if k != "timestamp_utc"}
        run["recomputed_utc"] = started["timestamp_utc"]
        run["note"] = "original run time not recorded in this checkpoint"
    run["checkpoint"] = display_path(ckpt)
    # The tier is a property of the dataset, not of the run: read it from the labels
    # file so a checkpoint that predates ground-truth headers still reports it.
    run["dataset"] = dict(run.get("dataset") or {})
    run["dataset"]["ground_truth"] = parse_ground_truth(
        dataset_meta.get("ground_truth")).to_dict()
    if subset:
        run["rows_subset"] = subset
    records = []
    # Checkpoint order — the order the judge answered, which a resumed run does not keep
    # sorted — as the Arena and jury tables read it, so their intervals (seeded bootstrap
    # over clusters in first-seen order) are the same numbers as this report's.
    chosen = set(wanted)
    for idx in [k for k in done if k in chosen]:
        row = rows[idx]
        labels = row.get("labels", {})
        for j in done[idx]["judgments"]:
            expected = labels.get(j["question"])
            if expected is None:
                continue
            records.append(checkpoint_record(idx, row, j, expected, run))
    # Intervals resample distinct texts, as every published interval does (the report
    # says so); without `groups` they would silently be row-i.i.d. and too narrow.
    return summarize(judge_name, records, run,
                     groups=groups_of(records, cluster_rows or rows))


def recorded_judge(done: dict[int, dict]) -> str | None:
    """The adapter name the checkpoint's header recorded (`llm` for `llm:gemma4:e4b`)."""
    if -1 not in done:
        return None
    name = (done[-1]["run"].get("judge") or {}).get("name")
    return str(name).split(":")[0] if name else None


def tag_of(judge_name: str) -> str:
    """The banner a report of this judge carries: only the simulated judge is fake."""
    return SIMULATED_TAG if judge_name == "simulated" else ""


def report_markdown(result: AuditResult, judge_name: str) -> str:
    md = render_markdown(result)
    if judge_name == "jev":
        return REAL_BANNER + md
    tag = tag_of(judge_name)
    return f"> ⚠️ **{tag}**\n\n" + md if tag else md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels")
    ap.add_argument("--judge", default="jev")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", default=None)
    ap.add_argument("--rows", default=None,
                    help="<split.json>:<part> — judge only these row indices (held-out runs)")
    ap.add_argument("--cluster-labels", default=None,
                    help="labels file whose row texts are the interval's clusters (default: "
                         "LABELS; a deliberation round passes the original dataset)")
    args = ap.parse_args()

    rows, dataset_meta = load_dataset(args.labels)
    wanted, subset = rows_subset(args.rows, len(rows))
    ckpt = Path(args.checkpoint)
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    done = load_checkpoint(ckpt)
    if -1 in done:
        was = done[-1]["run"].get("rows_subset") or {}
        now = subset or {}
        if (was.get("sha256"), was.get("part")) != (now.get("sha256"), now.get("part")):
            raise SystemExit(f"{ckpt} was started with a different --rows subset; "
                             "use a new checkpoint")
    n_done = sum(k in done for k in wanted)
    print(f"checkpoint: {n_done}/{len(wanted)} rows already done"
          + (f" (subset {subset['part']} of {subset['split']})" if subset else ""))

    # Who answered is what the checkpoint recorded, not what this command line says: a
    # simulated checkpoint recomputed with `--judge llm` is still a simulation.
    name = recorded_judge(done) or args.judge
    if n_done >= len(wanted):
        # Complete checkpoint: recompute only. No key, no judge, no API call.
        judge, tag = None, tag_of(name)
        started = {"judge": {"name": name, "model": "typesafe-ai/jev", "backend": "gateway"}
                   if name == "jev" else {"name": name},
                   "judge_audit_version": __version__,
                   "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    else:
        if name != args.judge:
            raise SystemExit(f"{ckpt} was started by judge {name!r}, not {args.judge!r}; "
                             "use a new checkpoint")
        judge, tag = _judge(args.judge, rows)
        started = run_metadata(judge, args.labels, len(rows), dataset_meta)
    if subset:
        started["rows_subset"] = subset

    with open(ckpt, "a", encoding="utf-8") as f:
        if not done:
            # First line of a fresh checkpoint: how this run was produced.
            header = {"idx": -1, "run": started}
            f.write(json.dumps(header) + "\n")
            done[-1] = header  # the report reads the run time from here, as a rerun would
        for idx in wanted:
            row = rows[idx]
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
                                  "cost_usd": j.cost_usd, "raw": j.raw,
                                  "parse_status": j.parse_status}
                                 for j in judgments]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            done[idx] = rec
            n_done += 1
            if n_done % 10 == 0:
                print(f"  {n_done}/{len(wanted)}", flush=True)

    cluster_rows = load_dataset(args.cluster_labels)[0] if args.cluster_labels else None
    result = build_result(name, rows, dataset_meta, wanted, done, ckpt, started, subset,
                          cluster_rows)
    md = report_markdown(result, name)
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.json).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_html(result, tag=tag), encoding="utf-8")
    confidence = result.confidence
    cost = f"${result.total_cost_usd:.4f}" if result.total_cost_usd is not None else "unknown"
    print(f"judge={result.judge} n={result.n} accuracy={result.accuracy:.1%} "
          f"confidence_known={confidence['known']}/{confidence['total']} "
          f"ece={fmt4(result.ece)} ece_equal_mass={fmt4(result.ece_equal_mass)} "
          f"brier={fmt4(result.brier)} gt={result.run['dataset']['ground_truth']['tier']} "
          f"cost={cost} -> {args.out}")


if __name__ == "__main__":
    main()
