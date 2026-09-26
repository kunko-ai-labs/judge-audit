"""Human-labelled public datasets for the v0.5 benchmark (#86), from pinned upstream files.

Each source is fetched at a fixed commit of its official repository, checked against the
sha256 recorded below, and converted to the judge-audit labels format with a dataset header
that declares its ground-truth tier, its caveats, and where every row came from. The
conversion is deterministic: running it twice writes byte-identical files, and `--check`
(run in CI) fails if a committed file differs from what the pinned upstream files produce.

  BANKING77   PolyAI-LDN/task-specific-datasets, CC BY 4.0 (Casanueva et al. 2020)
              examples/banking77/labels-test.jsonl    the 3,080-query official test split
              examples/banking77/labels-pilot.jsonl   4 train queries per intent (seed 2026),
                                                      for the pilot; never scored in the study
  CLINC150    clinc/oos-eval, CC BY 3.0 (Larson et al. 2019)
              examples/clinc150/labels-test-banking-credit.jsonl
                                                      the banking and credit_cards domains
                                                      (30 intents) of the test split plus
                                                      the 1,000 out-of-scope test queries

The question wording, the option lists and CLINC150's domain subset are drafts until the
v0.5 pre-registration (#91) fixes them; after that they are frozen evidence.

  python scripts/fetch_real_datasets.py                # fetch, verify, write
  python scripts/fetch_real_datasets.py --check        # exit 1 naming any file that differs
  python scripts/fetch_real_datasets.py --src DIR      # read the upstream files from DIR
                                                       # (DIR/<repo name>/<path>) offline
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 2026
PILOT_PER_INTENT = 4

SOURCES = {
    "banking77": {
        "name": "BANKING77",
        "repo": "PolyAI-LDN/task-specific-datasets",
        "commit": "57ec275d8078af65b7731c2a98be812d844a6d6b",
        "licence": "CC BY 4.0",
        "citation": ("Casanueva, Temcinas, Gerz, Henderson & Vulic 2020, Efficient Intent "
                     "Detection with Dual Sentence Encoders, NLP4ConvAI (ACL 2020)"),
        "files": {
            "banking_data/test.csv":
                "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d",
            "banking_data/train.csv":
                "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b",
            "banking_data/categories.json":
                "53261da888122daf2d120d925458631d9619e15d82e56052e7a42e535ce32b63",
            "LICENSE": "7e7170e3cebf88a9f60c7b8421418323c09304da1af4d5e90f4da1dc1c8a2661",
        },
    },
    "clinc150": {
        "name": "CLINC150",
        "repo": "clinc/oos-eval",
        "commit": "828f8093932c8fe6ca7936c3d2e52903b1c523de",
        "licence": "CC BY 3.0",
        "citation": ("Larson, Mahendran, Peper, Clarke, Lee, Hill, Kummerfeld, Leach, "
                     "Laurenzano, Tang & Mars 2019, An Evaluation Dataset for Intent "
                     "Classification and Out-of-Scope Prediction, EMNLP-IJCNLP 2019"),
        "files": {
            "data/data_full.json":
                "36923c3705a59e08fe9c3883d8bc2dd966ef93e22cb78ac41171782a698d56e0",
            "data/domains.json":
                "b947b579d3b8e74b06f93b01083d8efaff2888b43a3e362533bd88a6e1211b3a",
            "LICENSE": "e6bc9e9c474700b708f568bac9e5a8a9bcb2b1dad53442f5ba449fcb848b8e76",
        },
    },
}

BANKING77_INSTRUCTIONS = ("Which intent does this online-banking customer message express? "
                          "Choose exactly one.")
CLINC_DOMAINS = ("banking", "credit_cards")
OUT_OF_SCOPE = "out_of_scope"
CLINC_INSTRUCTIONS = ("Which intent does this request to a banking assistant express? "
                      f"Choose {OUT_OF_SCOPE} if it asks for none of the listed intents.")


def normalise(text: str) -> str:
    """Case- and whitespace-insensitive key used only to flag test texts seen in train."""
    return " ".join(text.lower().split())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(source: dict, path: str, src_dir: Path | None) -> bytes:
    """One upstream file at the pinned commit, verified against its recorded sha256."""
    if src_dir is not None:
        data = (src_dir / source["repo"].split("/")[1] / path).read_bytes()
    else:
        url = f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{path}"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
    got, want = sha256_bytes(data), source["files"][path]
    if got != want:
        raise SystemExit(f"{source['repo']}/{path}: sha256 {got} != pinned {want}")
    return data


def provenance(key: str, path: str) -> dict:
    s = SOURCES[key]
    return {"name": s["name"], "repository": f"https://github.com/{s['repo']}",
            "commit": s["commit"], "file": path, "sha256": s["files"][path],
            "licence": s["licence"], "citation": s["citation"]}


def jsonl(header: dict, rows: list[dict]) -> str:
    lines = [{"idx": -1, "dataset": header}] + rows
    return "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines)


def read_csv(data: bytes) -> list[tuple[str, str]]:
    with io.StringIO(data.decode("utf-8"), newline="") as f:
        return [(r["text"], r["category"]) for r in csv.DictReader(f)]


def banking77_row(text: str, label: str, intents: list[str], split: str, index: int,
                  in_train: bool | None = None) -> dict:
    meta: dict = {"source": "banking77", "split": split, "source_index": index}
    if in_train is not None:
        meta["text_in_train"] = in_train
    return {"state": text,
            "questions": [{"name": "intent", "type": "choice",
                           "instructions": BANKING77_INSTRUCTIONS, "options": intents}],
            "labels": {"intent": label}, "_meta": meta}


def banking77(test: list[tuple[str, str]], train: list[tuple[str, str]],
              intents: list[str]) -> dict[str, str]:
    """The two BANKING77 files: the test split, and the pilot sample of the train split."""
    unknown = {label for _, label in test + train} - set(intents)
    if unknown:
        raise SystemExit(f"BANKING77 labels outside categories.json: {sorted(unknown)}")
    train_keys = {normalise(t) for t, _ in train}
    in_train = [normalise(t) in train_keys for t, _ in test]
    test_rows = [banking77_row(t, label, intents, "test", i, seen)
                 for i, ((t, label), seen) in enumerate(zip(test, in_train, strict=True))]
    common_caveats = [
        "public since 2020: probably in the pretraining data of the judges audited",
        "one label per query from the dataset's authors, no published inter-annotator "
        "agreement; Ying & Thomas (2022) estimate that about 14 % of the train split may be "
        "mislabelled, and the test split's label noise is measured by a relabelled sample",
        "the options are the dataset's label names without definitions; some names mislead "
        "(get_physical_card also holds questions about the PIN)",
    ]
    test_header = {
        "ground_truth": {
            "tier": "GT-3", "label": "human-annotated", "validation": "not_validated",
            "purpose": ["calibration and selective prediction on real customer-support "
                        "messages", "comparison between judges on the same rows"],
            "caveats": common_caveats + [
                f"{sum(in_train)} of {len(test)} test texts also appear in the train split "
                "(case and whitespace ignored); _meta.text_in_train marks them"],
        },
        "source": provenance("banking77", "banking_data/test.csv"),
    }

    by_label: dict[str, list[int]] = defaultdict(list)
    for i, (_, label) in enumerate(train):
        by_label[label].append(i)
    rng = random.Random(SEED)
    picked: list[int] = []
    for label in intents:                          # categories.json order, then seeded
        idx = list(by_label[label])
        rng.shuffle(idx)
        picked.extend(sorted(idx[:PILOT_PER_INTENT]))
    pilot_rows = [banking77_row(train[i][0], train[i][1], intents, "train", i) for i in picked]
    pilot_header = {
        "ground_truth": {
            "tier": "GT-3", "label": "human-annotated", "validation": "not_validated",
            "purpose": ["pilot: token counts, throughput and variance before the "
                        "pre-registration fixes n; never used to score a judge"],
            "caveats": common_caveats + [
                f"{PILOT_PER_INTENT} train queries per intent, drawn with "
                f"random.Random({SEED}) in categories.json order"],
        },
        "source": provenance("banking77", "banking_data/train.csv"),
    }
    return {"examples/banking77/labels-test.jsonl": jsonl(test_header, test_rows),
            "examples/banking77/labels-pilot.jsonl": jsonl(pilot_header, pilot_rows)}


def clinc150(data: dict, domains: dict[str, list[str]],
             selected: tuple[str, ...] = CLINC_DOMAINS) -> dict[str, str]:
    """CLINC150's test split restricted to `selected` domains, plus every out-of-scope
    test query, with one extra option for "none of these"."""
    missing = [d for d in selected if d not in domains]
    if missing:
        raise SystemExit(f"CLINC150 has no domain {missing}")
    intents = [i for d in selected for i in domains[d]]
    options = intents + [OUT_OF_SCOPE]
    train_keys = {normalise(t) for part in ("train", "val", "oos_train", "oos_val")
                  for t, _ in data[part]}
    question = {"name": "intent", "type": "choice", "instructions": CLINC_INSTRUCTIONS,
                "options": options,
                "descriptions": {OUT_OF_SCOPE: "the request asks for none of the other intents"}}
    rows: list[dict] = []
    for part in ("test", "oos_test"):
        for i, (text, label) in enumerate(data[part]):
            if part == "test" and label not in intents:
                continue
            rows.append({"state": text, "questions": [question],
                         "labels": {"intent": label if part == "test" else OUT_OF_SCOPE},
                         "_meta": {"source": "clinc150", "split": part, "source_index": i,
                                   "text_in_train": normalise(text) in train_keys}})
    in_scope = sum(1 for r in rows if r["labels"]["intent"] != OUT_OF_SCOPE)
    seen = sum(1 for r in rows if r["_meta"]["text_in_train"])
    header = {
        "ground_truth": {
            "tier": "GT-3", "label": "human-annotated", "validation": "not_validated",
            "purpose": ["selective prediction when no option applies: does confidence fall "
                        "on out-of-scope requests?"],
            "caveats": [
                "public since 2019: probably in the pretraining data of the judges audited",
                "crowd-sourced queries and labels, one label per query; label noise is "
                "measured by a relabelled sample",
                f"domains {', '.join(selected)} only: {in_scope} in-scope test queries, "
                f"{len(rows) - in_scope} out-of-scope ones (out of scope for all 150 "
                "intents); a draft subset until the pre-registration fixes it",
                f"{seen} of {len(rows)} texts also appear in the train or validation "
                "splits (case and whitespace ignored); _meta.text_in_train marks them",
            ],
        },
        "source": provenance("clinc150", "data/data_full.json"),
        "subset": {"domains": list(selected), "out_of_scope_label": OUT_OF_SCOPE},
    }
    name = "examples/clinc150/labels-test-banking-credit.jsonl"
    return {name: jsonl(header, rows)}


def build(src_dir: Path | None) -> dict[str, str]:
    b = SOURCES["banking77"]
    intents = json.loads(fetch(b, "banking_data/categories.json", src_dir))
    fetch(b, "LICENSE", src_dir)
    out = banking77(read_csv(fetch(b, "banking_data/test.csv", src_dir)),
                    read_csv(fetch(b, "banking_data/train.csv", src_dir)), intents)
    c = SOURCES["clinc150"]
    fetch(c, "LICENSE", src_dir)
    out.update(clinc150(json.loads(fetch(c, "data/data_full.json", src_dir)),
                        json.loads(fetch(c, "data/domains.json", src_dir))))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a committed file differs from the regenerated one")
    ap.add_argument("--src", type=Path, default=None,
                    help="read upstream files from DIR/<repo name>/<path> instead of fetching")
    args = ap.parse_args(argv)
    files = build(args.src)
    changed = []
    for rel, text in files.items():
        path = ROOT / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        changed.append(rel)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for rel in changed:
        print(("differs: " if args.check else "wrote: ") + rel)
    if args.check and changed:
        return 1
    print(f"{len(files)} files, {len(changed)} {'differ' if args.check else 'written'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
