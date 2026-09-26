"""Measure a dataset's label noise: a blind relabelled sample, scored against two annotators.

A human-labelled dataset (GT-3) carries an unknown share of wrong labels, and a wrong label
moves every calibration number (docs/ground-truth.md). This script turns that share into a
measured one, in three steps:

  sample   draw a label-stratified random sample of rows (seeded) and commit its indices
           before anyone labels them:
             python scripts/relabel.py sample examples/banking77/labels-test.jsonl \
                 --n 500 --out examples/banking77/relabel-sample.json
  sheet    write the blind annotation sheet for one annotator: id and text only, never the
           dataset's label or any judge's answer, plus the list of allowed options:
             python scripts/relabel.py sheet examples/banking77/relabel-sample.json \
                 --out /tmp/relabel-sheet.csv
  score    read two annotators' filled sheets (id,label) and report their agreement
           (Cohen's kappa), each one's agreement with the dataset's label, the rows both
           annotators label differently from the dataset (likely label errors), and the
           rows they disagree on (to adjudicate):
             python scripts/relabel.py score examples/banking77/relabel-sample.json \
                 annotator-a.csv annotator-b.csv --json relabel-result.json

The sample is random, never chosen from where judges disagree with the label: that would
make the "clean" subset agree with the judges by construction.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import load_jsonl, sha256_rows_of  # noqa: E402

SEED = 2026


def stratified_sample(labels: list[str], n: int, seed: int = SEED) -> list[int]:
    """`n` row indices, stratified by label in proportion to each label's share of the
    dataset, so the sample's error rate estimates the dataset's without reweighting: each
    label gets floor(n · share), and the remaining rows go one each to the labels with the
    largest fractional parts (ties in a seeded random order). Within a label, rows are
    drawn at random. Deterministic for a seed; returned sorted."""
    by_label: dict[str, list[int]] = defaultdict(list)
    for i, label in enumerate(labels):
        by_label[label].append(i)
    names = sorted(by_label)
    total = len(labels)
    if not 0 < n <= total:
        raise ValueError(f"cannot sample {n} of {total} rows")
    rng = random.Random(seed)
    tiebreak = list(names)
    rng.shuffle(tiebreak)
    rank = {name: i for i, name in enumerate(tiebreak)}
    quota = {name: n * len(by_label[name]) // total for name in names}
    # exact fractional parts as integer remainders: n·count mod total
    by_remainder = sorted(names, key=lambda k: (-(n * len(by_label[k]) % total), rank[k]))
    for name in by_remainder[:n - sum(quota.values())]:
        quota[name] += 1
    picked: list[int] = []
    for name in names:
        pool = list(by_label[name])
        rng.shuffle(pool)
        picked.extend(pool[:quota[name]])
    if len(picked) != n:
        raise ValueError(f"only {len(picked)} rows could be drawn for n={n}")
    return sorted(picked)


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa between two annotators' labels on the same items:
    (observed agreement − chance agreement) / (1 − chance agreement), chance from each
    annotator's own label frequencies. None when chance agreement is 1 (both annotators
    used one and the same label everywhere): kappa is undefined there."""
    if len(a) != len(b):
        raise ValueError(f"{len(a)} labels from annotator A, {len(b)} from B")
    if not a:
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    chance = sum(ca[k] * cb[k] for k in ca) / (n * n)
    if chance == 1:
        return None
    return (observed - chance) / (1 - chance)


def question_of(rows: list[dict], question: str | None) -> str:
    names = {q["name"] for r in rows for q in r["questions"]}
    if question is None:
        if len(names) != 1:
            raise SystemExit(f"the dataset has several questions {sorted(names)}: pass --question")
        return next(iter(names))
    if question not in names:
        raise SystemExit(f"no question {question!r} in the dataset")
    return question


def cmd_sample(args) -> int:
    rows = load_jsonl(args.dataset)
    q = question_of(rows, args.question)
    labels = [r["labels"][q] for r in rows]
    idx = stratified_sample(labels, args.n, args.seed)
    out = {"dataset": args.dataset, "sha256_rows": sha256_rows_of(args.dataset),
           "question": q, "seed": args.seed, "n": len(idx),
           "method": "random sample stratified by label in proportion to its share (scripts/relabel.py stratified_sample)",
           "indices": idx}
    Path(args.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"{len(idx)} rows over {len(set(labels[i] for i in idx))} labels -> {args.out}")
    return 0


