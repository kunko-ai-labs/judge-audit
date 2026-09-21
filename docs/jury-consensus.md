# Jury consensus audit — deliberation (round 2)

Round 1 (independent votes, every judge, no new API call) is in [consensus-2026-09.md](consensus-2026-09.md). Here each judge votes again after seeing the other judges' round-1 decisions and confidences, anonymised and shuffled (protocol pre-registered in [jury-consensus-plan.md](jury-consensus-plan.md); inputs and raw answers under `docs/runs/jury/`). Recompute: `python scripts/jury_report.py`.

The question is the one Shao (2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) and Huang et al. (2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) raise: after communication, does agreement go up because the panel got closer to the truth, or just closer to each other?

## Task router, bare option labels (n=120)

_Round 2 not run yet._

## Task router, described options (n=120)

_Round 2 not run yet._

## How to read it

- A jury that deliberates well moves **majority accuracy** up and keeps **conf when wrong** low.
- A jury that merely converges moves **pairwise agreement** and **unanimous** up while accuracy stays put — Shao's "nearly unanimous, mostly incorrect" in miniature.
- **followed the panel majority** counts switches that landed on the majority of the votes the judge actually saw (committed in its `.r2.input.jsonl`): conformity, whether or not it was right.
- **no answer**: blank (unparseable) answers per round. They are abstentions — not votes, not switches — and were not shown to other judges.
- **ties**: an even split among those who answered is no decision; counted as not correct in majority accuracy, excluded from share statistics.

## Caveats

- Illustration, not replication: no human groups, a routing task instead of Wason, n=120 (40 hard). Ground truth for routing is by construction.
- One deliberation prompt, one round; the panel seen is round-1 votes, so judges do not see each other's revisions.
- Judges without a text prompt (zero-shot NLI) keep their round-1 vote in the round-2 panel; this is stated per dataset above.
