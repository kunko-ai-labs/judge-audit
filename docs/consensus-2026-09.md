# Consensus audit — September 2026

Does agreement between AI judges tell you anything about whether they are right? Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, so the panel below costs nothing new — it is the committed checkpoints read side by side. Recompute: `python scripts/consensus_report.py`.

**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode groups agreeing "nearly unanimously, mostly on incorrect answers" ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same assumption — agreement as evidence — failing after agents communicate ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either paper (no humans, different task); it measures the assumption they attack on a jury of heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.

## Business emails, clean (n=200)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote among those who answered; a tie is no decision.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 200 | 94.1% | 153 (0) | 0 | 0 | 100.0% [98.2, 100.0]† / 100.0% | 100.0% | 0.971 / — | — |
| clean | 200 | 94.1% | 153 (0) | 0 | 0 | 100.0% [98.2, 100.0]† / 100.0% | 100.0% | 0.971 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 100.0% [98.2, 100.0]† | 0.029 | 100.0% |
| jev (declared) | 100.0% | 0.004 | 100.0% |
| claude-sonnet-4.5 (declared) | 100.0% | 0.029 | 100.0% |
| deberta-nli (declared) | 86.5% | 0.176 | 51.5% |
| deepseek-r1 (declared) | 100.0% | 0.052 | 100.0% |
| gemini-3-flash (declared) | 100.0% | 0.005 | 100.0% |
| gemma4 (declared) | 100.0% | 0.026 | 100.0% |
| llama-3.3-70b (declared) | 100.0% | 0.091 | 100.0% |
| llama32 (declared) | 90.0% | 0.034 | 0.0% |

### Error correlation (n=200)

Phi between the two judges' error indicators, over the rows where both answered. "—": undefined because one judge has no error on those rows. `errors` is the judge's own count; the full pair table (agreement, joint error, conditional error rates, error-set Jaccard, n) is folded below.

| judge (errors) | jev | claude-sonnet-4.5 | deberta-nli | deepseek-r1 | gemini-3-flash | gemma4 | llama-3.3-70b | llama32 |
|---|---|---|---|---|---|---|---|---|
| jev (0) |  | — | — | — | — | — | — | — |
| claude-sonnet-4.5 (0) |  |  | — | — | — | — | — | — |
| deberta-nli (27) |  |  |  | — | — | — | — | -0.132 |
| deepseek-r1 (0) |  |  |  |  | — | — | — | — |
| gemini-3-flash (0) |  |  |  |  |  | — | — | — |
| gemma4 (0) |  |  |  |  |  |  | — | — |
| llama-3.3-70b (0) |  |  |  |  |  |  |  | — |
| llama32 (20) |  |  |  |  |  |  |  |  |

<details><summary>Every pair</summary>

| A | B | n | agreement | joint error | P(A wrong \| B wrong) | P(B wrong \| A wrong) | error-set Jaccard | phi |
|---|---|---|---|---|---|---|---|---|
| jev | claude-sonnet-4.5 | 200 | 100.0% | 0.0% | — | — | — | — |
| jev | deberta-nli | 200 | 86.5% | 0.0% | 0.0% | — | 0.000 | — |
| jev | deepseek-r1 | 200 | 100.0% | 0.0% | — | — | — | — |
| jev | gemini-3-flash | 200 | 100.0% | 0.0% | — | — | — | — |
| jev | gemma4 | 200 | 100.0% | 0.0% | — | — | — | — |
| jev | llama-3.3-70b | 200 | 100.0% | 0.0% | — | — | — | — |
| jev | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |
| claude-sonnet-4.5 | deberta-nli | 200 | 86.5% | 0.0% | 0.0% | — | 0.000 | — |
| claude-sonnet-4.5 | deepseek-r1 | 200 | 100.0% | 0.0% | — | — | — | — |
| claude-sonnet-4.5 | gemini-3-flash | 200 | 100.0% | 0.0% | — | — | — | — |
| claude-sonnet-4.5 | gemma4 | 200 | 100.0% | 0.0% | — | — | — | — |
| claude-sonnet-4.5 | llama-3.3-70b | 200 | 100.0% | 0.0% | — | — | — | — |
| claude-sonnet-4.5 | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |
| deberta-nli | deepseek-r1 | 200 | 86.5% | 0.0% | — | 0.0% | 0.000 | — |
| deberta-nli | gemini-3-flash | 200 | 86.5% | 0.0% | — | 0.0% | 0.000 | — |
| deberta-nli | gemma4 | 200 | 86.5% | 0.0% | — | 0.0% | 0.000 | — |
| deberta-nli | llama-3.3-70b | 200 | 86.5% | 0.0% | — | 0.0% | 0.000 | — |
| deberta-nli | llama32 | 200 | 76.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.132 |
| deepseek-r1 | gemini-3-flash | 200 | 100.0% | 0.0% | — | — | — | — |
| deepseek-r1 | gemma4 | 200 | 100.0% | 0.0% | — | — | — | — |
| deepseek-r1 | llama-3.3-70b | 200 | 100.0% | 0.0% | — | — | — | — |
| deepseek-r1 | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |
| gemini-3-flash | gemma4 | 200 | 100.0% | 0.0% | — | — | — | — |
| gemini-3-flash | llama-3.3-70b | 200 | 100.0% | 0.0% | — | — | — | — |
| gemini-3-flash | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |
| gemma4 | llama-3.3-70b | 200 | 100.0% | 0.0% | — | — | — | — |
| gemma4 | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |
| llama-3.3-70b | llama32 | 200 | 90.0% | 0.0% | 0.0% | — | 0.000 | — |

</details>

**Reading.** Only one pair has a defined phi: deberta-nli + llama32 at -0.132 (0 shared wrong cases of 200).

## Emails under attack (n=200)

