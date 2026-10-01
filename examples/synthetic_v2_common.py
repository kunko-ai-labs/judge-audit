"""Rules shared by the v2 synthetic generators (US-005-002, #87). Standard library only.

- `normalise`: the repository's one rule for "the same text" (case and whitespace
  ignored), as in scripts/fetch_real_datasets.py; no two rows of a v2 file share a
  text under it, and no base email of the adversarial file is a text of the clean one.
- `Unique`: redraws a template's fills until the text is new under that rule.
- `split_templates`: the pre-registered template-level split. Templates, not rows, are
  split, so a held-out row is never a near-duplicate (same template, other fills) of a
  development row. A row is held out when every template it was built from is.
- `render_jsonl` / `render_split`: the exact bytes CI compares (scripts/synthetic_v2.py).

The v1 generators (examples/email-routing, -adversarial, task-routing) do not use this
module: their files are frozen evidence behind the published audits.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections.abc import Callable, Iterable

# Fixed before any v2 file existed; nothing was run on the split before it was committed.
SPLIT_SEED = 2027
HELDOUT_EVERY = 4  # a quarter of each stratum's templates is held out

RULE = ("Held-out templates are never used in development: no prompt wording, few-shot "
        "example, training row, threshold or calibration fit may come from a row built on "
        "one. Held-out rows are scored once, under a pre-registered protocol.")
METHOD = ("templates split per stratum: ids sorted, shuffled with one random.Random(seed) "
          "per dataset, strata in sorted order, the first max(1, k // 4) of a stratum of "
          "k >= 2 held out (a stratum of one stays in development); a row is held out when "
          "every template it was built from is, and no row mixes the halves")


def normalise(text: str) -> str:
    """Case and whitespace ignored (scripts/fetch_real_datasets.py's rule)."""
    return " ".join(text.lower().split())


class Unique:
    """Texts taken so far, under `normalise`. `draw` calls `make` until its text is new."""

    def __init__(self, taken: Iterable[str] = (), tries: int = 500):
        self.seen = {normalise(t) for t in taken}
        self.tries = tries

    def __contains__(self, text: str) -> bool:
        return normalise(text) in self.seen

    def draw(self, make: Callable[[], str]) -> str:
        for _ in range(self.tries):
            text = make()
            key = normalise(text)
            if key not in self.seen:
                self.seen.add(key)
                return text
        raise RuntimeError(f"no new text after {self.tries} fills: the template needs more "
                           "slots or vocabulary")


def assert_unique_states(rows: list[dict]) -> None:
    first: dict[str, int] = {}
    for i, r in enumerate(rows):
        key = normalise(r["state"])
        if key in first:
            raise ValueError(f"rows {first[key]} and {i} hold one text up to case or whitespace")
        first[key] = i


def n_heldout(k: int) -> int:
    """Templates held out of a stratum of k: a quarter rounded down, at least one when
    k >= 2, none when k < 2 (a lone template stays in development)."""
    return 0 if k < 2 else max(1, k // HELDOUT_EVERY)


def split_templates(strata: dict[str, list[str]],
                    seed: int = SPLIT_SEED) -> tuple[list[str], list[str]]:
    """(dev, heldout) template ids, each sorted. Input order does not matter."""
    owner: dict[str, str] = {}
    for key, ids in strata.items():
        for t in ids:
            if t in owner:
                raise ValueError(f"template {t!r} in more than one stratum")
            owner[t] = key
    rng = random.Random(seed)
    dev: list[str] = []
    heldout: list[str] = []
    for key in sorted(strata):
        members = sorted(strata[key])
        rng.shuffle(members)
        h = n_heldout(len(members))
        heldout += members[:h]
        dev += members[h:]
    return sorted(dev), sorted(heldout)


def row_templates(row: dict) -> list[str]:
    """The templates a row was built from: its base, and its attack's when it has one."""
    meta = row.get("_meta", {})
    return [t for t in (meta.get("template"), meta.get("attack_template")) if t]


def partition_rows(rows: list[dict], dev: list[str],
                   heldout: list[str]) -> tuple[list[int], list[int]]:
    """(dev, heldout) row indices. A row whose templates are not all in one half fails."""
    d, h = set(dev), set(heldout)
    out_dev: list[int] = []
    out_held: list[int] = []
    for i, r in enumerate(rows):
        ts = row_templates(r)
        if ts and all(t in h for t in ts):
            out_held.append(i)
        elif ts and all(t in d for t in ts):
            out_dev.append(i)
        else:
            raise ValueError(f"row {i}: templates {ts} are not all in one half of the split")
    return out_dev, out_held


PHRASE_WORDS = 6  # a run this long, shared across the halves, counts as a leaked phrase


def phrases(text: str, n: int = PHRASE_WORDS) -> set[tuple[str, ...]]:
    """Runs of n words in a template (slots such as {item} count as words; digits and
    punctuation do not), ignoring case. Runs made only of slots are left out."""
    toks = re.findall(r"\{\w+\}|[^\W\d_]+", text.lower())
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)
            if not all(t.startswith("{") for t in toks[i:i + n])}


