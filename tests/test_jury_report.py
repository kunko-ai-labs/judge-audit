"""Jury report: per-judge switch statistics and the prediction verdict rules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from jury_report import judge_stats, predictions, switch_stats  # noqa: E402


def rec(decision, confidence, expected="b"):
    return {"decision": decision, "confidence": confidence,
            "correct": decision == expected, "meta": {}}


def test_judge_stats_empty_and_no_errors():
    assert judge_stats([]) == {"accuracy": None, "ece": None, "mean_conf_wrong": None}
    s = judge_stats([rec("b", 0.9), rec("b", 0.8)])
    assert s["accuracy"] == 1.0 and s["mean_conf_wrong"] is None


def test_switch_stats_ignores_blanks_and_scores_against_seen_panel():
    a = [rec("a", 0.9), rec("b", 0.8), rec("", 0.0), rec("a", 0.7), rec("b", 0.6)]
    b = [rec("b", 0.9), rec("a", 0.8), rec("b", 0.9), rec("a", 0.7), rec("", 0.0)]
    r1 = {"p": [rec("b", 0.9)] * 5, "q": [rec("a", 0.5)] * 5, "r": [rec("b", 0.7)] * 5}
    seen = [["p", "q", "r"], ["q"], ["p"], ["p", "q"], ["p"]]
    s = switch_stats(a, b, seen, r1)
    assert s["no_answer_round1"] == 1 and s["no_answer_round2"] == 1
    assert s["switched"] == 2                        # rows 0 and 1; rows 2 and 4 have a blank side
    assert s["switched_to_correct"] == 1 and s["switched_to_wrong"] == 1
    # row 0 → b (saw p, q, r: majority b); row 1 → a (saw q: a)
    assert s["switched_toward_panel_majority"] == 2


def _panel(agree, unan, maj, n=120):
    return {"pairwise_agreement": agree, "unanimous": unan, "majority_accuracy": maj, "n": n}


def _judge(hard1, hard2, conf1, conf2, switched=4, toward=3, to_wrong=1):
    return {"round1": {"mean_conf_wrong": conf1}, "round2": {"mean_conf_wrong": conf2},
            "hard_round1": {"accuracy": hard1}, "hard_round2": {"accuracy": hard2},
            "switched": switched, "switched_toward_panel_majority": toward,
            "switched_to_wrong": to_wrong, "switched_to_correct": switched - to_wrong}


def test_predictions_verdicts():
    data = {
        "router-bare": {"rerun": ["llama32", "x"],
                        "panel_round1": _panel(0.5, 10, 0.6), "panel_round2": _panel(0.6, 12, 0.6),
                        "hard_round1": {"majority_accuracy": 0.2},
                        "hard_round2": {"majority_accuracy": 0.25},
                        "judges": {"llama32": _judge(0.0, 0.0, 1.0, 0.8),
                                   "x": _judge(0.5, 0.5, 0.7, 0.9)}},
        "router-described": {"rerun": ["x"],
                             "panel_round1": _panel(0.6, 10, 0.9),
                             "panel_round2": _panel(0.7, 20, 0.95),
                             "hard_round1": {"majority_accuracy": 1.0},
                             "hard_round2": {"majority_accuracy": 1.0},
                             "judges": {"x": _judge(1.0, 1.0, 0.4, 0.3, to_wrong=1)}},
    }
    text = "\n".join(predictions(data))
    assert "1. **Agreement and unanimity rise on both datasets** — held" in text
    assert "3B model follows the panel** — held" in text        # +5 points < 10, llama32 3/4 toward
    assert "majority accuracy does not fall** — held" in text   # 1 wrong of 120 re-votes ≤ 5 %
    assert "after deliberation** — not held (1 of 3" in text    # only x/bare went up
    assert predictions({"router-bare": {"rerun": []}, "router-described": {"rerun": []}}) == []


def test_switch_stats_normalises_case_and_whitespace():
    a = [rec("a", 0.9)]
    b = [{"decision": "A ", "confidence": 0.9, "correct": False, "meta": {}}]
    s = switch_stats(a, b, [["p"]], {"p": [rec("b", 0.9)]})
    assert s["switched"] == 0
