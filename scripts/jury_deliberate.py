"""Round 2 of the jury-consensus audit: one judge re-votes after seeing the panel.

Builds a deliberation dataset — the original rows with the other judges'
round-1 votes (anonymised, shuffled) appended to `state` — and runs the
resumable driver on it, so the judge, the prompt path and the checkpoint
format are exactly those of round 1. Protocol pre-registered in
docs/jury-consensus-plan.md; reported by scripts/jury_report.py.

  scripts/arena_run.sh-style env for the judge, then:
  python scripts/jury_deliberate.py router-bare claude-sonnet-4.5 --judge llm
  python scripts/jury_deliberate.py --check      # committed inputs regenerate byte-identical (CI)

The panel is frozen in docs/runs/jury/panel.json so a judge joining the
Arena later cannot change what round-2 judges saw. A blank (unparseable)
round-1 answer is an abstention and is not shown. Writes
docs/runs/jury/<dataset>/<slug>.r2.input.jsonl (what the judge saw) and
docs/runs/jury/<dataset>/<slug>.r2.ckpt.jsonl (what it answered).
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import DATASETS  # noqa: E402
from consensus_report import votes_of  # noqa: E402

from judge_audit.runner import read_dataset_header  # noqa: E402

JURY = ROOT / "docs" / "runs" / "jury"
PANEL_FILE = JURY / "panel.json"
SEED = 2026
PREAMBLE = ("\n\n--- Deliberation round ---\n"
            "{k} other judge{s} assessed this same task independently. Their votes:\n{votes}\n"
            "You may keep or revise your answer. Give your own decision and confidence.")
PREAMBLE_NONE = ("\n\n--- Deliberation round ---\n"
                 "Other judges assessed this same task independently; none of them gave an answer.\n"
                 "You may keep or revise your answer. Give your own decision and confidence.")


def frozen_panel() -> list[str]:
    return json.loads(PANEL_FILE.read_text(encoding="utf-8"))["panel"]


def deliberation_rows(dataset: str, slug: str, panel: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Original rows + the frozen panel's round-1 votes (minus this judge) in `state`.

    Blank round-1 answers are abstentions: not shown, not listed in panel_seen."""
    votes, rows = votes_of(dataset)
    panel = [j for j in (panel or frozen_panel()) if j != slug]
    missing = [j for j in panel if j not in votes]
    if missing:
        raise SystemExit(f"{dataset}: no complete round-1 run for {missing}")
    out = []
    for idx, row in enumerate(rows):
        order = [j for j in panel if votes[j][idx]["decision"].strip()]
        random.Random(f"{SEED}:{idx}").shuffle(order)
        lines = [f"- Judge {chr(65 + k)}: {votes[j][idx]['decision']} "
                 f"(confidence {votes[j][idx]['confidence']:.2f})" for k, j in enumerate(order)]
        text = (PREAMBLE.format(k=len(order), s="" if len(order) == 1 else "s", votes="\n".join(lines))
                if order else PREAMBLE_NONE)
        new = dict(row)
        new["state"] = row["state"] + text
        new["_meta"] = dict(row.get("_meta", {}), round=2, panel_seen=order)
        out.append(new)
    return out, panel


def input_text(dataset: str, rows: list[dict]) -> str:
    """The round-2 labels file: the source dataset's header (ground-truth tier), then the rows."""
    header = read_dataset_header(str(ROOT / DATASETS[dataset][0]))
    lines = [json.dumps({"idx": -1, "dataset": header}, ensure_ascii=False)] if header else []
    lines += [json.dumps(r, ensure_ascii=False) for r in rows]
    return "".join(line + "\n" for line in lines)


def check() -> int:
    """Every committed round-2 input regenerates byte-identical from the frozen panel."""
    bad = 0
    for inp in sorted(JURY.glob("*/*.r2.input.jsonl")):
        dataset, slug = inp.parent.name, inp.name[: -len(".r2.input.jsonl")]
        rows, _ = deliberation_rows(dataset, slug)
        want = input_text(dataset, rows)
        if inp.read_text(encoding="utf-8") != want:
            print(f"STALE {inp}")
            bad += 1
    print(f"{bad} stale round-2 input(s)")
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", nargs="?", choices=sorted(DATASETS))
    ap.add_argument("slug", nargs="?", help="arena slug of the judge being re-run (docs/runs/arena/<slug>)")
    ap.add_argument("--judge", default="llm", help="adapter name for the CLI (jev, llm, ...)")
    ap.add_argument("--dry-run", action="store_true", help="write the input file only")
    ap.add_argument("--check", action="store_true", help="verify committed inputs regenerate identically")
    a = ap.parse_args()
    if a.check:
        sys.exit(check())
    if not (a.dataset and a.slug):
        ap.error("dataset and slug are required unless --check")
    out = JURY / a.dataset
    out.mkdir(parents=True, exist_ok=True)
    rows, panel = deliberation_rows(a.dataset, a.slug)
    inp = out / f"{a.slug}.r2.input.jsonl"
    inp.write_text(input_text(a.dataset, rows), encoding="utf-8")
    print(f"{a.dataset}/{a.slug}: panel shown = {panel}; input -> {inp.relative_to(ROOT)}")
    if a.dry_run:
        return
    cmd = [sys.executable, str(ROOT / "scripts" / "audit_resumable.py"), str(inp),
           "--judge", a.judge, "--checkpoint", str(out / f"{a.slug}.r2.ckpt.jsonl"),
           "--out", str(out / f"{a.slug}.r2.md"), "--json", str(out / f"{a.slug}.r2.json")]
    sys.exit(subprocess.call(cmd, cwd=ROOT))


if __name__ == "__main__":
    main()