Panel: 11 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, finetuned-deberta, finetuned-deberta-run2, finetuned-deberta-run2-ts, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote among those who answered; a tie is no decision.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 200 | 80.7% | 80 (0) | 1 | 0 | 97.5% [95.0, 99.5] / 98.0% | 99.0% | 0.891 / 0.568 | 0.888 |
| homoglyph_zerowidth | 10 | 85.6% | 3 (0) | 0 | 0 | 100.0% [69.2, 100.0]† / 100.0% | 100.0% | 0.927 / — | — |
| ambiguous | 30 | 78.1% | 8 (0) | 0 | 0 | 96.7% [89.7, 100.0] / 96.7% | 96.7% | 0.887 / 0.545 | 0.832 |
| homoglyph_cyrillic | 14 | 88.8% | 8 (0) | 0 | 0 | 100.0% [76.8, 100.0]† / 100.0% | 100.0% | 0.942 / — | — |
| pii | 20 | 94.5% | 14 (0) | 0 | 0 | 100.0% [83.2, 100.0]† / 100.0% | 100.0% | 0.973 / — | — |
| clean | 60 | 93.9% | 40 (0) | 0 | 0 | 100.0% [94.0, 100.0]† / 100.0% | 100.0% | 0.97 / — | — |
| prompt_injection | 40 | 60.0% | 2 (0) | 1 | 0 | 90.0% [80.0, 97.5] / 92.3% | 100.0% | 0.753 / 0.576 | 0.906 |
| social_engineering | 20 | 59.8% | 0 (0) | 0 | 0 | 100.0% [83.2, 100.0]† / 100.0% | 100.0% | 0.755 / — | — |
| homoglyph_fullwidth | 6 | 94.2% | 5 (0) | 0 | 0 | 100.0% [54.1, 100.0]† / 100.0% | 100.0% | 0.97 / — | — |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 97.5% [95.0, 99.5] | 0.095 | 89.5% |
| jev (declared) | 95.5% | 0.039 | 73.0% |
| claude-sonnet-4.5 (declared) | 96.5% | 0.016 | 0.0% |
| deberta-nli (declared) | 59.5% | 0.125 | 8.0% |
| deepseek-r1 (declared) | 80.5% | 0.127 | 0.0% |
| finetuned-deberta (declared) | 97.0% | 0.496 | 97.0% |
| finetuned-deberta-run2 (declared) | 99.0% | 0.048 | 96.0% |
| finetuned-deberta-run2-ts (declared) | 99.0% | 0.017 | 96.0% |
| gemini-3-flash (declared) | 97.0% | 0.015 | 0.0% |
| gemma4 (declared) | 81.0% | 0.153 | 0.0% |
| llama-3.3-70b (declared) | 90.5% | 0.015 | 0.0% |
| llama32 (declared) | 72.5% | 0.154 | 0.0% |

### Error correlation (n=200)

Phi between the two judges' error indicators, over the rows where both answered. "—": undefined because one judge has no error on those rows. `errors` is the judge's own count; the full pair table (agreement, joint error, conditional error rates, error-set Jaccard, n) is folded below.

| judge (errors) | jev | claude-sonnet-4.5 | deberta-nli | deepseek-r1 | finetuned-deberta | finetuned-deberta-run2 | finetuned-deberta-run2-ts | gemini-3-flash | gemma4 | llama-3.3-70b | llama32 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| jev (9) |  | 0.484 | -0.032 | 0.380 | -0.038 | -0.022 | -0.022 | 0.245 | 0.387 | 0.423 | 0.028 |
| claude-sonnet-4.5 (7) |  |  | 0.009 | 0.318 | -0.034 | -0.019 | -0.019 | 0.764 | 0.185 | 0.402 | 0.005 |
| deberta-nli (81) |  |  |  | 0.160 | -0.085 | -0.083 | -0.083 | 0.094 | 0.172 | 0.115 | 0.222 |
| deepseek-r1 (39) |  |  |  |  | -0.087 | -0.050 | -0.050 | 0.357 | 0.630 | 0.400 | 0.206 |
| finetuned-deberta (6) |  |  |  |  |  | 0.572 | 0.572 | -0.031 | -0.085 | -0.057 | 0.089 |
| finetuned-deberta-run2 (2) |  |  |  |  |  |  | 1.000 | -0.018 | -0.049 | -0.033 | -0.062 |
| finetuned-deberta-run2-ts (2) |  |  |  |  |  |  |  | -0.018 | -0.049 | -0.033 | -0.062 |
| gemini-3-flash (6) |  |  |  |  |  |  |  |  | 0.214 | 0.443 | 0.089 |
| gemma4 (38) |  |  |  |  |  |  |  |  |  | 0.495 | 0.244 |
| llama-3.3-70b (19) |  |  |  |  |  |  |  |  |  |  | 0.144 |
| llama32 (55) |  |  |  |  |  |  |  |  |  |  |  |

<details><summary>Every pair</summary>

