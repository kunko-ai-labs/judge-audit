"""Consensus audit: majority vote, panel statistics and the deliberation prompt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from consensus_report import majority, panel_stats  # noqa: E402


def rec(decision, confidence, expected="b"):
    return {"decision": decision, "confidence": confidence,
            "correct": decision == expected, "meta": {}}


ROWS = [{"labels": {"q": "b"}} for _ in range(4)]
VOTES = {
    "x": [rec("b", 0.9), rec("b", 0.9), rec("a", 0.8), rec("a", 0.7)],
    "y": [rec("b", 0.6), rec("a", 0.5), rec("a", 0.9), rec("b", 0.6)],
    "z": [rec("b", 0.7), rec("b", 0.8), rec("a", 0.6), rec("a", 0.9)],
}


def test_majority_treats_ties_and_blanks_as_no_vote():
    assert majority(["b", "b", "a"]) == ("b", 2 / 3, False)
    assert majority(["A", "a ", "b"]) == ("a", 2 / 3, False)   # case and whitespace normalised
    assert majority(["a", "b"]) == (None, 0.5, True)           # tie: no decision
    assert majority(["b", "", " "]) == ("b", 1.0, False)        # blanks abstain
    assert majority(["", ""]) == (None, 0.0, False)


def test_panel_stats_ties_and_abstentions():
    votes = {"x": [rec("b", 0.9), rec("", 0.0)], "y": [rec("a", 0.6), rec("b", 0.7)]}
    rows = [{"labels": {"q": "b"}}, {"labels": {"q": "b"}}]
    s = panel_stats(votes, rows, "q")
    assert s["ties"] == 1 and s["abstentions"] == 1
    assert s["majority_accuracy"] == 0.5   # row 0 tie = not correct; row 1 decided by y alone
    assert s["majority_accuracy_ci"] == [0.0, 1.0]   # two rows: every resample is 0, 50 or 100 %
    assert s["majority_accuracy_ci_method"] == "bootstrap"
    assert s["majority_accuracy_decided"] == 1.0
    assert s["unanimous"] == 0                      # one voter is not unanimity
    assert s["mean_share_when_right"] == 1.0 and s["mean_share_when_wrong"] is None
    assert s["pairwise_agreement"] == 0.0           # only row 0 has both votes, and they differ


def test_panel_stats_counts_agreement_and_wrong_majorities():
    s = panel_stats(VOTES, ROWS, "q")
    assert s["n"] == 4 and s["judges"] == ["x", "y", "z"]
    # row 0 unanimous and right; row 2 unanimous and wrong; rows 1 and 3 split.
    assert s["unanimous"] == 2 and s["unanimous_wrong"] == 1
    assert s["majority_accuracy"] == 0.5 and s["majority_wrong"] == 2
    assert s["best_single_accuracy"] == 0.5
    # judges who voted with a wrong majority: row 2 (0.8, 0.9, 0.6), row 3 (0.7, 0.9)
    assert s["mean_conf_of_wrong_majority"] == round((0.8 + 0.9 + 0.6 + 0.7 + 0.9) / 5, 3)


def test_panel_stats_subset_and_empty():
    assert panel_stats(VOTES, ROWS, "q", [0]) ["majority_accuracy"] == 1.0
    assert panel_stats(VOTES, ROWS, "q", []) == {}


def test_deliberation_prompt_hides_names_and_excludes_self(monkeypatch):
    import jury_deliberate

    rows = [{"state": "task", "questions": [], "labels": {"q": "b"},
             "_meta": {"difficulty": "hard"}}]
    votes = {"alpha": VOTES["x"][:1], "beta": VOTES["y"][:1], "gamma": VOTES["z"][:1]}
    monkeypatch.setattr(jury_deliberate, "votes_of", lambda ds: (votes, rows))
    trio = ["alpha", "beta", "gamma"]
    out, panel = jury_deliberate.deliberation_rows("router-bare", "beta", panel=trio)
    assert panel == ["alpha", "gamma"]
    state = out[0]["state"]
    assert "2 other judges" in state and "Judge A: b" in state and "Judge B: b" in state
    assert "alpha" not in state and "gamma" not in state  # anonymised
    assert sorted(out[0]["_meta"]["panel_seen"]) == ["alpha", "gamma"]
    # a blank round-1 answer is not shown and not listed
    votes["gamma"] = [rec("", 0.0)]
    out, _ = jury_deliberate.deliberation_rows("router-bare", "beta", panel=trio)
    assert "1 other judge assessed" in out[0]["state"]
    assert out[0]["_meta"]["panel_seen"] == ["alpha"]
    votes["alpha"] = [rec("", 0.0)]
    out, _ = jury_deliberate.deliberation_rows("router-bare", "beta", panel=trio)
    assert "none of them gave an answer" in out[0]["state"]
    assert out[0]["_meta"]["panel_seen"] == []
    assert out[0]["_meta"]["round"] == 2
    assert rows[0]["state"] == "task"  # original row untouched


def test_by_row_reorders_and_rejects_incomplete_or_duplicated():
    from consensus_report import by_row

    recs = [{"idx": 2, "decision": "c"}, {"idx": 0, "decision": "a"}, {"idx": 1, "decision": "b"}]
    assert [r["decision"] for r in by_row(recs, 3)] == ["a", "b", "c"]
    assert by_row(recs[:2], 3) is None                      # incomplete
    assert by_row(recs + [{"idx": 1, "decision": "x"}], 3) is None  # duplicated row


def test_check_detects_a_stale_input(monkeypatch, tmp_path):
    import jury_deliberate

    rows = [{"state": "task", "questions": [], "labels": {"q": "b"}, "_meta": {}}]
    votes = {"alpha": [rec("b", 0.9)], "beta": [rec("a", 0.5)]}
    monkeypatch.setattr(jury_deliberate, "votes_of", lambda ds: (votes, rows))
    monkeypatch.setattr(jury_deliberate, "read_dataset_header", lambda path: {})
    monkeypatch.setattr(jury_deliberate, "JURY", tmp_path)
    (tmp_path / "router-bare").mkdir()
    inp = tmp_path / "router-bare" / "beta.r2.input.jsonl"
    good, _ = jury_deliberate.deliberation_rows("router-bare", "beta", panel=["alpha", "beta"])
    inp.write_text(jury_deliberate.input_text("router-bare", good), encoding="utf-8")
    monkeypatch.setattr(jury_deliberate, "frozen_panel", lambda: ["alpha", "beta"])
    assert jury_deliberate.check() == 0
    inp.write_text("{}\n", encoding="utf-8")
    assert jury_deliberate.check() == 1
# ----------------------------------------------------------------- error correlation (#45)
def _rows(n, expected="b"):
    return [{"labels": {"q": expected}} for _ in range(n)]


def test_pairwise_error_stats_hand_computed():
    from consensus_report import pairwise_error_stats

    # x: right right wrong wrong right blank  /  y: right wrong wrong right right right
    votes = {"x": [rec("b", .9), rec("b", .9), rec("a", .8), rec("a", .7), rec("b", .6),
                   rec("", 0)],
             "y": [rec("b", .6), rec("a", .5), rec("a", .9), rec("b", .6), rec("b", .6),
                   rec("b", .6)]}
    [s] = pairwise_error_stats(votes, _rows(6), "q")
    assert (s["a"], s["b"], s["n"]) == ("x", "y", 5)      # row 5: x abstained, excluded
    assert s["agreement"] == 0.6                           # rows 0, 2, 4 agree
    assert s["errors_a"] == 2 and s["errors_b"] == 2 and s["shared_wrong"] == 1  # row 2
    assert s["joint_error"] == 0.2
    assert s["p_a_wrong_given_b_wrong"] == 0.5 and s["p_b_wrong_given_a_wrong"] == 0.5
    assert s["error_jaccard"] == round(1 / 3, 4)
    # 2x2 error table: both wrong 1, only x 1, only y 1, both right 2
    # phi = (1*2 - 1*1) / sqrt(2 * 3 * 2 * 3) = 1/6
    assert s["phi"] == round(1 / 6, 4)


def test_pairwise_error_stats_degenerate_cases():
    from consensus_report import pairwise_error_stats

    x = [rec("b", .9), rec("a", .9), rec("b", .9)]      # one error (row 1)
    z = [rec("b", .9), rec("b", .9), rec("b", .9)]      # no errors
    # a judge with no errors: conditional on its errors and phi are undefined
    [s] = pairwise_error_stats({"x": x, "z": z}, _rows(3), "q")
    assert s["phi"] is None and s["p_a_wrong_given_b_wrong"] is None
    assert s["p_b_wrong_given_a_wrong"] == 0.0 and s["error_jaccard"] == 0.0
    assert s["joint_error"] == 0.0 and s["agreement"] == round(2 / 3, 4)
    # both judges flawless: no error set to compare
    [s] = pairwise_error_stats({"z": z, "w": list(z)}, _rows(3), "q")
    assert s["error_jaccard"] is None and s["phi"] is None and s["agreement"] == 1.0
    # identical judges with errors: perfect correlation
    [s] = pairwise_error_stats({"x": x, "x2": list(x)}, _rows(3), "q")
    assert s["phi"] == 1.0 and s["error_jaccard"] == 1.0 and s["agreement"] == 1.0
    assert s["p_a_wrong_given_b_wrong"] == 1.0 and s["p_b_wrong_given_a_wrong"] == 1.0
    # opposite judges: one wrong exactly where the other is right
    y = [rec("a", .9), rec("b", .9), rec("a", .9)]
    [s] = pairwise_error_stats({"x": x, "y": y}, _rows(3), "q")
    assert s["phi"] == -1.0 and s["error_jaccard"] == 0.0 and s["shared_wrong"] == 0
    # nothing to compare: every row has an abstention on one side, or n = 1
    [s] = pairwise_error_stats({"x": [rec("", 0), rec("b", .9)],
                                "y": [rec("b", .9), rec("", 0)]}, _rows(2), "q")
    assert s["n"] == 0 and s["phi"] is None and s["agreement"] is None
    [s] = pairwise_error_stats({"x": x[:1], "y": y[:1]}, _rows(1), "q")
    assert s["n"] == 1 and s["phi"] is None and s["agreement"] == 0.0
    # subset selection and pair count
    out = pairwise_error_stats({"x": x, "y": y, "z": z}, _rows(3), "q", [1])
    assert len(out) == 3 and all(s["n"] == 1 for s in out)
    assert pairwise_error_stats({"x": x}, _rows(3), "q") == []


def test_spearman_hand_computed():
    from consensus_report import spearman

    assert spearman([1, 2, 3], [3, 2, 1]) == -1.0
    assert spearman([1, 2, 3], [10, 20, 30]) == 1.0
    # tied x ranks (1.5, 1.5, 3) vs (1, 2, 3): r = 1.5 / sqrt(1.5 * 2)
    assert spearman([1, 1, 2], [1, 2, 3]) == round(1.5 / (1.5 * 2) ** 0.5, 4)
    assert spearman([1, 1, 1], [1, 2, 3]) is None        # no variance
    assert spearman([1, 2], [2, 1]) is None               # fewer than three points


def test_jury_composition_on_a_four_judge_panel():
    from consensus_report import jury_composition

    from judge_audit.metrics.calibration import expected_calibration_error

    votes = {"p": [rec("b", .9), rec("b", .9), rec("b", .9), rec("a", .9)],
             "q": [rec("b", .9), rec("b", .9), rec("a", .9), rec("a", .9)],
             "r": [rec("b", .9), rec("a", .9), rec("a", .9), rec("b", .9)],
             "s": [rec("a", .9), rec("b", .9), rec("b", .9), rec("a", .9)]}
    costs = {j: {"cost_usd": c, "p50_latency_s": t}
             for j, c, t in [("p", .1, 1.0), ("q", .2, 2.0), ("r", .3, 3.0), ("s", 0.0, 6.0)]}
    out = jury_composition(votes, _rows(4), "q", [0, 1, 2, 3], ["p", "q", "r", "s"], costs)
    assert out["panel"] == ["p", "q", "r", "s"] and len(out["juries"]) == 4
    # sorted by majority accuracy, then decided accuracy, then name
    assert [j["jury"] for j in out["juries"]] == ["p + q + s", "p + r + s", "p + q + r",
                                                  "q + r + s"]
    assert [j["majority_accuracy"] for j in out["juries"]] == [0.75, 0.75, 0.5, 0.5]
    pqs = out["juries"][0]
    assert pqs["ties"] == 0 and pqs["majority_accuracy_decided"] == 0.75
    assert pqs["shared_wrong"] == 1                    # row 3: all three say a
    # errors p={3} q={2,3} s={0,3}: phi(p,q) = phi(p,s) = 2/sqrt(12), phi(q,s) = 0
    assert pqs["mean_phi"] == round((2 * 2 / 12 ** 0.5) / 3, 4)
    assert pqs["vote_share_ece"] == round(expected_calibration_error(
        [2 / 3, 1.0, 2 / 3, 1.0], [True, True, True, False]), 4)
    assert pqs["cost_usd"] == 0.3 and pqs["p50_latency_s"] == 3.0
    assert out["juries"][2]["jury"] == "p + q + r" and out["juries"][2]["shared_wrong"] == 0
    assert pqs["pairs_with_phi"] == 3 and pqs["mean_phi_all"] == pqs["mean_phi"]  # same rows
    # diversity vs accuracy is the Spearman correlation over juries with a defined mean phi
    d = out["diversity_vs_accuracy"]
    assert d["juries"] == 4 and d["spearman"] is not None
    assert out["diversity_vs_accuracy_all_rows"] == d
    # scored on rows 0-2 only: p has no error there, so only the q-s pair has a phi
    # (q wrong on 2, s wrong on 0: n11=0 n10=1 n01=1 n00=1 -> -1/2); all-rows phi unchanged
    out = jury_composition(votes, _rows(4), "q", [0, 1, 2], ["p", "q", "r", "s"], costs)
    pqs = next(j for j in out["juries"] if j["jury"] == "p + q + s")
    assert pqs["majority_accuracy"] == 1.0 and pqs["n"] == 3 and pqs["n_all"] == 4
    assert (pqs["mean_phi"], pqs["pairs_with_phi"]) == (-0.5, 1)
    assert (pqs["mean_phi_all"], pqs["pairs_with_phi_all"]) == (round((4 / 12 ** 0.5) / 3, 4), 3)
    # a judge missing from the cost table renders no cost, not a wrong one
    out = jury_composition(votes, _rows(4), "q", [0, 1, 2, 3], ["p", "q", "r"], {"p": costs["p"]})
    assert len(out["juries"]) == 1 and out["juries"][0]["cost_usd"] is None
    assert out["juries"][0]["p50_latency_s"] is None


def test_jury_composition_mean_phi_undefined_when_nobody_errs():
    from consensus_report import jury_composition

    votes = {j: [rec("b", .9), rec("b", .9)] for j in "pqr"}
    out = jury_composition(votes, _rows(2), "q", [0, 1], ["p", "q", "r"], {})
    assert out["juries"][0]["mean_phi"] is None and out["juries"][0]["majority_accuracy"] == 1.0
    assert out["diversity_vs_accuracy"] == {"spearman": None, "juries": 0}
    assert out["diversity_vs_accuracy_all_rows"] == {"spearman": None, "juries": 0}


def test_jury_composition_counts_ties_and_splits_all_from_decided():
    from consensus_report import jury_composition

    # row 1: p says b, q says a, r abstains -> tie, no decision; row 5: all three wrong
    votes = {"p": [rec(d, .9) for d in ("b", "b", "a", "b", "a", "a")],
             "q": [rec(d, .9) for d in ("b", "a", "a", "b", "b", "a")],
             "r": [rec(d, .9) for d in ("b", "", "b", "a", "a", "a")]}
    [j] = jury_composition(votes, _rows(6), "q", list(range(6)), ["p", "q", "r"], {})["juries"]
    assert j["ties"] == 1
    assert j["majority_accuracy"] == round(2 / 6, 4)        # rows 0 and 3; the tie counts as wrong
    assert j["majority_accuracy_decided"] == 0.4             # 2 of the 5 decided rows
    assert j["shared_wrong"] == 1 and j["n"] == 6


def test_render_sections_survive_undefined_statistics():
    from consensus_report import render_error_correlation, render_jury_composition, spearman

    votes = {j: [rec("b", .9), rec("b", .9)] for j in "pqr"}
    from consensus_report import error_correlation, jury_composition

    ec = render_error_correlation(error_correlation(votes, _rows(2), "q"))
    assert any("undefined for every pair" in line for line in ec)
    comp = render_jury_composition(jury_composition(votes, _rows(2), "q", [0, 1], list("pqr"), {}),
                                   2)
    assert any("Spearman is undefined" in line for line in comp)
    text = "\n".join(comp)
    # Right on both rows: the exact 2/2 interval, marked †, not a zero-width bootstrap.
    assert "| p + q + r | 100.0% [15.8, 100.0]† / 100.0% | 0 |" in text and "| — / — |" in text
    assert spearman([], []) is None


# ------------------------------------------------ only the frozen panel votes (US-004-011, #65)
def _intruder_arena(tmp_path, with_intruder):
    """A copy of the Arena directory (symlinks) plus, optionally, a complete non-panel judge:
    llama32's checkpoints under another name, so it would move every statistic if it voted."""
    import consensus_report

    arena = tmp_path / ("with" if with_intruder else "without")
    arena.mkdir()
    for d in consensus_report.ARENA.iterdir():
        if d.is_dir():
            (arena / d.name).symlink_to(d, target_is_directory=True)
    if with_intruder:
        (arena / "zz-intruder").mkdir()
        for ck in (consensus_report.ARENA / "llama32").glob("*.ckpt.jsonl"):
            lines = ck.read_text(encoding="utf-8").replace("llama3.2:3b", "intruder:1b")
            (arena / "zz-intruder" / ck.name).write_text(lines, encoding="utf-8")
    return arena


