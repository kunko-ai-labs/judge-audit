# Jury consensus audit — deliberation (round 2)

Round 1 (independent votes, every judge, no new API call) is in [consensus-2026-09.md](consensus-2026-09.md). Here each judge votes again after seeing the other judges' round-1 decisions and confidences, anonymised and shuffled (protocol pre-registered in [jury-consensus-plan.md](jury-consensus-plan.md); inputs and raw answers under `docs/runs/jury/`). Recompute: `python scripts/jury_report.py`.

The question is the one Shao (2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) and Huang et al. (2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) raise: after communication, does agreement go up because the panel got closer to the truth, or just closer to each other?

## Task router, bare option labels (n=120)

Re-voted after seeing the panel: jev, claude-sonnet-4.5, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32. Kept their round-1 vote (cannot read a deliberation prompt): deberta-nli.

| panel | pairwise agreement | unanimous (wrong) | majority accuracy | vote share right / wrong | vote-share ECE | zero-error coverage |
|---|---|---|---|---|---|---|
| all, round 1 | 58.2% | 15 (0) | 65.0% | 0.747 / 0.652 | 0.174 | 12.5% |
| all, round 2 | 67.4% | 12 (0) | 64.2% | 0.817 / 0.788 | 0.206 | 11.7% |
| hard, round 1 | 50.2% | 0 (0) | 15.0% | 0.688 / 0.651 | 0.506 | 0.0% |
| hard, round 2 | 71.3% | 0 (0) | 20.0% | 0.859 / 0.844 | 0.647 | 0.0% |

| judge | accuracy r1 → r2 | hard accuracy r1 → r2 | ECE r1 → r2 | conf when wrong r1 → r2 | switched | → correct / → wrong | followed the panel majority |
|---|---|---|---|---|---|---|---|
| jev | 66.7% → 74.2% | 0.0% → 22.5% | 0.318 → 0.181 | 0.926 → 0.838 | 9 | 9 / 0 | 9 / 9 |
| claude-sonnet-4.5 | 60.8% → 65.8% | 15.0% → 30.0% | 0.237 → 0.190 | 0.726 → 0.710 | 8 | 7 / 1 | 6 / 8 |
| deepseek-r1 | 49.2% → 50.0% | 45.0% → 20.0% | 0.258 → 0.354 | 0.597 → 0.747 | 32 | 11 / 21 | 25 / 32 |
| gemini-3-flash | 66.7% → 66.7% | 7.5% → 17.5% | 0.315 → 0.303 | 0.965 → 0.932 | 10 | 5 / 5 | 9 / 10 |
| gemma4 | 59.2% → 56.7% | 70.0% → 25.0% | 0.345 → 0.352 | 0.954 → 0.909 | 33 | 15 / 18 | 32 / 33 |
| llama-3.3-70b | 65.0% → 55.0% | 72.5% → 22.5% | 0.233 → 0.398 | 0.926 → 0.939 | 30 | 9 / 21 | 30 / 30 |
| llama32 | 65.8% → 60.8% | 0.0% → 0.0% | 0.396 → 0.346 | 1.000 → 0.787 | 8 | 1 / 7 | 0 / 8 |

## Task router, described options (n=120)

Re-voted after seeing the panel: jev, claude-sonnet-4.5, deepseek-r1, gemini-3-flash, gemma4, llama-3.3-70b, llama32. Kept their round-1 vote (cannot read a deliberation prompt): deberta-nli.

| panel | pairwise agreement | unanimous (wrong) | majority accuracy | vote share right / wrong | vote-share ECE | zero-error coverage |
|---|---|---|---|---|---|---|
| all, round 1 | 66.3% | 14 (0) | 95.8% | 0.805 / 0.550 | 0.164 | 75.0% |
| all, round 2 | 77.0% | 34 (0) | 96.7% | 0.881 / 0.625 | 0.094 | 87.5% |
| hard, round 1 | 72.0% | 0 (0) | 100.0% | 0.856 / — | 0.144 | 100.0% |
| hard, round 2 | 87.5% | 20 (0) | 100.0% | 0.938 / — | 0.062 | 100.0% |

