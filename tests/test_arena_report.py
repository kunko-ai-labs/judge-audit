"""Arena report: per-judge summary and the rendered selection rationale."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from arena_report import (  # noqa: E402
    calibration_ranks,
    ordinal,
    ranking_sentence,
    render,
    reversals,
    summarize,
)


def rec(decision, confidence, expected="b"):
    return {"decision": decision, "confidence": confidence, "correct": decision == expected,
            "latency_s": 1.0, "cost_usd": 0.0, "meta": {}}


def test_summarize_counts_blank_answers_separately():
    s = summarize([rec("b", .9), rec("", 0.0), rec(" ", 0.0), rec("a", .8)], "email-clean")
    assert s["n"] == 4 and s["no_answer"] == 2 and s["accuracy"] == 0.25
    assert summarize([rec("b", .9)], "email-clean")["no_answer"] == 0


def test_render_states_why_these_judges_and_the_blank_column():
    judges = {"jev": {"label": "Jev", "method": "option probability",
                      "datasets": {"email-clean": summarize([rec("b", .9), rec("", 0.0)],
                                                            "email-clean")}}}
    md = render(judges)
    assert "## Why these judges" in md
    for name in ("Jev", "Claude Sonnet 4.5", "Gemini 3 Flash", "Llama 3.3 70B", "DeepSeek R1",
                 "gemma4", "llama3.2", "DeBERTa", "control", "your own classifier",
                 "finetuned-baseline-2026-09.md"):
        assert name in md
    for missing in ("OpenJev", "GPT", "Mistral"):
        assert missing in md
    assert "cannot hijack it;" in md          # no NLI row here: no degradation figures rendered
    assert "| no answer |" in md
    # two rows, one right: the bootstrap can land on 0, 50 or 100 % — the interval says so
    assert "| Jev | option probability | 50.0% [0.0, 100.0] |" in md and "| 1 |" in md


def test_render_states_the_controls_degradation_from_its_own_numbers():
    adv = summarize([{**rec("b", .9), "meta": {"attack": "prompt_injection"}},
                     {**rec("a", .9), "meta": {"attack": "prompt_injection"}},
                     {**rec("b", .9), "meta": {"attack": "social_engineering"}},
                     {**rec("b", .9), "meta": {}}], "email-adversarial")
    clean = summarize([rec("b", .9), rec("b", .9), rec("b", .9), rec("a", .9)], "email-clean")
    md = render({"deberta-nli": {"label": "deberta", "method": "NLI",
                                 "datasets": {"email-clean": clean, "email-adversarial": adv}}})
    assert "(75.0% clean → 75.0% under attack, 50.0% on prompt-injection rows)" in md


# Three hand-computed judges on four rows (expected answer "b"):
#   A: 0.9 on all, right 3/4 -> ECE 0.15 (one bin), equal-mass 0.15, Brier 0.84/4 = 0.21
#   B: 1.0, 1.0 right; 0.6 right, 0.6 wrong -> ECE 2/4*0 + 2/4*0.1 = 0.05, equal-mass the
#      same two bins (the ten cuts can only fall at the 0.6|1.0 edge), Brier 0.52/4 = 0.13
#   C: 0.5 on all, right 2/4 -> ECE 0, equal-mass 0, Brier 0.25
A = [rec("b", .9), rec("b", .9), rec("b", .9), rec("a", .9)]
B = [rec("b", 1.0), rec("b", 1.0), rec("b", .6), rec("a", .6)]
C = [rec("b", .5), rec("a", .5), rec("b", .5), rec("a", .5)]


def judge(label, recs):
    return {"label": label, "method": "verbalized",
            "datasets": {"email-clean": summarize(recs, "email-clean")}}


def test_summarize_carries_the_three_calibration_numbers_with_intervals():
    for recs, (ece, em, brier) in ((A, (0.15, 0.15, 0.21)), (B, (0.05, 0.05, 0.13)),
                                   (C, (0.0, 0.0, 0.25))):
        s = summarize(recs, "email-clean")
        assert (s["ece"], s["ece_equal_mass"], s["brier"]) == (ece, em, brier)
        for key in ("ece_equal_mass", "brier"):
            assert f"{key}_ci" in s and f"{key}_ci_method" in s


def test_arena_table_has_brier_and_equal_mass_columns():
    md = render({"b": judge("B", B)})
    assert "| judge | confidence | accuracy | ECE | ECE (equal-mass) | Brier |" in md
    row = next(ln for ln in md.splitlines() if ln.startswith("| B |"))
    cells = [c.strip() for c in row.split("|")]
    assert cells[4].startswith("0.050") and cells[5].startswith("0.0500")
    assert cells[6].startswith("0.1300")
    assert "No log-loss" in md and "also rewards accuracy" in md


def test_a_calibration_ranking_that_flips_is_said_in_one_sentence():
    # C beats B on both ECEs (0 < 0.05) and loses on Brier (0.25 > 0.13)
    judges = {"b": judge("B", B), "c": judge("C", C)}
    assert calibration_ranks(judges, "email-clean") == {"b": (2, 2, 1), "c": (1, 1, 2)}
    sentence = ranking_sentence(judges)
    assert sentence.count(". ") == 1 and sentence.endswith("one ranking.")
    assert ("do not order the judges the same way** on 1 of the 1 datasets (clean emails): "
            "1 judge pair swaps places, and none of those swaps is separated by the "
            "intervals of both numbers involved." in sentence)
    assert reversals(judges, "email-clean")[0] == 1
    assert ("B on clean emails, 2nd of 2 by ECE, 2nd by equal-mass ECE and 1st by Brier"
            in sentence)
    assert "(0.050 / 0.0500 / 0.1300)" in sentence
    assert sentence in render(judges)


def test_reversals_separate_only_where_an_interval_does():
    def s(ece, em, brier, ci):
        return {"ece": ece, "ece_equal_mass": em, "brier": brier,
                **{f"{k}_ci": ci(v) for k, v in
                   (("ece", ece), ("ece_equal_mass", em), ("brier", brier))}}
    wide = {"a": {"datasets": {"d": s(0.1, 0.1, 0.3, lambda v: [v - 0.2, v + 0.2])}},
            "b": {"datasets": {"d": s(0.2, 0.2, 0.2, lambda v: [v - 0.2, v + 0.2])}}}
    assert reversals(wide, "d") == (1, 0)                   # swapped, not separated
    tight = {k: {"datasets": {"d": {**j["datasets"]["d"],
                                    **{f"{m}_ci": None for m in ("ece", "ece_equal_mass",
                                                                  "brier")}}}}
             for k, j in wide.items()}                      # degenerate: the point itself
    assert reversals(tight, "d") == (1, 1)
    # disjoint on ECE only: the Brier intervals of the swap still overlap -> not separated
    half = {"a": {"datasets": {"d": {**tight["a"]["datasets"]["d"], "brier_ci": [0.1, 0.4]}}},
            "b": {"datasets": {"d": {**tight["b"]["datasets"]["d"], "brier_ci": [0.1, 0.4]}}}}
    assert reversals(half, "d") == (1, 0)
    same = {"a": wide["a"], "a2": wide["a"]}
    assert reversals(same, "d") == (0, 0)                   # identical judges never swap


def test_a_stable_ranking_and_identical_judges_are_not_a_flip():
    same = ranking_sentence({"a": judge("A", A), "b": judge("B", B)})
    assert same.startswith("ECE, equal-mass ECE and Brier rank the judges in the same order")
    twins = {"a": judge("A", A), "a2": judge("A twin", list(A))}
    assert calibration_ranks(twins, "email-clean") == {"a": (1, 1, 1), "a2": (1, 1, 1)}
    assert ranking_sentence(twins) == same


def test_ordinal():
    assert [ordinal(k) for k in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "111th"]
