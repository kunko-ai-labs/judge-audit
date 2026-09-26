"""Third-party datasets (#86): conversion, provenance, relabelling — no network."""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from judge_audit.runner import load_dataset, sha256_rows_of

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fetch = _load("fetch_real_datasets")
relabel = _load("relabel")

COMMITTED = {
    "examples/banking77/labels-test.jsonl": ("banking77", "banking_data/test.csv", 3080, 77),
    "examples/banking77/labels-pilot.jsonl": ("banking77", "banking_data/train.csv", 308, 77),
    "examples/clinc150/labels-test-banking-credit.jsonl":
        ("clinc150", "data/data_full.json", 1900, 31),
}


def _rows(path: str) -> list[dict]:
    return [json.loads(x) for x in (ROOT / path).read_text(encoding="utf-8").splitlines()][1:]


# --- conversion on small fixtures --------------------------------------------------------


def test_banking77_conversion_marks_texts_seen_in_train_and_samples_the_pilot():
    intents = ["a", "b"]
    test = [("Where is my card?", "a"), ("Top up failed", "b")]
    train = [("where  is my CARD?", "a")] + [(f"t{i}", "a" if i % 2 else "b") for i in range(12)]
    files = fetch.banking77(test, train, intents)
    header, *rows = [json.loads(x) for x in files["examples/banking77/labels-test.jsonl"]
                     .splitlines()]
    assert header["dataset"]["ground_truth"]["tier"] == "GT-3"
    assert "1 of 2 test texts also appear in the train split" in \
        header["dataset"]["ground_truth"]["caveats"][-1]
    assert [r["_meta"]["text_in_train"] for r in rows] == [True, False]
    assert rows[0]["questions"][0]["options"] == intents
    assert rows[1]["labels"] == {"intent": "b"}
    pilot = [json.loads(x) for x in files["examples/banking77/labels-pilot.jsonl"]
             .splitlines()][1:]
    counts = Counter(r["labels"]["intent"] for r in pilot)
    assert counts == {"a": fetch.PILOT_PER_INTENT, "b": fetch.PILOT_PER_INTENT}
    assert all(r["_meta"]["split"] == "train" for r in pilot)
    assert fetch.banking77(test, train, intents) == files           # deterministic


def test_banking77_refuses_a_label_outside_the_categories():
    with pytest.raises(SystemExit, match="outside categories"):
        fetch.banking77([("x", "zzz")], [], ["a"])


def test_clinc150_keeps_the_selected_domains_and_every_out_of_scope_query():
    data = {"test": [("pay my bill", "pay_bill"), ("book a flight", "book_flight"),
                     ("freeze my card", "freeze_account")],
            "oos_test": [("what is the meaning of life", "oos")],
            "train": [("PAY my bill", "pay_bill")], "val": [], "oos_train": [], "oos_val": []}
    domains = {"banking": ["pay_bill", "freeze_account"], "travel": ["book_flight"]}
    files = fetch.clinc150(data, domains, ("banking",))
    header, *rows = [json.loads(x) for x in next(iter(files.values())).splitlines()]
    assert [r["labels"]["intent"] for r in rows] == ["pay_bill", "freeze_account",
                                                     fetch.OUT_OF_SCOPE]
    assert rows[0]["questions"][0]["options"] == ["pay_bill", "freeze_account",
                                                  fetch.OUT_OF_SCOPE]
    assert rows[0]["_meta"]["text_in_train"] is True
    assert header["dataset"]["subset"]["domains"] == ["banking"]
    with pytest.raises(SystemExit, match="no domain"):
        fetch.clinc150(data, domains, ("nope",))


def test_fetch_refuses_a_file_whose_sha256_does_not_match_the_pin(tmp_path, monkeypatch):
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / "f.txt").write_text("changed upstream")
    monkeypatch.setitem(fetch.SOURCES, "x", {"repo": "owner/repo", "commit": "0",
                                             "files": {"f.txt": "0" * 64}})
    with pytest.raises(SystemExit, match="sha256"):
        fetch.fetch(fetch.SOURCES["x"], "f.txt", tmp_path)


