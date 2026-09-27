"""scripts/v05_pilot.py: every estimate of docs/v05-pilot.md §5 on hand-computed fixtures.

The fixture in tests/fixtures/v05_pilot/ is six rows, one `intent` question with options
a, b, c, labels a b c a b c, read by the four pilot runs:

| row | label | verbalized       | self-consistency (k = 5)   | log-prob (mass) | Laya      |
|-----|-------|------------------|----------------------------|-----------------|-----------|
| 0   | a     | a 0.9            | a 1.0 {a: 5}               | a 0.97 (0.99)   | b 0.40    |
| 1   | b     | b 0.9            | b 0.8 {b: 4}, 1 failed     | b 0.55 (0.90)   | b 0.50    |
| 2   | c     | a 0.6            | c 0.6 {c: 3, a: 2}         | c 0.71 (0.95)   | c 0.35    |
| 3   | a     | a 0.8            | a 0.6 {a: 3, b: 2}         | b 0.62 (0.80)   | (missing) |
| 4   | b     | b 0.95           | c 1.0 {c: 5}               | b 0.88 (0.97)   | a 0.30    |
| 5   | c     | c, no confidence | no answer, 5 samples fail  | c 0.93 (0.85)   | c 0.45    |

Latencies per row: 2 s, 10 s, 1.5 s, 0.5 s. Tokens per call: 700 in, 30 out (verbalized);
700 in, 20 out per sample (self-consistency). Laya's header clamps `choice:11+` from
0.1006 to 0.5.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import random
import shutil
import sys
from pathlib import Path
from statistics import NormalDist

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "v05_pilot"
spec = importlib.util.spec_from_file_location("v05_pilot", ROOT / "scripts" / "v05_pilot.py")
pilot = importlib.util.module_from_spec(spec)
sys.modules["v05_pilot"] = pilot
spec.loader.exec_module(pilot)

VERB, SC, LP, LAYA = "llm-qwen3-8b", "llm-qwen3-8b-sc5", "logprob-qwen3-8b", "laya"
N_SIM = 20_000          # the report uses 100,000; the fixtures do not need them
N_BOOT = 300


@pytest.fixture(scope="module")
def d():
    return pilot.compute(FIXTURE, FIXTURE / "labels.jsonl", n_sim=N_SIM, n_boot=N_BOOT)


def pair(rows: list[dict], a: str, b: str) -> dict:
    return next(r for r in rows if r["pair"] == [a, b])


# --- accuracy, counts, overconfidence --------------------------------------------------------


def test_accuracy_counts_every_labelled_row_and_no_confidence_as_wrong(d):
    from relabel import wilson_interval

    runs = d["runs"]
    # verbalized: rows 0, 1, 3, 4 right; row 5 names the label but carries no confidence,
    # and §5 counts it wrong
    assert runs[VERB]["accuracy"]["right"] == 4 and runs[VERB]["accuracy"]["n"] == 6
    assert runs[VERB]["no_confidence"] == 1 and runs[VERB]["no_confidence_decision_right"] == 1
    assert runs[SC]["accuracy"]["right"] == 4 and runs[SC]["no_answer"] == 1
    assert runs[LP]["accuracy"]["right"] == 5
    # Laya: row 3 is missing from the checkpoint; it counts as wrong, n stays 6
    assert runs[LAYA]["missing"] == 1 and runs[LAYA]["in_checkpoint"] == 5
    assert runs[LAYA]["accuracy"]["right"] == 3 and runs[LAYA]["accuracy"]["n"] == 6
    lo, hi = wilson_interval(3, 6)
    assert runs[LAYA]["accuracy"]["wilson_95"] == [round(lo, 4), round(hi, 4)]
    assert runs[LAYA]["accuracy"]["wilson_95"] == pytest.approx([0.1876, 0.8124])


def test_overconfidence_is_mean_confidence_minus_accuracy_on_the_scored_rows(d):
    runs = d["runs"]
    # verbalized: (0.9 + 0.9 + 0.6 + 0.8 + 0.95) / 5 = 0.83 against 4 / 5 right
    assert runs[VERB]["overconfidence"]["value"] == pytest.approx(0.03, abs=1e-9)
    assert runs[VERB]["overconfidence"]["n"] == 5
    assert runs[SC]["overconfidence"]["value"] == pytest.approx(0.0, abs=1e-9)
    assert runs[LP]["overconfidence"]["value"] == pytest.approx(4.66 / 6 - 5 / 6, abs=1e-4)
    assert runs[LAYA]["overconfidence"]["value"] == pytest.approx(-0.2, abs=1e-9)


# --- decision agreement ----------------------------------------------------------------------


def test_decision_agreement_by_hand(d):
    rows = d["decision_agreement"]
    # verbalized a b a a b c, self-consistency a b c a c -: same on 0, 1, 3; correctness
    # T T F T T F against T T T T F F: same on 0, 1, 3, 5
    vs = pair(rows, VERB, SC)
    assert (vs["same_decision"], vs["same_correctness"], vs["n"]) == (3, 4, 6)
    vl = pair(rows, VERB, LP)
    assert (vl["same_decision"], vl["same_correctness"]) == (4, 3)
    sl = pair(rows, SC, LP)
    assert (sl["same_decision"], sl["same_correctness"]) == (3, 3)
    assert vs["same_decision_share"] == 0.5


# --- tie shares and the verbalized distribution ----------------------------------------------


def test_tie_shares_leave_out_rows_without_a_confidence(d):
    runs = d["runs"]
    assert runs[VERB]["tie_shares"]["levels"] == [[0.6, 1, 0.2], [0.8, 1, 0.2], [0.9, 2, 0.4],
                                                  [0.95, 1, 0.2]]
    assert runs[SC]["tie_shares"]["levels"] == [[0.6, 2, 0.4], [0.8, 1, 0.2], [1.0, 2, 0.4]]
    assert runs[LP]["tie_shares"]["n"] == 6 and len(runs[LP]["tie_shares"]["levels"]) == 6


def test_tie_shares_round_to_a_millionth():
    assert pilot.tie_levels([0.3333334, 0.3333333, 0.5]) == [(0.333333, 2), (0.5, 1)]


def test_verbalized_levels_round_half_down_to_the_lower_twentieth():
    assert pilot.twentieth(0.925) == 18          # 0.925 is exactly between 0.90 and 0.95
    assert pilot.twentieth(0.93) == 19
    assert pilot.twentieth(0.974) == 19 and pilot.twentieth(0.976) == 20
    assert pilot.twentieth(1.0) == 20 and pilot.twentieth(0.0) == 0


def test_pooling_moves_rare_levels_to_the_nearest_kept_one_and_ties_go_down():
    """200 rows: 0.6 x 50 and 0.8 x 147 are kept (25 %, 73.5 %); 0.7 (one row) is as far from
    0.6 as from 0.8 and goes down to 0.6; 0.93 rounds to 0.95 and 0.925 to 0.90, one row each,
    both nearest to 0.8. Weights 51 / 200 and 149 / 200."""
    confs = [0.6] * 50 + [0.8] * 147 + [0.7, 0.93, 0.925]
    out = pilot.pool_verbalized(confs)
    assert out["levels"] == [[0.6, 50], [0.7, 1], [0.8, 147], [0.9, 1], [0.95, 1]]
    assert out["pooled"] == [[0.6, 51], [0.8, 149]]
    assert out["values"] == [0.6, 0.8] and out["weights"] == [0.255, 0.745]


def test_a_level_at_exactly_one_percent_is_kept():
    out = pilot.pool_verbalized([0.5] + [0.9] * 99)
    assert out["values"] == [0.5, 0.9] and out["weights"] == [0.01, 0.99]


def test_weights_sum_to_one_with_the_remainder_on_the_largest():
    assert pilot.milli([1, 1, 1]) == [334, 333, 333]            # ties: the lowest level
    assert pilot.milli([1, 2, 3]) == [167, 333, 500]            # 166.7, 333.3, 500 → 1000
    assert pilot.milli([1, 1, 1, 1, 1, 1, 1]) == [142, 143, 143, 143, 143, 143, 143]
    assert sum(pilot.milli([3, 7, 11, 13])) == 1000


def test_fixture_verbalized_distribution(d):
    v = d["verbalized_distribution"]
    assert v["n"] == 5 and v["values"] == [0.6, 0.8, 0.9, 0.95]
    assert v["weights"] == [0.2, 0.2, 0.4, 0.2]


# --- Spearman and the latent rho -------------------------------------------------------------


def test_spearman_uses_average_ranks():
    # x ranks 2.5 2.5 1, y ranks 3 2 1: 1.5 / sqrt(1.5 * 2)
    assert pilot.spearman([0.9, 0.9, 0.8], [1.0, 0.8, 0.6]) == pytest.approx(math.sqrt(3) / 2)
    assert pilot.spearman([0.9, 0.9, 0.95], [0.97, 0.55, 0.88]) == pytest.approx(0.0)
    assert pilot.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert pilot.spearman([1.0, 1.0, 1.0], [0.1, 0.2, 0.3]) is None      # one level: undefined
    assert pilot.spearman([0.5], [0.5]) is None and pilot.spearman([], []) is None


def test_rank_agreement_on_the_both_right_rows(d):
    rows = d["rank_agreement"]
    vs = pair(rows, VERB, SC)          # rows 0, 1, 3
    assert vs["both_right"] == 3 and vs["both_wrong"] == 1
    assert vs["spearman"] == pytest.approx(0.8660, abs=1e-4)
    # verbalized 0.8, 0.9, 0.9 is cut in two levels; self-consistency 1.0, 0.8, 0.6 has no tie
    # on these rows, so, like a continuous method, it is not cut
    assert vs["levels"] == [2, None]
    vl = pair(rows, VERB, LP)          # rows 0, 1, 4
    assert vl["spearman"] == pytest.approx(0.0, abs=1e-12)
    assert vl["levels"] == [2, None]   # log-probability untied: not cut
    sl = pair(rows, SC, LP)            # rows 0, 1, 2
    assert sl["spearman"] == pytest.approx(0.5)
    assert vs["rho"] > vl["rho"]
    assert 0.0 <= vs["rho"] <= 0.999


def _base(n: int = N_SIM) -> list[tuple[float, float]]:
    rng = random.Random(pilot.SEED)
    return [pilot.normal_pair(rng, 0.0) for _ in range(n)]


def test_rho_zero_and_anything_below_it_maps_to_zero():
    f = pilot.RankMap(_base(), [0.2, 0.3, 0.5], None)
    at_zero = f(0.0)
    assert abs(at_zero) < 0.03
    assert pilot.latent_rho(at_zero, f) == 0.0
    assert pilot.latent_rho(at_zero - 0.2, f) == 0.0
    assert pilot.latent_rho(-1.0, f) == 0.0
    assert pilot.latent_rho(None, f) is None


def test_the_rank_map_is_monotone_and_the_inversion_reproduces_the_observed_value():
    f = pilot.RankMap(_base(), [0.1, 0.2, 0.3, 0.4], [0.5, 0.5])
    grid = [f(r / 10) for r in range(10)]
    assert grid == sorted(grid)
    target = f(0.55)
    rho = pilot.latent_rho(target, f)
    assert rho == pytest.approx(0.55, abs=1e-3)
    assert f(rho) == pytest.approx(target, abs=2e-3)
    assert pilot.latent_rho(0.9999, f) == pytest.approx(0.999, abs=1e-6)   # the top of [0, 0.999]


def test_the_mapping_recovers_a_known_rho_on_simulated_rows():
    """3,000 rows drawn with latent rho 0.6; the first method cut into three levels, the
    second continuous. The observed Spearman is attenuated by the ties; the mapping, fed the
    shares measured on those rows, gives rho back within sampling error."""
    rng = random.Random(3)
    pairs = [pilot.normal_pair(rng, 0.6) for _ in range(3000)]
    x = pilot.levels([a for a, _ in pairs], [0.2, 0.3, 0.5])
    y = [b for _, b in pairs]
    observed = pilot.spearman(x, y)
    assert observed < 0.55                              # attenuated
    shares = [c / 3000 for _, c in pilot.tie_levels(x)]
    f = pilot.RankMap(_base(), shares, None)
    assert pilot.latent_rho(observed, f) == pytest.approx(0.6, abs=0.04)


def test_rho_is_undefined_when_one_method_is_constant_on_the_both_right_rows(tmp_path):
    """Self-consistency unanimous on every row, log-probability at one value: neither H1
    pair has a rank correlation, so RHOS proposes nothing and says why."""
    runs = _synthetic(tmp_path,
                      verbalized=[(x, 0.5 + i / 10) for i, x in enumerate(LABELS)],
                      sc=[(x, 1.0) for x in LABELS])
    d = pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)
    vs = pair(d["rank_agreement"], VERB, SC)
    assert vs["both_right"] == 6 and vs["levels"] == [None, 1]
    assert vs["spearman"] is None and vs["rho"] is None and vs["rho_95"] is None
    rhos = d["proposed_constants"]["RHOS"]
    assert rhos["value"] == [] and rhos["note"].count("not estimable") == 2


# --- AUROC and its latent inversion ----------------------------------------------------------


def test_auroc_with_a_delong_interval_by_hand():
    """Right answers 0.9, 0.8, 0.3, wrong 0.5, 0.1. Placements: right (1, 1, 1/2), wrong
    (2/3, 1). AUROC 5/6; Var = (1/12) / 3 + (1/18) / 2 = 1/18."""
    out = pilot.auroc_delong([0.9, 0.8, 0.3, 0.5, 0.1], [True, True, True, False, False])
    z = NormalDist().inv_cdf(0.975)
    assert out["value"] == pytest.approx(5 / 6, abs=5e-5)          # published to 4 decimals
    assert out["delong_95"] == [round(5 / 6 - z * math.sqrt(1 / 18), 4), 1.0]    # clipped
    assert (out["right"], out["wrong"]) == (3, 2)


def test_auroc_degenerate_cases():
    one_wrong = pilot.auroc_delong([0.9, 0.9, 0.6, 0.8, 0.95], [True, True, False, True, True])
    assert one_wrong["value"] == 1.0 and one_wrong["delong_95"] is None   # no variance from 1
    none_wrong = pilot.auroc_delong([0.9, 0.8], [True, True])
    assert none_wrong["value"] is None and none_wrong["delong_95"] is None
    assert pilot.auroc_delong([], [])["value"] is None


def test_fixture_aurocs(d):
    runs = d["runs"]
    assert runs[VERB]["auroc"]["value"] == 1.0
    # self-consistency: its one wrong answer ties the top (1.0): (1/2 + 0 + 0 + 0) / 4
    assert runs[SC]["auroc"]["value"] == pytest.approx(0.125)
    assert runs[LP]["auroc"]["value"] == pytest.approx(0.8)
    assert runs[LAYA]["auroc"]["value"] == pytest.approx(5 / 6, abs=5e-5)
    assert runs[LAYA]["auroc"]["delong_95"] == pytest.approx([0.3714, 1.0], abs=1e-4)


def test_latent_auroc_inverts_population_auroc():
    shares = [0.05, 0.05, 0.10, 0.15, 0.25, 0.40]
    observed = pilot.population_auroc(1.0, 0.85, shares)
    out = pilot.latent_auroc(observed, 0.85, shares)
    assert out["mu"] == pytest.approx(1.0, abs=1e-6)
    assert out["latent"] == pytest.approx(NormalDist().cdf(1 / math.sqrt(2)), abs=1e-6)
    assert out["auroc_a"] == 0.75 and out["capped"] is False        # 0.7602 to the nearest 0.05
    # ties pull the observed AUROC down: the latent one is higher
    assert out["latent"] > observed


def test_latent_auroc_is_capped_and_floored():
    top = pilot.latent_auroc(0.99, 0.8, [0.2, 0.2, 0.4, 0.2])
    assert top["auroc_a"] == 0.9 and top["capped"] is True
    low = pilot.latent_auroc(0.45, 0.8, [0.2, 0.2, 0.4, 0.2])
    assert low["mu"] == 0.0 and low["auroc_a"] == 0.5
    assert pilot.latent_auroc(None, 0.8, [1.0]) is None


# --- tetrachoric -----------------------------------------------------------------------------


def test_bivariate_normal_against_the_closed_form():
    for rho in (-0.8, -0.3, 0.0, 0.5, 0.9):
        want = 0.25 + math.asin(rho) / (2 * math.pi)
        assert pilot.bvn_upper(0.0, 0.0, rho) == pytest.approx(want, abs=1e-7)
    assert pilot.bvn_upper(1.0, -0.5, 0.0) == pytest.approx(
        (1 - NormalDist().cdf(1.0)) * NormalDist().cdf(0.5), abs=1e-7)


def test_tetrachoric_by_hand():
    # 8 rows, both right 3, one only 1, other only 1, both wrong 3: margins 1/2, so
    # P(both right) = 1/4 + asin(rho) / 2 pi = 3/8 gives rho = sin(pi / 4)
    a = [True] * 3 + [True] + [False] + [False] * 3
    b = [True] * 3 + [False] + [True] + [False] * 3
    out = pilot.tetrachoric(a, b)
    assert out["value"] == pytest.approx(math.sin(math.pi / 4), abs=5e-5)    # to 4 decimals
    assert out["cells"] == {"both_right": 3, "first_only": 1, "second_only": 1, "both_wrong": 3}
    # independence: P(both right) = product of the margins
    a = [True, True, False, False] * 3
    b = [True, False, True, False] * 3
    assert pilot.tetrachoric(a, b)["value"] == pytest.approx(0.0, abs=1e-6)


def test_tetrachoric_degenerate_cases():
    assert pilot.tetrachoric([True, True], [True, False])["value"] is None   # a margin of 1
    assert pilot.tetrachoric([False, False], [True, False])["value"] is None
    agree = pilot.tetrachoric([True, False, True], [True, False, False])
    assert agree["value"] == 1.0 and agree["boundary"] is True               # an empty cell


def test_fixture_tetrachoric(d):
    rows = d["tetrachoric"]
    # Laya right on 1, 2, 5 (row 3 missing counts wrong); verbalized on 0, 1, 3, 4: no row
    # both wrong, P(both right) at its lower bound
    lv = pair(rows, LAYA, VERB)
    assert lv["cells"] == {"both_right": 1, "first_only": 2, "second_only": 3, "both_wrong": 0}
    assert lv["value"] == -1.0 and lv["boundary"] is True
    ll = pair(rows, LAYA, LP)
    assert ll["value"] == 1.0 and ll["boundary"] is True
    ls = pair(rows, LAYA, SC)
    assert ls["boundary"] is False and -1 < ls["value"] < 1
    h, k = NormalDist().inv_cdf(0.5), NormalDist().inv_cdf(1 - 4 / 6)
    assert pilot.bvn_upper(h, k, ls["value"]) == pytest.approx(2 / 6, abs=1e-4)


# --- also reported ---------------------------------------------------------------------------


def test_failed_samples_option_mass_temperatures_and_throughput(d):
    s = d["self_consistency_samples"]
    assert (s["samples"], s["failed"], s["rows_with_a_failed_sample"]) == (30, 6, 2)
    m = d["option_mass"]
    # 0.80 0.85 0.90 0.95 0.97 0.99, type 7 quantiles
    assert m["n"] == 6 and m["min"] == 0.8 and m["max"] == 0.99
    assert m["q1"] == pytest.approx(0.8625) and m["median"] == pytest.approx(0.925)
    assert m["q3"] == pytest.approx(0.965)
    t = d["laya_softmax_temperature"]
    assert t["clamped"] == [{"entry": "choice:11+", "shipped": 0.1006, "applied": 0.5}]
    assert t["options_in_question"] == 3
    runs = d["runs"]
    assert runs[VERB]["throughput"]["rows_per_minute"] == pytest.approx(30.0)
    assert runs[VERB]["throughput"]["input_tokens_per_call"] == pytest.approx(700)
    assert runs[VERB]["throughput"]["output_tokens_per_call"] == pytest.approx(30)
    assert runs[SC]["throughput"]["calls"] == 30
    assert runs[SC]["throughput"]["output_tokens_per_call"] == pytest.approx(20)
    assert runs[SC]["throughput"]["rows_per_minute"] == pytest.approx(6.0)
    assert runs[LAYA]["throughput"]["rows_timed"] == 5
    assert runs[LAYA]["throughput"]["rows_per_minute"] == pytest.approx(120.0)
    assert runs[LP]["throughput"]["input_tokens_per_call"] is None           # not recorded


# --- the proposed constants ------------------------------------------------------------------


def test_proposed_constants_follow_the_rules(d):
    c = d["proposed_constants"]
    # 4/6 and 4/6 and 5/6 to 0.01, distinct, plus the Wilson upper bound of 5/6 (0.9700)
    assert c["ACCURACIES"]["value"] == [0.67, 0.83, 0.97]
    assert c["TIE_SHARES_A"]["value"] == [0.2, 0.2, 0.4, 0.2]
    assert c["TIE_SHARES_B"]["value"] == [0.4, 0.2, 0.4]
    assert c["CONF_VALUES"]["value"] == [0.6, 0.8, 0.9, 0.95]
    assert c["CONF_WEIGHTS"]["value"] == [0.2, 0.2, 0.4, 0.2]
    # verbalized AUROC 1.0 is beyond any tied binormal: the latent one is capped at 0.90
    assert c["AUROC_A"]["value"] == 0.9 and c["AUROC_B"]["value"] == 0.95
    rhos = c["RHOS"]["value"]
    assert rhos == sorted(set(rhos)) and all(round(r * 20) == r * 20 for r in rhos)
    # the smaller H1 point estimate is verbalized-log-probability (Spearman 0): its lower
    # bound maps to 0
    assert rhos[0] == 0.0


def test_accuracies_are_capped_below_one(tmp_path):
    right = [("a", 0.9), ("b", 0.9), ("c", 0.9), ("a", 0.9), ("b", 0.9), ("c", 0.9)]
    runs = _synthetic(tmp_path, verbalized=right, sc=[(x, 1.0) for x, _ in right],
                      logprob=[(x, 0.9 + i / 100) for i, (x, _) in enumerate(right)])
    d = pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)
    acc = d["proposed_constants"]["ACCURACIES"]
    assert acc["value"] == [0.99] and "0.99" in acc["note"]
    assert d["runs"][VERB]["auroc"]["value"] is None                      # nothing to rank
    assert d["proposed_constants"]["AUROC_A"]["value"] is None
    assert d["tetrachoric"][0]["value"] is None                           # a margin of 1


def test_all_errors(tmp_path):
    wrong = [("b", 0.9), ("c", 0.8), ("a", 0.7), ("b", 0.9), ("c", 0.6), ("a", 0.5)]
    runs = _synthetic(tmp_path, verbalized=wrong, sc=wrong, logprob=wrong)
    d = pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)
    assert d["runs"][VERB]["accuracy"]["right"] == 0
    for r in d["rank_agreement"]:
        assert r["both_right"] == 0 and r["spearman"] is None and r["rho"] is None
        assert r["both_wrong"] == 6
    assert d["proposed_constants"]["RHOS"]["value"] == []


def test_all_ties(tmp_path):
    tied = [("a", 0.9), ("b", 0.9), ("a", 0.9), ("a", 0.9), ("b", 0.9), ("a", 0.9)]
    runs = _synthetic(tmp_path, verbalized=tied, sc=[(x, 1.0) for x, _ in tied])
    d = pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)
    assert d["runs"][VERB]["tie_shares"]["levels"] == [[0.9, 6, 1.0]]
    assert d["runs"][VERB]["auroc"]["value"] == 0.5
    assert d["proposed_constants"]["TIE_SHARES_A"]["value"] == [1.0]
    assert d["verbalized_distribution"]["weights"] == [1.0]
    assert pair(d["rank_agreement"], VERB, SC)["spearman"] is None


def test_missing_confidence_everywhere(tmp_path):
    none = [("a", None)] * 6
    runs = _synthetic(tmp_path, verbalized=none)
    d = pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)
    v = d["runs"][VERB]
    assert v["no_confidence"] == 6 and v["accuracy"]["right"] == 0
    assert v["no_confidence_decision_right"] == 2
    assert v["tie_shares"]["n"] == 0 and v["auroc"]["value"] is None
    assert d["verbalized_distribution"]["values"] == []
    assert d["proposed_constants"]["CONF_VALUES"]["value"] is None


# --- files, headers, --check -----------------------------------------------------------------


def test_a_missing_checkpoint_fails_clearly(tmp_path, capsys):
    runs = tmp_path / "runs"
    shutil.copytree(FIXTURE, runs)
    (runs / "llm-qwen3-8b-sc5.ckpt.jsonl").unlink()
    code = pilot.main(["--runs", str(runs), "--labels", str(runs / "labels.jsonl"),
                       "--out-md", str(tmp_path / "x.md"), "--out-json", str(tmp_path / "x.json")])
    assert code == 2
    err = capsys.readouterr().err
    assert "llm-qwen3-8b-sc5.ckpt.jsonl" in err and "missing" in err
    assert not (tmp_path / "x.md").exists()


def test_a_checkpoint_of_other_labels_is_refused(tmp_path):
    runs = tmp_path / "runs"
    shutil.copytree(FIXTURE, runs)
    labels = runs / "labels.jsonl"
    labels.write_text(labels.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="sha256"):
        pilot.compute(runs, labels, n_sim=2000, n_boot=50)


def test_a_swapped_checkpoint_is_refused(tmp_path):
    runs = tmp_path / "runs"
    shutil.copytree(FIXTURE, runs)
    shutil.copy(runs / "llm-qwen3-8b.ckpt.jsonl", runs / "llm-qwen3-8b-sc5.ckpt.jsonl")
    with pytest.raises(SystemExit, match="self-consistency"):
        pilot.compute(runs, runs / "labels.jsonl", n_sim=2000, n_boot=50)


def test_check_mode_and_determinism(tmp_path, monkeypatch):
    monkeypatch.setattr(pilot, "N_SIM", 2000)
    monkeypatch.setattr(pilot, "N_BOOT", 50)
    md, js = tmp_path / "e.md", tmp_path / "e.json"
    args = ["--runs", str(FIXTURE), "--labels", str(FIXTURE / "labels.jsonl"),
            "--out-md", str(md), "--out-json", str(js)]
    assert pilot.main([*args, "--check"]) == 1                 # nothing written yet
    assert pilot.main(args) == 0
    assert pilot.main([*args, "--check"]) == 0
    md.write_text(md.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert pilot.main([*args, "--check"]) == 1
    text = pilot.markdown(json.loads(js.read_text(encoding="utf-8")))
    assert "## Proposed PILOT constants" in text and "TIE_SHARES_B = [0.4, 0.2, 0.4]" in text
    assert "train" in text and "not a result about any judge" in text


# --- helpers ---------------------------------------------------------------------------------


LABELS = ["a", "b", "c", "a", "b", "c"]


def _synthetic(tmp_path: Path, verbalized=None, sc=None, logprob=None, laya=None) -> Path:
    """Four checkpoints over the fixture's six labels from (decision, confidence) lists; a
    None confidence is a no-confidence row (no answer when the decision is blank). The
    self-consistency votes are the confidence times 5, the rest failed samples."""
    runs = tmp_path / "runs"
    runs.mkdir()
    labels = runs / "labels.jsonl"
    shutil.copy(FIXTURE / "labels.jsonl", labels)
    sha = hashlib.sha256(labels.read_bytes()).hexdigest()
    base = [(x, 0.8) for x in LABELS]
    judges = {VERB: {"name": "llm:q"}, SC: {"name": "llm:q:sc5", "samples": 5},
              LP: {"name": "logprob:q"}, LAYA: {"name": "laya:laya"}}
    for slug, spec_rows in ((VERB, verbalized), (SC, sc), (LP, logprob), (LAYA, laya)):
        lines = [{"idx": -1, "run": {"judge": judges[slug],
                                     "dataset": {"sha256": sha, "rows": 6}}}]
        for i, (dec, conf) in enumerate(spec_rows or base):
            status = "parsed" if conf is not None else ("no_confidence" if dec else "no_answer")
            raw: dict = {"option_mass": 0.9}
            if slug == SC:
                k = round((conf or 0) * 5)
                raw = {"samples": [{"usage": {"input_tokens": 1, "output_tokens": 1}}] * 5,
                       "votes": {dec: k} if k else {}}
            lines.append({"idx": i, "judgments": [{
                "question": "intent", "decision": dec, "confidence": conf, "latency_s": 1.0,
                "cost_usd": 0.0, "raw": raw, "parse_status": status}]})
        (runs / f"{slug}.ckpt.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return runs
