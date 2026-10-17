"""The repeat-runs report scores the pre-registered predictions mechanically."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from repeats_report import RUNS, render, rng, score, spread  # noqa: E402


def run(acc, zec, ci, inf):
    return {"accuracy": acc, "zero_error_coverage": zec, "zero_error_coverage_ci": ci,
            "zec_upper": (ci or [None, None])[1],
            "nll_infinite": inf, "mean_conf_correct": 0.9, "mean_conf_wrong": 0.8}


def judges(gemini_zec=0.0, jev_lo=0.66, sonnet_zec=0.0, jev_inf=0, jev_zec=0.73, jev_acc=0.955):
    g = {k: run(0.97, gemini_zec, [0.0, 0.0183], 5) for k in RUNS}
    s = {k: run(0.965, sonnet_zec, [0.0, 0.9], 2) for k in RUNS}
    v = {k: run(jev_acc, jev_zec, [jev_lo, 0.94], jev_inf) for k in RUNS}
    arena = {"accuracy_ci": [0.9, 0.99]}
    return {"gemini-3-flash": {"repeats": g, "arena": arena},
            "claude-sonnet-4.5": {"repeats": s, "arena": arena},
            "jev": {"repeats": v, "arena": arena}}


def test_all_six_hold_on_data_that_repeats_the_arena():
    assert [p["held"] for p in score(judges())] == [True] * 6


def test_each_prediction_can_fail():
    assert score(judges(gemini_zec=0.05))[0]["held"] is False
    assert score(judges(jev_zec=0.45))[1]["held"] is False
    assert score(judges(jev_acc=0.80))[4]["held"] is False
    assert score(judges(jev_lo=0.01))[2]["held"] is False
    assert score(judges(sonnet_zec=0.9))[3]["held"] is False
    assert score(judges(jev_inf=1))[5]["held"] is False


def test_spread_is_min_max_and_sd_over_the_runs():
    sp = spread([run(0.95, 0.7, None, 0), run(0.97, 0.74, None, 0)])
    assert sp["accuracy"]["min"] == 0.95 and sp["accuracy"]["max"] == 0.97
    assert rng(sp["zero_error_coverage"], True).startswith("70.0–74.0 %")


def test_predictions_carry_their_pre_registered_ids():
    assert [p["id"] for p in score(judges())] == ["P1", "P2", "P3", "P4", "P5", "P6"]


def test_printed_upper_bounds_round_up_never_to_nearest():
    sp = spread([run(0.97, 0.0, [0.0, 0.0183], 5), run(0.96, 0.685, [0.6224, 0.9554], 0)])
    assert rng(sp["zec_upper"], True, bound=True).startswith("1.9–95.6 %")
    data = json.loads((ROOT / "docs" / "repeats-2026-09.json").read_text())
    data["sonnet_vs_jev"]["r1"]["sonnet_upper"] = 0.3352
    assert "33.6 % (r1)" in render(data)
    md = (ROOT / "docs" / "repeats-2026-09.md").read_text()
    assert "| 1.9–1.9 % (SD 0.00) |" in md
    assert "| 94.4–95.6 % (SD 0.59) |" in md

