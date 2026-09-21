"""Pre-registered held-out split: seeded, label-stratified 50/50 over row indices.

The fine-tuned classifier baseline (docs/finetuned-baseline-2026-09.md) trains
on one half of a dataset and is evaluated on the other. The split is decided
here, once, from a fixed seed, and committed *before* any training run — so
nobody (human or agent) can pick the half that looks best. CI regenerates the
files and fails if they differ.

Stratification: every label is split 50/50; for the router the stratum also
carries `_meta.difficulty` and `_meta.adversarial`, so both halves hold the
same number of hard tasks and of cost-inflation attacks. Within a stratum the
rows are shuffled with `random.Random(seed)` seeded once per dataset; the
first half of each stratum (ceil) goes to `heldout`, the rest to `train`.

The two router files (`labels.jsonl`, `labels-described.jsonl`) share states
and labels row for row, so they share one split.

  python scripts/split_heldout.py            # writes examples/*/split-heldout.json
  python scripts/split_heldout.py --check    # exit 1 if a committed split differs
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import load_jsonl, sha256_rows_of  # noqa: E402

SEED = 2026
# dataset -> (labels file, question, extra _meta keys that join the stratum)
SPLITS = {
    "email-routing": ("examples/email-routing/labels.jsonl", "category", ()),
    "task-routing": ("examples/task-routing/labels.jsonl", "route", ("difficulty", "adversarial")),
}


def stratum_of(row: dict, question: str, meta_keys: tuple[str, ...]) -> str:
    parts = [str(row["labels"][question])]
    parts += [f"{k}={row.get('_meta', {}).get(k)}" for k in meta_keys]
    return "|".join(parts)


def split_rows(rows: list[dict], question: str, meta_keys: tuple[str, ...],
               seed: int = SEED) -> tuple[list[int], list[int]]:
    """(train, heldout) row indices, each sorted; every stratum split in half."""
    strata: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        strata[stratum_of(row, question, meta_keys)].append(idx)
    rng = random.Random(seed)
    train: list[int] = []
    heldout: list[int] = []
    for key in sorted(strata):  # sorted: the shuffle order does not depend on file order
        members = list(strata[key])
        rng.shuffle(members)
        half = (len(members) + 1) // 2
        heldout += members[:half]
        train += members[half:]
    return sorted(train), sorted(heldout)


def build(dataset: str) -> dict:
    labels, question, meta_keys = SPLITS[dataset]
    rows = load_jsonl(str(ROOT / labels))
    train, heldout = split_rows(rows, question, meta_keys)
    counts = defaultdict(lambda: {"train": 0, "heldout": 0})
    for idx in train:
        counts[stratum_of(rows[idx], question, meta_keys)]["train"] += 1
    for idx in heldout:
        counts[stratum_of(rows[idx], question, meta_keys)]["heldout"] += 1
    return {
        "dataset": dataset, "labels": labels, "question": question,
        "method": "label-stratified 50/50, random.Random(seed) per dataset, "
                  "strata sorted, first ceil(half) of each stratum held out",
        "seed": SEED, "strata_keys": ["label", *meta_keys],
        "sha256_rows": sha256_rows_of(str(ROOT / labels)),
        "n": len(rows), "n_train": len(train), "n_heldout": len(heldout),
        "strata": {k: counts[k] for k in sorted(counts)},
        "train": train, "heldout": heldout,
    }


def dumps(split: dict) -> str:
    """Pretty JSON with the two index lists on one line each (diff-friendly)."""
    text = json.dumps(split, indent=1)
    return re.sub(r'\[\s+((?:\d+,\s+)*\d+)\s+\]',
                  lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text) + "\n"


def split_path(dataset: str) -> Path:
    return ROOT / Path(SPLITS[dataset][0]).parent / "split-heldout.json"


def load_split(path: str | Path) -> dict:
    """A committed split file, validated: disjoint halves covering every row once."""
    split = json.loads(Path(path).read_text(encoding="utf-8"))
    train, heldout = split["train"], split["heldout"]
    if set(train) & set(heldout):
        raise ValueError(f"{path}: train and heldout overlap")
    if sorted(train + heldout) != list(range(split["n"])):
        raise ValueError(f"{path}: halves do not cover rows 0..{split['n'] - 1} exactly once")
    return split


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed split differs")
    args = ap.parse_args()
    bad = 0
    for dataset in SPLITS:
        text = dumps(build(dataset))
        path = split_path(dataset)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                print(f"DIFF  {path.relative_to(ROOT)}")
                bad += 1
            else:
                print(f"ok    {path.relative_to(ROOT)}")
            continue
        path.write_text(text, encoding="utf-8")
        s = load_split(path)
        print(f"{dataset}: n={s['n']} train={s['n_train']} heldout={s['n_heldout']} -> "
              f"{path.relative_to(ROOT)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