def test_a_non_panel_judge_never_votes(monkeypatch, tmp_path):
    import consensus_report
    import jury_report

    runs = {}
    for with_intruder in (False, True):
        monkeypatch.setattr(consensus_report, "ARENA", _intruder_arena(tmp_path, with_intruder))
        runs[with_intruder] = (consensus_report.collect(), jury_report.collect())
    (c0, j0), (c1, j1) = runs[False], runs[True]
    assert j1 == j0                                            # round 1 and round 2 panels
    for ds, e0 in c0.items():
        e1 = c1[ds]
        assert set(e1) == set(e0)
        for key in e0:
            if key != "declared_confidence":
                assert e1[key] == e0[key], (ds, key)           # every panel statistic
        # the outsider is shown on its own, labelled, and nothing else in the table moved
        intruder = e1["declared_confidence"].pop("zz-intruder")
        assert intruder["juror"] is False
        assert intruder["not_a_juror"] == consensus_report.OUTSIDE_PANEL
        assert e1["declared_confidence"] == e0["declared_confidence"]


def test_fine_tuned_runs_are_listed_but_never_vote():
    import consensus_report

    panel = json.loads(consensus_report.PANEL.read_text(encoding="utf-8"))["panel"]
    e = consensus_report.collect_dataset("email-adversarial")
    assert e["panel"]["judges"] == panel and len(panel) == 8
    assert all(s["judges"] == panel for s in e["subsets"].values())
    assert e["error_correlation"]["judges"] == panel
    # trained on the train half of the clean emails; 13 attacked emails equal a training
    # text and 36 more contain one (docs/finetuned-baseline-2026-09.md): 49 of 200
    reason = ("not a juror: fine-tuned on half of email-clean; 49 of these 200 rows contain a "
              "training text")
    for j in ["finetuned-deberta", "finetuned-deberta-run2", "finetuned-deberta-run2-ts"]:
        d = e["declared_confidence"][j]
        assert d["juror"] is False and d["not_a_juror"] == reason
        assert (d["trained_on"], d["rows_with_training_text"]) == ("email-clean", 49)
        assert d["model_family"] == "microsoft/deberta-v3-base fine-tuned on email-clean"
    assert all(e["declared_confidence"][j]["juror"] for j in panel)
    assert "not_a_juror" not in e["declared_confidence"]["jev"]
    text = consensus_report.render({ds: consensus_report.collect_dataset(ds)
                                    for ds in consensus_report.DATASETS})
    assert f"| finetuned-deberta-run2 (declared; {reason}) |" in text
    under_attack = text.split("## Emails under attack")[1].split("## Task router")[0]
    assert ("finetuned-deberta, finetuned-deberta-run2, finetuned-deberta-run2-ts are one model "
            "family (microsoft/deberta-v3-base fine-tuned on email-clean), entered 3 times: not "
            "3 independent jurors.") in under_attack
    assert "finetuned" not in under_attack.split("### Error correlation")[1]


