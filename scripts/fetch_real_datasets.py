"""Human-labelled public datasets for the benchmarks (#86, #133), from pinned upstream files.

Each source is fetched at a fixed commit of its official repository (MASSIVE: its official
release archive), checked against the sha256 recorded below, and converted to the
judge-audit labels format with a dataset header
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
  MASSIVE 1.1 alexa/massive release archive, CC BY 4.0 (FitzGerald et al. 2023), derived
              from SLURP (Bastianelli et al. 2020); locales en-US, es-ES and ca-ES
              examples/massive/labels-test-<locale>.jsonl
                                                      the 2,974-utterance test split, the
                                                      same items in each locale (_meta.id)
              examples/massive/labels-pilot-<locale>.jsonl
                                                      4 dev utterances per intent (seed 2026),
                                                      for the pilot; never scored in the study

The question wording, the option lists and CLINC150's domain subset are drafts until the
v0.5 pre-registration (#91) fixes them; after that they are frozen evidence. MASSIVE's are
drafts until the v0.6 pre-registration (#132) fixes them.

  python scripts/fetch_real_datasets.py                # fetch, verify, write
  python scripts/fetch_real_datasets.py --check        # exit 1 naming any file that differs
  python scripts/fetch_real_datasets.py --src DIR      # read the upstream files from DIR
                                                       # (DIR/<repo name>/<path>) offline
  python scripts/fetch_real_datasets.py --cache DIR    # reuse verified downloads kept in DIR
  python scripts/fetch_real_datasets.py --massive-full DIR
                                                       # also write MASSIVE's whole train and
                                                       # dev splits to DIR (not committed)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import io
import json
import random
import re
import sys
import tarfile
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 2026
DOWNLOAD_ATTEMPTS = 4                              # 1 + 3 retries, 5 s, 10 s, 20 s apart
PILOT_PER_INTENT = 4

SOURCES = {
    "banking77": {
        "name": "BANKING77",
        "repo": "PolyAI-LDN/task-specific-datasets",
        "commit": "57ec275d8078af65b7731c2a98be812d844a6d6b",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
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
        "licence_url": "https://creativecommons.org/licenses/by/3.0/",
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
    "massive": {
        "name": "MASSIVE 1.1",
        "repo": "alexa/massive",
        # the release archive the upstream README and the Hugging Face loader point to;
        # the archive is served without a commit, so it and each member are pinned by sha256
        "archive": ("https://amazon-massive-nlu-dataset.s3.amazonaws.com/"
                    "amazon-massive-dataset-1.1.tar.gz"),
        "archive_sha256": "4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": ("FitzGerald, Hench, Peris, Mackie, Rottmann, Sanchez, Nash, Urbach, "
                     "Kakarala, Singh, Ranganath, Crist, Britan, Leeuwis, Tur & Natarajan "
                     "2023, MASSIVE: A 1M-Example Multilingual Natural Language "
                     "Understanding Dataset with 51 Typologically-Diverse Languages, ACL 2023"),
        "derived_from": ("SLURP, CC BY 4.0: Bastianelli, Vanzo, Swietojanski & Rieser 2020, "
                         "SLURP: A Spoken Language Understanding Resource Package, EMNLP 2020"),
        "files": {
            "1.1/LICENSE": "c2e6ea015269147de02117ebdd91f30ef09831251f5345fa8365273b1db1d435",
            "1.1/NOTICE.md": "b90534ccd20c6f0e1e5239567af0d150496339542b75a15bfbc3e1e737593ddb",
            "1.1/data/en-US.jsonl":
                "c70f75c6a543a26e249ec383df67733ad9b1066f6c0406c2e04a3f03356e407e",
            "1.1/data/es-ES.jsonl":
                "310462a79fa181ff83c643a8d356c7b8155fd37a25e80a77ba3ca9b29305c4a5",
            "1.1/data/ca-ES.jsonl":
                "7da25fa3f731ea96dc9caa48363863c117c652ad628e5c7be0d9fdab7ccb7ed3",
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
    """The one rule for "the same text", used for every distinctness and train-overlap
    claim here: case and whitespace ignored."""
    return " ".join(text.lower().split())


def distinct_caveat(rows: list[tuple[str, str]]) -> str:
    """How many distinct texts a file holds under `normalise`, naming the rows (0-based,
    header excluded) that repeat one: clustered statistics must count them as one text."""
    by_key: dict[str, list[int]] = defaultdict(list)
    for i, (text, _) in enumerate(rows):
        by_key[normalise(text)].append(i)
    repeats = [idx for idx in by_key.values() if len(idx) > 1]
    out = f"{len(by_key)} distinct texts in {len(rows)} rows (case and whitespace ignored)"
    for idx in repeats:
        labels = sorted({rows[i][1] for i in idx})
        out += (f"; rows {' and '.join(map(str, idx))} hold one text up to case or whitespace, "
                + ("same label" if len(labels) == 1 else f"labelled {' / '.join(labels)}"))
    return out


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get(url: str, timeout: int) -> bytes:
    for attempt in range(1, DOWNLOAD_ATTEMPTS):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except (OSError, http.client.HTTPException):   # URLError, timeouts, resets, a cut body
            time.sleep(5 * 2 ** (attempt - 1))
    try:                                          # the last attempt
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read()
    except (OSError, http.client.HTTPException) as exc:
        raise SystemExit(f"{url}: {exc!r} after {DOWNLOAD_ATTEMPTS} attempts") from exc


def download(url: str, want: str, cached: Path | None = None, timeout: int = 300) -> bytes:
    """The bytes at `url`, verified against `want`. A network failure is retried with
    backoff; a sha256 mismatch is not (the pin, not the network, is wrong). With `cached`,
    a file there that matches the pin is used without the network, and verified bytes
    are written there."""
    if cached is not None and cached.exists():
        data = cached.read_bytes()
        if sha256_bytes(data) == want:
            return data
    data = _get(url, timeout)
    got = sha256_bytes(data)
    if got != want:
        raise SystemExit(f"{url}: sha256 {got} != pinned {want}")
    if cached is not None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
    return data


def fetch(source: dict, path: str, src_dir: Path | None,
          cache_dir: Path | None = None) -> bytes:
    """One upstream file at the pinned commit, verified against its recorded sha256
    (cached as DIR/<repo name>/<path>, the layout --src reads)."""
    local = Path(source["repo"].split("/")[1]) / path
    if src_dir is None:
        url = f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{path}"
        return download(url, source["files"][path],
                        cache_dir / local if cache_dir is not None else None, timeout=60)
    data = (src_dir / local).read_bytes()
    got, want = sha256_bytes(data), source["files"][path]
    if got != want:
        raise SystemExit(f"{source['repo']}/{path}: sha256 {got} != pinned {want}")
    return data


def provenance(key: str, path: str) -> dict:
    s = SOURCES[key]
    return {"name": s["name"], "repository": f"https://github.com/{s['repo']}",
            "commit": s["commit"], "file": path, "sha256": s["files"][path],
            "licence": s["licence"], "licence_url": s["licence_url"],
            "citation": s["citation"]}


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
        ("online-banking queries with one intent label each, as released by the authors; how "
         "the queries were collected and labelled is not documented upstream, and no "
         "inter-annotator agreement is published"),
        ("Ying & Thomas (2022, https://aclanthology.org/2022.insights-1.19/) flag over 1,400 "
         "of the 10,003 train queries (about 14 %) as possibly mislabelled, found by automated "
         "detection, not by relabelling"),
        ("the options are the dataset's label names without definitions; some names mislead "
         "(get_physical_card also holds questions about the PIN)"),
    ]
    test_header = {
        "ground_truth": {
            "tier": "GT-3", "label": "human-annotated", "validation": "not_validated",
            "purpose": [("calibration and selective prediction on human-written "
                         "online-banking queries"), "comparison between judges on the same rows"],
            "caveats": common_caveats + [
                ("label noise of the test split not yet measured: a 500-row random sample is "
                 "drawn for two blind annotators (examples/banking77/relabel-sample.json)"),
                distinct_caveat(test),
                (f"{sum(in_train)} of {len(test)} test texts also appear in the train split "
                 "(case and whitespace ignored); _meta.text_in_train marks them")],
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
            "purpose": [("pilot: token counts, throughput and variance before the "
                         "pre-registration fixes n; never used to score a judge")],
            "caveats": common_caveats + [
                (f"{PILOT_PER_INTENT} train queries per intent, drawn with "
                 f"random.Random({SEED}) in categories.json order; label noise not measured"),
                distinct_caveat([train[i] for i in picked])],
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
            "purpose": [("selective prediction when no option applies: does confidence fall "
                         "on out-of-scope requests?")],
            "caveats": [
                "public since 2019: probably in the pretraining data of the judges audited",
                ("queries written by crowd workers to a prompt (paraphrase a seed phrase, or "
                 "answer a scenario, for a given intent; out-of-scope queries crowd-sourced "
                 "too; Larson et al. 2019), not production traffic; one label per query, no "
                 "inter-annotator agreement published"),
                ("label noise not yet measured: a 500-row random sample is drawn for two blind "
                 "annotators (examples/clinc150/relabel-sample.json)"),
                distinct_caveat([(r["state"], r["labels"]["intent"]) for r in rows]),
                (f"domains {', '.join(selected)} only: {in_scope} in-scope test queries, "
                 f"{len(rows) - in_scope} out-of-scope ones (out of scope for all 150 "
                 "intents); a draft subset until the pre-registration fixes it"),
                (f"{seen} of {len(rows)} texts also appear in the train or validation "
                 "splits (case and whitespace ignored); _meta.text_in_train marks them"),
            ],
        },
        "source": provenance("clinc150", "data/data_full.json"),
        "subset": {"domains": list(selected), "out_of_scope_label": OUT_OF_SCOPE},
    }
    name = "examples/clinc150/labels-test-banking-credit.jsonl"
    return {name: jsonl(header, rows)}


MASSIVE_LOCALES = ("en-US", "es-ES", "ca-ES")
MASSIVE_SOURCE_LOCALE = "en-US"
MASSIVE_PILOT_SPLIT = "dev"
# The English-criteria arm. A translated arm is another dict of this shape whose `origin`
# says who wrote the translation (MASSIVE ships no intent descriptions in any language);
# the option identifiers, and so the labels, never change, and its files carry a
# `.criteria-<language>-<digest>` suffix (`_massive_arm`).
MASSIVE_ENGLISH_CRITERIA = {
    "language": "en",
    "instructions": ("Which intent does this request to a voice assistant express? "
                     "Choose exactly one."),
    "descriptions": {},
    "origin": ("instructions written in English by the judge-audit maintainers; the options "
               "are MASSIVE's intent identifiers, unchanged, without definitions"),
}
MASSIVE_TRANSLATION_CAVEAT = ("translated parallel data, not native traffic; labels from SLURP "
                              "annotation carried over by localisation")
MASSIVE_INTENT_SCORE = {0: "No", 1: "Yes", 2: "It is a reasonable interpretation of the goal"}
NUMBER_WORDS = {1: "one", 2: "two", 3: "three"}


def fetch_archive(source: dict, src_dir: Path | None,
                  cache_dir: Path | None = None) -> dict[str, bytes]:
    """The pinned members of a release archive, the archive and each member verified
    against their recorded sha256 (offline or cached: DIR/<repo name>/<archive file name>)."""
    name = source["archive"].rsplit("/", 1)[1]
    local = Path(source["repo"].split("/")[1]) / name
    if src_dir is not None:
        data = (src_dir / local).read_bytes()
    else:
        data = download(source["archive"], source["archive_sha256"],
                        cache_dir / local if cache_dir is not None else None)
    got = sha256_bytes(data)
    if got != source["archive_sha256"]:
        raise SystemExit(f"{name}: sha256 {got} != pinned {source['archive_sha256']}")
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for path, want in source["files"].items():
            try:
                member = tar.extractfile(path)
            except KeyError:
                member = None
            if member is None:
                raise SystemExit(f"{name}: {path} not in the archive")
            out[path] = member.read()
            got = sha256_bytes(out[path])
            if got != want:
                raise SystemExit(f"{name}: {path}: sha256 {got} != pinned {want}")
    return out


def read_jsonl(data: bytes) -> list[dict]:
    return [json.loads(x) for x in data.decode("utf-8").splitlines() if x.strip()]


def massive_provenance(locale: str) -> dict:
    s = SOURCES["massive"]
    path = f"1.1/data/{locale}.jsonl"
    return {"name": s["name"], "repository": f"https://github.com/{s['repo']}",
            "archive": s["archive"], "archive_sha256": s["archive_sha256"],
            "file": path, "sha256": s["files"][path], "licence": s["licence"],
            "licence_url": s["licence_url"], "citation": s["citation"],
            "derived_from": s["derived_from"]}


def _massive_check_criteria(criteria: dict, intents: list[str]) -> None:
    for key in ("language", "instructions", "origin"):
        if not criteria.get(key):
            raise SystemExit(f"MASSIVE criteria need a non-empty {key!r} (who wrote them, "
                             "in which language)")
    if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]+)*", criteria["language"]):
        raise SystemExit(f"MASSIVE criteria language {criteria['language']!r}: not a "
                         "language tag")
    unknown = sorted(set(criteria.get("descriptions", {})) - set(intents))
    if unknown:
        raise SystemExit(f"MASSIVE criteria describe {unknown}: not an intent")


def _massive_arm(criteria: dict) -> str:
    """The file-name suffix of a criteria arm: none for the English arm, else its language
    and a digest of the whole criteria object, so no arm overwrites another's files."""
    if criteria == MASSIVE_ENGLISH_CRITERIA:
        return ""
    canonical = json.dumps(criteria, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return f".criteria-{criteria['language']}-{sha256_bytes(canonical)[:8]}"


def _massive_aligned(locales: dict[str, list[dict]]) -> dict[str, list[tuple[str, int]]]:
    """For each split, its (id, index in the source-locale file) in source-locale file
    order, once every locale is checked to hold the same ids with the same intents."""
    src = locales[MASSIVE_SOURCE_LOCALE]
    by_id = {loc: {r["id"]: r for r in rows} for loc, rows in locales.items()}
    for loc, rows in locales.items():
        if len(by_id[loc]) != len(rows):
            raise SystemExit(f"MASSIVE {loc}: an id appears twice")
    splits: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for i, r in enumerate(src):
        splits[r["partition"]].append((r["id"], i))
    for part, items in splits.items():
        want = {i for i, _ in items}
        for loc in locales:
            have = {i for i, r in by_id[loc].items() if r["partition"] == part}
            for name, diff in (("lacks", want - have), ("adds", have - want)):
                if diff:
                    ids = sorted(diff, key=int)
                    raise SystemExit(f"MASSIVE {part}: {loc} {name} {len(ids)} id(s) of "
                                     f"{MASSIVE_SOURCE_LOCALE}: {', '.join(ids[:10])}")
        for i, _ in items:
            intents = {by_id[loc][i]["intent"] for loc in locales}
            if len(intents) > 1:
                raise SystemExit(f"MASSIVE id {i} has a different intent per locale: "
                                 f"{sorted(intents)}")
    return dict(splits)


def _massive_row(r: dict, index: int, question: dict, **seen: bool) -> dict:
    """`seen`: text_in_train_or_dev (test rows; BANKING77's text_in_train is train only)
    or text_in_test (pilot rows), under `normalise`, within the row's locale."""
    meta: dict = {"source": "massive", "locale": r["locale"], "split": r["partition"],
                  "id": r["id"], "source_index": index, "scenario": r["scenario"], **seen}
    if "judgments" in r:
        meta["intent_judgments"] = [j["intent_score"] for j in r["judgments"]]
    return {"state": r["utt"], "questions": [question], "labels": {"intent": r["intent"]},
            "_meta": meta}


def _massive_localisation_caveat(locale: str, rows: list[dict]) -> str:
    if locale == MASSIVE_SOURCE_LOCALE:
        return ("en-US is the source language: SLURP's English utterances, from which the "
                "other locales were localised; it carries no localisation judgments")
    scores = [r["_meta"]["intent_judgments"] for r in rows]
    some = sum(1 for s in scores if 0 in s)
    most = sum(1 for s in scores if 2 * s.count(0) > len(s))
    counts = sorted({len(s) for s in scores})
    judges = " or ".join(NUMBER_WORDS.get(k, str(k)) for k in counts)
    out = (f"localised from en-US by translators (FitzGerald et al. 2023 describe professional "
           "translators; the upstream card names each localiser by an obfuscated crowd-worker "
           f"ID) and judged by {judges} workers of the locale: {some} of {len(rows)} rows "
           "have at least one of the localisation judges answering No to 'Does the sentence "
           f"match the intent?', {most} a majority; _meta.intent_judgments keeps the scores "
           f"({', '.join(f'{k} {v}' for k, v in MASSIVE_INTENT_SCORE.items())})")
    if locale == "ca-ES":
        out += ("; ca-ES was added in MASSIVE 1.1, after the paper, which does not describe "
                "its localisation")
    return out


def _massive_unused(rows: list[dict]) -> list[str]:
    """The intents that are an option but never the label in this file."""
    options = rows[0]["questions"][0]["options"]
    unused = sorted(set(options) - {r["labels"]["intent"] for r in rows})
    return ([f"{len(unused)} of the {len(options)} intents never the label here "
             f"({', '.join(unused)}), still an option"] if unused else [])


def _massive_header(locale: str, rows: list[dict], criteria: dict, purpose: list[str],
                    extra: list[str]) -> dict:
    return {
        "ground_truth": {
            "tier": "GT-3", "label": "human-annotated", "validation": "not_validated",
            "purpose": purpose,
            "caveats": [
                MASSIVE_TRANSLATION_CAVEAT,
                "public since 2022: probably in the pretraining data of the judges audited",
                ("SLURP's utterances are requests to a home voice assistant collected for a "
                 "research corpus, not production traffic; one intent label each, and "
                 "MASSIVE publishes no inter-annotator agreement on the intent labels"),
                _massive_localisation_caveat(locale, rows),
                (f"options: the {len(rows[0]['questions'][0]['options'])} MASSIVE intent "
                 "identifiers in alphabetical order, without definitions; instructions in "
                 f"criteria.language ({criteria['language']}) whatever the locale of the text"),
                "label noise not measured",
                distinct_caveat([(r["state"], r["labels"]["intent"]) for r in rows]),
                *_massive_unused(rows), *extra],
        },
        "source": massive_provenance(locale),
        "locale": locale,
        "criteria": {"language": criteria["language"], "origin": criteria["origin"]},
        "parallel": {"key": "_meta.id", "locales": list(MASSIVE_LOCALES)},
    }


def _massive_question(intents: list[str], criteria: dict) -> dict:
    q = {"name": "intent", "type": "choice", "instructions": criteria["instructions"],
         "options": intents}
    if criteria.get("descriptions"):
        q["descriptions"] = dict(criteria["descriptions"])
    return q


def _massive_prepare(locales: dict[str, list[dict]], criteria: dict):
    missing = [loc for loc in MASSIVE_LOCALES if loc not in locales]
    if missing:
        raise SystemExit(f"MASSIVE: no data for {missing}")
    locales = {loc: locales[loc] for loc in MASSIVE_LOCALES}
    intents = sorted({r["intent"] for r in locales[MASSIVE_SOURCE_LOCALE]})
    _massive_check_criteria(criteria, intents)
    return locales, intents, _massive_aligned(locales), _massive_question(intents, criteria)


def massive(locales: dict[str, list[dict]],
            criteria: dict = MASSIVE_ENGLISH_CRITERIA) -> dict[str, str]:
    """The test split in each locale, and the pilot sample of the dev split, as the same
    items in the same order in every locale (rows aligned on MASSIVE's `id`)."""
    locales, intents, splits, question = _massive_prepare(locales, criteria)
    by_id = {loc: {r["id"]: (k, r) for k, r in enumerate(rows)} for loc, rows in locales.items()}

    # the pilot: PILOT_PER_INTENT dev items per intent, drawn once for every locale
    dev_by_label: dict[str, list[str]] = defaultdict(list)
    for i, _ in splits.get(MASSIVE_PILOT_SPLIT, []):
        dev_by_label[by_id[MASSIVE_SOURCE_LOCALE][i][1]["intent"]].append(i)
    rng = random.Random(SEED)
    pilot_ids: list[str] = []
    for label in intents:                          # alphabetical, then seeded
        ids = list(dev_by_label[label])
        rng.shuffle(ids)
        pilot_ids.extend(sorted(ids[:PILOT_PER_INTENT], key=int))
    short = [f"{label} {len(dev_by_label[label])}" for label in intents
             if len(dev_by_label[label]) < PILOT_PER_INTENT]

    test_ids = [i for i, _ in splits.get("test", [])]
    arm = _massive_arm(criteria)
    out: dict[str, str] = {}
    for loc in MASSIVE_LOCALES:
        seen = {normalise(r["utt"]) for r in locales[loc] if r["partition"] in ("train", "dev")}
        test_rows = []
        for i in test_ids:
            k, r = by_id[loc][i]
            test_rows.append(_massive_row(r, k, question,
                                          text_in_train_or_dev=normalise(r["utt"]) in seen))
        n_seen = sum(1 for r in test_rows if r["_meta"]["text_in_train_or_dev"])
        header = _massive_header(
            loc, test_rows, criteria,
            [("calibration and selective prediction per language on the same items"),
             "comparison between judges and between languages on parallel rows"],
            [(f"{n_seen} of {len(test_rows)} test texts also appear in the train or dev split "
              "of the same locale (case and whitespace ignored); _meta.text_in_train_or_dev "
              "marks them (BANKING77's text_in_train covers train only)")])
        out[f"examples/massive/labels-test-{loc}{arm}.jsonl"] = jsonl(header, test_rows)

        in_test = {normalise(r["state"]) for r in test_rows}
        pilot_rows = []
        for i in pilot_ids:
            k, r = by_id[loc][i]
            pilot_rows.append(_massive_row(r, k, question,
                                           text_in_test=normalise(r["utt"]) in in_test))
        n_test = sum(1 for r in pilot_rows if r["_meta"]["text_in_test"])
        header = _massive_header(
            loc, pilot_rows, criteria,
            [("pilot: token counts, throughput and variance before the pre-registration "
              "fixes n; never used to score a judge")],
            [(f"up to {PILOT_PER_INTENT} {MASSIVE_PILOT_SPLIT} utterances per intent, drawn "
              f"with random.Random({SEED}) over intents in alphabetical order, the same items "
              "in every locale; drawn from dev, not train, so that a classifier fine-tuned on "
              "train never saw them"
              + (f"; fewer in dev: {', '.join(short)}" if short else "")),
             (f"{n_test} of {len(pilot_rows)} pilot texts also appear in the test split of the "
              "same locale (case and whitespace ignored), though no pilot item is a test item; "
              "_meta.text_in_test marks them")])
        out[f"examples/massive/labels-pilot-{loc}{arm}.jsonl"] = jsonl(header, pilot_rows)
    return out


def massive_full_splits(locales: dict[str, list[dict]],
                        criteria: dict = MASSIVE_ENGLISH_CRITERIA) -> dict[str, str]:
    """Every train and dev utterance in each locale, for fine-tuning a classifier; written
    outside the repository (`--massive-full DIR`), never committed."""
    locales, _, splits, question = _massive_prepare(locales, criteria)
    by_id = {loc: {r["id"]: (k, r) for k, r in enumerate(rows)} for loc, rows in locales.items()}
    arm = _massive_arm(criteria)
    out: dict[str, str] = {}
    for part in ("train", "dev"):
        for loc in MASSIVE_LOCALES:
            rows = [_massive_row(by_id[loc][i][1], by_id[loc][i][0], question)
                    for i, _ in splits.get(part, [])]
            header = _massive_header(
                loc, rows, criteria,
                [f"training a classifier ({part} split); never used to score a judge"], [])
            out[f"labels-{part}-{loc}{arm}.jsonl"] = jsonl(header, rows)
    return out


def build(src_dir: Path | None, cache_dir: Path | None = None,
          locales: dict[str, list[dict]] | None = None) -> dict[str, str]:
    """Every committed file; `locales`: MASSIVE already read, to read its archive once."""
    b = SOURCES["banking77"]
    intents = json.loads(fetch(b, "banking_data/categories.json", src_dir, cache_dir))
    fetch(b, "LICENSE", src_dir, cache_dir)
    out = banking77(read_csv(fetch(b, "banking_data/test.csv", src_dir, cache_dir)),
                    read_csv(fetch(b, "banking_data/train.csv", src_dir, cache_dir)), intents)
    c = SOURCES["clinc150"]
    fetch(c, "LICENSE", src_dir, cache_dir)
    out.update(clinc150(json.loads(fetch(c, "data/data_full.json", src_dir, cache_dir)),
                        json.loads(fetch(c, "data/domains.json", src_dir, cache_dir))))
    if locales is None:
        locales = massive_locales(src_dir, cache_dir)
    out.update(massive(locales))
    return out


def massive_locales(src_dir: Path | None,
                    cache_dir: Path | None = None) -> dict[str, list[dict]]:
    files = fetch_archive(SOURCES["massive"], src_dir, cache_dir)
    return {loc: read_jsonl(files[f"1.1/data/{loc}.jsonl"]) for loc in MASSIVE_LOCALES}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a committed file differs from the regenerated one")
    ap.add_argument("--src", type=Path, default=None,
                    help=("read upstream files from DIR/<repo name>/<path> (MASSIVE: "
                          "DIR/massive/<archive file name>) instead of fetching"))
    ap.add_argument("--cache", type=Path, default=None, metavar="DIR",
                    help=("keep verified downloads in DIR (the --src layout) and reuse them; "
                          "a cached file that no longer matches its pin is fetched again"))
    ap.add_argument("--massive-full", type=Path, default=None, metavar="DIR",
                    help="also write MASSIVE's whole train and dev splits to DIR")
    args = ap.parse_args(argv)
    locales = massive_locales(args.src, args.cache)
    files = build(args.src, args.cache, locales)
    if args.massive_full is not None:
        args.massive_full.mkdir(parents=True, exist_ok=True)
        for name, text in massive_full_splits(locales).items():
            (args.massive_full / name).write_text(text, encoding="utf-8")
            print(f"wrote: {args.massive_full / name}")
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
