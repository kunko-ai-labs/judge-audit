"""The repeat-runs report scores the pre-registered predictions mechanically."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from repeats_report import RUNS, rng, score, spread  # noqa: E402


def run(acc, zec, ci, inf):
    return {"accuracy": acc, "zero_error_coverage": zec, "zero_error_coverage_ci": ci,
            "nll_infinite": inf, "mean_conf_correct": 0.9, "mean_conf_wrong": 0.8}


def judges(gemini_zec=0.0, jev_lo=0.66, sonnet_zec=0.0, jev_inf=0):
    g = {k: run(0.97, gemini_zec, [0.0, 0.0183], 5) for k in RUNS}
    s = {k: run(0.965, sonnet_zec, [0.0, 0.9], 2) for k in RUNS}
    v = {k: run(0.955, 0.73, [jev_lo, 0.94], jev_inf) for k in RUNS}
    arena = {"accuracy_ci": [0.9, 0.99]}
    return {"gemini-3-flash": {"repeats": g, "arena": arena},
            "claude-sonnet-4.5": {"repeats": s, "arena": arena},
            "jev": {"repeats": v, "arena": arena}}


def test_all_six_hold_on_data_that_repeats_the_arena():
    assert [p["held"] for p in score(judges())] == [True] * 6


def test_each_prediction_can_fail():
    assert score(judges(gemini_zec=0.05))[0]["held"] is False
    assert score(judges(jev_lo=0.01))[2]["held"] is False
    assert score(judges(sonnet_zec=0.9))[3]["held"] is False
    assert score(judges(jev_inf=1))[5]["held"] is False


def test_spread_is_min_max_and_sd_over_the_runs():
    sp = spread([run(0.95, 0.7, None, 0), run(0.97, 0.74, None, 0)])
    assert sp["accuracy"]["min"] == 0.95 and sp["accuracy"]["max"] == 0.97
    assert rng(sp["zero_error_coverage"], True).startswith("70.0–74.0 %")
