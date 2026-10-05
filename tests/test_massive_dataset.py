"""MASSIVE 1.1 in en-US, es-ES and ca-ES (#133): conversion, alignment, pins — no network."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path

import pytest

from judge_audit.runner import load_dataset

ROOT = Path(__file__).resolve().parent.parent
needs_data = pytest.mark.skipif(not (ROOT / "examples/massive/labels-test-en-US.jsonl").exists(),
                                reason="third-party datasets are not in this source tree")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fetch = _load("fetch_real_datasets")
LOCALES = fetch.MASSIVE_LOCALES


def _utt(i: int, locale: str, partition: str, intent: str, text: str,
         scores: tuple[int, ...] = (1, 1, 1)) -> dict:
    row = {"id": str(i), "locale": locale, "partition": partition,
           "scenario": intent.split("_")[0], "intent": intent, "utt": text,
           "annot_utt": text, "worker_id": "1"}
    if locale != "en-US":
        row["judgments"] = [{"worker_id": str(k), "intent_score": s, "slots_score": 1,
                             "grammar_score": 4, "spelling_score": 2,
                             "language_identification": "target"}
                            for k, s in enumerate(scores)]
    return row


def _corpus() -> dict[str, list[dict]]:
    """Three locales, the same ids, two intents; 2 test, 10 dev, 2 train rows each."""
    plan = ([("test", "alarm_set"), ("test", "weather_query")]
            + [("dev", "alarm_set" if k % 2 else "weather_query") for k in range(10)]
            + [("train", "alarm_set"), ("train", "weather_query")])
    text = {"en-US": "wake me at {i}", "es-ES": "despiértame a las {i}",
            "ca-ES": "desperta'm a les {i}"}
    out = {}
    for loc in LOCALES:
        rows = [_utt(i, loc, part, intent, text[loc].format(i=i))
                for i, (part, intent) in enumerate(plan)]
        rows[-2]["utt"] = rows[0]["utt"].upper()           # a test text seen in train
        out[loc] = rows
    out["ca-ES"][1]["judgments"][0]["intent_score"] = 0    # one judge: intent does not match
    out["ca-ES"][1]["judgments"][1]["intent_score"] = 0    # ... and a second: a majority
    return out


def _lines(text: str) -> tuple[dict, list[dict]]:
    header, *rows = [json.loads(x) for x in text.splitlines()]
    return header["dataset"], rows


# --- conversion on small fixtures --------------------------------------------------------


def test_massive_writes_one_test_and_one_pilot_file_per_locale_on_the_same_ids():
    files = fetch.massive(_corpus())
    assert sorted(files) == sorted(
        [f"examples/massive/labels-test-{loc}.jsonl" for loc in LOCALES]
        + [f"examples/massive/labels-pilot-{loc}.jsonl" for loc in LOCALES])
    ids = {}
    for loc in LOCALES:
        dataset, rows = _lines(files[f"examples/massive/labels-test-{loc}.jsonl"])
        assert dataset["ground_truth"]["tier"] == "GT-3"
        assert dataset["locale"] == loc
        assert [r["_meta"]["locale"] for r in rows] == [loc, loc]
        assert [r["labels"]["intent"] for r in rows] == ["alarm_set", "weather_query"]
        q = rows[0]["questions"][0]
        assert q["options"] == ["alarm_set", "weather_query"]          # alphabetical
        assert q["instructions"] == fetch.MASSIVE_ENGLISH_CRITERIA["instructions"]
        assert [r["_meta"]["text_in_train"] for r in rows] == [True, False]
        ids[loc] = [r["_meta"]["id"] for r in rows]
    assert ids["en-US"] == ids["es-ES"] == ids["ca-ES"] == ["0", "1"]
    assert fetch.massive(_corpus()) == files                             # deterministic


def test_massive_header_carries_the_translation_caveat_and_the_criteria_origin():
    files = fetch.massive(_corpus())
    for loc in LOCALES:
        dataset, _ = _lines(files[f"examples/massive/labels-test-{loc}.jsonl"])
        caveats = dataset["ground_truth"]["caveats"]
        assert fetch.MASSIVE_TRANSLATION_CAVEAT in caveats
        assert "translated parallel data, not native traffic" in caveats[0]
        assert dataset["criteria"]["language"] == "en"
        assert "maintainers" in dataset["criteria"]["origin"]
        assert dataset["parallel"] == {"key": "_meta.id", "locales": list(LOCALES)}
        assert any(c.startswith("2 distinct texts in 2 rows") for c in caveats)
        assert any(c.startswith("1 of 2 test texts also appear in the train or dev split")
                   for c in caveats)


def test_massive_keeps_the_localisation_judgments_and_counts_the_doubtful_ones():
    files = fetch.massive(_corpus())
    dataset, rows = _lines(files["examples/massive/labels-test-ca-ES.jsonl"])
    assert rows[1]["_meta"]["intent_judgments"] == [0, 0, 1]
    assert any("1 of 2 rows have at least one of the localisation judges answering No" in c
               and "1 a majority" in c for c in dataset["ground_truth"]["caveats"])
    _, en = _lines(files["examples/massive/labels-test-en-US.jsonl"])
    assert "intent_judgments" not in en[0]["_meta"]                  # the source language


def test_massive_pilot_is_drawn_from_dev_per_intent_and_shared_by_every_locale():
    files = fetch.massive(_corpus())
    pilot_ids = {}
    for loc in LOCALES:
        dataset, rows = _lines(files[f"examples/massive/labels-pilot-{loc}.jsonl"])
        assert all(r["_meta"]["split"] == "dev" for r in rows)
        assert Counter(r["labels"]["intent"] for r in rows) == {
            "alarm_set": fetch.PILOT_PER_INTENT, "weather_query": fetch.PILOT_PER_INTENT}
        assert "never used to score a judge" in dataset["ground_truth"]["purpose"][0]
        pilot_ids[loc] = [r["_meta"]["id"] for r in rows]
    assert pilot_ids["en-US"] == pilot_ids["es-ES"] == pilot_ids["ca-ES"]


def test_massive_names_an_intent_a_file_never_uses_and_keeps_it_as_an_option():
    corpus = _corpus()
    for loc in LOCALES:
        corpus[loc][1]["intent"] = "alarm_set"                  # no weather_query in test
        for r in corpus[loc][2:10]:                             # 1 weather_query left in dev
            r["intent"] = "alarm_set"
    files = fetch.massive(corpus)
    dataset, rows = _lines(files["examples/massive/labels-test-es-ES.jsonl"])
    assert rows[0]["questions"][0]["options"] == ["alarm_set", "weather_query"]
    assert ("1 of the 2 intents never the label here (weather_query), still an option"
            in dataset["ground_truth"]["caveats"])
    dataset, rows = _lines(files["examples/massive/labels-pilot-es-ES.jsonl"])
    assert Counter(r["labels"]["intent"] for r in rows) == {"alarm_set": 4, "weather_query": 1}
    assert any("fewer in dev: weather_query 1" in c for c in dataset["ground_truth"]["caveats"])


def test_massive_refuses_a_locale_that_misses_an_id_and_names_it():
    corpus = _corpus()
    corpus["es-ES"] = [r for r in corpus["es-ES"] if r["id"] != "1"]
    with pytest.raises(SystemExit, match=r"test: es-ES lacks 1 id.*\b1\b"):
        fetch.massive(corpus)


def test_massive_refuses_one_id_with_two_intents_across_locales():
    corpus = _corpus()
    corpus["ca-ES"][0]["intent"] = "weather_query"
    with pytest.raises(SystemExit, match="id 0 .*intent"):
        fetch.massive(corpus)


def test_massive_refuses_criteria_without_an_origin_or_with_an_unknown_intent():
    base = dict(fetch.MASSIVE_ENGLISH_CRITERIA)
    with pytest.raises(SystemExit, match="origin"):
        fetch.massive(_corpus(), {**base, "origin": ""})
    with pytest.raises(SystemExit, match="not an intent"):
        fetch.massive(_corpus(), {**base, "descriptions": {"alarm_sett": "x"}})


def test_massive_full_splits_hold_every_train_and_dev_row():
    files = fetch.massive_full_splits(_corpus())
    assert sorted(files) == sorted(f"labels-{part}-{loc}.jsonl"
                                   for part in ("train", "dev") for loc in LOCALES)
    _, dev = _lines(files["labels-dev-es-ES.jsonl"])
    assert len(dev) == 10 and {r["_meta"]["split"] for r in dev} == {"dev"}


def _tarball(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_fetch_archive_verifies_the_archive_and_every_member(tmp_path, monkeypatch):
    members = {"1.1/LICENSE": b"licence", "1.1/data/en-US.jsonl": b"{}\n"}
    archive = _tarball(members)
    (tmp_path / "massive").mkdir()
    (tmp_path / "massive" / "m.tar.gz").write_bytes(archive)
    pins = {name: hashlib.sha256(data).hexdigest() for name, data in members.items()}
    source = {"name": "MASSIVE", "repo": "alexa/massive",
              "archive": "https://example.invalid/m.tar.gz",
              "archive_sha256": hashlib.sha256(archive).hexdigest(), "files": pins}
    monkeypatch.setitem(fetch.SOURCES, "massive", source)
    assert fetch.fetch_archive(source, tmp_path) == members
    with pytest.raises(SystemExit, match="1.1/LICENSE: sha256"):
        fetch.fetch_archive({**source, "files": {**pins, "1.1/LICENSE": "0" * 64}}, tmp_path)
    with pytest.raises(SystemExit, match="m.tar.gz: sha256"):
        fetch.fetch_archive({**source, "archive_sha256": "0" * 64}, tmp_path)
    with pytest.raises(SystemExit, match="not in the archive"):
        fetch.fetch_archive({**source, "files": {**pins, "1.1/NOTICE.md": "0" * 64}}, tmp_path)


# --- the committed files -----------------------------------------------------------------


def _committed(kind: str, loc: str) -> tuple[list[dict], dict]:
    return load_dataset(str(ROOT / f"examples/massive/labels-{kind}-{loc}.jsonl"))


@needs_data
@pytest.mark.parametrize("loc", LOCALES)
def test_committed_massive_file_is_what_its_header_says(loc):
    src = fetch.SOURCES["massive"]
    # dev has no audio_volume_other and two of cooking_query, general_greet and
    # music_dislikeness: 4 x 56 + 3 x 2; test has no cooking_query
    for kind, n in (("test", 2974), ("pilot", 230)):
        rows, dataset = _committed(kind, loc)
        assert len(rows) == n
        assert dataset["ground_truth"]["tier"] == "GT-3"
        assert dataset["source"]["archive_sha256"] == src["archive_sha256"]
        assert dataset["source"]["sha256"] == src["files"][f"1.1/data/{loc}.jsonl"]
        assert dataset["source"]["licence"] == "CC BY 4.0"
        caveats = dataset["ground_truth"]["caveats"]
        assert fetch.MASSIVE_TRANSLATION_CAVEAT in caveats
        distinct = {fetch.normalise(r["state"]) for r in rows}
        assert f"{len(distinct)} distinct texts in {n} rows" in " ".join(caveats)
        for r in rows:
            (q,) = r["questions"]
            assert len(q["options"]) == 60 and r["labels"]["intent"] in q["options"]


@needs_data
@pytest.mark.parametrize("kind", ["test", "pilot"])
def test_committed_locales_are_the_same_items_with_the_same_labels(kind):
    by_loc = {loc: [(r["_meta"]["id"], r["labels"]["intent"]) for r in _committed(kind, loc)[0]]
              for loc in LOCALES}
    assert by_loc["en-US"] == by_loc["es-ES"] == by_loc["ca-ES"]
    assert len({i for i, _ in by_loc["en-US"]}) == len(by_loc["en-US"])


@needs_data
def test_committed_pilot_never_shares_an_item_with_the_test_split():
    test = {r["_meta"]["id"] for r in _committed("test", "en-US")[0]}
    pilot = {r["_meta"]["id"] for r in _committed("pilot", "en-US")[0]}
    assert not test & pilot


@needs_data
def test_the_dataset_card_names_the_sha256_of_every_committed_and_upstream_file():
    card = (ROOT / "examples/massive/README.md").read_text(encoding="utf-8")
    for path in sorted((ROOT / "examples/massive").glob("labels-*.jsonl")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert f"`{path.name}`" in card and digest in card, path.name
    src = fetch.SOURCES["massive"]
    for digest in [src["archive_sha256"], *src["files"].values()]:
        assert digest in card
