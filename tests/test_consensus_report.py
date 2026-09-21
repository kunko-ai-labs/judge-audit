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


def test_majority_treats_ties_and_blanks_as_no_vote():
    assert majority(["b", "b", "a"]) == ("b", 2 / 3, False)
    assert majority(["a", "b"]) == (None, 0.5, True)           # tie: no decision
    assert majority(["b", "", " "]) == ("b", 1.0, False)        # blanks abstain
    assert majority(["", ""]) == (None, 0.0, False)


def test_panel_stats_ties_and_abstentions():
    votes = {"x": [rec("b", 0.9), rec("", 0.0)], "y": [rec("a", 0.6), rec("b", 0.7)]}
    rows = [{"labels": {"q": "b"}}, {"labels": {"q": "b"}}]
    s = panel_stats(votes, rows, "q")
    assert s["ties"] == 1 and s["abstentions"] == 1
    assert s["majority_accuracy"] == 0.5   # row 0 tie = not correct; row 1 decided by y alone
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
