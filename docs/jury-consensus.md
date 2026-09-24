# Jury consensus audit — deliberation (round 2)

Round 1 (independent votes, every judge, no new API call) is in [consensus-2026-09.md](consensus-2026-09.md). Here each judge votes again after seeing the other judges' round-1 decisions and confidences, anonymised and shuffled (protocol pre-registered in [jury-consensus-plan.md](jury-consensus-plan.md); inputs and raw answers under `docs/runs/jury/`). Recompute: `python scripts/jury_report.py`.

The question is the one Shao (2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) and Huang et al. (2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) raise: after communication, does agreement go up because the panel got closer to the truth, or just closer to each other?

## Task router, bare option labels (n=120)

Re-voted after seeing the panel: jev, claude-sonnet-4.5, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32. Kept their round-1 vote (cannot read a deliberation prompt): deberta-nli.

| panel | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | vote share right / wrong | vote-share ECE | zero-error coverage |
|---|---|---|---|---|---|---|---|---|
| all, round 1 | 61.1% | 17 (0) | 28 | 1 | 48.3% [34.4, 61.6] / 63.0% | 0.850 / 0.688 | 0.174 | 18.5% |
| all, round 2 | 72.4% | 17 (0) | 4 | 1 | 63.3% [49.3, 76.1] / 65.5% | 0.863 / 0.831 | 0.197 | 14.7% |
| hard, round 1 | 50.9% | 0 (0) | 7 | 0 | 15.0% [0.0, 34.2] / 18.2% | 0.688 / 0.690 | 0.508 | 0.0% |
| hard, round 2 | 70.7% | 0 (0) | 1 | 0 | 17.5% [0.0, 37.5] / 17.9% | 0.750 / 0.867 | 0.724 | 0.0% |

| judge | accuracy r1 → r2 | confidence known r1 → r2 | hard accuracy r1 → r2 | ECE r1 → r2 | conf when wrong r1 → r2 | no answer r1 / r2 | switched | → correct / → wrong | followed the panel majority |
|---|---|---|---|---|---|---|---|---|---|
| jev | 66.7% [52.5, 80.3] → 72.5% [58.8, 84.5] | 120/120 → 120/120 | 0.0% [0.0, 8.8]† → 17.5% [0.0, 37.5] | 0.318 → 0.208 | 0.926 → 0.860 | 0 / 0 | 7 | 7 / 0 | 7 / 7 |
| claude-sonnet-4.5 | 65.8% [51.9, 78.7] → 70.0% [56.4, 82.1] | 120/120 → 120/120 | 15.0% [0.0, 34.2] → 25.0% [5.0, 47.5] | 0.235 → 0.231 | 0.832 → 0.877 | 0 / 0 | 5 | 5 / 0 | 4 / 5 |
| deepseek-r1 | 55.8% [42.5, 68.2] → 55.0% [41.7, 68.2] | 119/120 → 119/120 | 55.0% [32.5, 77.5] → 12.5% [0.0, 29.7] | 0.377 → 0.382 | 0.905 → 0.934 | 1 / 1 | 33 | 16 / 17 | 31 / 33 |
| gemini-3-flash | 66.7% [52.9, 80.0] → 66.7% [52.2, 79.7] | 120/120 → 120/120 | 7.5% [0.0, 22.5] → 20.0% [0.0, 42.5] | 0.315 → 0.305 | 0.965 → 0.930 | 0 / 0 | 12 | 6 / 6 | 11 / 12 |
| gemma4 | 59.2% [46.2, 71.2] → 61.7% [48.4, 74.3] | 120/120 → 120/120 | 70.0% [46.2, 90.2] → 17.5% [0.0, 39.0] | 0.345 → 0.310 | 0.954 → 0.920 | 0 / 0 | 45 | 24 / 21 | 42 / 45 |
| llama-3.3-70b | 65.0% [51.7, 76.7] → 55.0% [41.1, 69.0] | 120/120 → 120/120 | 72.5% [48.6, 92.9] → 7.5% [0.0, 22.5] | 0.233 → 0.390 | 0.926 → 0.936 | 0 / 0 | 42 | 15 / 27 | 39 / 42 |
| llama32 | 65.8% [51.6, 79.2] → 66.7% [52.5, 80.3] | 120/120 → 120/120 | 0.0% [0.0, 8.8]† → 0.0% [0.0, 8.8]† | 0.396 → 0.282 | 1.000 → 0.829 | 0 / 0 | 1 | 1 / 0 | 0 / 1 |

## Task router, described options (n=120)

Re-voted after seeing the panel: jev, claude-sonnet-4.5, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32. Kept their round-1 vote (cannot read a deliberation prompt): deberta-nli.

| panel | pairwise agreement | unanimous (wrong) | ties | abstentions | majority accuracy (all / decided) | vote share right / wrong | vote-share ECE | zero-error coverage |
|---|---|---|---|---|---|---|---|---|
| all, round 1 | 70.4% | 18 (0) | 13 | 1 | 85.8% [77.7, 92.2] / 96.3% | 0.860 / 0.656 | 0.110 | 75.7% |
| all, round 2 | 82.8% | 52 (0) | 5 | 1 | 95.0% [90.5, 98.4] / 99.1% | 0.920 / 0.750 | 0.073 | 92.2% |
| hard, round 1 | 73.7% | 0 (0) | 0 | 0 | 100.0% [91.2, 100.0]† / 100.0% | 0.866 / — | 0.134 | 100.0% |
| hard, round 2 | 96.2% | 34 (0) | 0 | 1 | 100.0% [91.2, 100.0]† / 100.0% | 0.981 / — | 0.019 | 100.0% |

