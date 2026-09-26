"""Every committed checkpoint answers every labelled question of every row it covers, once.

The live runner counts a skipped question as a wrong no-answer (US-004-015); a report rebuilt
from a checkpoint reads only the judgments the checkpoint holds. This check closes that gap:
a checkpoint with a row missing or written twice, a labelled question unanswered or answered
twice, or a blank label fails CI,
so no published number rests on a denominator that quietly shrank.

  python scripts/check_complete.py      # exit 1 listing each gap
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import answer_gaps, load_jsonl  # noqa: E402

# The three first audits predate run headers; their dataset is fixed by name.
LEGACY = {"audit-jev-real.ckpt.jsonl": "examples/email-routing/labels.jsonl",
          "audit-jev-adversarial.ckpt.jsonl": "examples/email-routing-adversarial/labels.jsonl",
          "audit-jev-router.ckpt.jsonl": "examples/task-routing/labels.jsonl"}


def gaps(ckpt: Path) -> list[str]:
    lines = [json.loads(x) for x in ckpt.read_text(encoding="utf-8").splitlines() if x.strip()]
    headers = [x["run"] for x in lines if x["idx"] == -1]
    run = headers[-1] if headers else {}  # the readers take the last header
    labels = (run.get("dataset") or {}).get("path") or LEGACY.get(ckpt.name)
    if not labels:
        return [f"{ckpt}: no dataset path in the header and no legacy mapping"]
    rows = load_jsonl(str(ROOT / labels))
    subset = run.get("rows_subset")
    if subset:
        wanted = sorted(json.loads((ROOT / subset["split"]).read_text())[subset["part"]])
    else:
        wanted = list(range(len(rows)))
    # Every reader counts every row line, so a row written twice is counted twice: a gap.
    seen: dict[int, int] = {}
    for x in lines:
        if x["idx"] >= 0:
            seen[x["idx"]] = seen.get(x["idx"], 0) + 1
    done = {x["idx"]: x for x in lines if x["idx"] >= 0}
    out = [f"{ckpt}: row {i} written {k} times" for i, k in sorted(seen.items()) if k > 1]
    out += [f"{ckpt}: row {i} missing" for i in wanted if i not in done]
    for i in wanted:
        if i in done:
            g = answer_gaps(rows[i], [j["question"] for j in done[i]["judgments"]])
            out += [f"{ckpt}: row {i} {kind} {names}" for kind, names in g.items()
                    if names and kind != "unexpected"]
    return out


def main() -> None:
    ckpts = sorted((ROOT / "docs" / "runs").rglob("*.ckpt.jsonl"))
    found = [g for c in ckpts for g in gaps(c)]
    for g in found:
        print("GAP", g)
    print(f"{len(ckpts)} checkpoints checked, {len(found)} gap(s)")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
