"""Consensus audit: majority vote, panel statistics and the deliberation prompt."""
from __future__ import annotations

import sys
from pathlib import Path

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


def test_majority_breaks_ties_alphabetically():
    assert majority(["b", "b", "a"]) == ("b", 2 / 3)
    assert majority(["a", "b"]) == ("a", 0.5)


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
    out, panel = jury_deliberate.deliberation_rows("router-bare", "beta")
    assert panel == ["alpha", "gamma"]
    state = out[0]["state"]
    assert "2 other judges" in state and "Judge A: b" in state and "Judge B: b" in state
    assert "alpha" not in state and "gamma" not in state  # anonymised
    assert out[0]["_meta"]["round"] == 2
    assert sorted(out[0]["_meta"]["panel_seen"]) == ["alpha", "gamma"]
    assert rows[0]["state"] == "task"  # original row untouched
