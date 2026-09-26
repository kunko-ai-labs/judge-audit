"""scripts/v05_power.py: the exact binomial part by hand, the simulation helpers on
fixtures. The report itself is regenerated and diffed in CI."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("v05_power", ROOT / "scripts" / "v05_power.py")
power = importlib.util.module_from_spec(spec)
sys.modules["v05_power"] = power
spec.loader.exec_module(power)


def test_binomial_cdf_equals_the_sum_written_out():
    for m, p in ((10, 0.3), (40, 0.01), (7, 0.5)):
        for k in range(m + 1):
            brute = sum(math.comb(m, i) * p ** i * (1 - p) ** (m - i) for i in range(k + 1))
            assert power.binom_cdf(k, m, p) == pytest.approx(brute, abs=1e-12)


def test_zero_errors_need_the_textbook_row_counts():
    # (1 - r)^m < 0.05: m > ln(0.05) / ln(1 - r)
    assert power.rows_to_certify(0.01, 0) == 299       # 0.99^298 = 0.0501, 0.99^299 = 0.0496
    assert power.rows_to_certify(0.02, 0) == 149
    assert power.rows_to_certify(0.05, 0) == 59
    m = power.rows_to_certify(0.01, 1)
    assert power.binom_cdf(1, m, 0.01) < 0.05 <= power.binom_cdf(1, m - 1, 0.01)


def test_certifiable_errors_and_power():
    assert power.certifiable_errors(298, 0.01) == -1 and power.certifiable_errors(299, 0.01) == 0
    assert power.power_to_certify(299, 0.01, 0.0) == 1.0
    assert power.power_to_certify(100, 0.01, 0.0) == 0.0     # too few rows to certify at all
    m = power.rows_for_power(0.05, 0.01)
    assert all(power.power_to_certify(j, 0.05, 0.01) >= 0.8 for j in range(m, 2 * m + 1))
    assert power.power_to_certify(m - 1, 0.05, 0.01) < 0.8


def test_auroc_counts_ties_one_half():
    # right answers score 3, 2, 2; wrong ones 2, 1: pairs (3>2, 3>1, 2=2, 2>1, 2=2, 2>1)
    assert power.auroc([3, 2, 2, 2, 1], [True, True, True, False, False]) == pytest.approx(5 / 6)


def test_levels_cut_the_sorted_rows_into_the_given_shares():
    out = power.levels([0.9, 0.1, 0.5, 0.7, 0.3, 0.2, 0.8, 0.6, 0.4, 1.0], [0.2, 0.3, 0.5])
    assert out == [2.0, 0.0, 1.0, 2.0, 1.0, 0.0, 2.0, 2.0, 1.0, 2.0]


def test_normal_pairs_have_the_asked_correlation():
    import random

    rng = random.Random(0)
    pairs = [power.normal_pair(rng, 0.7) for _ in range(20000)]
    xs, ys = zip(*pairs, strict=True)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in pairs) / len(pairs)
    vx = sum((x - mx) ** 2 for x in xs) / len(xs)
    vy = sum((y - my) ** 2 for y in ys) / len(ys)
    assert cov / math.sqrt(vx * vy) == pytest.approx(0.7, abs=0.02)
