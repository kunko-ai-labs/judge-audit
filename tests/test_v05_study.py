"""scripts/v05_study.py: the decision rules of docs/v05-plan.md §6 and amendment 2, on
hand-built inputs (the study's own numbers are checked by CI regenerating the report)."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("v05_study", ROOT / "scripts" / "v05_study.py")
study = importlib.util.module_from_spec(spec)
sys.modules["v05_study"] = study
spec.loader.exec_module(study)

OPTIONS = ["transfer", "balance", "out_of_scope"]
DESC = {"out_of_scope": "the request asks for none of the other intents"}


# --- amendment 2's re-reading ------------------------------------------------------------


@pytest.mark.parametrize("decision, expected", [
    ("out_of_scope: the request asks for none of the other intents", "out_of_scope"),
    ("out_of_scope:the request asks for none of the other intents  ", "out_of_scope"),
    ("out_of_scope:\tthe request asks for none of the other intents\n", "out_of_scope"),
])
def test_an_option_with_its_description_is_read_as_the_option(decision, expected):
    assert study.reread(decision, OPTIONS, DESC) == expected


@pytest.mark.parametrize("decision", [
    "out_of_scope",                                                    # nothing to re-read
    "out_of_scope : the request asks for none of the other intents",   # head not byte-exact
    "Out_of_scope: the request asks for none of the other intents",    # no case folding
    "out_of_scope: the request asks for none of the listed intents",   # another description
    "out_of_scope: The request asks for none of the other intents",    # description's case
    "transfer: move money",                                            # option, no description
    "refund: the request asks for none of the other intents",          # not an option
    "",
])
def test_anything_else_is_left_as_it_was(decision):
    assert study.reread(decision, OPTIONS, DESC) == decision


def test_the_split_is_at_the_first_colon():
    desc = {"a": "x: y"}
    assert study.reread("a: x: y", ["a"], desc) == "a"
    assert study.reread("a: x", ["a"], desc) == "a: x"


# --- reading a checkpoint under both rules ----------------------------------------------


def _row(label="out_of_scope"):
    return {"state": "Hello  World", "labels": {"intent": label},
            "questions": [{"name": "intent", "type": "choice", "instructions": "Which?",
                           "options": OPTIONS, "descriptions": DESC}]}


def _reply(decision, confidence=0.9):
    return json.dumps({"answers": {"intent": {"decision": decision, "confidence": confidence}}})


def _rec(decision, confidence, raw=None, status="parsed"):
    return {"decision": decision, "confidence": confidence, "parse_status": status,
            "raw": raw or {}, "correct": None}


FULL = "out_of_scope: the request asks for none of the other intents"


def test_a_verbalized_row_is_rescored_but_keeps_its_confidence():
    labels = {"rows": [_row(), _row("transfer")]}
    run = {"adapter": "llm", "samples": 1,
           "records": [_rec(FULL, 0.97), _rec("transfer", 0.8)]}
    strict, _ = study.read_rows(run, labels, "strict")
    reread, changed = study.read_rows(run, labels, "reread")
    assert [r["correct"] for r in strict] == [False, True]
    assert [r["correct"] for r in reread] == [True, True]
    assert [r["confidence"] for r in reread] == [0.97, 0.8]
    assert changed == {"rows": 1, "samples": 0, "decisions_changed": 1,
                       "revote_mismatches": 0}


def test_self_consistency_re_reads_every_sample_before_the_vote():
    """Three samples say the option with its description, two say the option: strictly
    the first spelling wins 3/5 and is wrong; re-read, all five agree, 5/5 and right."""
    texts = [_reply(FULL), _reply("out_of_scope"), _reply(FULL), _reply("out_of_scope"),
             _reply(FULL)]
    raw = {"samples": [{"text": t} for t in texts]}
    run = {"adapter": "llm", "samples": 5, "records": [_rec(FULL, 0.6, raw)]}
    labels = {"rows": [_row()]}
    strict, ch_s = study.read_rows(run, labels, "strict")
    reread, ch_r = study.read_rows(run, labels, "reread")
    assert (strict[0]["decision"], strict[0]["confidence"], strict[0]["correct"]) == (
        FULL, 0.6, False)
    assert (reread[0]["decision"], reread[0]["confidence"], reread[0]["correct"]) == (
        "out_of_scope", 1.0, True)
    assert ch_s["revote_mismatches"] == 0
    assert ch_r == {"rows": 1, "samples": 3, "decisions_changed": 1, "revote_mismatches": 0}


def test_a_re_read_that_does_not_change_the_vote_winner_still_moves_its_share():
    texts = [_reply("out_of_scope"), _reply("out_of_scope"), _reply(FULL), _reply("transfer"),
             _reply("transfer")]
    raw = {"samples": [{"text": t} for t in texts]}
    run = {"adapter": "llm", "samples": 5, "records": [_rec("out_of_scope", 0.4, raw)]}
    reread, ch = study.read_rows(run, {"rows": [_row()]}, "reread")
    assert (reread[0]["decision"], reread[0]["confidence"]) == ("out_of_scope", 0.6)
    assert ch["rows"] == 1 and ch["decisions_changed"] == 0


def test_a_checkpoint_that_does_not_re_vote_to_its_record_is_caught():
    raw = {"samples": [{"text": _reply("transfer")} for _ in range(5)]}
    run = {"adapter": "llm", "samples": 5, "records": [_rec("balance", 1.0, raw)]}
    _, ch = study.read_rows(run, {"rows": [_row("transfer")]}, "strict")
    assert ch["revote_mismatches"] == 1


def test_other_adapters_are_never_re_read_and_unusable_rows_have_no_confidence():
    labels = {"rows": [_row(), _row(), _row()]}
    run = {"adapter": "jev", "samples": 1,
           "records": [_rec(FULL, 0.9), None, _rec("", None, status="no_answer")]}
    rows, ch = study.read_rows(run, labels, "reread")
    assert [r["status"] for r in rows] == ["scored", "missing", "no_answer"]
    assert [r["confidence"] for r in rows] == [0.9, None, None]
    assert rows[0]["correct"] is False and ch["rows"] == 0


# --- §6: own usable rows, Holm, outcome, verdicts ----------------------------------------


def test_each_method_is_scored_on_its_own_usable_rows():
    rs = [(0.9, True), (None, False), (0.2, False), (0.8, True)]
    assert study.auroc_own(rs) == 1.0
    assert study.auroc_own([(None, True)]) is None


def _family(diffs, ps):
    return {t: {"difference": d, "p": p}
            for t, d, p in zip([f"T{i}" for i in range(1, 9)], diffs, ps, strict=True)}


def test_resolved_needs_holm_and_the_predicted_sign():
    fam = study.settle(_family([+0.1, -0.05, -0.07, -0.2, -0.14, +0.36, +0.1, +0.48],
                               [0.0002, 0.01, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.04]))
    # Holm: the six 0.0002s give 8 × 0.0002 = 0.0016 (never falling down the order);
    # then 0.01 × 2 = 0.02 and 0.04 × 1
    assert fam["T1"]["p_holm"] == pytest.approx(0.0016)
    assert fam["T2"]["p_holm"] == pytest.approx(0.02)
    assert fam["T8"]["p_holm"] == pytest.approx(0.04)
    assert [fam[t]["resolved"] for t in fam] == [True, False, False, False, False, True,
                                                 True, True]
    assert [fam[t]["opposite_sign"] for t in fam] == [False, True, True, True, True, False,
                                                      False, False]
    assert fam["T6"]["as_predicted"] is False and fam["T3"]["as_predicted"] is True
    assert study.outcome(fam["T2"]).startswith("not resolved: opposite sign")


def test_a_test_that_flips_with_the_reading_marks_its_hypothesis():
    p = [0.0002] * 8
    strict = study.settle(_family([0.1, 0.1, -0.07, -0.2, -0.14, +0.36, 0.1, 0.48], p))
    reread = study.settle(_family([0.1, 0.1, -0.07, -0.2, -0.14, -0.28, 0.1, 0.0], p[:7]
                                  + [0.97]))
    v = {(x["hypothesis"], x["model"]): x for x in
         study.verdicts_of({"strict": strict, "reread": reread})}
    assert strict["T6"]["depends_on_scoring_rule"]          # sign flips
    assert strict["T8"]["depends_on_scoring_rule"]          # resolved, then not
    assert not strict["T1"]["depends_on_scoring_rule"]
    assert v[("H1-lp", study.QWEN)]["strict"] and v[("H1-lp", study.QWEN)]["reread"]
    assert v[("H2", study.GEMINI)]["strict"] and not v[("H2", study.GEMINI)]["reread"]
    assert v[("H2", study.GEMINI)]["depends_on_scoring_rule"]
    assert v[("H1-sc", study.GEMINI)]["depends_on_scoring_rule"]
    assert not v[("H1-sc", study.GEMINI)]["strict"]
    assert not v[("H2", study.QWEN)]["depends_on_scoring_rule"]


# --- amendment 1's near-ties --------------------------------------------------------------


def test_the_near_tie_margin_is_the_top_two_recorded_log_probabilities():
    assert study.option_margin({"logprobs": {"a": -0.935825, "b": -0.935825,
                                             "c": -1.7}}) == 0.0
    assert study.option_margin({"logprobs": {"a": -0.5, "b": -1.2, "c": -3.0}}) == (
        pytest.approx(0.7))
    assert study.option_margin({"logprobs": {"a": -0.1}}) == math.inf
    assert study.option_margin({}) == math.inf


def test_a_margin_on_the_bfloat16_step_is_a_near_tie_whatever_the_rounding():
    """Log-probabilities 0.5 apart stay a near-tie when each is rounded to 1e-6; the same
    pair read from probabilities rounded to 1e-6 (small ones) would not."""
    for a, b in ((-8.0, -8.5), (-1.234567, -1.734568), (-1.234568, -1.734567)):
        m = study.option_margin({"logprobs": {"x": a, "y": b, "z": -20.0}})
        assert abs(m - 0.5) <= 1e-6 + 1e-12
        assert m <= study.NEAR_TIE + study.MARGIN_TOL
    assert study.option_margin({"logprobs": {"x": -8.0, "y": -8.500011}}) > (
        study.NEAR_TIE + study.MARGIN_TOL)
    rounded = [round(math.exp(-8.0), 6), round(math.exp(-8.5), 6)]
    assert math.log(rounded[0]) - math.log(rounded[1]) > study.NEAR_TIE + study.MARGIN_TOL


def test_the_groups_are_the_repository_normalisation():
    assert study.normalise("  Hello \t World\n") == "hello world"
