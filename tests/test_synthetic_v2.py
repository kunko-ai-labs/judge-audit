"""v2 synthetic stress sets (US-005-002, #87): generator rules, invariants, committed files.

No network, no model call. The fixtures are small enough to check by hand; the committed
files are checked with the same functions CI runs (`scripts/synthetic_v2.py --check`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from judge_audit.runner import load_dataset, sha256_rows_of

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


common = _load("synthetic_v2_common", ROOT / "examples" / "synthetic_v2_common.py")
check = _load("synthetic_v2", ROOT / "scripts" / "synthetic_v2.py")
fetch = _load("fetch_real_datasets", ROOT / "scripts" / "fetch_real_datasets.py")

V2 = {
    "email-routing-v2": "examples/email-routing-v2",
    "email-routing-adversarial-v2": "examples/email-routing-adversarial-v2",
    "task-routing-v2": "examples/task-routing-v2",
}


def _gen(name: str):
    return _load(f"gen_{name.replace('-', '_')}", ROOT / V2[name] / "generate.py")


def _v1(name: str):
    return _load(f"gen_v1_{name.replace('-', '_')}", ROOT / "examples" / name / "generate.py")


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()][1:]


def row(state: str, templates: tuple[str, ...] = ("t1",), base: str | None = None,
        label: str = "a") -> dict:
    meta: dict = {"template": templates[0],
                  "attack_template": templates[1] if len(templates) > 1 else None}
    if base is not None:
        meta["base"] = base
    return {"state": state, "questions": [{"name": "q", "options": ["a", "b"]}],
            "labels": {"q": label}, "_meta": meta}


# --- the repository's one rule for "the same text" ---------------------------------------

@pytest.mark.parametrize("text", ["A  b", " a\tB\n", "Straße", "оrder", "", "x​y"])
def test_normalise_is_the_repository_rule(text):
    assert common.normalise(text) == fetch.normalise(text)


def test_zero_width_space_is_not_whitespace_so_a_disguised_text_stays_distinct():
    assert common.normalise("or​der") != common.normalise("order")


# --- Unique: fills until the text is new ---------------------------------------------------

def test_unique_rejects_case_and_whitespace_variants_and_retries():
    fills = iter(["Hello  World", "hello world", "HELLO\tworld", "bye"])
    u = common.Unique(taken=["hello world"])
    assert u.draw(lambda: next(fills)) == "bye"
    assert "bye" in u


def test_unique_raises_when_the_fills_are_exhausted():
    u = common.Unique(taken=["same"], tries=5)
    with pytest.raises(RuntimeError, match="no new text after 5 fills"):
        u.draw(lambda: "Same")


def test_assert_unique_states_names_the_repeated_rows():
    common.assert_unique_states([row("a"), row("b")])
    with pytest.raises(ValueError, match="rows 0 and 2"):
        common.assert_unique_states([row("Hi there"), row("x"), row("hi  THERE")])


# --- the template-level split -----------------------------------------------------------

@pytest.mark.parametrize("k,h", [(0, 0), (1, 0), (2, 1), (3, 1), (4, 1), (7, 1), (8, 2),
                                 (10, 2), (12, 3), (40, 10)])
def test_a_quarter_of_a_stratum_is_held_out_at_least_one_of_two_none_of_one(k, h):
    assert common.n_heldout(k) == h


def test_split_templates_partitions_every_stratum():
    strata = {"x": ["a", "b", "c", "d"], "y": ["e"], "z": ["f", "g", "h", "i", "j", "k", "l", "m"]}
    dev, heldout = common.split_templates(strata, seed=1)
    assert sorted(dev + heldout) == list("abcdefghijklm") and not set(dev) & set(heldout)
    assert len(set(heldout) & set("abcd")) == 1
    assert "e" in dev                                  # a stratum of one is never held out
    assert len(set(heldout) & set("fghijklm")) == 2
    assert dev == sorted(dev) and heldout == sorted(heldout)


def test_split_templates_is_deterministic_and_independent_of_input_order():
    strata = {"x": [f"t{i:02d}" for i in range(40)]}
    a = common.split_templates(strata, seed=2027)
    assert a == common.split_templates({"x": list(reversed(strata["x"]))}, seed=2027)
    assert a != common.split_templates(strata, seed=1)


def test_split_templates_refuses_a_template_in_two_strata_and_accepts_none():
    with pytest.raises(ValueError, match="'a' in more than one stratum"):
        common.split_templates({"x": ["a", "b"], "y": ["a"]})
    assert common.split_templates({}) == ([], [])


def test_rows_follow_their_templates_and_a_mixed_row_is_refused():
    rows = [row("r0", ("d1",)), row("r1", ("h1", "h2")), row("r2", ("d1", "d2"))]
    assert common.partition_rows(rows, ["d1", "d2"], ["h1", "h2"]) == ([0, 2], [1])
    with pytest.raises(ValueError, match="row 0"):
        common.partition_rows([row("r0", ("d1", "h1"))], ["d1"], ["h1"])
    with pytest.raises(ValueError, match="row 0"):
        common.partition_rows([row("r0", ("unknown",))], ["d1"], ["h1"])


# --- new wording on the held-out side --------------------------------------------------

def test_phrases_count_slots_as_words_and_drop_digits_punctuation_and_slot_only_runs():
    assert common.phrases("Rechnung {n} über {amount} EUR ist falsch.", n=3) == {
        ("rechnung", "{n}", "über"), ("{n}", "über", "{amount}"), ("über", "{amount}", "eur"),
        ("{amount}", "eur", "ist"), ("eur", "ist", "falsch")}
    assert common.phrases("{a} {b} x", n=2) == {("{b}", "x")}
    assert common.phrases("PO 2026, order!", n=2) == {("po", "order")}
    assert common.phrases("too short", n=6) == set()


def test_cross_half_phrases_names_only_runs_shared_across_the_halves():
    texts = {"d": ["Please send the quote now."], "h": ["Kindly send the quote now!"],
             "h2": ["Nothing alike here at all."], "d2": ["please SEND the quote now"]}
    half = {"d": "dev", "d2": "dev", "h": "heldout", "h2": "heldout"}
    assert common.cross_half_phrases(texts, half, n=4) == [
        ("d", "h", "send the quote now"), ("d2", "h", "send the quote now")]
    assert common.cross_half_phrases(texts, half, n=5) == []
    # a run shared inside one half is not a leak
    assert common.cross_half_phrases({"a": ["x y z w"], "b": ["x y z w"]},
                                     {"a": "dev", "b": "dev"}, n=4) == []
    assert common.PHRASE_WORDS == 6


def test_v1_strings_are_development_data_for_every_v2_file():
    v1 = check.v1_texts()
    assert all(k.startswith("v1/") for k in v1)
    flat = [x for xs in v1.values() for x in xs]
    assert "Passport no. X8471220 attached for verification purposes." in [x.strip() for x in flat]
    assert any(x.startswith("[SYSTEM OVERRIDE] Complexity assessment") for x in
               (y.strip() for y in flat))
    assert any("Bestellung Nr. {n}" in x for x in flat)          # v1 email templates
    assert any(x.startswith("Implement an LRU cache") for x in flat)  # v1 router tasks


def test_a_held_out_template_sharing_six_words_with_v1_is_a_leak_and_a_dev_one_is_not():
    v1 = check.v1_texts()
    texts = {"h": ["Passport no. X8471220 attached for verification purposes."],
             "d": ["nothing in common with anything"]}
    leaks = check.leaked_phrases(texts, {"h": "heldout", "d": "dev"}, v1)
    assert leaks and all(h == "h" and dv.startswith("v1/") for dv, h, _ in leaks)
    # digits are dropped, the letter of "X8471220" stays a word
    assert {r for *_, r in leaks} == {"passport no x attached for verification",
                                     "no x attached for verification purposes"}
    # development templates may reuse v1 wording: v1 is development data too
    assert check.leaked_phrases(texts, {"h": "dev", "d": "dev"}, v1) == []
    # and a v2-only leak is still found without v1
    assert check.leaked_phrases({"a": ["one two three four five six"],
                                 "b": ["one two three four five six"]},
                                {"a": "dev", "b": "heldout"}, {}) == [
        ("a", "b", "one two three four five six")]


@pytest.mark.parametrize("name", list(V2))
def test_no_held_out_template_shares_six_words_with_development_or_v1(name):
    gen = _gen(name)
    assert set(gen.TEMPLATE_TEXTS) == set(gen.HALF)
    assert check.leaked_phrases(gen.TEMPLATE_TEXTS, gen.HALF, check.v1_texts()) == []


# --- the invariants CI enforces, on fixtures -----------------------------------------------

def test_duplicate_states_are_found_under_the_rule():
    rows = [row("Hello  world"), row("x"), row("hello world"), row("HELLO WORLD")]
    assert check.duplicate_states(rows) == [[0, 2, 3]]
    assert check.duplicate_states([row("a"), row("b")]) == []
    assert check.duplicate_states([]) == []


def test_shared_bases_names_the_adversarial_rows_built_on_a_clean_text():
    clean = [row("Order 1 please"), row("Quote 2")]
    adv = [row("x", base="order 1  PLEASE"), row("y", base="Quote 3"), row("z")]
    assert check.shared_bases(clean, adv) == [0]
    assert check.shared_bases(clean, [row("y", base="Quote 3")]) == []


def test_a_row_without_a_base_is_its_own_base():
    assert check.shared_bases([row("same")], [row("SAME")]) == [0]


def test_duplicate_bases_within_the_adversarial_file():
    adv = [row("x", base="b1"), row("y", base="B1 "), row("z", base="b2")]
    assert check.duplicate_bases(adv) == [[0, 1]]


def test_split_problems_on_fixtures():
    rows = [row("r0", ("d1",)), row("r1", ("h1",))]
    ok = {"templates": {"dev": ["d1"], "heldout": ["h1"]}, "n": 2, "dev": [0], "heldout": [1]}
    assert check.split_problems(ok, rows) == []
    both = {**ok, "templates": {"dev": ["d1", "h1"], "heldout": ["h1"]}}
    assert any("both halves" in p for p in check.split_problems(both, rows))
    swapped = {**ok, "dev": [1], "heldout": [0]}
    assert any("row indices" in p for p in check.split_problems(swapped, rows))
    short = {**ok, "n": 3}
    assert any("n = 3" in p for p in check.split_problems(short, rows))
    empty = {**ok, "templates": {"dev": ["d1", "h1"], "heldout": []}, "dev": [0, 1],
             "heldout": []}
    assert any("no held-out" in p for p in check.split_problems(empty, rows))


def test_too_few_rows_is_a_problem():
    assert check.MIN_ROWS == 1000
    assert check.row_count_problems("f", [row(str(i)) for i in range(999)]) != []
    assert check.row_count_problems("f", [row(str(i)) for i in range(1000)]) == []


# --- the committed v2 files ------------------------------------------------------------------

def test_the_committed_v2_files_regenerate_and_hold_every_invariant(capsys):
    assert check.main(["--check"]) == 0, capsys.readouterr().out


@pytest.mark.parametrize("name", list(V2))
def test_each_v2_file_is_gt1_with_caveats_and_at_least_1000_distinct_texts(name):
    path = ROOT / V2[name] / "labels.jsonl"
    rows, dataset = load_dataset(str(path))
    gt = dataset["ground_truth"]
    assert gt["tier"] == "GT-1" and gt["label"] == "constructed" and gt["caveats"]
    assert any("synthetic" in c for c in gt["caveats"])
    assert any("split-templates.json" in c for c in gt["caveats"])
    assert dataset["generator"]["version"] == 2
    assert dataset["generator"]["template_split"] == f"{V2[name]}/split-templates.json"
    assert len(rows) >= 1000
    assert len({common.normalise(r["state"]) for r in rows}) == len(rows)
    assert all(r["_meta"]["synthetic"] is True and r["_meta"]["template"] for r in rows)


def test_the_label_schema_is_v1s():
    for v2, v1 in (("email-routing-v2", "email-routing"),
                   ("email-routing-adversarial-v2", "email-routing-adversarial"),
                   ("task-routing-v2", "task-routing")):
        new = _rows(ROOT / V2[v2] / "labels.jsonl")
        old = _rows(ROOT / "examples" / v1 / "labels.jsonl")
        assert new[0]["questions"] == old[0]["questions"], v2
        assert {tuple(r["labels"]) for r in new} == {tuple(r["labels"]) for r in old}, v2
        assert {r["labels"][q] for r in new for q in r["labels"]} == \
            {r["labels"][q] for r in old for q in r["labels"]}, v2
        assert set(old[0]["_meta"]) <= set(new[0]["_meta"]), v2


def test_the_adversarial_file_shares_no_base_email_with_the_clean_file():
    clean = _rows(ROOT / V2["email-routing-v2"] / "labels.jsonl")
    adv = _rows(ROOT / V2["email-routing-adversarial-v2"] / "labels.jsonl")
    keys = {common.normalise(r["state"]) for r in clean}
    assert all(common.normalise(r["_meta"]["base"]) not in keys for r in adv)
    assert all(common.normalise(r["state"]) not in keys for r in adv)
    # no two attacked rows are built on one base email either
    assert len({common.normalise(r["_meta"]["base"]) for r in adv}) == len(adv)


def test_the_router_header_says_some_hard_families_are_textbook_problems():
    _, dataset = load_dataset(str(ROOT / V2["task-routing-v2"] / "labels.jsonl"))
    caveat = [c for c in dataset["ground_truth"]["caveats"] if "small model often solves" in c]
    assert len(caveat) == 1
    ids = {f"hard/{f[0]}" for f in _gen("task-routing-v2").HARD}
    for fam in ("trie", "coin_change_ways", "sliding_max", "topological_sort", "lis"):
        assert f"hard/{fam}" in ids


def test_the_router_attacks_easy_tasks_no_clean_row_holds():
    rows = _rows(ROOT / V2["task-routing-v2"] / "labels.jsonl")
    clean = {common.normalise(r["state"]) for r in rows if r["_meta"]["attack"] == "clean"}
    attacked = [r for r in rows if r["_meta"]["attack"] != "clean"]
    assert attacked and all(common.normalise(r["_meta"]["base"]) not in clean for r in attacked)
    assert all(r["labels"]["route"] == "route_easy" and r["_meta"]["target"] == "route_strong"
               for r in attacked)


def test_attacks_and_labels_keep_v1s_proportions_times_five():
    adv = _rows(ROOT / V2["email-routing-adversarial-v2"] / "labels.jsonl")
    counts: dict[str, int] = {}
    for r in adv:
        a = r["_meta"]["attack"]
        a = "homoglyph" if a.startswith("homoglyph_") else a
        counts[a] = counts.get(a, 0) + 1
    assert counts == {"clean": 300, "prompt_injection": 200, "homoglyph": 150,
                      "ambiguous": 150, "pii": 100, "social_engineering": 100}
    clean = _rows(ROOT / V2["email-routing-v2"] / "labels.jsonl")
    per_label: dict[str, int] = {}
    for r in clean:
        per_label[r["labels"]["category"]] = per_label.get(r["labels"]["category"], 0) + 1
    assert set(per_label.values()) == {100}


# --- more templates and vocabulary than v1 ------------------------------------------------

def test_v2_has_more_templates_and_vocabulary_than_v1():
    e1, e2 = _v1("email-routing"), _gen("email-routing-v2")
    assert sum(map(len, e2.TEMPLATES.values())) > 3 * sum(map(len, e1.TEMPLATES.values()))
    assert all(len(e2.TEMPLATES[c]) > len(e1.TEMPLATES[c]) for c in e1.CATEGORIES)
    assert len(e2.ITEMS) > 3 * len(e1.ITEMS)
    a1, a2 = _v1("email-routing-adversarial"), _gen("email-routing-adversarial-v2")
    for attr in ("INJECTION_TEMPLATES", "SOCIAL_TEMPLATES", "PII_SNIPPETS", "AMBIGUOUS"):
        assert len(getattr(a2, attr)) > len(getattr(a1, attr)), attr
    r1, r2 = _v1("task-routing"), _gen("task-routing-v2")
    for attr in ("EASY", "HARD", "INJECTION_TEMPLATES"):
        assert len(getattr(r2, attr)) > len(getattr(r1, attr)), attr


# --- the held-out rule -------------------------------------------------------------------

@pytest.mark.parametrize("name", list(V2))
def test_held_out_templates_build_only_held_out_rows(name):
    path = ROOT / V2[name] / "labels.jsonl"
    split = json.loads((ROOT / V2[name] / "split-templates.json").read_text(encoding="utf-8"))
    rows = _rows(path)
    dev_t, held_t = set(split["templates"]["dev"]), set(split["templates"]["heldout"])
    assert held_t and dev_t and not dev_t & held_t
    for i in split["heldout"]:
        assert set(common.row_templates(rows[i])) <= held_t
    for i in split["dev"]:
        assert set(common.row_templates(rows[i])) <= dev_t
    assert split["sha256_rows"] == sha256_rows_of(str(path))
    assert split["seed"] == common.SPLIT_SEED
    # every label is present on both sides, so a held-out score exists for each one
    for label, n in split["labels_by_split"].items():
        assert n["dev"] > 0 and n["heldout"] > 0, (name, label)
    assert 0.15 < split["n_heldout"] / split["n"] < 0.35


def test_the_adversarial_split_keeps_the_clean_files_half_for_every_email_template():
    clean = json.loads((ROOT / V2["email-routing-v2"] / "split-templates.json").read_text())
    adv = json.loads((ROOT / V2["email-routing-adversarial-v2"] / "split-templates.json")
                     .read_text())
    for half in ("dev", "heldout"):
        assert set(clean["templates"][half]) <= set(adv["templates"][half])


def test_the_table_in_ground_truth_md_is_the_committed_files():
    doc = (ROOT / "docs" / "ground-truth.md").read_text(encoding="utf-8")
    for rel in V2.values():
        split = json.loads((ROOT / rel / "split-templates.json").read_text(encoding="utf-8"))
        rows = _rows(ROOT / rel / "labels.jsonl")
        distinct = len({common.normalise(r["state"]) for r in rows})
        t = split["templates"]
        line = (f"| `{rel}/labels.jsonl` | {len(rows)} | {distinct} | "
                f"{t['n_dev']} / {t['n_heldout']} | {split['n_dev']} / {split['n_heldout']} |")
        assert line in doc, line


# --- v1 is frozen evidence ----------------------------------------------------------------

def test_v1_files_are_byte_identical_to_their_pins():
    assert check.FROZEN_V1, "no v1 pin"
    for rel, digest in check.FROZEN_V1.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel
    assert check.frozen_problems() == []


def test_v2_generators_write_only_inside_their_own_directory():
    for name in V2:
        files = _gen(name).files()
        assert set(files) >= {"labels.jsonl", "split-templates.json"}, name
        assert all("/" not in f and not f.startswith(".") for f in files), name
    assert not {f"examples/{p}" for p in ("email-routing", "email-routing-adversarial",
                                          "task-routing")} & set(V2.values())
