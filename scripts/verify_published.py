"""Recompute every published audit from its raw checkpoint; fail if the numbers drift.

This is the house rule made executable: docs/audit-*.json must be re-derivable
from docs/runs/*.ckpt.jsonl and examples/*/labels.jsonl. No API call is made.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import is_correct, load_jsonl, summarize  # noqa: E402

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
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