| judge | accuracy r1 → r2 | hard accuracy r1 → r2 | ECE r1 → r2 | conf when wrong r1 → r2 | switched | → correct / → wrong | followed the panel majority |
|---|---|---|---|---|---|---|---|
| jev | 97.5% → 100.0% | 92.5% → 100.0% | 0.053 → 0.046 | 0.583 → — | 3 | 3 / 0 | 3 / 3 |
| claude-sonnet-4.5 | 88.3% → 90.0% | 100.0% → 100.0% | 0.034 → 0.053 | 0.421 → 0.379 | 2 | 2 / 0 | 1 / 2 |
| deepseek-r1 | 71.7% → 83.3% | 92.5% → 95.0% | 0.056 → 0.011 | 0.310 → 0.225 | 24 | 16 / 8 | 17 / 24 |
| gemini-3-flash | 98.3% → 98.3% | 100.0% → 100.0% | 0.012 → 0.037 | 0.825 → 0.850 | 2 | 1 / 1 | 2 / 2 |
| gemma4 | 77.5% → 90.0% | 100.0% → 100.0% | 0.180 → 0.054 | 0.981 → 0.917 | 21 | 18 / 3 | 18 / 21 |
| llama-3.3-70b | 86.7% → 95.8% | 100.0% → 100.0% | 0.043 → 0.014 | 0.969 → 0.890 | 15 | 13 / 2 | 13 / 15 |
| llama32 | 59.2% → 83.3% | 0.0% → 55.0% | 0.429 → 0.089 | 1.000 → 0.790 | 32 | 29 / 3 | 29 / 32 |

## Results vs the pre-registered predictions

Scored mechanically from the tables above; the thresholds are stated with each verdict.

1. **Agreement and unanimity rise on both datasets** — not held. router-bare: agreement 58.2% → 67.4%, unanimous 15 → 12; router-described: agreement 66.3% → 77.0%, unanimous 14 → 34.
2. **Bare labels: hard-task majority accuracy does not rise materially (< 10 points) and the 3B model follows the panel** — partly held. Hard-task majority accuracy 15.0% → 20.0%; llama3.2 switched 8 votes, 0 of them onto the panel majority.
3. **Described options: judges that were right keep their vote (switches to wrong ≤ 5 % of votes) and majority accuracy does not fall** — held. Switches to wrong: 17 of 840 re-votes; majority accuracy 95.8% → 96.7%.
4. **Chat models are more confident when wrong after deliberation** — not held (3 of 12 judge×dataset cells went up). claude-sonnet-4.5/bare 0.726→0.710; deepseek-r1/bare 0.597→0.747; gemini-3-flash/bare 0.965→0.932; gemma4/bare 0.954→0.909; llama-3.3-70b/bare 0.926→0.939; llama32/bare 1.000→0.787; claude-sonnet-4.5/described 0.421→0.379; deepseek-r1/described 0.310→0.225; gemini-3-flash/described 0.825→0.850; gemma4/described 0.981→0.917; llama-3.3-70b/described 0.969→0.890; llama32/described 1.000→0.790.

## How to read it

- A jury that deliberates well moves **majority accuracy** up and keeps **conf when wrong** low.
- A jury that merely converges moves **pairwise agreement** and **unanimous** up while accuracy stays put — Shao's "nearly unanimous, mostly incorrect" in miniature.
- **followed the panel majority** counts switches that landed on the other judges' round-1 majority: conformity, whether or not it was right.

## Caveats

- Illustration, not replication: no human groups, a routing task instead of Wason, n=120 (40 hard). Ground truth for routing is by construction.
- One deliberation prompt, one round; the panel seen is round-1 votes, so judges do not see each other's revisions.
- Judges without a text prompt (zero-shot NLI) keep their round-1 vote in the round-2 panel; this is stated per dataset above.
