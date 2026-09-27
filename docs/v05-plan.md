# v0.5 study — pre-registered plan (DRAFT)

**Issue:** [#91](https://github.com/kunko-ai-labs/judge-audit/issues/91) · **Status: DRAFT for the maintainer's review. Not frozen; no study call has been made.** Items marked **DECISION** are open and carry a proposed default; the plan is frozen (tagged `v05-plan-freeze`) only when every one is settled, and nothing in §4–§7 changes after the first study call without a dated amendment in §10.

Inputs: [power analysis](v05-power.md) on the [pilot's estimates](v05-pilot-estimates.md) (protocol: [v05-pilot.md](v05-pilot.md)); the method notes in [docs/v05/](v05/README.md).

## 1. Question

> Can a judge's declared confidence decide what you automate? How much of the traffic can it handle alone at an error rate you can live with, and can that rate be certified?

## 2. Hypotheses and predictions

- **H1 (primary, within model).** For the same model on the same rows, verbalized confidence ranks errors worse (lower AUROC of confidence for correctness) and supports less certified automation than a confidence read another way.
  - **H1-lp:** token log-probability (`logprob`) against verbalized, Qwen3-8B, both datasets. *Prediction:* AUROC(logprob) − AUROC(verbalized) > 0, resolved by the paired test on BANKING77 and on CLINC150.
  - **H1-sc:** self-consistency against verbalized, for every chat model in the roster. *Prediction:* see **DECISION D1**: with k = 5 the pilot's ties (82 % of Qwen3's rows unanimous) turn an assumed latent advantage of 0.05 into an observed deficit of 0.014–0.019 ([power § B](v05-power.md)), so as registered H1-sc at k = 5 is expected to fail for reasons of resolution, not of the model.
- **H2 (secondary).** Jev's native probability against each chat model's best confidence method (the best chosen per model on BANKING77, then tested on CLINC150), paired, AUROC and coverage at risk. *Prediction:* Jev's AUROC is higher than each chat model's best, resolved on at least one dataset.

The pilot is not evidence for or against any of these: it was run on train rows, with one open model, to size the study (its observed AUROCs are reported there as planning inputs only). Results are published whether or not the predictions hold; a difference the paired test does not resolve is reported as not resolved, not as no difference.

## 3. Datasets and n

| dataset | file | rows scored | distinct texts | licence |
|---|---|---:|---:|---|
| BANKING77 test | `examples/banking77/labels-test.jsonl` | 3,080 | 3,079 (rows 1441 and 1461 differ by a leading newline; same label) | CC BY 4.0 |
| CLINC150 banking + credit cards + out-of-scope | `examples/clinc150/labels-test-banking-credit.jsonl` | 1,900 | 1,900 | CC BY 3.0 |

- **n = every row.** Paired AUROC, ECE and accuracy use every distinct text (duplicates aggregated by `aggregate_by_group`). Certification uses `coverage_at_risk_crossfit` (two halves split by distinct text, each half certifying on one and tested on the other, pooled), **split seed 2026**; the spread over seeds 2027–2036 is reported as secondary.
- **Label noise is not measured** (#86: the two-annotator relabel of 500 rows per dataset has not been done). About 14 % of BANKING77 **train** queries were flagged as possibly mislabelled by automated detection (Ying & Thomas 2022); the test split's rate is unknown. A label error counts as a judge error, so it floors every error rate. **DECISION D4.**
- The CLINC150 subset is the draft of #99; this plan freezes it as listed.

## 4. Roster and confidence methods

| judge | how it runs | methods | role |
|---|---|---|---|
| Qwen3-8B, 4-bit, MLX, pinned `545dc4251c05440727734bcd94334791f6ab0192` | local, the maintainer's machine | token log-probability; verbalized (T = 0); self-consistency (k per **D1**, T = 1), all with thinking off, served as in the pilot | H1 (all three read-outs) |
| Jev (`jev-latest`, TypeSafe endpoint) | hosted | native probability of the chosen option | H2 |
| `gemini-3.6-flash` | hosted, OpenAI-compatible endpoint | verbalized (T = 0); self-consistency (k per **D1**, T = 1); no token log-probability (its endpoint rejects the parameter: `logprob_smoke.py`, 2026-09-27) | H1-sc, H2 |
| Laya, pinned `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, budgets 640 / 1,024 | local | probability of the chosen option | context only (budgets outside the shipped ones; a softmax temperature clamped by the library) |
| Claude (**DECISION D5**) | hosted, the maintainer's private provider module | verbalized; self-consistency | H1-sc, H2 if included |

GPT-5 and other OpenAI proprietary models are out: no key. Prompts are the ones the pilot ran (`prompt_sha256` in each checkpoint header) and do not change.

## 5. Repeats

One primary run per judge and method; every primary analysis uses it. Exploratory (#90): two more runs of Jev and of Qwen3 verbalized on BANKING77, to report the between-run spread next to the primary numbers. Repeats never replace the primary run.

## 6. Metrics

- **Primary:** paired AUROC difference (DeLong, two-sided, α = 0.05) for H1 and H2; certified coverage at risk (§7), with the rows automated on the test halves and their exact bound.
- **Secondary:** accuracy with Wilson intervals and McNemar on discordant rows; ECE (10 equal-width bins) and MCE, paired differences by clustered bootstrap; AURC; Brier; NLL (infinite counts printed); zero-error coverage; cost and latency. No composite score.
- **Multiplicity:** H1-lp and H1-sc are two families tested at α = 0.05 each on two datasets; a claim of support needs the test resolved on the dataset named in the prediction. Everything outside §2 is exploratory and labelled so.

## 7. Certification: targets and where the sequence starts

What the pilot shows ([estimates](v05-pilot-estimates.md), train rows, planning only): no read-out's most confident slice was below 5 % error. Jev's top level (46 % of rows at 1.0) erred on 5.6 %, Qwen3 log-probability's top 20 % on about 8 %, Qwen3 verbalized's top level on 17 %. Certifying 1 % or 2 % would then certify nothing for any judge, and the report would read "0 %" everywhere.

Rows one set must hold to certify, with 0 / 1 / 2 / 5 errors (exact, one-sided 95 %): 1 %: 299 / 473 / 628 / 1,049; 2 %: 149 / 236 / 313 / 523; 5 %: 59 / 93 / 124 / 208; 10 %: 29 / 46 / 61 / 103.

- **DECISION D2 — targets.** Proposed: **5 % and 10 % primary**, 1 % and 2 % secondary (reported, expected to certify little). Alternative: keep 1 / 2 / 5 % and accept mostly-zero coverage.
- **DECISION D3 — where the fixed sequence starts.** As implemented (#98), the walk starts at the smallest cut that could pass and stops at the first failure; with continuous confidences it certifies with probability (1 − r′)^m₀, about 47 % when the true rate r′ is a quarter of the target ([power § A2](v05-power.md)). Proposed: start at the first cut holding the rows needed to certify with **2 errors** (628 / 313 / 124 / 61 at 1 / 2 / 5 / 10 %), a new pre-registered parameter of `coverage_at_risk` (the guarantee is unchanged: one fixed sequence, no peeking), implemented with tests and A2 rerun on it **before** the freeze. With halves of 1,540 (BANKING77) and 950 (CLINC150), a 1 % start at 628 rows needs 41 % and 66 % of a half to be automatable, which is a further reason for D2.

## 8. Smallest detectable differences (declared before the runs)

From [v05-power.md](v05-power.md) with the pilot's constants, 80 % power, α = 0.05:

| comparison | cell the pilot matches | BANKING77 (n = 3,079) | CLINC150 (n = 1,900) |
|---|---|---:|---:|
| paired AUROC, verbalized vs self-consistency (tied, 4 and 5 levels) | accuracy 62–64 %, ρ 0.40–0.45 | **0.028–0.029** | **0.036–0.037** |
| same, conservative cell | accuracy 69 % (Wilson upper), ρ 0 | 0.035 | 0.045 |
| paired ECE (design gaps 0.05 / 0.08, verbalized distribution from the pilot) | ρ_C 0.3–0.7 | 0.017–0.021 | 0.022–0.026 |

Limits, stated with the numbers: the power model scores both methods on one shared set of decisions (the pilot's read-outs agree on 80–97 % of decisions); it does not model a tied method against a continuous one (verbalized vs log-probability), whose MDE is expected between the tied and untied cells; the accuracies are Qwen3's on train, and a more accurate judge has fewer errors and a larger MDE.

## 9. Cost ceiling and time

Per-call costs measured in the pilot (Gemini: about 855 input and 24 visible output tokens, $0.00032 at list prices; Jev: $0.000043 per row). Gemini may bill reasoning tokens the recorded usage does not show; the provider's billing console is the check.

| item | calls | estimate |
|---|---:|---:|
| Gemini verbalized, both datasets | 4,980 | $1.60 |
| Gemini self-consistency k = 5 | 24,900 | $7.90 |
| Jev, primary + 2 exploratory repeats (BANKING77) | 11,140 | $0.50 |
| Claude Sonnet 5 verbalized, if included (D5) | 4,980 | ≈ $10 |
| Claude Sonnet 5 self-consistency k = 5, if included | 24,900 | ≈ $50 |

- **DECISION D6 — ceiling.** Proposed: **$40 without Claude** (three times the Gemini + Jev estimate, for unseen reasoning tokens), **$100 with Claude**. A run that would cross it stops; going on needs a dated amendment.
- **Local time** (pilot rates on the 16 GB M4, sequential): verbalized ≈ 5.5 h, self-consistency k = 5 ≈ 13 h, log-probability ≈ 13 h, Laya ≈ 0.5 h: about 32 h of machine time (k = 10 roughly doubles the self-consistency share). The log-probability judge holds about 12 GB resident; the 24 GB Mac is preferred for it.

## 10. Execution, stopping rules and deviations

- Order: local runs first (no cost), then Jev, then Gemini, then Claude if included; each through `scripts/audit_resumable.py`, checkpoints committed under `docs/runs/v05/`.
- The pilot's stop rules apply per run (more than 5 % unparsed rows or samples in the first 40 rows, or a failed `logprob_selfcheck.py`, stops the run pending an amendment).
- A provider that fails for good (quota, deprecation) leaves its rows missing; they are counted, and the judge is reported on the rows it answered only if at least 95 % were, otherwise as incomplete.
- Deviations are dated amendments in this section, committed before the affected call.

## 11. Review

An external human reviewer is sought for this plan before the freeze. **None has read it yet**; if none does before the first study call, the published report says so.

## Decisions for the maintainer

| id | question | proposed default |
|---|---|---|
| D1 | self-consistency k | **k = 10** for Qwen3 (free, ≈ +13 h) and k = 5 for hosted models, with H1-sc's prediction stated for k = 10; or keep k = 5 everywhere and register the expected failure |
| D2 | primary certification targets | **5 % and 10 %** primary; 1 % and 2 % secondary |
| D3 | where the fixed sequence starts | **at the 2-error cut**, as a new pre-registered parameter, A2 rerun before the freeze |
| D4 | label noise before the runs | **relabel the 500-row samples (#86) before the freeze**, or state that certification bounds include label noise |
| D5 | Claude in the roster | through the private provider module, if the maintainer names the model id it expects |
| D6 | cost ceiling | **$40** without Claude, **$100** with |
