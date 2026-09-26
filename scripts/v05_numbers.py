"""Recompute every number that docs/v05-analysis.md derives itself. No API call.

The analysis quotes three kinds of numbers. External ones (a paper's result, a dataset's
size, a vendor's claim) are cited to their source and not recomputed here. Numbers read
from this repository's committed evidence (the Arena JSON, the checkpoints' token counts)
and numbers that follow from a formula (exact binomial bounds, the chance of observing no
error, an approximate AUROC standard error, a cost projection under a stated assumption)
are printed by this script, so a reader can check each one.

  python scripts/v05_numbers.py

Planning figures, not results: nothing here is a measurement of a judge on v0.5 data.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.judges.llm import PRICES  # noqa: E402
from judge_audit.metrics.calibration import clopper_pearson  # noqa: E402

HEADLINE = ("jev", "claude-sonnet-4.5", "gemini-3-flash")
Z_ALPHA, Z_POWER = 1.96, 0.8416  # two-sided 5 % test, 80 % power
AUROC = 0.75                     # an illustrative failure-prediction AUROC
BANKING77_TEST = 3080            # official test split (Casanueva et al. 2020)
ASSUMED_INPUT_TOKENS = 2000      # 77 labels with one-line definitions; a pilot replaces it
SC_K = 10                        # self-consistency samples per row


def errors_behind_headline() -> list[str]:
    arena = json.loads((ROOT / "docs/arena-2026-09.json").read_text(encoding="utf-8"))
    out = ["## Errors behind the v0.4 headline (emails under attack)", "",
           "| judge | n | accuracy | errors | conf right / wrong |", "|---|---|---|---|---|"]
    for slug in HEADLINE:
        d = arena[slug]["datasets"]["email-adversarial"]
        wrong = round(d["n"] * (1 - d["accuracy"]))
        out.append(f"| {slug} | {d['n']} | {d['accuracy']:.1%} | {wrong} | "
                   f"{d['mean_conf_correct']:.2f} / {d['mean_conf_wrong']:.2f} |")
    return out + [""]


def zero_error_fragility() -> list[str]:
    ps = (0.002, 0.005, 0.01, 0.03)
    out = ["## P(no observed error among the m most confident rows), true risk p there", "",
           "| m | " + " | ".join(f"p={p:.1%}" for p in ps) + " |", "|---|" + "---|" * len(ps)]
    for m in (100, 300, 1000):
        out.append(f"| {m} | " + " | ".join(f"{(1 - p) ** m:.3f}" for p in ps) + " |")
    return out + [""]


def exact_bounds() -> list[str]:
    out = ["## Exact (Clopper–Pearson) bounds", "",
           "Zero errors in k automated rows, two-sided 95 % upper bound:", "",
           "| k | upper bound |", "|---|---|"]
    for k in (100, 200, 300, 500, 1000):
        out.append(f"| {k} | {clopper_pearson(0, k)[1]:.2%} |")
    k_min = math.ceil(math.log(0.05) / math.log(0.99))
    out += ["", f"One-sided 95 % bound below 1 % with zero errors needs k >= {k_min} rows.", "",
            "k automated rows with e errors, one-sided 95 % upper bound on the risk:", "",
            "| k | e | observed | upper bound |", "|---|---|---|---|"]
    for k, e in ((300, 0), (500, 2), (1000, 5), (1000, 10), (2000, 20)):
        out.append(f"| {k} | {e} | {e / k:.2%} | {clopper_pearson(e, k, alpha=0.10)[1]:.2%} |")
    return out + [""]


def hanley_mcneil_se(a: float, n_err: int, n_ok: int) -> float:
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    return math.sqrt((a * (1 - a) + (n_err - 1) * (q1 - a * a) + (n_ok - 1) * (q2 - a * a))
                     / (n_err * n_ok))


def auroc_power() -> list[str]:
    z = Z_ALPHA + Z_POWER
    out = [f"## AUROC of confidence as an error predictor: approximate precision (AUROC {AUROC})",
           "", "Hanley–McNeil standard error; the smallest difference two judges must show to be "
           "told apart at 5 % / 80 % power, unpaired and paired (correlation 0.5 between the two "
           "judges' AUROC estimates on the same rows). An order of magnitude for planning; the "
           "pre-registration replaces it with a simulation on pilot data.", "",
           "| n | accuracy | errors | SE | detectable difference, unpaired | paired |",
           "|---|---|---|---|---|---|"]
    for n, acc in ((200, 0.955), (1000, 0.90), (1000, 0.80), (3080, 0.92), (3080, 0.80)):
        n_err = round(n * (1 - acc))
        se = hanley_mcneil_se(AUROC, n_err, n - n_err)
        out.append(f"| {n} | {acc:.1%} | {n_err} | {se:.3f} | {z * math.sqrt(2) * se:.3f} | "
                   f"{z * se:.3f} |")
    return out + [""]


def mean_tokens(ckpt: Path) -> tuple[float, float]:
    ins, outs = [], []
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["idx"] == -1:
            continue
        usage = row["judgments"][0]["raw"]["usage"]
        ins.append(usage["input_tokens"])
        outs.append(usage["output_tokens"])
    return sum(ins) / len(ins), sum(outs) / len(outs)


def cost_projection() -> list[str]:
    out = ["## Cost projection for BANKING77's test split", "",
           f"Measured: mean tokens per row on the 200 emails under attack (10 options). Assumed: "
           f"{ASSUMED_INPUT_TOKENS} input tokens per row with 77 options and definitions, the "
           f"measured output tokens, {BANKING77_TEST} rows, self-consistency with k={SC_K}.", "",
           "| judge | USD per M in / out | measured in / out per row | one run | "
           f"self-consistency k={SC_K} |", "|---|---|---|---|---|"]
    runs = {"claude-sonnet-4.5": None, "gemini-3-flash": "gemini-3-flash-preview"}
    for slug, price_key in runs.items():
        ckpt = ROOT / f"docs/runs/arena/{slug}/email-adversarial.ckpt.jsonl"
        header = json.loads(ckpt.read_text(encoding="utf-8").splitlines()[0])["run"]["judge"]
        p_in, p_out = header.get("prices_usd_per_mtok") or PRICES[price_key]
        t_in, t_out = mean_tokens(ckpt)
        one = BANKING77_TEST * (ASSUMED_INPUT_TOKENS * p_in + t_out * p_out) / 1e6
        out.append(f"| {slug} | {p_in:.2f} / {p_out:.2f} | {t_in:.0f} / {t_out:.0f} | "
                   f"${one:.2f} | ${one * SC_K:.2f} |")
    return out + [""]


def main() -> None:
    lines = ["# v0.5 analysis — recomputed planning numbers", ""]
    for part in (errors_behind_headline, zero_error_fragility, exact_bounds, auroc_power,
                 cost_projection):
        lines += part()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
