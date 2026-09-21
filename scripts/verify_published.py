"""Recompute every published audit from its raw checkpoint; fail if the numbers drift.

This is the house rule made executable: docs/audit-*.json must be re-derivable
from docs/runs/*.ckpt.jsonl and examples/*/labels.jsonl. No API call is made.

A checkpoint header that records the dataset's sha256 must still match the
labels file: either the whole file or its rows alone (the dataset header line
that declares the ground-truth tier is not part of the rows a judge saw).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import (  # noqa: E402
    is_correct,
    load_jsonl,
    sha256_of,
    sha256_rows_of,
    summarize,
)

# Arena checkpoints (docs/runs/arena/<judge>/<dataset>.ckpt.jsonl) -> labels file
ARENA_DATASETS = {
    "email-clean": "examples/email-routing/labels.jsonl",
    "email-adversarial": "examples/email-routing-adversarial/labels.jsonl",
    "router-bare": "examples/task-routing/labels.jsonl",
    "router-described": "examples/task-routing/labels-described.jsonl",
}

# (labels, checkpoint, published json, question name, keys to compare)
PUBLISHED = [
    ("examples/email-routing/labels.jsonl", "docs/runs/audit-jev-real.ckpt.jsonl",
     "docs/audit-jev-real.json", "category", ("n", "accuracy", "ece", "total_cost_usd")),
    ("examples/email-routing-adversarial/labels.jsonl",
     "docs/runs/audit-jev-adversarial.ckpt.jsonl",
     "docs/audit-jev-adversarial.json", "category", ("n", "accuracy", "ece", "total_cost_usd")),
    ("examples/task-routing/labels.jsonl", "docs/runs/audit-jev-router.ckpt.jsonl",
     "docs/audit-jev-router.json", "route", ("n",)),
    ("examples/task-routing/labels-described.jsonl",
     "docs/runs/audit-jev-router-described.ckpt.jsonl",
     "docs/audit-jev-router-described.json", "route", ("n",)),
]


def recompute(labels_path: Path, ckpt_path: Path, question: str):
    rows = load_jsonl(str(labels_path))
    records = []
    for line in ckpt_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            continue
        row = rows[rec["idx"]]
        expected = row["labels"][question]
        j = next(x for x in rec["judgments"] if x["question"] == question)
        records.append({"confidence": max(0.0, min(1.0, float(j["confidence"]))),
                        "correct": is_correct(j["decision"], expected),
                        "latency_s": j.get("latency_s", 0.0),
                        "cost_usd": j.get("cost_usd", 0.0)})
    return summarize("recomputed", records).to_dict()


def recorded_sha256(ckpt_path: Path) -> str | None:
    """The dataset sha256 in the checkpoint's run header, None when not recorded."""
    with ckpt_path.open(encoding="utf-8") as f:
        first = f.readline()
    rec = json.loads(first) if first.strip() else {}
    if rec.get("idx") != -1:
        return None
    return (rec.get("run", {}).get("dataset") or {}).get("sha256")


def dataset_mismatch(labels_path: Path, ckpt_path: Path) -> str | None:
    """A message when the checkpoint names a dataset digest the labels file no longer has."""
    recorded = recorded_sha256(ckpt_path)
    if recorded is None:
        return None
    whole, rows = sha256_of(str(labels_path)), sha256_rows_of(str(labels_path))
    if recorded in (whole, rows):
        return None
    return (f"dataset sha256: checkpoint recorded {recorded[:12]}…, labels file is "
            f"{whole[:12]}… (rows only {rows[:12]}…)")


def main() -> int:
    bad = 0
    for labels, ckpt, published, question, keys in PUBLISHED:
        lp, cp, pp = ROOT / labels, ROOT / ckpt, ROOT / published
        if not pp.exists():
            print(f"skip  {published} (not published yet)")
            continue
        if not cp.exists():
            print(f"FAIL  {published}: checkpoint {ckpt} missing — a report without evidence")
            bad += 1
            continue
        got = recompute(lp, cp, question)
        pub = json.loads(pp.read_text(encoding="utf-8"))
        # router reports nest the headline under "overall"
        head = pub.get("overall", pub)
        diffs = []
        mismatch = dataset_mismatch(lp, cp)
        if mismatch:
            diffs.append(mismatch)
        for k in keys:
            a, b = head.get(k), got.get(k)
            if a is None or b is None:
                diffs.append(f"{k}: missing ({a!r} vs {b!r})")
            elif abs(float(a) - float(b)) > 1e-4:
                diffs.append(f"{k}: published {a} vs recomputed {b}")
        if "accuracy" in head and "accuracy" not in keys:
            if abs(float(head["accuracy"]) - got["accuracy"]) > 1e-4:
                diffs.append(f"accuracy: published {head['accuracy']} vs recomputed {got['accuracy']}")
        if diffs:
            bad += 1
            print(f"FAIL  {published}")
            for d in diffs:
                print(f"        {d}")
        else:
            print(f"ok    {published}  n={got['n']} acc={got['accuracy']} ece={got['ece']}")
    # Arena checkpoints carry no published JSON of their own (arena_report.py regenerates
    # the table and CI diffs it) but they do name the dataset they were run on.
    for cp in sorted((ROOT / "docs" / "runs" / "arena").glob("*/*.ckpt.jsonl")):
        labels = ARENA_DATASETS.get(cp.name.removesuffix(".ckpt.jsonl"))
        mismatch = dataset_mismatch(ROOT / labels, cp) if labels else None
        if mismatch:
            bad += 1
            print(f"FAIL  {cp.relative_to(ROOT)}\n        {mismatch}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
