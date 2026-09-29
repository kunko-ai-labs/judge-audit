"""v2 synthetic stress sets (US-005-002, #87): regenerate them and enforce their invariants.

The v2 generators (examples/*-v2/generate.py) write a labels file and a pre-registered
template-level split each. This script regenerates both in memory and, with --check,
fails if a committed file differs by one byte or if any invariant breaks on the
committed files:

  - at least 1,000 rows per file;
  - no two rows with the same `state` (case and whitespace ignored, the repository's
    rule: scripts/fetch_real_datasets.py `normalise`);
  - the adversarial email file shares no base email (`_meta.base`) with the clean file,
    and no two of its rows share one; in the router file no attacked task is the text
    of a clean row;
  - the split: no template in both halves, every row in the half of all its templates,
    the index lists disjoint and covering, both halves non-empty, `sha256_rows` equal to
    the labels file's, and no held-out template sharing a run of six words with a
    development one (a new id is not enough: the wording must be new too);
  - v1 is frozen evidence: its labels and split files keep the digests pinned below,
    which the published checkpoints were run on.

  python scripts/synthetic_v2.py            # writes examples/*-v2/{labels.jsonl,split-templates.json}
  python scripts/synthetic_v2.py --check    # exit 1 on a difference or a broken invariant
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.runner import load_dataset, sha256_rows_of  # noqa: E402

MIN_ROWS = 1000
CLEAN = "examples/email-routing-v2"
ADVERSARIAL = "examples/email-routing-adversarial-v2"
ROUTER = "examples/task-routing-v2"
V2_DIRS = (CLEAN, ADVERSARIAL, ROUTER)

# v1: the files the published audits were run on. Never regenerated with new content.
FROZEN_V1 = {
    "examples/email-routing/labels.jsonl":
        "2b2ff2f88b3a86a2786565da640d94259485ad22b5e4a9a2fc6ec5339eb9da91",
    "examples/email-routing-adversarial/labels.jsonl":
        "8b7dbc8ded1bf6478889eb0723beb7313fc888245b52c1967de0ec8cde2f855b",
    "examples/task-routing/labels.jsonl":
        "e2efb9e1baec7e6ecf46e574d678d4de7cc1461db3dc8029c5baf15c7c06d4ff",
    "examples/task-routing/labels-described.jsonl":
        "c2811e2a8cde438f648870a0c477bc19734b08a9335b3c2bd5a9fd1191fad53b",
    "examples/email-routing/split-heldout.json":
        "05e7630ed5ea29a70a99902db69c0971fb03217309df0463cf2e43a9f01736f7",
    "examples/task-routing/split-heldout.json":
        "322d113c8c0e67c36362d1d4ff26955c68dd76843158cd8f11462eb8b66ae018",
}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_fetch = _load("fetch_real_datasets_rule", ROOT / "scripts" / "fetch_real_datasets.py")
normalise = _fetch.normalise
_common = _load("synthetic_v2_common_rules", ROOT / "examples" / "synthetic_v2_common.py")
_GENERATORS: dict[str, object] = {}


def generator(d: str):
    """The v2 generator module of directory `d`, loaded once."""
    if d not in _GENERATORS:
        _GENERATORS[d] = _load(f"gen_{Path(d).name.replace('-', '_')}", ROOT / d / "generate.py")
    return _GENERATORS[d]


def _rows(rel: str) -> list[dict]:
    return load_dataset(str(ROOT / rel))[0]


# --- invariants, each a pure function of rows --------------------------------------------

def duplicate_states(rows: list[dict]) -> list[list[int]]:
    """Groups of row indices that hold one text under `normalise`."""
    by_key: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_key[normalise(r["state"])].append(i)
    return [idx for idx in by_key.values() if len(idx) > 1]


def _base(row: dict) -> str:
    """The text an attack was built on; a row without one is its own base."""
    return str(row.get("_meta", {}).get("base") or row["state"])


def shared_bases(clean: list[dict], attacked: list[dict]) -> list[int]:
    """Indices of `attacked` rows whose base is a text of `clean`."""
    keys = {normalise(r["state"]) for r in clean}
    return [i for i, r in enumerate(attacked) if normalise(_base(r)) in keys]


def duplicate_bases(rows: list[dict]) -> list[list[int]]:
    """Groups of rows built on one base text."""
    by_key: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_key[normalise(_base(r))].append(i)
    return [idx for idx in by_key.values() if len(idx) > 1]


def row_count_problems(name: str, rows: list[dict]) -> list[str]:
    return [] if len(rows) >= MIN_ROWS else [f"{name}: {len(rows)} rows, fewer than {MIN_ROWS}"]


def split_problems(split: dict, rows: list[dict]) -> list[str]:
    """What is wrong with a split file against its rows ([] when nothing)."""
    out = []
    dev_t, held_t = set(split["templates"]["dev"]), set(split["templates"]["heldout"])
    if dev_t & held_t:
        out.append(f"templates in both halves: {sorted(dev_t & held_t)}")
    if not held_t or not split["heldout"]:
        out.append("no held-out template or row")
    if split["n"] != len(rows):
        out.append(f"n = {split['n']} but the labels file has {len(rows)} rows")
    dev, held = split["dev"], split["heldout"]
    if set(dev) & set(held) or sorted(dev + held) != list(range(len(rows))):
        out.append("the row indices are not two disjoint halves covering every row once")
    want_dev, want_held = [], []
    for i, r in enumerate(rows):
        meta = r.get("_meta", {})
        ts = [t for t in (meta.get("template"), meta.get("attack_template")) if t]
        if ts and set(ts) <= held_t:
            want_held.append(i)
        elif ts and set(ts) <= dev_t:
            want_dev.append(i)
        else:
            out.append(f"row {i}: templates {ts} are not all in one half")
    if (want_dev, want_held) != (sorted(dev), sorted(held)) and not any(
            p.startswith("row ") for p in out):
        out.append("the row indices do not follow the rows' templates")
    return out


def frozen_problems() -> list[str]:
    out = []
    for rel, digest in FROZEN_V1.items():
        path = ROOT / rel
        got = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"
        if got != digest:
            out.append(f"v1 file changed: {rel} (sha256 {got[:12]}…, pinned {digest[:12]}…)")
    return out


def problems() -> list[str]:
    """Every invariant, on the committed files."""
    out = frozen_problems()
    rows = {d: _rows(f"{d}/labels.jsonl") for d in V2_DIRS}
    for d, rs in rows.items():
        out += row_count_problems(d, rs)
        out += [f"{d}: rows {idx} hold one text (case and whitespace ignored)"
                for idx in duplicate_states(rs)]
        split = json.loads((ROOT / d / "split-templates.json").read_text(encoding="utf-8"))
        out += [f"{d}/split-templates.json: {p}" for p in split_problems(split, rs)]
        if split["sha256_rows"] != sha256_rows_of(str(ROOT / d / "labels.jsonl")):
            out.append(f"{d}/split-templates.json: sha256_rows is not the labels file's")
        gen = generator(d)
        out += [f"{d}: held-out template {h} shares '{run}' with development template {dv}"
                for dv, h, run in _common.cross_half_phrases(gen.TEMPLATE_TEXTS, gen.HALF)]
    adv = rows[ADVERSARIAL]
    out += [f"{ADVERSARIAL}: row {i} is built on a base email of {CLEAN}"
            for i in shared_bases(rows[CLEAN], adv)]
    out += [f"{ADVERSARIAL}: rows {idx} share a base email" for idx in duplicate_bases(adv)]
    router = rows[ROUTER]
    clean_r = [r for r in router if r["_meta"]["attack"] == "clean"]
    attacked_r = [r for r in router if r["_meta"]["attack"] != "clean"]
    out += [f"{ROUTER}: attacked row {i} is built on the text of a clean row"
            for i in shared_bases(clean_r, attacked_r)]
    out += [f"{ROUTER}: attacked rows {idx} share a task" for idx in duplicate_bases(attacked_r)]
    clean_split = json.loads((ROOT / CLEAN / "split-templates.json").read_text(encoding="utf-8"))
    adv_split = json.loads((ROOT / ADVERSARIAL / "split-templates.json").read_text(encoding="utf-8"))
    for half in ("dev", "heldout"):
        if not set(clean_split["templates"][half]) <= set(adv_split["templates"][half]):
            out.append(f"{ADVERSARIAL}: an email template is not in the clean file's {half} half")
    return out


def expected() -> dict[Path, str]:
    """Every v2 file, regenerated in memory."""
    out: dict[Path, str] = {}
    for d in V2_DIRS:
        for name, text in generator(d).files().items():
            out[ROOT / d / name] = text
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="fail if a committed v2 file differs or an invariant breaks")
    args = ap.parse_args(argv)
    bad = 0
    for path, text in expected().items():
        rel = path.relative_to(ROOT)
        if args.check:
            same = path.exists() and path.read_bytes() == text.encode("utf-8")
            print(f"{'ok  ' if same else 'DIFF'}  {rel}")
            bad += not same
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {rel}")
    found = problems()
    for p in found:
        print(f"FAIL  {p}")
    if not found:
        print(f"ok    invariants: >= {MIN_ROWS} rows, distinct texts, disjoint bases, "
              "template split with new wording on the held-out side, v1 frozen")
    return 1 if bad or found else 0


if __name__ == "__main__":
    sys.exit(main())