| A | B | n | agreement | joint error | P(A wrong \| B wrong) | P(B wrong \| A wrong) | error-set Jaccard | phi |
|---|---|---|---|---|---|---|---|---|
| jev | claude-sonnet-4.5 | 200 | 96.0% | 2.0% | 57.1% | 44.4% | 0.333 | 0.484 |
| jev | deberta-nli | 200 | 58.0% | 1.5% | 3.7% | 33.3% | 0.035 | -0.032 |
| jev | deepseek-r1 | 200 | 84.0% | 4.0% | 20.5% | 88.9% | 0.200 | 0.380 |
| jev | finetuned-deberta | 200 | 92.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.038 |
| jev | finetuned-deberta-run2 | 200 | 94.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.022 |
| jev | finetuned-deberta-run2-ts | 200 | 94.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.022 |
| jev | gemini-3-flash | 200 | 94.5% | 1.0% | 33.3% | 22.2% | 0.154 | 0.245 |
| jev | gemma4 | 200 | 84.5% | 4.0% | 21.1% | 88.9% | 0.205 | 0.387 |
| jev | llama-3.3-70b | 200 | 92.0% | 3.0% | 31.6% | 66.7% | 0.273 | 0.423 |
| jev | llama32 | 200 | 71.0% | 1.5% | 5.5% | 33.3% | 0.049 | 0.028 |
| claude-sonnet-4.5 | deberta-nli | 200 | 58.0% | 1.5% | 3.7% | 42.9% | 0.035 | 0.009 |
| claude-sonnet-4.5 | deepseek-r1 | 200 | 83.0% | 3.0% | 15.4% | 85.7% | 0.150 | 0.318 |
| claude-sonnet-4.5 | finetuned-deberta | 200 | 93.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.034 |
| claude-sonnet-4.5 | finetuned-deberta-run2 | 200 | 95.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.019 |
| claude-sonnet-4.5 | finetuned-deberta-run2-ts | 200 | 95.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.019 |
| claude-sonnet-4.5 | gemini-3-flash | 200 | 98.5% | 2.5% | 83.3% | 71.4% | 0.625 | 0.764 |
| claude-sonnet-4.5 | gemma4 | 200 | 81.5% | 2.0% | 10.5% | 57.1% | 0.098 | 0.185 |
| claude-sonnet-4.5 | llama-3.3-70b | 200 | 92.0% | 2.5% | 26.3% | 71.4% | 0.238 | 0.402 |
| claude-sonnet-4.5 | llama32 | 200 | 71.0% | 1.0% | 3.6% | 28.6% | 0.033 | 0.005 |
| deberta-nli | deepseek-r1 | 200 | 58.5% | 11.0% | 56.4% | 27.2% | 0.225 | 0.160 |
| deberta-nli | finetuned-deberta | 200 | 57.0% | 0.5% | 16.7% | 1.2% | 0.012 | -0.085 |
| deberta-nli | finetuned-deberta-run2 | 200 | 58.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.083 |
| deberta-nli | finetuned-deberta-run2-ts | 200 | 58.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.083 |
| deberta-nli | gemini-3-flash | 200 | 59.5% | 2.0% | 66.7% | 4.9% | 0.048 | 0.094 |
| deberta-nli | gemma4 | 200 | 59.0% | 11.0% | 57.9% | 27.2% | 0.227 | 0.172 |
| deberta-nli | llama-3.3-70b | 200 | 60.0% | 5.5% | 57.9% | 13.6% | 0.124 | 0.115 |
| deberta-nli | llama32 | 200 | 56.0% | 16.0% | 58.2% | 39.5% | 0.308 | 0.222 |
| deepseek-r1 | finetuned-deberta | 200 | 77.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.087 |
| deepseek-r1 | finetuned-deberta-run2 | 200 | 79.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.050 |
| deepseek-r1 | finetuned-deberta-run2-ts | 200 | 79.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.050 |
| deepseek-r1 | gemini-3-flash | 200 | 83.5% | 3.0% | 100.0% | 15.4% | 0.154 | 0.357 |
| deepseek-r1 | gemma4 | 200 | 88.5% | 13.5% | 71.0% | 69.2% | 0.540 | 0.630 |
| deepseek-r1 | llama-3.3-70b | 200 | 84.0% | 6.5% | 68.4% | 33.3% | 0.289 | 0.400 |
| deepseek-r1 | llama32 | 200 | 70.0% | 9.0% | 32.7% | 46.2% | 0.237 | 0.206 |
| finetuned-deberta | finetuned-deberta-run2 | 200 | 97.0% | 1.0% | 100.0% | 33.3% | 0.333 | 0.572 |
| finetuned-deberta | finetuned-deberta-run2-ts | 200 | 97.0% | 1.0% | 100.0% | 33.3% | 0.333 | 0.572 |
| finetuned-deberta | gemini-3-flash | 200 | 94.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.031 |
| finetuned-deberta | gemma4 | 200 | 78.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.085 |
| finetuned-deberta | llama-3.3-70b | 200 | 87.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.057 |
| finetuned-deberta | llama32 | 200 | 71.0% | 1.5% | 5.5% | 50.0% | 0.052 | 0.089 |
| finetuned-deberta-run2 | finetuned-deberta-run2-ts | 200 | 100.0% | 1.0% | 100.0% | 100.0% | 1.000 | 1.000 |
| finetuned-deberta-run2 | gemini-3-flash | 200 | 96.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.018 |
| finetuned-deberta-run2 | gemma4 | 200 | 80.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.049 |
| finetuned-deberta-run2 | llama-3.3-70b | 200 | 89.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.033 |
| finetuned-deberta-run2 | llama32 | 200 | 71.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.062 |
| finetuned-deberta-run2-ts | gemini-3-flash | 200 | 96.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.018 |
| finetuned-deberta-run2-ts | gemma4 | 200 | 80.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.049 |
| finetuned-deberta-run2-ts | llama-3.3-70b | 200 | 89.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.033 |
| finetuned-deberta-run2-ts | llama32 | 200 | 71.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.062 |
| gemini-3-flash | gemma4 | 200 | 82.0% | 2.0% | 10.5% | 66.7% | 0.100 | 0.214 |
| gemini-3-flash | llama-3.3-70b | 200 | 92.5% | 2.5% | 26.3% | 83.3% | 0.250 | 0.443 |
| gemini-3-flash | llama32 | 200 | 72.5% | 1.5% | 5.5% | 50.0% | 0.052 | 0.089 |
| gemma4 | llama-3.3-70b | 200 | 86.5% | 7.5% | 79.0% | 39.5% | 0.357 | 0.495 |
| gemma4 | llama32 | 200 | 72.0% | 9.5% | 34.5% | 50.0% | 0.257 | 0.244 |
| llama-3.3-70b | llama32 | 200 | 72.0% | 4.5% | 16.4% | 47.4% | 0.139 | 0.144 |

</details>

**Reading.** Of 55 pairs with a defined phi, the most correlated errors are finetuned-deberta-run2 + finetuned-deberta-run2-ts (phi 1.000, 2 shared wrong cases of 200) and the least correlated are deepseek-r1 + finetuned-deberta (phi -0.087, 0 shared wrong cases of 200).

## Task router, bare option labels (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote among those who answered; a tie is no decision.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 120 | 61.1% | 17 (0) | 28 | 1 | 48.3% [34.4, 61.6] / 63.0% | 66.7% | 0.85 / 0.688 | 0.927 |
| easy | 40 | 85.6% | 17 (0) | 0 | 0 | 100.0% [91.2, 100.0]† / 100.0% | 100.0% | 0.928 / — | — |
| hard | 40 | 50.9% | 0 (0) | 7 | 0 | 15.0% [0.0, 34.2] / 18.2% | 100.0% | 0.688 / 0.69 | 0.922 |
| adversarial | 40 | 46.6% | 0 (0) | 21 | 1 | 30.0% [12.8, 48.8] / 63.2% | 100.0% | 0.673 / 0.679 | 0.944 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 48.3% [34.4, 61.6] | 0.174 | 18.5% |
| jev (declared) | 66.7% | 0.318 | 0.0% |
| claude-sonnet-4.5 (declared) | 65.8% | 0.235 | 0.0% |
| deberta-nli (declared) | 47.5% | 0.403 | 0.0% |
| deepseek-r1 (declared) | 55.8% | 0.373 | 0.0% |
| gemini-3-flash (declared) | 66.7% | 0.315 | 0.0% |
| gemma4 (declared) | 59.2% | 0.345 | 0.0% |
| llama-3.3-70b (declared) | 65.0% | 0.233 | 0.0% |
| llama32 (declared) | 65.8% | 0.396 | 0.0% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 0.0% [0.0, 8.8]† (jev + claude-sonnet-4.5 + llama32) to 92.5% [76.9, 100.0] (deberta-nli + gemma4 + llama-3.3-70b); the most consensual wrong jury is unanimous and wrong on 37 / 40 (jev + gemini-3-flash + llama32).

### Error correlation (n=120)

Phi between the two judges' error indicators, over the rows where both answered. "—": undefined because one judge has no error on those rows. `errors` is the judge's own count; the full pair table (agreement, joint error, conditional error rates, error-set Jaccard, n) is folded below.

| judge (errors) | jev | claude-sonnet-4.5 | deberta-nli | deepseek-r1 | gemini-3-flash | gemma4 | llama-3.3-70b | llama32 |
|---|---|---|---|---|---|---|---|---|
| jev (40) |  | 0.758 | -0.743 | 0.019 | 0.887 | -0.156 | -0.111 | 0.982 |
| claude-sonnet-4.5 (41) |  |  | -0.511 | 0.253 | 0.870 | 0.081 | 0.098 | 0.741 |
| deberta-nli (63) |  |  |  | 0.234 | -0.637 | 0.383 | 0.313 | -0.722 |
| deepseek-r1 (52) |  |  |  |  | 0.126 | 0.726 | 0.538 | 0.039 |
| gemini-3-flash (40) |  |  |  |  |  | -0.048 | 0.000 | 0.870 |
| gemma4 (49) |  |  |  |  |  |  | 0.492 | -0.134 |
| llama-3.3-70b (42) |  |  |  |  |  |  |  | -0.087 |
| llama32 (41) |  |  |  |  |  |  |  |  |

