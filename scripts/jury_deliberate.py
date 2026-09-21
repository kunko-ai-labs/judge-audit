"""Round 2 of the jury-consensus audit: one judge re-votes after seeing the panel.

Builds a deliberation dataset — the original rows with the other judges'
round-1 votes (anonymised, shuffled) appended to `state` — and runs the
resumable driver on it, so the judge, the prompt path and the checkpoint
format are exactly those of round 1. Protocol pre-registered in
docs/jury-consensus-plan.md; reported by scripts/jury_report.py.

  scripts/arena_run.sh-style env for the judge, then:
  python scripts/jury_deliberate.py router-bare claude-sonnet-4.5 --judge llm

Writes docs/runs/jury/<dataset>/<slug>.r2.input.jsonl (what the judge saw)
and docs/runs/jury/<dataset>/<slug>.r2.ckpt.jsonl (what it answered).
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import DATASETS  # noqa: E402
from consensus_report import votes_of  # noqa: E402

JURY = ROOT / "docs" / "runs" / "jury"
SEED = 2026
PREAMBLE = ("\n\n--- Deliberation round ---\n"
            "{k} other judges assessed this same task independently. Their votes:\n{votes}\n"
            "You may keep or revise your answer. Give your own decision and confidence.")


def deliberation_rows(dataset: str, slug: str) -> tuple[list[dict], list[str]]:
    """Original rows + the panel's round-1 votes (minus this judge) in `state`."""
    votes, rows = votes_of(dataset)
    panel = [j for j in votes if j != slug]
    out = []
    for idx, row in enumerate(rows):
        order = list(panel)
        random.Random(f"{SEED}:{idx}").shuffle(order)
        lines = [f"- Judge {chr(65 + k)}: {votes[j][idx]['decision']} "
                 f"(confidence {votes[j][idx]['confidence']:.2f})" for k, j in enumerate(order)]
        new = dict(row)
        new["state"] = row["state"] + PREAMBLE.format(k=len(order), votes="\n".join(lines))
        new["_meta"] = dict(row.get("_meta", {}), round=2, panel_seen=order)
        out.append(new)
    return out, panel


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=sorted(DATASETS))
    ap.add_argument("slug", help="arena slug of the judge being re-run (docs/runs/arena/<slug>)")
    ap.add_argument("--judge", default="llm", help="adapter name for the CLI (jev, llm, ...)")
    ap.add_argument("--dry-run", action="store_true", help="write the input file only")
    a = ap.parse_args()
    out = JURY / a.dataset
    out.mkdir(parents=True, exist_ok=True)
    rows, panel = deliberation_rows(a.dataset, a.slug)
    inp = out / f"{a.slug}.r2.input.jsonl"
    inp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{a.dataset}/{a.slug}: panel shown = {panel}; input -> {inp.relative_to(ROOT)}")
    if a.dry_run:
        return
    cmd = [sys.executable, str(ROOT / "scripts" / "audit_resumable.py"), str(inp),
           "--judge", a.judge, "--checkpoint", str(out / f"{a.slug}.r2.ckpt.jsonl"),
           "--out", str(out / f"{a.slug}.r2.md"), "--json", str(out / f"{a.slug}.r2.json")]
    sys.exit(subprocess.call(cmd, cwd=ROOT))


if __name__ == "__main__":
    main()