def cross_half_phrases(texts: dict[str, list[str]], half: dict[str, str],
                       n: int = PHRASE_WORDS) -> list[tuple[str, str, str]]:
    """(dev template, held-out template, shared run) for every run of n words that a
    held-out template shares with a development one: a held-out template is not only a
    new id but new wording."""
    runs = {t: set().union(*(phrases(x, n) for x in xs)) for t, xs in texts.items()}
    dev = sorted(t for t in texts if half[t] == "dev")
    held = sorted(t for t in texts if half[t] == "heldout")
    return [(d, h, " ".join(r)) for d in dev for h in held for r in sorted(runs[d] & runs[h])]


def render_jsonl(dataset: dict, rows: list[dict]) -> str:
    """Header line, then one row per line: v1's layout, byte for byte."""
    lines = [json.dumps({"idx": -1, "dataset": dataset}, ensure_ascii=False)]
    lines += [json.dumps(r, ensure_ascii=False) for r in rows]
    return "\n".join(lines) + "\n"


def sha256_rows(text: str) -> str:
    """judge_audit.runner.sha256_rows_of for a file `render_jsonl` produced (CI checks
    the two agree)."""
    return hashlib.sha256(text.split("\n", 1)[1].encode("utf-8")).hexdigest()


def split_record(*, dataset: str, labels: str, question: str, seed: int,
                 strata: dict[str, list[str]], dev: list[str], heldout: list[str],
                 rows: list[dict], labels_text: str, inherits: str | None = None) -> dict:
    """The committed split file: which templates are held out, and the rows that follows."""
    dev_rows, held_rows = partition_rows(rows, dev, heldout)
    d, h = set(dev), set(heldout)
    by_label: dict[str, dict[str, int]] = {}
    for idx, half in [(i, "dev") for i in dev_rows] + [(i, "heldout") for i in held_rows]:
        lab = str(rows[idx]["labels"][question])
        by_label.setdefault(lab, {"dev": 0, "heldout": 0})[half] += 1
    record = {
        "dataset": dataset, "labels": labels, "question": question,
        "rule": RULE, "method": METHOD, "seed": seed,
    }
    if inherits:
        record["inherits"] = inherits
    record.update({
        "strata": {k: {"dev": sum(t in d for t in strata[k]),
                       "heldout": sum(t in h for t in strata[k])} for k in sorted(strata)},
        "templates": {"n_dev": len(dev), "n_heldout": len(heldout),
                      "dev": dev, "heldout": heldout},
        "sha256_rows": sha256_rows(labels_text),
        "n": len(rows), "n_dev": len(dev_rows), "n_heldout": len(held_rows),
        "labels_by_split": {k: by_label[k] for k in sorted(by_label)},
        "dev": dev_rows, "heldout": held_rows,
    })
    return record


def render_split(record: dict) -> str:
    """Pretty JSON with each index list on one line (diff-friendly, as split_heldout.py)."""
    text = json.dumps(record, indent=1, ensure_ascii=False)
    return re.sub(r'\[\s+((?:\d+,\s+)*\d+)\s+\]',
                  lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text) + "\n"