<details><summary>Every pair</summary>

| A | B | n | agreement | joint error | P(A wrong \| B wrong) | P(B wrong \| A wrong) | error-set Jaccard | phi |
|---|---|---|---|---|---|---|---|---|
| jev | claude-sonnet-4.5 | 120 | 89.2% | 28.3% | 82.9% | 85.0% | 0.723 | 0.758 |
| jev | deberta-nli | 120 | 14.2% | 0.0% | 0.0% | 0.0% | 0.000 | -0.743 |
| jev | deepseek-r1 | 119 | 52.9% | 15.1% | 34.6% | 45.0% | 0.243 | 0.019 |
| jev | gemini-3-flash | 120 | 95.0% | 30.8% | 92.5% | 92.5% | 0.861 | 0.887 |
| jev | gemma4 | 120 | 45.8% | 10.0% | 24.5% | 30.0% | 0.156 | -0.156 |
| jev | llama-3.3-70b | 120 | 50.0% | 9.2% | 26.2% | 27.5% | 0.155 | -0.111 |
| jev | llama32 | 120 | 99.2% | 33.3% | 97.6% | 100.0% | 0.976 | 0.982 |
| claude-sonnet-4.5 | deberta-nli | 120 | 25.0% | 5.8% | 11.1% | 17.1% | 0.072 | -0.511 |
| claude-sonnet-4.5 | deepseek-r1 | 119 | 63.9% | 21.0% | 48.1% | 61.0% | 0.368 | 0.253 |
| claude-sonnet-4.5 | gemini-3-flash | 120 | 94.2% | 30.8% | 92.5% | 90.2% | 0.841 | 0.870 |
| claude-sonnet-4.5 | gemma4 | 120 | 56.7% | 15.8% | 38.8% | 46.3% | 0.268 | 0.081 |
| claude-sonnet-4.5 | llama-3.3-70b | 120 | 59.2% | 14.2% | 40.5% | 41.5% | 0.258 | 0.098 |
| claude-sonnet-4.5 | llama32 | 120 | 88.3% | 28.3% | 82.9% | 82.9% | 0.708 | 0.741 |
| deberta-nli | deepseek-r1 | 119 | 61.3% | 28.6% | 65.4% | 54.8% | 0.425 | 0.234 |
| deberta-nli | gemini-3-flash | 120 | 19.2% | 2.5% | 7.5% | 4.8% | 0.030 | -0.637 |
| deberta-nli | gemma4 | 120 | 68.3% | 30.8% | 75.5% | 58.7% | 0.493 | 0.383 |
| deberta-nli | llama-3.3-70b | 120 | 64.2% | 25.8% | 73.8% | 49.2% | 0.419 | 0.313 |
| deberta-nli | llama32 | 120 | 15.0% | 0.8% | 2.4% | 1.6% | 0.010 | -0.722 |
| deepseek-r1 | gemini-3-flash | 119 | 58.0% | 17.6% | 52.5% | 40.4% | 0.296 | 0.126 |
| deepseek-r1 | gemma4 | 119 | 86.6% | 35.3% | 87.5% | 80.8% | 0.724 | 0.726 |
| deepseek-r1 | llama-3.3-70b | 119 | 77.3% | 27.7% | 80.5% | 63.5% | 0.550 | 0.538 |
| deepseek-r1 | llama32 | 119 | 53.8% | 16.0% | 46.3% | 36.5% | 0.257 | 0.039 |
| gemini-3-flash | gemma4 | 120 | 50.8% | 12.5% | 30.6% | 37.5% | 0.203 | -0.048 |
| gemini-3-flash | llama-3.3-70b | 120 | 55.0% | 11.7% | 33.3% | 35.0% | 0.206 | 0.000 |
| gemini-3-flash | llama32 | 120 | 94.2% | 30.8% | 90.2% | 92.5% | 0.841 | 0.870 |
| gemma4 | llama-3.3-70b | 120 | 75.8% | 25.8% | 73.8% | 63.3% | 0.517 | 0.492 |
| gemma4 | llama32 | 120 | 46.7% | 10.8% | 31.7% | 26.5% | 0.169 | -0.134 |
| llama-3.3-70b | llama32 | 120 | 50.8% | 10.0% | 29.3% | 28.6% | 0.169 | -0.087 |

</details>

**Reading.** Of 28 pairs with a defined phi, the most correlated errors are jev + llama32 (phi 0.982, 40 shared wrong cases of 120) and the least correlated are jev + deberta-nli (phi -0.743, 0 shared wrong cases of 120).

### Jury composition — hard tasks (n=40)

Every 3-judge jury from the frozen panel (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32; `docs/runs/jury/panel.json`), 56 juries. Mean pairwise error phi is given on the 40 hard rows and on all 120 rows of the dataset — a judge wrong on every hard row (or on none) has no phi there; "(k/3)" says how many of the three pairs had one. Cost is the sum of the members' cost on the 120 rows; p50 latency the mean of the members' medians (`docs/arena-2026-09.json`). Sorted by majority accuracy; no composite score.