def _checkpoint(arena, slug, dataset, header):
    (arena / slug).mkdir(parents=True, exist_ok=True)
    lines = ([json.dumps({"idx": -1, "run": header})] if header is not None else []) + \
        [json.dumps({"idx": 0, "judgments": []})]
    (arena / slug / f"{dataset}.ckpt.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_not_a_juror_reads_the_data_not_the_slug(monkeypatch, tmp_path):
    import consensus_report
    from consensus_report import OUTSIDE_PANEL, TRAINING_UNVERIFIABLE, not_a_juror

    from judge_audit.runner import sha256_of

    monkeypatch.setattr(consensus_report, "ARENA", tmp_path)
    split = "examples/task-routing/split-heldout.json"
    trained = {"judge": {"backbone": "b", "train_rows_sha256": "x",
                         "split": {"path": split,
                                   "sha256": sha256_of(str(consensus_report.ROOT / split))}}}
    # no run header at all (like Jev's audits), and a header without a training split
    _checkpoint(tmp_path, "bare", "email-adversarial", None)
    _checkpoint(tmp_path, "chat", "email-adversarial", {"judge": {"name": "llm:x"}})
    assert not_a_juror("email-adversarial", "bare") == {"not_a_juror": OUTSIDE_PANEL}
    assert not_a_juror("email-adversarial", "chat") == {"not_a_juror": OUTSIDE_PANEL}
    # trained on another dataset: the reason says so, and no email contains a router text
    _checkpoint(tmp_path, "router-tuned", "email-adversarial", trained)
    d = not_a_juror("email-adversarial", "router-tuned")
    assert (d["trained_on"], d["rows_with_training_text"]) == ("router-bare", 0)
    assert d["not_a_juror"] == ("not a juror: fine-tuned on half of router-bare; 0 of these 200 "
                                "rows contain a training text")
    # on its own dataset, every train-half row is a training text (60 of 120 at least)
    _checkpoint(tmp_path, "router-tuned", "router-bare", trained)
    assert not_a_juror("router-bare", "router-tuned")["rows_with_training_text"] >= 60
    # a split file that no longer hashes to what the header recorded proves nothing
    trained["judge"]["split"]["sha256"] = "0" * 64
    _checkpoint(tmp_path, "stale", "email-adversarial", trained)
    assert not_a_juror("email-adversarial", "stale") == {"not_a_juror": TRAINING_UNVERIFIABLE}
    del trained["judge"]["split"]
    _checkpoint(tmp_path, "no-split", "email-adversarial", trained)
    assert not_a_juror("email-adversarial", "no-split") == {"not_a_juror": TRAINING_UNVERIFIABLE}


def test_a_panel_without_jev_lists_jev_as_an_outsider(monkeypatch, tmp_path):
    import consensus_report

    panel = json.loads(consensus_report.PANEL.read_text(encoding="utf-8"))["panel"]
    smaller = tmp_path / "panel.json"
    smaller.write_text(json.dumps({"panel": [j for j in panel if j != "jev"]}), encoding="utf-8")
    monkeypatch.setattr(consensus_report, "PANEL", smaller)
    e = consensus_report.collect_dataset("email-clean")      # Jev's checkpoint is not in the Arena
    assert "jev" not in e["panel"]["judges"] and len(e["panel"]["judges"]) == 7
    assert e["declared_confidence"]["jev"] == {**e["declared_confidence"]["jev"], "juror": False,
                                               "not_a_juror": consensus_report.OUTSIDE_PANEL}


def test_frozen_panel_keeps_its_order_and_requires_the_panel_file(monkeypatch, tmp_path):
    import consensus_report

    panel = tmp_path / "panel.json"
    panel.write_text('{"panel": ["b", "a"]}', encoding="utf-8")
    monkeypatch.setattr(consensus_report, "PANEL", panel)
    # order is the panel's; an outsider never enters
    assert consensus_report.frozen_panel({"a": [], "b": [], "z": []}) == ["b", "a"]
    monkeypatch.setattr(consensus_report, "PANEL", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):             # no panel file is not "everyone votes"
        consensus_report.frozen_panel({"a": []})


def test_panel_member_without_complete_run_fails_loudly(monkeypatch, tmp_path):
    import consensus_report

    panel = tmp_path / "panel.json"
    panel.write_text('{"panel": ["a", "b", "c"]}', encoding="utf-8")
    monkeypatch.setattr(consensus_report, "PANEL", panel)
    with pytest.raises(ValueError, match="without a complete run: b, c"):
        consensus_report.frozen_panel({"a": [], "z": []})
    with pytest.raises(ValueError, match="a, b, c"):
        consensus_report.frozen_panel({})
    # end to end: a panel naming a judge with no run on the dataset stops the report
    panel.write_text('{"panel": ["jev", "nobody"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="nobody"):
        consensus_report.jury_votes("email-clean")


