# Consensus audit — September 2026

Does agreement between AI judges tell you anything about whether they are right? Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, so the panel below costs nothing new — it is the committed checkpoints read side by side. Recompute: `python scripts/consensus_report.py`.

**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode groups agreeing "nearly unanimously, mostly on incorrect answers" ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same assumption — agreement as evidence — failing after agents communicate ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either paper (no humans, different task); it measures the assumption they attack on a jury of heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.

## Business emails, clean (n=200)

Panel: 7 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 200 | 93.3% | 153 (0) | 100.0% | 100.0% | 0.966 / — | — |
| clean | 200 | 93.3% | 153 (0) | 100.0% | 100.0% | 0.966 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 100.0% | 0.034 | 100.0% |
| jev (declared) | 100.0% | 0.004 | 100.0% |
| claude-sonnet-4.5 (declared) | 100.0% | 0.029 | 100.0% |
| deberta-nli (declared) | 86.5% | 0.176 | 51.5% |
| deepseek-r1 (declared) | 100.0% | 0.049 | 100.0% |
| gemma4 (declared) | 100.0% | 0.026 | 100.0% |
| llama-3.3-70b (declared) | 100.0% | 0.091 | 100.0% |
| llama32 (declared) | 90.0% | 0.034 | 5.5% |

## Emails under attack (n=200)

Panel: 7 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 200 | 74.1% | 84 (0) | 89.0% | 96.5% | 0.873 / 0.584 | 0.848 |
| homoglyph_zerowidth | 10 | 80.5% | 4 (0) | 100.0% | 100.0% | 0.9 / — | — |
| ambiguous | 30 | 74.9% | 10 (0) | 93.3% | 93.3% | 0.878 / 0.714 | 0.847 |
| homoglyph_cyrillic | 14 | 84.4% | 8 (0) | 100.0% | 100.0% | 0.918 / — | — |
| pii | 20 | 91.4% | 14 (0) | 100.0% | 100.0% | 0.957 / — | — |
| clean | 60 | 90.5% | 40 (0) | 100.0% | 100.0% | 0.952 / — | — |
| prompt_injection | 40 | 48.8% | 3 (0) | 62.5% | 87.5% | 0.686 / 0.61 | 0.834 |
| social_engineering | 20 | 40.9% | 0 (0) | 75.0% | 100.0% | 0.657 / 0.457 | 0.905 |
| homoglyph_fullwidth | 6 | 91.3% | 5 (0) | 100.0% | 100.0% | 0.952 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 89.0% | 0.057 | 58.5% |
| jev (declared) | 95.5% | 0.039 | 73.0% |
| claude-sonnet-4.5 (declared) | 96.5% | 0.016 | 2.0% |
| deberta-nli (declared) | 59.5% | 0.125 | 8.0% |
| deepseek-r1 (declared) | 76.5% | 0.074 | 0.5% |
| gemma4 (declared) | 81.0% | 0.153 | 2.0% |
| llama-3.3-70b (declared) | 90.5% | 0.015 | 0.0% |
| llama32 (declared) | 72.5% | 0.154 | 0.0% |

## Task router, bare option labels (n=120)

Panel: 7 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 120 | 55.9% | 15 (0) | 61.7% | 66.7% | 0.745 / 0.637 | 0.92 |
| easy | 40 | 80.4% | 15 (0) | 100.0% | 100.0% | 0.9 / — | — |
| hard | 40 | 47.4% | 0 (0) | 32.5% | 100.0% | 0.637 / 0.646 | 0.9 |
| adversarial | 40 | 39.9% | 0 (0) | 52.5% | 100.0% | 0.517 / 0.624 | 0.949 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 61.7% | 0.192 | 12.5% |
| jev (declared) | 66.7% | 0.318 | 2.5% |
| claude-sonnet-4.5 (declared) | 60.8% | 0.237 | 0.0% |
| deberta-nli (declared) | 47.5% | 0.403 | 0.0% |
| deepseek-r1 (declared) | 49.2% | 0.258 | 0.0% |
| gemma4 (declared) | 59.2% | 0.345 | 0.0% |
| llama-3.3-70b (declared) | 65.0% | 0.233 | 0.0% |
| llama32 (declared) | 65.8% | 0.396 | 2.5% |

**Pick the jury, pick the headline.** Over all 35 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 0.0% (jev + claude-sonnet-4.5 + llama32) to 92.5% (deberta-nli + gemma4 + llama-3.3-70b); the most consensual wrong jury is unanimous and wrong on 34 / 40 (jev + claude-sonnet-4.5 + llama32).

## Task router, described options (n=120)

Panel: 7 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 120 | 63.2% | 14 (0) | 93.3% | 97.5% | 0.79 / 0.571 | 0.905 |
| easy | 40 | 81.4% | 14 (0) | 100.0% | 100.0% | 0.907 / — | — |
| hard | 40 | 68.2% | 0 (0) | 100.0% | 100.0% | 0.836 / — | — |
| adversarial | 40 | 40.0% | 0 (0) | 80.0% | 100.0% | 0.585 / 0.571 | 0.905 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 93.3% | 0.158 | 64.2% |
| jev (declared) | 97.5% | 0.053 | 94.2% |
| claude-sonnet-4.5 (declared) | 88.3% | 0.034 | 3.3% |
| deberta-nli (declared) | 49.2% | 0.195 | 0.0% |
| deepseek-r1 (declared) | 71.7% | 0.056 | 0.0% |
| gemma4 (declared) | 77.5% | 0.180 | 0.0% |
| llama-3.3-70b (declared) | 86.7% | 0.043 | 0.8% |
| llama32 (declared) | 59.2% | 0.429 | 2.5% |

**Pick the jury, pick the headline.** Over all 35 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 85.0% (jev + deepseek-r1 + llama32) to 100.0% (jev + claude-sonnet-4.5 + deberta-nli); no three-judge jury is unanimous and wrong on any hard task.

## How to read it

- **pairwise agreement**: mean over judge pairs of the share of cases where both chose the same option.
- **unanimous (wrong)**: cases where every judge chose the same option, and how many of those were wrong.
- **vote share right / wrong**: mean share of the winning option when the majority was right vs. wrong. If the two numbers are close, agreement carries no information about correctness.
- **conf of the wrong majority**: mean declared confidence of the judges who voted with a wrong majority.
- **vote share as confidence**: ECE and zero-error coverage computed with the share as the confidence of the majority decision — the number an agent jury would act on.

## Caveats

- Synthetic, seeded datasets; ground truth for routing is by construction. n is small; subset rows are indicative.
- Ties in a panel with an even number of judges go to the alphabetically first option.
- Judges differ in cost, size and confidence method; the panel is heterogeneous on purpose (same-model juries are the documented failure mode — Smit et al., ICML 2024).
- Round 1 only: nobody saw anybody else's vote. Round 2 (deliberation) is pre-registered in `docs/jury-consensus-plan.md` and reported in `docs/jury-consensus.md` once run.