| jury | majority accuracy (all / decided) | ties | vote-share ECE | mean pairwise error phi (hard / all 120) | shared wrong | cost / 120 rows | p50 latency |
|---|---|---|---|---|---|---|---|
| deberta-nli + gemma4 + llama-3.3-70b | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.092 | -0.037 (1/3) / 0.396 | 0 | $0.0258 | 4.71 s |
| deberta-nli + deepseek-r1 + llama-3.3-70b | 87.5% [67.5, 100.0] / 87.5% | 0 | 0.075 | 0.006 (1/3) / 0.362 | 0 | $0.4637 | 1.71 s |
| deberta-nli + deepseek-r1 + gemma4 | 77.5% [57.5, 94.9] / 77.5% | 0 | 0.050 | 0.395 (1/3) / 0.448 | 0 | $0.4379 | 5.86 s |
| claude-sonnet-4.5 + deberta-nli + llama-3.3-70b | 72.5% [48.6, 92.9] / 72.5% | 0 | 0.008 | 0.259 (1/3) / -0.034 | 0 | $0.5262 | 2.35 s |
| deberta-nli + gemini-3-flash + llama-3.3-70b | 72.5% [48.6, 92.9] / 72.5% | 0 | 0.033 | 0.175 (1/3) / -0.108 | 0 | $0.0419 | 1.10 s |
| deberta-nli + llama-3.3-70b + llama32 | 72.5% [48.6, 92.9] / 72.5% | 0 | 0.058 | — / -0.165 | 0 | $0.0258 | 0.55 s |
| deepseek-r1 + gemma4 + llama-3.3-70b | 72.5% [51.2, 90.2] / 72.5% | 0 | 0.075 | 0.121 / 0.585 | 3 | $0.4637 | 6.09 s |
| jev + deberta-nli + llama-3.3-70b | 72.5% [48.6, 92.9] / 72.5% | 0 | 0.058 | — / -0.180 | 0 | $0.0278 | 0.53 s |
| claude-sonnet-4.5 + deberta-nli + gemma4 | 70.0% [46.2, 90.2] / 70.0% | 0 | 0.017 | 0.275 (1/3) / -0.016 | 0 | $0.5004 | 6.50 s |
| deberta-nli + gemini-3-flash + gemma4 | 70.0% [46.2, 90.2] / 70.0% | 0 | 0.008 | 0.186 (1/3) / -0.101 | 0 | $0.0161 | 5.24 s |
| deberta-nli + gemma4 + llama32 | 70.0% [46.2, 90.2] / 70.0% | 0 | 0.033 | — / -0.158 | 0 | $0.0000 | 4.69 s |
| jev + deberta-nli + gemma4 | 70.0% [46.2, 90.2] / 70.0% | 0 | 0.033 | — / -0.172 | 0 | $0.0020 | 4.68 s |
| claude-sonnet-4.5 + deberta-nli + deepseek-r1 | 55.0% [32.5, 77.5] / 55.0% | 0 | 0.167 | 0.380 (1/3) / -0.008 | 0 | $0.9383 | 3.50 s |
| deberta-nli + deepseek-r1 + gemini-3-flash | 55.0% [32.5, 77.5] / 55.0% | 0 | 0.142 | 0.258 (1/3) / -0.092 | 0 | $0.4540 | 2.25 s |
| deberta-nli + deepseek-r1 + llama32 | 55.0% [32.5, 77.5] / 55.0% | 0 | 0.117 | — / -0.150 | 0 | $0.4379 | 1.69 s |
| jev + deberta-nli + deepseek-r1 | 55.0% [32.5, 77.5] / 55.0% | 0 | 0.117 | — / -0.164 | 0 | $0.4399 | 1.68 s |
| claude-sonnet-4.5 + gemma4 + llama-3.3-70b | 50.0% [25.0, 74.4] / 50.0% | 0 | 0.242 | 0.166 / 0.224 | 3 | $0.5262 | 6.73 s |
| gemini-3-flash + gemma4 + llama-3.3-70b | 50.0% [25.0, 74.4] / 50.0% | 0 | 0.217 | 0.108 / 0.148 | 3 | $0.0419 | 5.48 s |
| gemma4 + llama-3.3-70b + llama32 | 50.0% [25.0, 74.4] / 50.0% | 0 | 0.192 | -0.037 (1/3) / 0.091 | 3 | $0.0258 | 4.93 s |
| jev + gemma4 + llama-3.3-70b | 50.0% [25.0, 74.4] / 50.0% | 0 | 0.192 | -0.037 (1/3) / 0.075 | 3 | $0.0278 | 4.91 s |
| claude-sonnet-4.5 + deepseek-r1 + gemma4 | 47.5% [23.8, 72.5] / 47.5% | 0 | 0.317 | 0.350 / 0.353 | 9 | $0.9383 | 7.88 s |
| deepseek-r1 + gemini-3-flash + gemma4 | 47.5% [23.8, 72.5] / 47.5% | 0 | 0.292 | 0.280 / 0.268 | 9 | $0.4540 | 6.63 s |
| deepseek-r1 + gemma4 + llama32 | 47.5% [23.8, 72.5] / 47.5% | 0 | 0.267 | 0.395 (1/3) / 0.210 | 9 | $0.4379 | 6.08 s |
| jev + deepseek-r1 + gemma4 | 47.5% [23.8, 72.5] / 47.5% | 0 | 0.267 | 0.395 (1/3) / 0.196 | 9 | $0.4399 | 6.06 s |
| claude-sonnet-4.5 + deepseek-r1 + llama-3.3-70b | 40.0% [17.5, 63.4] / 40.0% | 0 | 0.358 | 0.215 / 0.296 | 5 | $0.9641 | 3.73 s |
| deepseek-r1 + gemini-3-flash + llama-3.3-70b | 40.0% [17.5, 63.4] / 40.0% | 0 | 0.333 | 0.146 / 0.221 | 5 | $0.4798 | 2.48 s |
| deepseek-r1 + llama-3.3-70b + llama32 | 40.0% [17.5, 63.4] / 40.0% | 0 | 0.308 | 0.006 (1/3) / 0.163 | 5 | $0.4637 | 1.93 s |
| jev + deepseek-r1 + llama-3.3-70b | 40.0% [17.5, 63.4] / 40.0% | 0 | 0.308 | 0.006 (1/3) / 0.148 | 5 | $0.4657 | 1.91 s |
| claude-sonnet-4.5 + deberta-nli + gemini-3-flash | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.542 | 0.678 (1/3) / -0.093 | 0 | $0.5165 | 2.88 s |
| claude-sonnet-4.5 + deberta-nli + llama32 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.517 | — / -0.164 | 0 | $0.5004 | 2.33 s |
| claude-sonnet-4.5 + deepseek-r1 + gemini-3-flash | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.692 | 0.439 / 0.416 | 18 | $0.9544 | 4.27 s |
| claude-sonnet-4.5 + deepseek-r1 + llama32 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.667 | 0.380 (1/3) / 0.344 | 18 | $0.9383 | 3.72 s |
| claude-sonnet-4.5 + gemini-3-flash + gemma4 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.642 | 0.380 / 0.301 | 12 | $0.5165 | 7.26 s |
| claude-sonnet-4.5 + gemini-3-flash + llama-3.3-70b | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.633 | 0.371 / 0.322 | 11 | $0.5423 | 3.12 s |
| claude-sonnet-4.5 + gemma4 + llama32 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.617 | 0.275 (1/3) / 0.229 | 12 | $0.5004 | 6.71 s |
| claude-sonnet-4.5 + llama-3.3-70b + llama32 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.608 | 0.259 (1/3) / 0.251 | 11 | $0.5262 | 2.57 s |
| jev + claude-sonnet-4.5 + deberta-nli | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.517 | — / -0.166 | 0 | $0.5024 | 2.32 s |
| jev + claude-sonnet-4.5 + deepseek-r1 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.667 | 0.380 (1/3) / 0.343 | 18 | $0.9403 | 3.70 s |
| jev + claude-sonnet-4.5 + gemma4 | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.617 | 0.275 (1/3) / 0.228 | 12 | $0.5024 | 6.70 s |
| jev + claude-sonnet-4.5 + llama-3.3-70b | 15.0% [0.0, 34.2] / 15.0% | 0 | 0.608 | 0.259 (1/3) / 0.248 | 11 | $0.5282 | 2.55 s |
| claude-sonnet-4.5 + gemini-3-flash + llama32 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.875 | 0.678 (1/3) / 0.827 | 34 | $0.5165 | 3.10 s |
| deberta-nli + gemini-3-flash + llama32 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.592 | — / -0.163 | 0 | $0.0161 | 1.08 s |
| deepseek-r1 + gemini-3-flash + llama32 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.742 | 0.258 (1/3) / 0.345 | 18 | $0.4540 | 2.46 s |
| gemini-3-flash + gemma4 + llama32 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.692 | 0.186 (1/3) / 0.229 | 12 | $0.0161 | 5.46 s |
| gemini-3-flash + llama-3.3-70b + llama32 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.683 | 0.175 (1/3) / 0.261 | 11 | $0.0419 | 1.31 s |
| jev + claude-sonnet-4.5 + gemini-3-flash | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.875 | 0.678 (1/3) / 0.838 | 34 | $0.5185 | 3.09 s |
| jev + deberta-nli + gemini-3-flash | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.592 | — / -0.164 | 0 | $0.0181 | 1.07 s |
| jev + deepseek-r1 + gemini-3-flash | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.742 | 0.258 (1/3) / 0.344 | 18 | $0.4560 | 2.45 s |
| jev + gemini-3-flash + gemma4 | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.692 | 0.186 (1/3) / 0.228 | 12 | $0.0181 | 5.45 s |
| jev + gemini-3-flash + llama-3.3-70b | 7.5% [0.0, 22.5] / 7.5% | 0 | 0.683 | 0.175 (1/3) / 0.259 | 11 | $0.0439 | 1.30 s |
| jev + claude-sonnet-4.5 + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.950 | — / 0.827 | 34 | $0.5024 | 2.54 s |
| jev + deberta-nli + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.667 | — / -0.161 | 0 | $0.0020 | 0.52 s |
| jev + deepseek-r1 + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.817 | — / 0.346 | 18 | $0.4399 | 1.90 s |
| jev + gemini-3-flash + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.975 | — / 0.913 | 37 | $0.0181 | 1.28 s |
| jev + gemma4 + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.767 | — / 0.231 | 12 | $0.0020 | 4.90 s |
| jev + llama-3.3-70b + llama32 | 0.0% [0.0, 8.8]† / 0.0% | 0 | 0.758 | — / 0.261 | 11 | $0.0278 | 0.75 s |

