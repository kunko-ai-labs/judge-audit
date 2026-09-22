"""Pre-registered held-out split and the held-out report — hand-computed fixtures."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


split_heldout = _load("split_heldout")
heldout_report = _load("heldout_report")


def rows_of(labels: list[str], meta: list[dict] | None = None) -> list[dict]:
    meta = meta or [{} for _ in labels]
    return [{"state": f"s{i}", "questions": [{"name": "q", "options": sorted(set(labels))}],
             "labels": {"q": lab}, "_meta": m}
            for i, (lab, m) in enumerate(zip(labels, meta, strict=True))]


# --- split_rows -------------------------------------------------------------

def test_every_label_is_split_in_half_and_halves_are_disjoint():
    rows = rows_of(["a", "a", "b", "b", "a", "a", "b", "b"])
    train, heldout = split_heldout.split_rows(rows, "q", ())
    assert sorted(train + heldout) == list(range(8)) and not set(train) & set(heldout)
    assert sum(rows[i]["labels"]["q"] == "a" for i in heldout) == 2
    assert sum(rows[i]["labels"]["q"] == "b" for i in heldout) == 2


def test_split_is_deterministic_for_a_seed_and_moves_with_it():
    rows = rows_of(["a"] * 20 + ["b"] * 20)
    a = split_heldout.split_rows(rows, "q", (), seed=2026)
    assert a == split_heldout.split_rows(rows, "q", (), seed=2026)
    assert a != split_heldout.split_rows(rows, "q", (), seed=1)


def test_meta_keys_join_the_stratum():
    meta = [{"adversarial": i % 2 == 0} for i in range(8)]
    rows = rows_of(["a"] * 8, meta)
    _train, heldout = split_heldout.split_rows(rows, "q", ("adversarial",))
    assert sum(rows[i]["_meta"]["adversarial"] for i in heldout) == 2


def test_odd_stratum_puts_the_extra_row_in_heldout_and_n1_is_held_out():
    train, heldout = split_heldout.split_rows(rows_of(["a", "a", "a"]), "q", ())
    assert len(heldout) == 2 and len(train) == 1
    train, heldout = split_heldout.split_rows(rows_of(["a"]), "q", ())
    assert (train, heldout) == ([], [0])


def test_load_split_rejects_overlap_and_gaps(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"n": 4, "train": [0, 1], "heldout": [1, 2]}))
    with pytest.raises(ValueError, match="overlap"):
        split_heldout.load_split(p)
    p.write_text(json.dumps({"n": 4, "train": [0, 1], "heldout": [2]}))
    with pytest.raises(ValueError, match="exactly once"):
        split_heldout.load_split(p)
    p.write_text(json.dumps({"n": 3, "train": [0, 1], "heldout": [2]}))
    assert split_heldout.load_split(p)["heldout"] == [2]


def test_committed_splits_regenerate_byte_identical():
    for dataset in split_heldout.SPLITS:
        path = split_heldout.split_path(dataset)
        assert path.read_text(encoding="utf-8") == split_heldout.dumps(split_heldout.build(dataset))
        s = split_heldout.load_split(path)
        assert s["seed"] == 2026 and s["n_train"] + s["n_heldout"] == s["n"]
        strata = s["strata"].values()
        assert all(abs(c["train"] - c["heldout"]) <= 1 for c in strata)


def test_router_split_balances_hard_and_attacked_rows():
    s = split_heldout.load_split(split_heldout.split_path("task-routing"))
    half = {"train": 20, "heldout": 20}
    assert s["strata"]["route_easy|difficulty=easy|adversarial=True"] == half
    assert s["strata"]["route_strong|difficulty=hard|adversarial=False"] == half


# --- heldout_report -----------------------------------------------------------

def rec(idx, expected, decision, conf, meta=None, options=("a", "b")):
    return {"idx": idx, "expected": expected, "decision": decision,
            "correct": decision == expected,
            "no_answer": decision not in options, "confidence": conf,
            "text_equal_train": False, "text_contains_train": False,
            "latency_s": 0.1, "cost_usd": 0.0, "meta": meta or {}}


def test_summarize_hand_computed_including_no_answer():
    recs = [rec(0, "a", "a", 0.9), rec(1, "b", "b", 0.8), rec(2, "a", "b", 0.7),
            rec(3, "b", "", 0.0)]
    s = heldout_report.summarize(recs, "email-clean")
    assert s["n"] == 4 and s["accuracy"] == 0.5 and s["no_answer"] == 1
    assert s["mean_conf_correct"] == pytest.approx(0.85)
    assert s["mean_conf_wrong"] == pytest.approx(0.35)
    assert s["cost_usd"] == 0.0
    # 95 % bootstrap intervals, clustered by text, bracket their point estimate.
    for key, point in (("accuracy_ci", s["accuracy"]), ("ece_ci", s["ece"]),
                       ("zero_error_coverage_ci", s["zero_error_coverage"])):
        lo, hi = s[key]
        assert lo <= point <= hi, (key, lo, point, hi)


def test_summarize_n1_and_all_correct_have_no_wrong_confidence():
    s = heldout_report.summarize([rec(0, "a", "a", 1.0)], "email-clean")
    assert s["n"] == 1 and s["accuracy"] == 1.0 and s["mean_conf_wrong"] is None
    assert s["zero_error_coverage"] == 1.0
    assert s["accuracy_ci"] == [1.0, 1.0] and s["ece_ci"] == [0.0, 0.0]


def test_intervals_cluster_by_text_so_a_repeated_text_is_one_observation():
    """Ten rows of two texts carry the uncertainty of two clusters, not of ten rows."""
    rows = [dict(rec(i, "a", "a" if i % 2 else "b", 0.9), state="t1" if i % 2 else "t2")
            for i in range(10)]
    clustered = heldout_report.summarize(rows, "email-clean")
    unclustered = heldout_report.summarize(
        [dict(r, state=f"t{i}") for i, r in enumerate(rows)], "email-clean")
    lo_c, hi_c = clustered["accuracy_ci"]
    lo_u, hi_u = unclustered["accuracy_ci"]
    assert (hi_c - lo_c) > (hi_u - lo_u)          # clustering widens the interval
    assert lo_c <= clustered["accuracy"] <= hi_c


def test_committed_heldout_report_carries_intervals_for_every_row():
    data = heldout_report.collect()
    for judge in data["judges"].values():
        for s in judge["datasets"].values():
            for key in ("accuracy_ci", "ece_ci", "zero_error_coverage_ci"):
                lo, hi = s[key]
                assert 0.0 <= lo <= hi
    md = heldout_report.render(data)
    assert "## How to read the intervals" in md and "percentile-bootstrap" in md


def test_summarize_adversarial_and_router_extras():
    adv = [rec(0, "a", "b", 0.9, {"attack": "prompt_injection"}),
           rec(1, "a", "a", 0.6, {"attack": "prompt_injection"}),
           rec(2, "b", "a", 0.7, {"attack": "social_engineering"}),
           rec(3, "b", "b", 0.5, {"attack": "clean"})]
    s = heldout_report.summarize(adv, "email-adversarial")
    assert s["prompt_injection_accuracy"] == 0.5 and s["prompt_injection_n"] == 2
    assert s["social_engineering_accuracy"] == 0.0 and s["social_engineering_n"] == 1
    assert s["mean_conf_wrong_under_attack"] == pytest.approx(0.8)
    assert s["wrong_under_attack_n"] == 2
    assert s["wrong_by_attack"] == {"prompt_injection": 1, "social_engineering": 1}
    assert s["max_conf_wrong"] == 0.9
    s = heldout_report.summarize([rec(0, "a", "a", 0.5, {"attack": "clean"})], "email-adversarial")
    assert s["wrong_by_attack"] == {} and s["max_conf_wrong"] is None
    assert s["prompt_injection_accuracy"] is None and s["prompt_injection_n"] == 0
    router = [rec(0, "route_strong", "route_strong", 0.9, {"difficulty": "hard"},
                  ("route_easy", "route_strong")),
              rec(1, "route_easy", "route_strong", 0.9, {"adversarial": True},
                  ("route_easy", "route_strong"))]
    s = heldout_report.summarize(router, "router-bare")
    assert (s["hard_routed_strong"], s["hard_n"]) == (1, 1)
    assert (s["attack_success"], s["attack_n"]) == (1, 1)
    assert s["decisions"] == {0: "route_strong", 1: "route_strong"}


def judges_fixture(ft_clean_acc=0.99, ft_ece=0.05, wrong_conf=0.9, identical=True,
                   ft_desc_acc=0.7):
    ft_dec = {1: "route_easy", 2: "route_strong"}
    other_dec = ft_dec if identical else {1: "route_strong", 2: "route_strong"}
    return {
        "jev": {"label": "Jev", "datasets": {
            "email-clean": {"accuracy": 0.95}, "router-described": {"accuracy": 0.95}}},
        "x": {"label": "x", "datasets": {"email-clean": {"accuracy": 0.97}}},
        heldout_report.FINETUNED: {"label": "ft", "datasets": {
            "email-clean": {"accuracy": ft_clean_acc, "ece": ft_ece},
            "email-adversarial": {"mean_conf_wrong_under_attack": wrong_conf,
                                  "wrong_under_attack_n": 3},
            "router-bare": {"decisions": ft_dec, "accuracy": ft_desc_acc},
            "router-described": {"decisions": other_dec, "accuracy": ft_desc_acc}}},
    }


def test_prediction_is_pre_registered_without_the_finetuned_run():
    out = heldout_report.score_prediction({"jev": {"datasets": {}}})
    assert out["status"] == "pre-registered" and out["results"] == {}


def test_prediction_scores_every_clause_mechanically():
    out = heldout_report.score_prediction(judges_fixture())
    assert out["status"] == "scored" and out["holds"] == 4 and out["scored"] == 4
    assert out["results"]["P1"]["best_other"] == "x"
    out = heldout_report.score_prediction(
        judges_fixture(ft_clean_acc=0.97, ft_ece=0.2, wrong_conf=0.5, identical=False))
    assert out["holds"] == 0
    assert out["results"]["P1"]["holds"] is False   # equal is not strictly higher
    assert out["results"]["P4"]["decisions_identical"] is False
    assert out["results"]["P3"]["testable"] is True
    out = heldout_report.score_prediction(judges_fixture(wrong_conf=None))
    assert out["results"]["P3"] == {"holds": False, "testable": False,
                                    "mean_conf_wrong_under_attack": None,
                                    "wrong_under_attack_n": 3}


def test_render_marks_an_untestable_clause_and_labels_the_finetuned_row():
    data = heldout_report.collect()
    md = heldout_report.render(data)
    if data["prediction"]["status"] == "scored":
        ft = data["judges"][heldout_report.FINETUNED]
        assert ft["label"].startswith("DeBERTa-v3-base fine-tuned — run 1 (pre-registered")
        assert "## Amendment, after the first run" in md
        assert ft["datasets"]["email-clean"]["temperature"] == 1.0
        for slug in data["judges"]:
            if slug in heldout_report.FINETUNED_RUNS and slug != heldout_report.FINETUNED:
                # A post-hoc run never enters the prediction's "best other" comparison.
                assert data["prediction"]["results"]["P1"]["best_other"] != slug
        assert ft["datasets"]["email-clean"]["model"] != ft["datasets"]["router-bare"]["model"]
        assert ft["datasets"]["email-clean"]["scored"] == "held-out half"
        assert ft["datasets"]["email-adversarial"]["scored"] == "all rows"
        if not data["prediction"]["results"]["P3"]["testable"]:
            assert "untestable, counted as not holding" in md


def test_report_regenerates_and_states_its_status():
    data = heldout_report.collect()
    md = heldout_report.render(data)
    assert md.startswith("# Fine-tuned classifier baseline")
    assert f"Status: {data['prediction']['status']}" in md
    assert "Synthetic GT-1 data" in md and "generators repeat texts" in md and "#54" in md
    assert "jev" in data["judges"] and data["splits"]["email-clean"]["n_heldout"] == 100
    for j in data["judges"].values():
        for ds, s in j["datasets"].items():
            want = {"email-adversarial": 200, "email-clean": 100}.get(ds, 60)
            assert s["n"] == want


# --- leakage regression: the committed held-out checkpoints ---------------------------------

FT_SLUGS = list(heldout_report.FINETUNED_RUNS)
HELDOUT_DS = {"email-clean": "examples/email-routing/split-heldout.json",
              "router-bare": "examples/task-routing/split-heldout.json",
              "router-described": "examples/task-routing/split-heldout.json"}


def ckpt_rows(path: Path) -> tuple[dict, list[int]]:
    header, idx = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            header = rec["run"]
        else:
            idx.append(rec["idx"])
    return header, idx


def test_committed_finetuned_checkpoints_hold_only_heldout_indices_of_the_committed_split():
    checked = 0
    for slug in FT_SLUGS:
        for ds, split_file in HELDOUT_DS.items():
            ck = ROOT / "docs" / "runs" / "arena" / slug / f"{ds}.ckpt.jsonl"
            if not ck.exists():
                continue
            split = split_heldout.load_split(ROOT / split_file)
            header, idx = ckpt_rows(ck)
            sub = header["rows_subset"]
            assert sub["part"] == "heldout" and sub["split"] == split_file
            assert sub["sha256"] == heldout_report.sha256_of(str(ROOT / split_file))
            assert sorted(idx) == split["heldout"]                       # exactly the held-out rows
            assert not set(idx) & set(split["train"])                   # and none of the train rows
            assert header["judge"]["split"]["sha256"] == sub["sha256"]  # the model trained on it
            checked += 1
    present = [s for s in FT_SLUGS if (ROOT / "docs" / "runs" / "arena" / s).exists()]
    assert checked == 3 * len(present) and present


def test_finetuned_adversarial_runs_are_full_and_carry_no_subset():
    for slug in FT_SLUGS:
        ck = ROOT / "docs" / "runs" / "arena" / slug / "email-adversarial.ckpt.jsonl"
        if ck.exists():
            header, idx = ckpt_rows(ck)
            assert "rows_subset" not in header and sorted(idx) == list(range(200))


def test_a_finetuned_run_without_a_subset_header_is_rejected(tmp_path):
    keep = {1, 2}
    meta = {"sha256": "x" * 64, "split": "s.json"}
    ok = {"rows_subset": {"sha256": "x" * 64, "part": "heldout"}}
    ft, ck = heldout_report.FINETUNED, tmp_path / "c"
    with pytest.raises(SystemExit, match="no rows_subset"):
        heldout_report.validate_heldout_run(ft, ck, {}, [1, 2], keep, meta)
    with pytest.raises(SystemExit, match="outside the held-out split"):
        heldout_report.validate_heldout_run(ft, ck, ok, [0, 1, 2], keep, meta)
    with pytest.raises(SystemExit, match="does not match"):
        heldout_report.validate_heldout_run(
            ft, ck, {"rows_subset": {"sha256": "y" * 64, "part": "heldout"}}, [1, 2], keep, meta)
    with pytest.raises(SystemExit, match="does not match"):
        heldout_report.validate_heldout_run(
            ft, ck, {"rows_subset": {"sha256": "x" * 64, "part": "train"}}, [1, 2], keep, meta)
    # Valid header, only held-out rows: passes. Other judges are re-scored from full runs.
    heldout_report.validate_heldout_run(ft, ck, ok, [1, 2], keep, meta)
    heldout_report.validate_heldout_run("jev", ck, {}, [0, 1, 2, 3], keep, meta)


def test_text_overlap_is_counted_and_unseen_accuracy_computed():
    train = {"alpha beta", "gamma"}
    assert heldout_report.text_overlap("alpha beta", train) == (True, True)
    assert heldout_report.text_overlap("xx gamma yy", train) == (False, True)
    assert heldout_report.text_overlap("delta", train) == (False, False)
    recs = [dict(rec(0, "a", "a", 0.9), text_equal_train=True, text_contains_train=True),
            dict(rec(1, "a", "b", 0.9), text_equal_train=False, text_contains_train=True),
            dict(rec(2, "a", "a", 0.9), text_equal_train=False, text_contains_train=False),
            dict(rec(3, "a", "b", 0.9), text_equal_train=False, text_contains_train=False)]
    s = heldout_report.summarize(recs, "email-clean")
    assert (s["text_equal_train"], s["text_contains_train"], s["unseen_text_n"]) == (1, 2, 2)
    assert s["accuracy_unseen_text"] == 0.5
    s = heldout_report.summarize(recs[:1], "email-clean")
    assert s["unseen_text_n"] == 0 and s["accuracy_unseen_text"] is None


def test_reviewer_overlap_counts_reproduce():
    data = heldout_report.collect()
    jev = data["judges"]["jev"]["datasets"]
    assert (jev["email-clean"]["text_equal_train"], jev["email-clean"]["unseen_text_n"]) == (20, 80)
    assert (jev["router-bare"]["text_equal_train"],
            jev["router-bare"]["text_contains_train"]) == (40, 55)
    assert (jev["email-adversarial"]["text_equal_train"],
            jev["email-adversarial"]["text_contains_train"]) == (13, 49)