# --- the committed files -----------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(COMMITTED))
def test_committed_dataset_is_what_its_header_says(path):
    key, upstream, n, n_options = COMMITTED[path]
    rows, dataset = load_dataset(str(ROOT / path))
    assert len(rows) == n
    assert dataset["ground_truth"]["tier"] == "GT-3"
    src = dataset["source"]
    assert src["commit"] == fetch.SOURCES[key]["commit"]
    assert src["sha256"] == fetch.SOURCES[key]["files"][upstream]
    assert src["licence"] == fetch.SOURCES[key]["licence"]
    assert len({r["state"] for r in rows}) == n                      # every text distinct
    for r in rows:
        (q,) = r["questions"]
        assert len(q["options"]) == n_options
        assert r["labels"][q["name"]] in q["options"]


def test_the_pilot_never_shares_a_text_with_the_test_split():
    test = {r["state"] for r in _rows("examples/banking77/labels-test.jsonl")}
    pilot = {r["state"] for r in _rows("examples/banking77/labels-pilot.jsonl")}
    assert not test & pilot


# --- relabelling -------------------------------------------------------------------------


def test_cohen_kappa_by_hand():
    # observed 3/4; chance: A says x half the time, B a quarter -> .5*.25 + .5*.75 = .5
    assert relabel.cohen_kappa(["x", "x", "y", "y"], ["x", "y", "y", "y"]) == pytest.approx(0.5)
    assert relabel.cohen_kappa(["x", "y"], ["x", "y"]) == 1.0
    assert relabel.cohen_kappa(["x", "x"], ["x", "x"]) is None        # chance agreement is 1
    with pytest.raises(ValueError):
        relabel.cohen_kappa(["x"], [])


def test_stratified_sample_is_proportional_and_seeded():
    labels = ["oos"] * 100 + [f"i{k}" for k in range(10) for _ in range(10)]   # 100 + 10x10
    idx = relabel.stratified_sample(labels, 50)
    counts = Counter(labels[i] for i in idx)
    assert len(idx) == 50 and counts["oos"] == 25
    assert all(counts[f"i{k}"] in (2, 3) for k in range(10))
    assert relabel.stratified_sample(labels, 50) == idx
    with pytest.raises(ValueError):
        relabel.stratified_sample(labels, 0)


def test_the_blind_sheet_does_not_keep_the_dataset_order():
    order = relabel.sheet_order(list(range(40)), seed=2026)
    assert sorted(order) == list(range(40)) and order != list(range(40))


@pytest.mark.parametrize("sample_path", ["examples/banking77/relabel-sample.json",
                                         "examples/clinc150/relabel-sample.json"])
def test_committed_relabel_samples_regenerate(sample_path):
    sample = json.loads((ROOT / sample_path).read_text(encoding="utf-8"))
    rows = _rows(sample["dataset"])
    assert sample["sha256_rows"] == sha256_rows_of(str(ROOT / sample["dataset"]))
    labels = [r["labels"][sample["question"]] for r in rows]
    assert sample["indices"] == relabel.stratified_sample(labels, sample["n"], sample["seed"])


def test_score_reports_agreement_and_likely_label_errors(tmp_path):
    rows = [{"state": f"s{i}", "questions": [{"name": "q", "options": ["x", "y"]}],
             "labels": {"q": "x"}} for i in range(4)]
    sample = {"question": "q", "indices": [0, 1, 2, 3]}
    a = {0: "x", 1: "x", 2: "y", 3: "y"}
    b = {0: "x", 1: "y", 2: "y", 3: "y"}
    res = relabel.score(sample, rows, a, b)
    assert res["annotator_agreement"] == 0.75 and res["cohen_kappa"] == 0.5
    assert res["agreement_with_dataset"] == {"a": 0.5, "b": 0.25}
    assert res["both_annotators_differ_from_dataset"]["ids"] == [2, 3]
    assert res["annotators_disagree"]["ids"] == [1]
    sheet = tmp_path / "a.csv"
    with open(sheet, "w", newline="") as f:
        csv.writer(f).writerows([["id", "text", "label"], [0, "s0", "z"]])
    with pytest.raises(SystemExit, match="not an option"):
        relabel.read_sheet(str(sheet), {"x", "y"})
