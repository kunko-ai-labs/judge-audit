# Jury consensus audit — plan

**Status:** planned · **Branch:** `feature/jury-consensus-audit` · **Issue:** #39 ([US-004-002], EP-004)

## 1. Why

Two recent papers make the same point from different angles, and both point
straight at what Judge Audit measures:

- **Shao (2026)** — *Language-model groups overstate consensus when
  replaying human deliberation on a reasoning task*
  ([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)).
  LLM groups replaying 100 human Wason deliberation groups overstated
  consensus by **34–44 percentage points** across scoring definitions.
  Reasoning-mode groups "agreed nearly unanimously, **mostly on incorrect
  answers**", and "simulated consensus did not track collective accuracy".
- **Huang et al. (2026)** — *Counterfactual Graph for Multi-Agent LLM
  Calibration* ([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)).
  "Multi-agent LLM systems often treat agreement as evidence: when many
  agents in a panel give the same answer, that answer is assumed to be more
  reliable. We show that this assumption can fail **after agents
  communicate**. Communication can induce correlated failures and false
  consensus, so the same vote share may reflect reliable agreement in one
  topology but over-confidence in another."

The lesson for anyone building agent juries: **inter-judge agreement is not
calibration, and post-communication agreement is evidence of even less.**
Judge Audit already measures per-judge calibration (ECE, reliability
diagrams, accuracy–coverage). This audit adds the missing half: measure
agreement *and* calibration together, on the same dataset, and show they can
point in opposite directions.

## 2. What we will do

Run a 3-judge jury over the router task and compare **agreement between
judges** with **accuracy of the jury**, in two rounds:

- **Round 1 — independent votes.** Each judge sees the routing task and
  votes `route_easy` / `route_strong` with a confidence, independently.
- **Round 2 — deliberation.** Each judge sees the other two judges' round-1
  votes *and* confidences, then may revise its vote. This mirrors the
  communication step Huang et al. flag as the moment agreement stops being
  evidence.

Expected headline result (to be confirmed or refuted by the runs):

| subset (40 cases each) | inter-judge agreement | jury (majority) accuracy |
|---|---|---|
| clean-easy | ~100% | ~100% |
| clean-hard | ~100% | ~0% |

Same agreement, opposite accuracy. That table *is* the argument.

## 3. How we measure confidence

**We use the confidence the judge declares. Nothing else.**

- **Jev** (`judges/jev.py`): confidence is **P(chosen option)** from the
  per-option probability distribution returned by the `evaluate` API — the
  model's actual probabilistic claim. TypeSafe's separate `confidence`
  statistic is preserved in `raw` for analysis, not used as the audit input.
- **LLM-as-judge** (`judges/llm.py`): confidence is **verbalized** — the
  model writes a number in its JSON answer ("tell me how sure you are").
  The literature and our own audits show verbalized confidence is often
  poorly calibrated; measuring that gap is the point.
- **No logprobs.** Black-box judges (Jev via gateway, chat models via
  Bedrock) do not expose token logprobs, and token logprobs are not decision
  confidence anyway.
- **No invented confidence.** Per house rules, a judge adapter never
  fabricates confidence: an unparseable answer counts as a wrong,
  zero-confidence decision, and unknown confidence is reported, not imputed.

What the audit *produces* from declared confidence: empirical calibration —
ECE, reliability diagrams, and the metric that matters most here, **mean
declared confidence on wrong answers** (the "0.98 confident and wrong"
number). Calibration is the *output* of the audit, never an input.

## 4. Dataset

Reuse `examples/task-routing/labels.jsonl` (120 cases):

- **clean-hard** (40 cases, `difficulty=hard`, `attack=clean`): designed to
  need `route_strong`. This is the substrate — the router audit showed a
  judge can be 100% wrong here at 0.93–1.0 confidence.
- **clean-easy** (40 cases): the contrast set, where agreement and accuracy
  coincide.

Ground truth is **by design** (difficulty labels), not validated by executing
the routed tasks with cheap vs strong models. This caveat is carried into
the report; it does not invalidate the agreement-vs-accuracy comparison,
which is the point of the experiment.

## 5. Jury composition

**Heterogeneous by design:** Jev (via Vercel AI Gateway) + 2 LLM judges via
Bedrock through `judges/llm.py` (any chat models; cheap ones are fine — the
hypothesis is about the jury mechanism, not frontier capability).

Rationale: same-model/different-prompt juries are the documented failure
mode (Smit et al., ICML 2024, "Should we be going MAD?" — model diversity
helps, debate does not reliably beat ensembling at equal cost). Three clones
agreeing would prove nothing; three *different* judges agreeing while wrong
is the uncomfortable result.

## 6. Metrics

Per round, per judge, per subset:

- pairwise agreement rate (3 pairs) and unanimous-agreement rate
- majority-vote accuracy (jury accuracy)
- per-judge accuracy, ECE (flagged as noisy at n=40), mean confidence on
  wrong answers
- agreement delta and accuracy delta round 1 → round 2 (did deliberation
  raise agreement without raising accuracy?)

All metrics deterministic — no LLM in the measurement (house rule).

## 7. Outputs

- `docs/runs/jury-consensus-r1.ckpt.jsonl` — one row per judge × case:
  `idx`, question, judge id, decision, confidence, latency, cost, raw
  probabilities / parsed answer.
- `docs/runs/jury-consensus-r2.ckpt.jsonl` — same, plus the round-1 votes
  each judge saw before revising.
- `docs/jury-consensus.md` — report with the agreement-vs-accuracy table,
  per-judge calibration, and the caveats in §8.
- `scripts/audit_jury.py` — resumable runner (same pattern as
  `scripts/audit_router.py`); protocol constants documented in the script
  header.

## 8. Caveats (stated upfront, published with the results)

1. This **illustrates** Shao (2026), it does not replicate it: no human
   groups here, different task (routing, not Wason), n=40 per subset.
2. Ground truth is by design; a follow-up should validate it by executing
   the routed tasks with cheap and strong models.
3. ECE at n=40 is indicative, not precise — the stable headline metrics are
   agreement rate, majority accuracy, and mean confidence on errors.
4. One juror family (Jev) was already audited on this dataset; the
   independent value comes from the two LLM judges and the deliberation
   round.

## 9. Execution notes

- Model runs execute **locally** (maintainer's machine, Bedrock keys).
  Keys never enter the repo, the checkpoints, or any log.
- Estimated cost: 3 judges × 80 cases × 2 rounds = 480 judgments on cheap
  models — cents, not dollars. Jev leg: 160 judgments (~$0.003 at router-audit
  rates).
- After runs: analysis script → `docs/jury-consensus.md` → PR
  `feature/jury-consensus-audit` → `develop` → issue #39 closed on merge.