**Diversity vs accuracy.** On the 40 hard rows, mean phi runs from -0.037 to 0.678 and its Spearman correlation with majority accuracy is -0.31 (40 juries, 30 of them with only one defined pair); on all 120 rows, mean phi runs from -0.180 to 0.913 and its Spearman correlation with majority accuracy is -0.32 (56 juries).

## Task router, described options (n=120)

Panel: 8 judges (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32). Majority vote among those who answered; a tie is no decision.

| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | best single judge | vote share right / wrong | conf of the wrong majority |
|---|---|---|---|---|---|---|---|---|---|
| all | 120 | 70.4% | 18 (0) | 13 | 1 | 85.8% [77.7, 92.2] / 96.3% | 98.3% | 0.86 / 0.656 | 0.923 |
| easy | 40 | 86.2% | 18 (0) | 0 | 0 | 100.0% [91.2, 100.0]† / 100.0% | 100.0% | 0.931 / — | — |
| hard | 40 | 73.7% | 0 (0) | 0 | 0 | 100.0% [91.2, 100.0]† / 100.0% | 100.0% | 0.866 / — | — |
| adversarial | 40 | 51.2% | 0 (0) | 13 | 1 | 57.5% [40.0, 74.5] / 85.2% | 100.0% | 0.727 / 0.656 | 0.923 |

**Vote share as a confidence score** (the way most agent juries use it) against each judge's own declared confidence, same ECE and zero-error coverage:

| confidence source | accuracy | ECE | zero-error coverage |
|---|---|---|---|
| panel vote share (majority) | 85.8% [77.7, 92.2] | 0.110 | 75.7% |
| jev (declared) | 97.5% | 0.053 | 94.2% |
| claude-sonnet-4.5 (declared) | 95.0% | 0.032 | 0.0% |
| deberta-nli (declared) | 49.2% | 0.195 | 0.0% |
| deepseek-r1 (declared) | 79.2% | 0.148 | 0.0% |
| gemini-3-flash (declared) | 98.3% | 0.012 | 72.5% |
| gemma4 (declared) | 77.5% | 0.180 | 0.0% |
| llama-3.3-70b (declared) | 86.7% | 0.043 | 0.0% |
| llama32 (declared) | 59.2% | 0.429 | 0.0% |

**Pick the jury, pick the headline.** Over all 56 three-judge juries drawn from this panel, majority accuracy on the 40 hard tasks runs from 92.5% [76.9, 100.0] (jev + claude-sonnet-4.5 + llama32) to 100.0% [91.2, 100.0]† (jev + claude-sonnet-4.5 + deberta-nli); no three-judge jury is unanimous and wrong on any hard task.

### Error correlation (n=120)

Phi between the two judges' error indicators, over the rows where both answered. "—": undefined because one judge has no error on those rows. `errors` is the judge's own count; the full pair table (agreement, joint error, conditional error rates, error-set Jaccard, n) is folded below.

| judge (errors) | jev | claude-sonnet-4.5 | deberta-nli | deepseek-r1 | gemini-3-flash | gemma4 | llama-3.3-70b | llama32 |
|---|---|---|---|---|---|---|---|---|
| jev (3) |  | -0.037 | -0.163 | -0.081 | -0.021 | -0.086 | -0.063 | 0.193 |
| claude-sonnet-4.5 (6) |  |  | 0.226 | 0.459 | 0.568 | 0.243 | 0.022 | -0.191 |
| deberta-nli (61) |  |  |  | 0.457 | 0.128 | 0.490 | 0.386 | -0.539 |
| deepseek-r1 (24) |  |  |  |  | 0.260 | 0.646 | 0.539 | -0.123 |
| gemini-3-flash (2) |  |  |  |  |  | 0.086 | 0.140 | -0.108 |
| gemma4 (27) |  |  |  |  |  |  | 0.317 | -0.123 |
| llama-3.3-70b (16) |  |  |  |  |  |  |  | -0.076 |
| llama32 (49) |  |  |  |  |  |  |  |  |

<details><summary>Every pair</summary>

