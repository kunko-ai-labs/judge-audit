"""Every committed checkpoint answers every labelled question of every row it covers, once,
of the dataset it recorded.

The live runner counts a skipped question as a wrong no-answer (US-004-015); a report rebuilt
from a checkpoint reads only the judgments the checkpoint holds. This check closes that gap:
a checkpoint with a row missing or written twice, a labelled question unanswered or answered
twice, or a blank label fails CI,
so no published number rests on a denominator that quietly shrank. The dataset read must
also be the one the run recorded: its sha256 (whole file) or sha256_rows (rows only) must
match the header's, either one as `check_drift` accepts, so a relabelled dataset fails (#80).

  python scripts/check_complete.py      # exit 1 listing each gap
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import answer_gaps, load_jsonl, sha256_of, sha256_rows_of  # noqa: E402

# The three first audits predate run headers; their dataset is fixed by name, and pinned by
# the rows digest of the file as committed with the checkpoint (v0.2.0). The ground-truth
# header line added later does not move a rows digest; a changed row does.
LEGACY = {
    "audit-jev-real.ckpt.jsonl": (
        "examples/email-routing/labels.jsonl",
        "c5b4c111290aa657236ea520a8043b14ce23e9b26af01a6c5e7ec9b87082e1cf"),
    "audit-jev-adversarial.ckpt.jsonl": (
        "examples/email-routing-adversarial/labels.jsonl",
        "74741868f533bf0c17b622cfbae43b917e52a964cd1c9e51fb9b74905c802e24"),
    "audit-jev-router.ckpt.jsonl": (
        "examples/task-routing/labels.jsonl",
        "27250d78eda62c5e5ad07906abd3c7fdeaecb1131a7d13e12146bed30f55ec8d"),
}
# Runs whose header names a scratch copy of a committed file (same sha256 in the header):
# the committed file is read instead, and the header is left as the run wrote it.
SCRATCH = {"gpt-6-luna-en-US.repeat40.ckpt.jsonl": "examples/massive/labels-pilot-en-US.first40.jsonl",
           "claude-sonnet-4.5-en-US.repeat40.ckpt.jsonl": "examples/massive/labels-pilot-en-US.first40.jsonl"}


def stopped(ckpt: Path, written: int) -> bool:
    """Whether run-notes.json beside the checkpoint declares its run stopped at exactly the
    `written` rows the checkpoint holds (the pilot's notes file:
    docs/runs/v05-pilot/run-notes.json). A note without that count, or with another one,
    declares nothing: a run that lost rows cannot hide behind a stale note."""
    notes = ckpt.parent / "run-notes.json"
    if not notes.exists():
        return False
    slug = ckpt.name.removesuffix(".ckpt.jsonl")
    runs = json.loads(notes.read_text(encoding="utf-8")).get("runs") or {}
    note = runs.get(slug) or {}
    return bool(note.get("stopped")) and note.get("rows") == written


def dataset_changed(ckpt: Path, run: dict, labels: Path) -> list[str]:
    """A gap when the dataset file is not the one the run recorded.

    The header's `dataset.sha256` (whole file) and `sha256_rows` (rows only) are both
    accepted, and either matches either, as `check_drift` does: a run made before the
    ground-truth header line recorded the whole file, which is today's rows digest. A header
    that records neither is held to its legacy pin, if it has one; otherwise to nothing."""
    ds = run.get("dataset") or {}
    recorded = {ds.get("sha256"), ds.get("sha256_rows")} - {None}
    if not recorded and ckpt.name in LEGACY:
        recorded = {LEGACY[ckpt.name][1]}
    if not recorded:
        return []
    now = {sha256_of(str(labels)), sha256_rows_of(str(labels))}
    if recorded & now:
        return []
    return [f"{rel(ckpt)}: dataset sha256 changed since the run: {rel(labels)} is "
            f"{sha256_rows_of(str(labels))!r} (rows), the run recorded {sorted(recorded)}"]


def subset_changed(ckpt: Path, subset: dict, split: Path, wanted: list[int]) -> list[str]:
    """Gaps when the split file is not the one the run recorded under `rows_subset`: its
    sha256, and the number of rows its part names. A header without them is not held to
    them. A cut of the split would otherwise pass: every row it still names is answered."""
    out = []
    if subset.get("sha256") is not None and sha256_of(str(split)) != subset["sha256"]:
        out.append(f"{rel(ckpt)}: split sha256 changed since the run: {rel(split)} is "
                   f"{sha256_of(str(split))!r}, the run recorded {subset['sha256']!r}")
    if subset.get("n") is not None and len(wanted) != subset["n"]:
        out.append(f"{rel(ckpt)}: the run recorded {subset['n']} rows in "
                   f"{rel(split)}:{subset['part']}, it names {len(wanted)} now")
    return out


def rel(path: Path) -> str:
    """A path as the repo names it: never the machine's absolute path in a CI log."""
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return str(path)


def gaps(ckpt: Path) -> list[str]:
    lines = [json.loads(x) for x in ckpt.read_text(encoding="utf-8").splitlines() if x.strip()]
    headers = [x["run"] for x in lines if x["idx"] == -1]
    run = headers[-1] if headers else {}  # the readers take the last header
    legacy = LEGACY[ckpt.name][0] if ckpt.name in LEGACY else None
    labels = SCRATCH.get(ckpt.name) or (run.get("dataset") or {}).get("path") or legacy
    if not labels:
        return [f"{ckpt}: no dataset path in the header and no legacy mapping"]
    changed = dataset_changed(ckpt, run, ROOT / labels)
    if changed:   # the labels are not the ones answered: the row checks below mean nothing
        return changed
    rows = load_jsonl(str(ROOT / labels))
    subset = run.get("rows_subset")
    if subset:
        split = ROOT / subset["split"]
        wanted = sorted(json.loads(split.read_text())[subset["part"]])
        changed = subset_changed(ckpt, subset, split, wanted)
        if changed:   # not the rows the run was made on: the row checks below mean nothing
            return changed
    else:
        wanted = list(range(len(rows)))
    # Every reader counts every row line, so a row written twice is counted twice: a gap.
    seen: dict[int, int] = {}
    for x in lines:
        if x["idx"] >= 0:
            seen[x["idx"]] = seen.get(x["idx"], 0) + 1
    done = {x["idx"]: x for x in lines if x["idx"] >= 0}
    out = [f"{ckpt}: row {i} written {k} times" for i, k in sorted(seen.items()) if k > 1]
    # A run the maintainer declares stopped (run-notes.json beside it) is kept so the driver
    # can resume it: the rows after its last written one are not gaps. A hole before them is.
    tail = []
    if stopped(ckpt, len(done)):
        last = max((wanted.index(i) for i in done if i in wanted), default=-1)
        tail = wanted[last + 1:]
    out += [f"{ckpt}: row {i} missing" for i in wanted if i not in done and i not in tail]
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
