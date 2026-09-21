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
            "latency_s": 0.1, "cost_usd": 0.0, "meta": meta or {}}


def test_summarize_hand_computed_including_no_answer():
    recs = [rec(0, "a", "a", 0.9), rec(1, "b", "b", 0.8), rec(2, "a", "b", 0.7),
            rec(3, "b", "", 0.0)]
    s = heldout_report.summarize(recs, "email-clean")
    assert s["n"] == 4 and s["accuracy"] == 0.5 and s["no_answer"] == 1
    assert s["mean_conf_correct"] == pytest.approx(0.85)
    assert s["mean_conf_wrong"] == pytest.approx(0.35)
    assert s["cost_usd"] == 0.0 and s["accuracy_interval"] is None


def test_summarize_n1_and_all_correct_have_no_wrong_confidence():
    s = heldout_report.summarize([rec(0, "a", "a", 1.0)], "email-clean")
    assert s["n"] == 1 and s["accuracy"] == 1.0 and s["mean_conf_wrong"] is None
    assert s["zero_error_coverage"] == 1.0


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


def test_report_regenerates_and_states_its_status():
    data = heldout_report.collect()
    md = heldout_report.render(data)
    assert md.startswith("# Fine-tuned classifier baseline")
    assert f"Status: {data['prediction']['status']}" in md
    assert "Synthetic GT-1 data" in md and "same generator" in md
    assert "jev" in data["judges"] and data["splits"]["email-clean"]["n_heldout"] == 100
    for j in data["judges"].values():
        for ds, s in j["datasets"].items():
            want = {"email-adversarial": 200, "email-clean": 100}.get(ds, 60)
            assert s["n"] == want