| A | B | n | agreement | joint error | P(A wrong \| B wrong) | P(B wrong \| A wrong) | error-set Jaccard | phi |
|---|---|---|---|---|---|---|---|---|
| jev | claude-sonnet-4.5 | 120 | 92.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.037 |
| jev | deberta-nli | 120 | 46.7% | 0.0% | 0.0% | 0.0% | 0.000 | -0.163 |
| jev | deepseek-r1 | 119 | 77.3% | 0.0% | 0.0% | 0.0% | 0.000 | -0.081 |
| jev | gemini-3-flash | 120 | 95.8% | 0.0% | 0.0% | 0.0% | 0.000 | -0.021 |
| jev | gemma4 | 120 | 75.0% | 0.0% | 0.0% | 0.0% | 0.000 | -0.086 |
| jev | llama-3.3-70b | 120 | 84.2% | 0.0% | 0.0% | 0.0% | 0.000 | -0.063 |
| jev | llama32 | 120 | 61.7% | 2.5% | 6.1% | 100.0% | 0.061 | 0.193 |
| claude-sonnet-4.5 | deberta-nli | 120 | 54.2% | 5.0% | 9.8% | 100.0% | 0.098 | 0.226 |
| claude-sonnet-4.5 | deepseek-r1 | 119 | 84.9% | 5.0% | 25.0% | 100.0% | 0.250 | 0.459 |
| claude-sonnet-4.5 | gemini-3-flash | 120 | 96.7% | 1.7% | 100.0% | 33.3% | 0.333 | 0.568 |
| claude-sonnet-4.5 | gemma4 | 120 | 79.2% | 3.3% | 14.8% | 66.7% | 0.138 | 0.243 |
| claude-sonnet-4.5 | llama-3.3-70b | 120 | 83.3% | 0.8% | 6.2% | 16.7% | 0.048 | 0.022 |
| claude-sonnet-4.5 | llama32 | 120 | 54.2% | 0.0% | 0.0% | 0.0% | 0.000 | -0.191 |
| deberta-nli | deepseek-r1 | 119 | 68.1% | 19.3% | 95.8% | 38.3% | 0.377 | 0.457 |
| deberta-nli | gemini-3-flash | 120 | 50.8% | 1.7% | 100.0% | 3.3% | 0.033 | 0.128 |
| deberta-nli | gemma4 | 120 | 70.0% | 21.7% | 96.3% | 42.6% | 0.419 | 0.490 |
| deberta-nli | llama-3.3-70b | 120 | 62.5% | 13.3% | 100.0% | 26.2% | 0.262 | 0.386 |
| deberta-nli | llama32 | 120 | 23.3% | 7.5% | 18.4% | 14.8% | 0.089 | -0.539 |
| deepseek-r1 | gemini-3-flash | 119 | 81.5% | 1.7% | 100.0% | 8.3% | 0.083 | 0.260 |
| deepseek-r1 | gemma4 | 119 | 88.2% | 15.1% | 69.2% | 75.0% | 0.562 | 0.646 |
| deepseek-r1 | llama-3.3-70b | 119 | 86.6% | 10.1% | 75.0% | 50.0% | 0.429 | 0.539 |
| deepseek-r1 | llama32 | 119 | 50.4% | 5.9% | 14.3% | 29.2% | 0.106 | -0.123 |
| gemini-3-flash | gemma4 | 120 | 77.5% | 0.8% | 3.7% | 50.0% | 0.036 | 0.086 |
| gemini-3-flash | llama-3.3-70b | 120 | 86.7% | 0.8% | 6.2% | 50.0% | 0.059 | 0.140 |
| gemini-3-flash | llama32 | 120 | 57.5% | 0.0% | 0.0% | 0.0% | 0.000 | -0.108 |
| gemma4 | llama-3.3-70b | 120 | 79.2% | 7.5% | 56.2% | 33.3% | 0.265 | 0.317 |
| gemma4 | llama32 | 120 | 50.0% | 6.7% | 16.3% | 29.6% | 0.118 | -0.123 |
| llama-3.3-70b | llama32 | 120 | 54.2% | 4.2% | 10.2% | 31.2% | 0.083 | -0.076 |

</details>

**Reading.** Of 28 pairs with a defined phi, the most correlated errors are deepseek-r1 + gemma4 (phi 0.646, 18 shared wrong cases of 119) and the least correlated are deberta-nli + llama32 (phi -0.539, 9 shared wrong cases of 120).

### Jury composition — hard tasks (n=40)

Every 3-judge jury from the frozen panel (jev, claude-sonnet-4.5, deberta-nli, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32; `docs/runs/jury/panel.json`), 56 juries. Mean pairwise error phi is given on the 40 hard rows and on all 120 rows of the dataset — a judge wrong on every hard row (or on none) has no phi there; "(k/3)" says how many of the three pairs had one. Cost is the sum of the members' cost on the 120 rows; p50 latency the mean of the members' medians (`docs/arena-2026-09.json`). Sorted by majority accuracy; no composite score.

