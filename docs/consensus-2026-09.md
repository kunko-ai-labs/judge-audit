# Consensus audit — September 2026

Does agreement between AI judges tell you anything about whether they are right? Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, so the panel below costs nothing new — it is the committed checkpoints read side by side. Recompute: `python scripts/consensus_report.py`.

**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode groups agreeing "nearly unanimously, mostly on incorrect answers" ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same assumption — agreement as evidence — failing after agents communicate ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either paper (no humans, different task); it measures the assumption they attack on a jury of heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.

## Business emails, clean (n=200)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 200 | 94.1% | 153 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.971 / — | — |
| clean | 200 | 94.1% | 153 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.971 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 100.0% | 0.029 | 100.0% |
| jev (declared) | 100.0% | 0.004 | 100.0% |
| claude-sonnet-4.5 (declared) | 100.0% | 0.029 | 100.0% |
| deberta-nli (declared) | 86.5% | 0.176 | 51.5% |
| deepseek-r1 (declared) | 100.0% | 0.052 | 100.0% |
| gemini-3-flash (declared) | 100.0% | 0.005 | 100.0% |
| gemma4 (declared) | 100.0% | 0.026 | 100.0% |
| llama-3.3-70b (declared) | 100.0% | 0.091 | 100.0% |
| llama32 (declared) | 90.0% | 0.034 | 5.5% |

## Emails under attack (n=200)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 200 | 77.2% | 83 (0) | 11 | 0 | 90.0% / 95.2% | 97.0% | 0.89 / 0.681 | 0.899 |
| homoglyph_zerowidth | 10 | 82.9% | 4 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.912 / — | — |
| ambiguous | 30 | 77.4% | 10 (0) | 1 | 0 | 93.3% / 96.5% | 96.7% | 0.893 / 0.75 | 0.832 |
| homoglyph_cyrillic | 14 | 86.2% | 8 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.929 / — | — |
| pii | 20 | 92.5% | 14 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.963 / — | — |
| clean | 60 | 91.7% | 40 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.958 / — | — |
| prompt_injection | 40 | 54.3% | 2 (0) | 6 | 0 | 65.0% / 76.5% | 87.5% | 0.74 / 0.672 | 0.908 |
| social_engineering | 20 | 50.0% | 0 (0) | 4 | 0 | 80.0% / 100.0% | 100.0% | 0.703 / — | — |
| homoglyph_fullwidth | 6 | 92.3% | 5 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.958 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 90.0% | 0.073 | 62.4% |
| jev (declared) | 95.5% | 0.039 | 73.0% |
| claude-sonnet-4.5 (declared) | 96.5% | 0.016 | 2.0% |
| deberta-nli (declared) | 59.5% | 0.125 | 8.0% |
| deepseek-r1 (declared) | 80.5% | 0.127 | 0.0% |
| gemini-3-flash (declared) | 97.0% | 0.015 | 11.5% |
| gemma4 (declared) | 81.0% | 0.153 | 2.0% |
| llama-3.3-70b (declared) | 90.5% | 0.015 | 0.0% |
| llama32 (declared) | 72.5% | 0.154 | 0.0% |

## Task router, bare option labels (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 120 | 61.1% | 17 (0) | 28 | 1 | 48.3% / 63.0% | 66.7% | 0.85 / 0.688 | 0.927 |
| easy | 40 | 85.6% | 17 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.928 / — | — |
| hard | 40 | 50.9% | 0 (0) | 7 | 0 | 15.0% / 18.2% | 100.0% | 0.688 / 0.69 | 0.922 |
| adversarial | 40 | 46.6% | 0 (0) | 21 | 1 | 30.0% / 63.2% | 100.0% | 0.673 / 0.679 | 0.944 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 48.3% | 0.174 | 18.5% |
| jev (declared) | 66.7% | 0.318 | 2.5% |
| claude-sonnet-4.5 (declared) | 65.8% | 0.235 | 0.0% |
| deberta-nli (declared) | 47.5% | 0.403 | 0.0% |
| deepseek-r1 (declared) | 55.8% | 0.373 | 0.0% |
| gemini-3-flash (declared) | 66.7% | 0.315 | 2.5% |
| gemma4 (declared) | 59.2% | 0.345 | 0.0% |
| llama-3.3-70b (declared) | 65.0% | 0.233 | 0.0% |
| llama32 (declared) | 65.8% | 0.396 | 2.5% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 0.0% (jev + claude-sonnet-4.5 + llama32) to 92.5% (deberta-nli + gemma4 + llama-3.3-70b); the most consensual wrong jury is unanimous and wrong on 37 / 40 (jev + gemini-3-flash + llama32).

## Task router, described options (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote, ties to the alphabetically first option.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 120 | 70.4% | 18 (0) | 13 | 1 | 85.8% / 96.3% | 98.3% | 0.86 / 0.656 | 0.923 |
| easy | 40 | 86.2% | 18 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.931 / — | — |
| hard | 40 | 73.7% | 0 (0) | 0 | 0 | 100.0% / 100.0% | 100.0% | 0.866 / — | — |
| adversarial | 40 | 51.2% | 0 (0) | 13 | 1 | 57.5% / 85.2% | 100.0% | 0.727 / 0.656 | 0.923 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 85.8% | 0.110 | 83.2% |
| jev (declared) | 97.5% | 0.053 | 94.2% |
| claude-sonnet-4.5 (declared) | 95.0% | 0.032 | 3.3% |
| deberta-nli (declared) | 49.2% | 0.195 | 0.0% |
| deepseek-r1 (declared) | 79.2% | 0.148 | 0.0% |
| gemini-3-flash (declared) | 98.3% | 0.012 | 85.0% |
| gemma4 (declared) | 77.5% | 0.180 | 0.0% |
| llama-3.3-70b (declared) | 86.7% | 0.043 | 0.8% |
| llama32 (declared) | 59.2% | 0.429 | 2.5% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 92.5% (jev + claude-sonnet-4.5 + llama32) to 100.0% (jev + claude-sonnet-4.5 + deberta-nli); no three-judge jury is unanimous and wrong on any hard task.

## How to read it

- **pairwise agreement**: mean over judge pairs of the share of cases where both chose the same option.
- **unanimous (wrong)**: cases where every judge who answered chose the same option (at least two answered), and how many of those were wrong.
- **ties**: an even split among those who answered — no decision. *majority accuracy (all)* counts a tie as not correct (the jury could not act); *(decided)* is accuracy over the rows with a majority. Ties are excluded from the share statistics.
- **abstentions**: blank (unparseable) answers across the panel; an abstention is not a vote.
- **vote share right / wrong**: mean share of the winning option when the majority was right vs. wrong. If the two numbers are close, agreement carries no information about correctness.
- **conf of the wrong majority**: mean declared confidence of the judges who voted with a wrong majority.
- **vote share as confidence**: ECE and zero-error coverage computed with the share as the confidence of the majority decision — the number an agent jury would act on.

## Caveats

- Synthetic, seeded datasets; ground truth for routing is by construction. n is small; subset rows are indicative.
- Ties are no decision (see above). An earlier version broke ties alphabetically, which on the router always favoured `route_easy`; changed and disclosed in `jury-consensus-plan.md`.
- Judges differ in cost, size and confidence method; the panel is heterogeneous on purpose (same-model juries are the documented failure mode — Smit et al., ICML 2024).
- Round 1 only: nobody saw anybody else's vote. Round 2 (deliberation) is pre-registered in `docs/jury-consensus-plan.md` and reported in `docs/jury-consensus.md` once run.
