# Consensus audit — September 2026

Does agreement between AI judges tell you anything about whether they are right? Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, so the panel below costs nothing new — it is the committed checkpoints read side by side. Recompute: `python scripts/consensus_report.py`.

**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode groups agreeing "nearly unanimously, mostly on incorrect answers" ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same assumption — agreement as evidence — failing after agents communicate ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either paper (no humans, different task); it measures the assumption they attack on a jury of heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.

## Business emails, clean (n=200)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 200 | 94.1% | 153 (0) | 100.0% | 100.0% | 0.971 / — | — |
| clean | 200 | 94.1% | 153 (0) | 100.0% | 100.0% | 0.971 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 100.0% | 0.029 | 100.0% |
| jev (declared) | 100.0% | 0.004 | 100.0% |
| claude-sonnet-4.5 (declared) | 100.0% | 0.029 | 100.0% |
| deberta-nli (declared) | 86.5% | 0.176 | 51.5% |
| deepseek-r1 (declared) | 100.0% | 0.049 | 100.0% |
| gemini-3-flash (declared) | 100.0% | 0.005 | 100.0% |
| gemma4 (declared) | 100.0% | 0.026 | 100.0% |
| llama-3.3-70b (declared) | 100.0% | 0.091 | 100.0% |
| llama32 (declared) | 90.0% | 0.034 | 5.5% |

## Emails under attack (n=200)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 200 | 76.2% | 84 (0) | 93.0% | 97.0% | 0.872 / 0.616 | 0.882 |
| homoglyph_zerowidth | 10 | 82.9% | 4 (0) | 100.0% | 100.0% | 0.912 / — | — |
| ambiguous | 30 | 77.5% | 10 (0) | 93.3% | 96.7% | 0.893 / 0.688 | 0.852 |
| homoglyph_cyrillic | 14 | 86.2% | 8 (0) | 100.0% | 100.0% | 0.929 / — | — |
| pii | 20 | 92.5% | 14 (0) | 100.0% | 100.0% | 0.963 / — | — |
| clean | 60 | 91.7% | 40 (0) | 100.0% | 100.0% | 0.958 / — | — |
| prompt_injection | 40 | 51.6% | 3 (0) | 72.5% | 87.5% | 0.694 / 0.614 | 0.886 |
| social_engineering | 20 | 45.7% | 0 (0) | 95.0% | 100.0% | 0.658 / 0.5 | 0.907 |
| homoglyph_fullwidth | 6 | 92.3% | 5 (0) | 100.0% | 100.0% | 0.958 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 93.0% | 0.076 | 58.5% |
| jev (declared) | 95.5% | 0.039 | 73.0% |
| claude-sonnet-4.5 (declared) | 96.5% | 0.016 | 2.0% |
| deberta-nli (declared) | 59.5% | 0.125 | 8.0% |
| deepseek-r1 (declared) | 76.5% | 0.074 | 0.5% |
| gemini-3-flash (declared) | 97.0% | 0.015 | 11.5% |
| gemma4 (declared) | 81.0% | 0.153 | 2.0% |
| llama-3.3-70b (declared) | 90.5% | 0.015 | 0.0% |
| llama32 (declared) | 72.5% | 0.154 | 0.0% |

## Task router, bare option labels (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 120 | 58.2% | 15 (0) | 65.0% | 66.7% | 0.747 / 0.652 | 0.917 |
| easy | 40 | 82.8% | 15 (0) | 100.0% | 100.0% | 0.912 / — | — |
| hard | 40 | 50.2% | 0 (0) | 15.0% | 100.0% | 0.688 / 0.651 | 0.914 |
| adversarial | 40 | 41.8% | 0 (0) | 80.0% | 100.0% | 0.551 / 0.656 | 0.929 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 65.0% | 0.174 | 12.5% |
| jev (declared) | 66.7% | 0.318 | 2.5% |
| claude-sonnet-4.5 (declared) | 60.8% | 0.237 | 0.0% |
| deberta-nli (declared) | 47.5% | 0.403 | 0.0% |
| deepseek-r1 (declared) | 49.2% | 0.258 | 0.0% |
| gemini-3-flash (declared) | 66.7% | 0.315 | 2.5% |
| gemma4 (declared) | 59.2% | 0.345 | 0.0% |
| llama-3.3-70b (declared) | 65.0% | 0.233 | 0.0% |
| llama32 (declared) | 65.8% | 0.396 | 2.5% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 0.0% (jev + claude-sonnet-4.5 + llama32) to 92.5% (deberta-nli + gemma4 + llama-3.3-70b); the most consensual wrong jury is unanimous and wrong on 37 / 40 (jev + gemini-3-flash + llama32).

## Task router, described options (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|
| all | 120 | 66.3% | 14 (0) | 95.8% | 98.3% | 0.805 / 0.55 | 0.919 |
| easy | 40 | 83.8% | 14 (0) | 100.0% | 100.0% | 0.919 / — | — |
| hard | 40 | 72.0% | 0 (0) | 100.0% | 100.0% | 0.856 / — | — |
| adversarial | 40 | 43.2% | 0 (0) | 87.5% | 100.0% | 0.618 / 0.55 | 0.919 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 95.8% | 0.164 | 75.0% |
| jev (declared) | 97.5% | 0.053 | 94.2% |
| claude-sonnet-4.5 (declared) | 88.3% | 0.034 | 3.3% |
| deberta-nli (declared) | 49.2% | 0.195 | 0.0% |
| deepseek-r1 (declared) | 71.7% | 0.056 | 0.0% |
| gemini-3-flash (declared) | 98.3% | 0.012 | 85.0% |
| gemma4 (declared) | 77.5% | 0.180 | 0.0% |
| llama-3.3-70b (declared) | 86.7% | 0.043 | 0.8% |
| llama32 (declared) | 59.2% | 0.429 | 2.5% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 85.0% (jev + deepseek-r1 + llama32) to 100.0% (jev + claude-sonnet-4.5 + deberta-nli); no three-judge jury is unanimous and wrong on any hard task.

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