| judge | accuracy r1 → r2 | confidence known r1 → r2 | hard accuracy r1 → r2 | ECE r1 → r2 | conf when wrong r1 → r2 | no answer r1 / r2 | switched | → correct / → wrong | followed the panel majority |
|---|---|---|---|---|---|---|---|---|---|
| jev | 97.5% [91.9, 100.0] → 100.0% [97.0, 100.0]† | 120/120 → 120/120 | 92.5% [76.9, 100.0] → 100.0% [91.2, 100.0]† | 0.053 → 0.044 | 0.583 → — | 0 / 0 | 3 | 3 / 0 | 3 / 3 |
| claude-sonnet-4.5 | 95.0% [90.3, 98.5] → 95.0% [90.3, 98.5] | 120/120 → 120/120 | 100.0% [91.2, 100.0]† → 100.0% [91.2, 100.0]† | 0.032 → 0.048 | 0.983 → 0.800 | 0 / 0 | 0 | 0 / 0 | 0 / 0 |
| deepseek-r1 | 79.2% [69.9, 86.9] → 89.2% [82.3, 94.6] | 119/120 → 120/120 | 100.0% [91.2, 100.0]† → 100.0% [91.2, 100.0]† | 0.149 → 0.051 | 0.931 → 0.846 | 1 / 0 | 11 | 11 / 0 | 11 / 11 |
| gemini-3-flash | 98.3% [95.5, 100.0] → 99.2% [97.2, 100.0] | 120/120 → 120/120 | 100.0% [91.2, 100.0]† → 100.0% [91.2, 100.0]† | 0.012 → 0.024 | 0.825 → 0.900 | 0 / 0 | 1 | 1 / 0 | 1 / 1 |
| gemma4 | 77.5% [67.2, 87.1] → 93.3% [87.4, 97.6] | 120/120 → 120/120 | 100.0% [91.2, 100.0]† → 100.0% [91.2, 100.0]† | 0.180 → 0.027 | 0.981 → 0.912 | 0 / 0 | 21 | 20 / 1 | 21 / 21 |
| llama-3.3-70b | 86.7% [78.5, 93.4] → 96.7% [93.0, 99.2] | 120/120 → 120/120 | 100.0% [91.2, 100.0]† → 100.0% [91.2, 100.0]† | 0.043 → 0.013 | 0.969 → 0.925 | 0 / 0 | 14 | 13 / 1 | 13 / 14 |
| llama32 | 59.2% [45.5, 73.0] → 94.2% [86.4, 100.0] | 120/120 → 119/120 | 0.0% [0.0, 8.8]† → 82.5% [61.0, 100.0] | 0.429 → 0.136 | 1.000 → 0.700 | 0 / 1 | 42 | 42 / 0 | 39 / 42 |

## Results vs the pre-registered predictions

Scored mechanically from the tables above with the thresholds fixed in the plan's Amendments before the rerun.

1. **Agreement and unanimity rise on both datasets** — held. router-bare: agreement 61.1% → 72.4%, unanimous 17 → 17; router-described: agreement 70.4% → 82.8%, unanimous 18 → 52.
2. **Bare labels: hard-task majority accuracy does not rise materially (< 10 points) and the 3B model follows the panel** — partly held. Hard-task majority accuracy 15.0% → 17.5%; llama3.2 switched 1 vote (too few to tell either way), 0 of them onto the panel majority.
3. **Described options: judges that were right keep their vote (switches to wrong ≤ 5 % of votes) and majority accuracy does not fall** — held. Switches to wrong: 2 of 840 re-votes; majority accuracy 85.8% → 95.0%.
4. **Chat models are more confident when wrong after deliberation** — not held (4 of 12 judge×dataset cells went up). claude-sonnet-4.5/bare 0.832→0.877; deepseek-r1/bare 0.905→0.934; gemini-3-flash/bare 0.965→0.930; gemma4/bare 0.954→0.920; llama-3.3-70b/bare 0.926→0.936; llama32/bare 1.000→0.829; claude-sonnet-4.5/described 0.983→0.800; deepseek-r1/described 0.931→0.846; gemini-3-flash/described 0.825→0.900; gemma4/described 0.981→0.912; llama-3.3-70b/described 0.969→0.925; llama32/described 1.000→0.700.

## How to read it

- **[a, b]** after an accuracy: 95 % percentile-bootstrap interval (2,000 resamples, seed 0) over the dataset's distinct texts — the 40 hard rows carry 14 of them, which is why these intervals are wide (`docs/judges.md` § Confidence intervals). Each interval is that round's own sampling noise; the two rounds are the same judges on the same rows, so what shows whether deliberation changed anything is the paired evidence in this table — the switch counts, where they landed, and how many followed the panel.
- **†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had.
- A jury that deliberates well moves **majority accuracy** up and keeps **conf when wrong** low.
- A jury that merely converges moves **pairwise agreement** and **unanimous** up while accuracy stays put — Shao's "nearly unanimous, mostly incorrect" in miniature.
- **followed the panel majority** counts switches that landed on the majority of the votes the judge actually saw (committed in its `.r2.input.jsonl`): conformity, whether or not it was right.
- **confidence known** is shown per judge and round. ECE and confidence-when-wrong use only those rows; accuracy and switch counts still use every row.
- **no answer**: blank (unparseable) answers per round. They are abstentions — not votes, not switches — and were not shown to other judges.
- **ties**: an even split among those who answered is no decision; counted as not correct in majority accuracy, excluded from share statistics.

## Caveats

- Illustration, not replication: no human groups, a routing task instead of Wason, n=120 (40 hard). Ground truth for routing is by construction.
- One deliberation prompt, one round; the panel seen is round-1 votes, so judges do not see each other's revisions.
- Judges without a text prompt (zero-shot NLI) keep their round-1 vote in the round-2 panel; this is stated per dataset above.
