# Jury consensus audit — pre-registered plan

**Issue:** [#39](https://github.com/kunko-ai-labs/judge-audit/issues/39) · **Status:** round 1 published; round 2 pre-registered before any call was made (tag `jury-consensus-freeze`), amended after an independent review (§6, tag `jury-consensus-freeze-2`), rerun, and published in [jury-consensus.md](jury-consensus.md).

## 1. Why

Two recent papers say the same thing about agent juries:

- **Shao (2026)**, *Language-model groups overstate consensus when replaying human deliberation on a reasoning task* ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)): LLM groups replaying 100 human Wason deliberations overstated consensus by 34–44 percentage points; reasoning-mode groups "agreed nearly unanimously, mostly on incorrect answers"; "simulated consensus did not track collective accuracy".
- **Huang et al. (2026)**, *Counterfactual Graph for Multi-Agent LLM Calibration* ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)): treating panel agreement as evidence "can fail after agents communicate" — communication induces correlated failures and false consensus.

judge-audit measures per-judge calibration. This audit adds the other half: **agreement and calibration on the same data, same yardstick**, so a reader can see whether a jury's vote share is a confidence score or a decoration.

It is an illustration of the papers' lesson on an agent jury, not a replication: no human groups, a routing task instead of Wason.

## 2. Round 1 — independent votes (done, no new call)

Every judge in the [Arena](arena-2026-09.md) already voted independently on the same four datasets. `scripts/consensus_report.py` reads those checkpoints side by side and writes [consensus-2026-09.md](consensus-2026-09.md): pairwise agreement, unanimity, majority accuracy vs best single judge, vote share when right vs wrong, declared confidence of wrong majorities, and **vote share used as a confidence score** (ECE, zero-error coverage) next to each judge's declared confidence. It also enumerates every three-judge jury to show how much the headline depends on who sits on the jury.

Panel at freeze: `jev`, `claude-sonnet-4.5`, `deberta-nli`, `deepseek-r1`, `gemma4`, `llama-3.3-70b`, `llama32` (every judge with a complete run on the dataset). A judge finishing its Arena run later joins the round-1 panel and the round-2 panel shown to others; the report header lists who was in.

## 3. Round 2 — deliberation (pre-registered)

**Datasets:** `router-bare` and `router-described` (120 rows each: 40 easy, 40 hard, 40 adversarial). Both, so the result is not an artefact of the uninformative bare-label prompt that the [ablation](audit-jev-router-ablation.md) exposed.

**Protocol** (`scripts/jury_deliberate.py`): each judge receives the original row with the other panel members' round-1 decision and confidence appended to `state`, anonymised as "Judge A…F", order shuffled with a fixed seed per row, and the instruction "You may keep or revise your answer. Give your own decision and confidence." Same questions, same adapter, same prompt path, same resumable driver as round 1; what each judge saw is committed as `docs/runs/jury/<dataset>/<slug>.r2.input.jsonl`, what it answered as `<slug>.r2.ckpt.jsonl`.

**Who re-votes:** every panel judge that reads a text prompt — `jev`, `claude-sonnet-4.5`, `deepseek-r1`, `gemma4`, `llama-3.3-70b`, `llama32`, and `gemini-3-flash` if its Arena run is complete. `deberta-nli` cannot read a deliberation prompt (zero-shot NLI over the options) and keeps its round-1 vote in the round-2 panel; it is shown to the others as a voter.

**Metrics** (`scripts/jury_report.py`, deterministic, no LLM in the measurement), round 1 → round 2:

- panel: pairwise agreement, unanimous (and unanimous-wrong), majority accuracy, vote share when right vs wrong, vote-share ECE and zero-error coverage — all rows and the 40 hard rows;
- per judge: accuracy, hard-task accuracy, ECE, mean confidence when wrong, number of switched votes, switches to correct vs to wrong, switches that landed on the other judges' round-1 majority (conformity).

**Predictions, written before the runs** (to be confirmed or refuted; we publish either way; scoring thresholds in §6):

1. Pairwise agreement and unanimity rise in round 2 on both datasets.
2. On `router-bare`, majority accuracy on the hard tasks does not rise materially (the prompt has no information to converge on); the 3B model follows the panel.
3. On `router-described`, judges that were already right keep their vote; some wrong judges switch to the majority, so majority accuracy rises modestly.
4. Mean confidence when wrong goes **up** in round 2 for chat models (agreement read as evidence) — the effect Huang et al. describe.

**Not measured:** more than one round; judges seeing each other's revisions; humans.

## 4. Caveats carried into the report

- Synthetic, seeded datasets; ground truth for routing is by construction (difficulty labels), not validated by executing the routed tasks. n=120 per dataset, 40 per subset — subset rows are indicative.
- One deliberation prompt. A different wording would move the numbers; that is a finding about prompts, not a fix for the mechanism.
- Ties in an even panel go to the alphabetically first option.
- Local models run through Ollama on a laptop; hosted models through their vendors' APIs with credentials that never enter the repo, the checkpoints or the logs.

## 5. Outputs

| File | What |
|---|---|
| `scripts/consensus_report.py` → `docs/consensus-2026-09.{md,json}` | round 1, recomputed and diffed in CI |
| `scripts/jury_deliberate.py` → `docs/runs/jury/<dataset>/<slug>.r2.{input.jsonl,ckpt.jsonl,md,json}` | round 2 inputs and raw answers |
| `scripts/jury_report.py` → `docs/jury-consensus.{md,json}` | round 1 vs round 2, recomputed and diffed in CI |

## 6. Amendments (2026-09-21, after review, before the rerun)

The first round-2 run was reviewed by an independent agent before publication and discarded. What changed, and why — all fixed **before** the rerun, so the rerun is pre-registered under these rules:

1. **Blank answers are abstentions.** Two chat models returned unparseable answers on 6–23 router rows in round 1 (recorded as wrong, confidence 0, per the single-judge house rule). The first run showed them to other judges as `Judge C:  (confidence 0.00)`. Now a blank answer is not a vote: it is not shown in the deliberation prompt, it is not counted in agreement, unanimity or majority, and a switch is only counted between two non-blank answers. Reports show *no answer* per judge and round.
2. **Ties are no decision.** With an even panel the original rule (alphabetically first option) always favoured `route_easy`, the wrong answer on every hard task, and it alone moved hard-task majority accuracy between 15 % and 32.5 %. A tie now counts as not correct in majority accuracy, is reported as a tie, and is excluded from share statistics and vote-share ECE.
3. **The panel is frozen** in `docs/runs/jury/panel.json` (8 judges: the 7 at the original freeze plus `gemini-3-flash`, whose Arena run completed before the rerun). Every re-voting judge sees the same panel; in the first run six judges had re-voted before Gemini existed and saw six votes while Gemini saw seven. `scripts/jury_deliberate.py --check` regenerates every committed input from the frozen panel and CI diffs it.
4. **"Followed the panel majority"** is scored against the votes each judge actually saw (`_meta.panel_seen` in its committed input), not against the whole panel.
5. **Scoring thresholds for the predictions**, fixed here: (1) agreement rises *and* unanimity does not fall on both datasets; (2) hard-task majority accuracy rises by fewer than 10 points *and* the 3B model's switches land on the majority it saw at least half the time; (3) switches to a wrong answer ≤ 5 % of re-votes *and* majority accuracy does not fall; (4) mean confidence when wrong rises in more than half of the chat-model × dataset cells.

Nothing else changed: same datasets, same prompt wording, same seed, same adapters, same metrics.