def _load_sample(path: str) -> tuple[dict, list[dict]]:
    sample = json.loads(Path(path).read_text(encoding="utf-8"))
    dataset = Path(sample["dataset"])
    if not dataset.is_absolute():
        dataset = ROOT / dataset                    # samples record repo-relative paths
    rows = load_jsonl(str(dataset))
    if sha256_rows_of(str(dataset)) != sample["sha256_rows"]:
        raise SystemExit(f"{sample['dataset']} changed since the sample was drawn")
    return sample, rows


def sheet_order(indices: list[int], seed: int = SEED) -> list[int]:
    """The sampled rows in a seeded random order. Datasets are often sorted by label
    (BANKING77's test split holds each intent's 40 queries together), so listing the rows
    by index would show an annotator which ones share a label."""
    order = list(indices)
    random.Random(seed).shuffle(order)
    return order


def cmd_sheet(args) -> int:
    sample, rows = _load_sample(args.sample)
    q = sample["question"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "text", "label"])
        for i in sheet_order(sample["indices"], sample["seed"]):
            w.writerow([i, rows[i]["state"], ""])
    options = next(qq["options"] for qq in rows[sample["indices"][0]]["questions"]
                   if qq["name"] == q)
    opt_path = Path(args.out).with_suffix(".options.txt")
    opt_path.write_text("\n".join(options) + "\n", encoding="utf-8")
    print(f"{len(sample['indices'])} rows -> {args.out}; allowed labels -> {opt_path}")
    return 0


def read_sheet(path: str, allowed: set[str]) -> dict[int, str]:
    with open(path, newline="", encoding="utf-8") as f:
        out: dict[int, str] = {}
        for r in csv.DictReader(f):
            label = (r.get("label") or "").strip()
            if label not in allowed:
                raise SystemExit(f"{path}: row id {r['id']} has label {label!r}, not an option")
            out[int(r["id"])] = label
    return out


def score(sample: dict, rows: list[dict], a: dict[int, str], b: dict[int, str]) -> dict:
    q = sample["question"]
    ids = sample["indices"]
    missing = [i for i in ids if i not in a or i not in b]
    if missing:
        raise SystemExit(f"{len(missing)} sampled rows are not labelled by both annotators, "
                         f"e.g. id {missing[0]}")
    gold = [rows[i]["labels"][q] for i in ids]
    la, lb = [a[i] for i in ids], [b[i] for i in ids]
    n = len(ids)
    both_differ = [i for i, g, x, y in zip(ids, gold, la, lb, strict=True) if x == y != g]
    disagree = [i for i, x, y in zip(ids, la, lb, strict=True) if x != y]
    kappa = cohen_kappa(la, lb)
    return {
        "n": n,
        "annotator_agreement": round(sum(x == y for x, y in zip(la, lb, strict=True)) / n, 4),
        "cohen_kappa": round(kappa, 4) if kappa is not None else None,
        "agreement_with_dataset": {
            "a": round(sum(x == g for x, g in zip(la, gold, strict=True)) / n, 4),
            "b": round(sum(y == g for y, g in zip(lb, gold, strict=True)) / n, 4)},
        "both_annotators_differ_from_dataset": {"n": len(both_differ),
                                                "share": round(len(both_differ) / n, 4),
                                                "ids": both_differ},
        "annotators_disagree": {"n": len(disagree), "ids": disagree},
    }


def cmd_score(args) -> int:
    sample, rows = _load_sample(args.sample)
    q = sample["question"]
    allowed = set(next(qq["options"] for qq in rows[sample["indices"][0]]["questions"]
                       if qq["name"] == q))
    result = score(sample, rows, read_sheet(args.a, allowed), read_sheet(args.b, allowed))
    print(json.dumps({k: v for k, v in result.items() if k != "annotators_disagree"}
                     | {"annotators_disagree": result["annotators_disagree"]["n"]}, indent=1))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample", help="draw and commit the sample's indices")
    s.add_argument("dataset")
    s.add_argument("--n", type=int, default=500)
    s.add_argument("--seed", type=int, default=SEED)
    s.add_argument("--question", default=None)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_sample)
    h = sub.add_parser("sheet", help="write a blind annotation sheet")
    h.add_argument("sample")
    h.add_argument("--out", required=True)
    h.set_defaults(func=cmd_sheet)
    c = sub.add_parser("score", help="score two filled sheets")
    c.add_argument("sample")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--json", default=None)
    c.set_defaults(func=cmd_score)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