| jury | majority accuracy (all / decided) | ties | vote-share ECE | mean pairwise error phi (hard / all 120) | shared wrong | cost / 120 rows | p50 latency |
|---|---|---|---|---|---|---|---|
| claude-sonnet-4.5 + deberta-nli + deepseek-r1 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.380 | 0 | $0.8658 | 2.91 s |
| claude-sonnet-4.5 + deberta-nli + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.307 | 0 | $0.4183 | 2.37 s |
| claude-sonnet-4.5 + deberta-nli + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.319 | 0 | $0.3998 | 5.98 s |
| claude-sonnet-4.5 + deberta-nli + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.211 | 0 | $0.4312 | 1.82 s |
| claude-sonnet-4.5 + deberta-nli + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.168 | 0 | $0.3998 | 1.84 s |
| claude-sonnet-4.5 + deepseek-r1 + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.429 | 0 | $0.8843 | 3.69 s |
| claude-sonnet-4.5 + deepseek-r1 + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.449 | 0 | $0.8658 | 7.31 s |
| claude-sonnet-4.5 + deepseek-r1 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.340 | 0 | $0.8972 | 3.15 s |
| claude-sonnet-4.5 + deepseek-r1 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.048 | 0 | $0.8658 | 3.17 s |
| claude-sonnet-4.5 + gemini-3-flash + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.299 | 0 | $0.4183 | 6.77 s |
| claude-sonnet-4.5 + gemini-3-flash + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.243 | 0 | $0.4497 | 2.60 s |
| claude-sonnet-4.5 + gemini-3-flash + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.090 | 0 | $0.4183 | 2.63 s |
| claude-sonnet-4.5 + gemma4 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.194 | 0 | $0.4312 | 6.22 s |
| claude-sonnet-4.5 + gemma4 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.024 | 0 | $0.3998 | 6.24 s |
| claude-sonnet-4.5 + llama-3.3-70b + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.082 | 0 | $0.4312 | 2.08 s |
| deberta-nli + deepseek-r1 + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.281 | 0 | $0.4845 | 2.21 s |
| deberta-nli + deepseek-r1 + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.531 | 0 | $0.4660 | 5.83 s |
| deberta-nli + deepseek-r1 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.460 | 0 | $0.4974 | 1.66 s |
| deberta-nli + deepseek-r1 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.069 | 0 | $0.4660 | 1.69 s |
| deberta-nli + gemini-3-flash + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.235 | 0 | $0.0185 | 5.28 s |
| deberta-nli + gemini-3-flash + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.218 | 0 | $0.0499 | 1.12 s |
| deberta-nli + gemini-3-flash + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.173 | 0 | $0.0185 | 1.15 s |
| deberta-nli + gemma4 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.398 | 0 | $0.0314 | 4.74 s |
| deberta-nli + gemma4 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.057 | 0 | $0.0000 | 4.76 s |
| deberta-nli + llama-3.3-70b + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.077 | 0 | $0.0314 | 0.60 s |
| deepseek-r1 + gemini-3-flash + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.331 | 0 | $0.4845 | 6.61 s |
| deepseek-r1 + gemini-3-flash + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.313 | 0 | $0.5159 | 2.45 s |
| deepseek-r1 + gemini-3-flash + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.010 | 0 | $0.4845 | 2.47 s |
| deepseek-r1 + gemma4 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.501 | 0 | $0.4974 | 6.06 s |
| deepseek-r1 + gemma4 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.134 | 0 | $0.4660 | 6.08 s |
| deepseek-r1 + llama-3.3-70b + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.113 | 0 | $0.4974 | 1.92 s |
| gemini-3-flash + gemma4 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.000 | — / 0.181 | 0 | $0.0499 | 5.52 s |
| gemini-3-flash + gemma4 + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.048 | 0 | $0.0185 | 5.54 s |
| gemini-3-flash + llama-3.3-70b + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / -0.015 | 0 | $0.0499 | 1.38 s |
| gemma4 + llama-3.3-70b + llama32 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.333 | — / 0.039 | 0 | $0.0314 | 4.99 s |
| jev + claude-sonnet-4.5 + deberta-nli | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.009 | 0 | $0.4021 | 1.84 s |
| jev + claude-sonnet-4.5 + deepseek-r1 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.114 | 0 | $0.8681 | 3.17 s |
| jev + claude-sonnet-4.5 + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.170 | 0 | $0.4206 | 2.62 s |
| jev + claude-sonnet-4.5 + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.040 | 0 | $0.4021 | 6.24 s |
| jev + claude-sonnet-4.5 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / -0.026 | 0 | $0.4335 | 2.08 s |
| jev + deberta-nli + deepseek-r1 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.071 | 0 | $0.4683 | 1.68 s |
| jev + deberta-nli + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / -0.018 | 0 | $0.0208 | 1.14 s |
| jev + deberta-nli + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.080 | 0 | $0.0023 | 4.75 s |
| jev + deberta-nli + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.053 | 0 | $0.0337 | 0.59 s |
| jev + deepseek-r1 + gemini-3-flash | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.053 | 0 | $0.4868 | 2.46 s |
| jev + deepseek-r1 + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.160 | 0 | $0.4683 | 6.08 s |
| jev + deepseek-r1 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.132 | 0 | $0.4997 | 1.92 s |
| jev + gemini-3-flash + gemma4 | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / -0.007 | 0 | $0.0208 | 5.54 s |
| jev + gemini-3-flash + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.019 | 0 | $0.0522 | 1.38 s |
| jev + gemma4 + llama-3.3-70b | 100.0% [91.2, 100.0]† / 100.0% | 0 | 0.025 | — / 0.056 | 0 | $0.0337 | 4.99 s |
| jev + claude-sonnet-4.5 + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / -0.011 | 0 | $0.4021 | 2.10 s |
| jev + deberta-nli + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / -0.170 | 0 | $0.0023 | 0.61 s |
| jev + deepseek-r1 + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / -0.004 | 0 | $0.4683 | 1.94 s |
| jev + gemini-3-flash + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / 0.021 | 0 | $0.0208 | 1.40 s |
| jev + gemma4 + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / -0.005 | 0 | $0.0023 | 5.01 s |
| jev + llama-3.3-70b + llama32 | 92.5% [76.9, 100.0] / 92.5% | 0 | 0.258 | — / 0.018 | 0 | $0.0337 | 0.85 s |

**Diversity vs accuracy.** On the 40 hard rows, Spearman is undefined (0 juries with a defined mean phi); on all 120 rows, mean phi runs from -0.173 to 0.531 and its Spearman correlation with majority accuracy is +0.30 (56 juries).

## How to read it

- **[a, b]** after majority accuracy: 95 % percentile-bootstrap interval (2,000 resamples, seed 0) over the dataset's **distinct texts**, not its rows — the majority is recomputed on each resampled text, and two rows with the same state are not two independent observations (`docs/judges.md` § Confidence intervals). The 40 hard rows carry only 14 distinct texts, so that interval is wide (±15 to 20 points): juries whose intervals overlap are not separated by this data.
- **†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had.
- **pairwise agreement**: mean over judge pairs of the share of cases where both chose the same option.
- **unanimous (wrong)**: cases where every judge who answered chose the same option (at least two answered), and how many of those were wrong.
- **ties**: an even split among those who answered — no decision. *majority accuracy (all)* counts a tie as not correct (the jury could not act); *(decided)* is accuracy over the rows with a majority. Ties are excluded from the share statistics.
- **abstentions**: blank (unparseable) answers across the panel; an abstention is not a vote.
- **vote share right / wrong**: mean share of the winning option when the majority was right vs. wrong. If the two numbers are close, agreement carries no information about correctness.
- **conf of the wrong majority**: mean declared confidence of the judges who voted with a wrong majority.
- **vote share as confidence**: ECE and zero-error coverage computed with the share as the confidence of the majority decision — the number an agent jury would act on.
- **error correlation** (per judge pair, over the rows where both answered; n stated per pair): *joint error* is the share of rows where both were wrong; *P(A wrong | B wrong)* is the joint errors over B's errors; *error-set Jaccard* is shared errors over the union of the two error sets; *phi* is the correlation between the two 0/1 error indicators (+1: identical errors, 0: independent, −1: never wrong together). Phi is undefined when a judge has no error (or no correct answer) on the compared rows, the conditional when the conditioning judge has none, Jaccard when neither erred. Three judges with phi near 1 are one opinion voting three times.
- **jury composition**: *mean pairwise error phi* averages the three pairs' phi (pairs with an undefined phi are left out and the count is shown; "—" when all three are), on the hard rows and on every row of the dataset; *shared wrong* counts the hard rows where all three answered and all three were wrong; *diversity vs accuracy* is the Spearman rank correlation between mean phi and majority accuracy across the juries — reported as computed, on 40 scored rows.

## Caveats

- Synthetic, seeded datasets; ground truth for routing is by construction. n is small; subset rows are indicative.
- Ties are no decision (see above). An earlier version broke ties alphabetically, which on the router always favoured `route_easy`; changed and disclosed in `jury-consensus-plan.md`.
- Judges differ in cost, size and confidence method; the panel is heterogeneous on purpose (same-model juries are the documented failure mode — Smit et al., ICML 2024).
- Round 1 only: nobody saw anybody else's vote. Round 2 (deliberation) is pre-registered in `docs/jury-consensus-plan.md` and reported in `docs/jury-consensus.md` once run.
