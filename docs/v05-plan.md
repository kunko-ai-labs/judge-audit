# v0.5 study — pre-registered plan (DRAFT)

**Issue:** [#91](https://github.com/kunko-ai-labs/judge-audit/issues/91) · **Status: DRAFT. Not frozen; no study call has been made.** The maintainer settled decisions D1–D6 on 2026-09-29 (table at the end). The plan is frozen (tag `v05-plan-freeze`) only when the pre-freeze work in §12 is merged; after the first study call nothing in §3–§10 changes without a dated amendment in §11.

Inputs: [power analysis](v05-power.md) on the [pilot's estimates](v05-pilot-estimates.md) (protocol: [v05-pilot.md](v05-pilot.md), checkpoints: `docs/runs/v05-pilot/`); the method notes in [docs/v05/](v05/README.md).

## 1. Question

> Can a judge's declared confidence decide what you automate? How much of the traffic can it handle alone at an error rate you can live with, and can that rate be certified?

## 2. Hypotheses

- **H1 (primary, within model).** For the same model on the same rows, verbalized confidence ranks the model's own errors worse (lower AUROC of confidence for correctness) than a confidence read another way: token log-probability (**H1-lp**, Qwen3-8B, the only model whose token probabilities a judge here reads) and self-consistency (**H1-sc**, every chat model in the roster).
- **H2 (secondary).** Jev's native probability ranks its errors better than each chat model's best confidence method (§6 defines "best").

Every confirmatory test, what counts as support, and the prediction for each are listed in §6. The pilot is not evidence for or against any of them: it ran on train rows, with one open model, to size the study, and its AUROCs are planning inputs only. Results are published whether or not the predictions hold; a difference the test does not resolve is reported as not resolved, not as no difference.

## 3. Datasets, rows and labels

| dataset | file | rows | distinct texts | options | licence |
|---|---|---:|---:|---:|---|
| BANKING77 test | `examples/banking77/labels-test.jsonl` | 3,080 | 3,079 | 77 | CC BY 4.0 |
| CLINC150 banking + credit cards + out-of-scope | `examples/clinc150/labels-test-banking-credit.jsonl` | 1,900 | 1,900 | 31 | CC BY 3.0 |

- **Every row is judged; every text counts once.** Texts are grouped by the repository's normalisation, lower case with runs of whitespace collapsed (`scripts/fetch_real_datasets.py`, `normalise`); BANKING77's rows 1441 and 1461 then form one group (same label). Resampling and certification splits are by group.
- **Rows without a usable answer**, per judge and method, follow the pilot's rules ([v05-pilot.md](v05-pilot.md) §5): a row with no answer or no confidence counts as wrong in accuracy and is left out of that method's AUROC, ECE and certification, and is counted in every table. In a paired test each method is scored on its own usable rows inside each resample.
- **Labels.** The published labels are primary. About 14 % of BANKING77 **train** queries were flagged as possibly mislabelled by automated detection (Ying & Thomas 2022); the test split's rate is unknown and a label error counts as a judge error, so it floors every error rate. **D4 (decided):** label noise is not measured before the runs; every certified bound and error rate is stated as including it. The two-annotator relabel of #86 is done after the runs, as a sensitivity analysis, never the primary label set.
- The CLINC150 subset is the draft of #99, frozen here as listed. The held-out slice of #106 is not part of this study.

## 4. Roster and confidence methods

| judge | runs where | methods | role |
|---|---|---|---|
| Qwen3-8B, 4-bit, MLX, pinned `545dc4251c05440727734bcd94334791f6ab0192` | the maintainer's machine | token log-probability; verbalized (T = 0); self-consistency (k fixed by the rule of [v05-pilot.md](v05-pilot.md) §5b: 10 or 5, T = 1); thinking off in all three, served as in the pilot | H1-lp, H1-sc, H2 |
| Jev (`jev-latest`, TypeSafe endpoint) | hosted | native probability of the chosen option | H2 |
| `gemini-3.6-flash` | hosted, OpenAI-compatible endpoint | verbalized (T = 0); self-consistency (k = 5, T = 1). No token log-probability: no judge here reads a hosted model's ([confidence methods](v05/confidence-methods.md)) | H1-sc, H2 |
| Laya, pinned `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`, budgets 640 / 1,024 | the maintainer's machine | probability of the chosen option | context only (budgets outside the shipped ones; a softmax temperature clamped by the library) |
| Claude | — | — | **out of this study (D5)**; may be added later as exploratory, under its own amendment |

GPT-5 and other OpenAI proprietary models are out: no key. Prompts are those the pilot ran (`prompt_sha256` in each checkpoint header) and do not change. The Qwen3 server records the served model and the mlx versions but not the weights revision; the pin rests on offline serving with the cache's `refs/main` checked against it before each server start, as in the pilot.

## 5. Repeats

One primary run per judge and method; every confirmatory test uses it. Exploratory (#90): two more runs of Jev and of Qwen3 verbalized on BANKING77, reported as between-run spread next to the primary numbers, never replacing them.

## 6. Confirmatory tests

**Confidences are compared exactly** as recorded in the checkpoints, never rounded: the pilot's 1e-6 rounding merged 205 distinct log-probability confidences into 21 levels, 146 of them into one tie at 1. **The statistic.** For methods A and B: AUROC(A) − AUROC(B), each the AUROC of that method's confidence for **its own** correctness (ties one half), on its usable rows. The read-outs make different decisions (in the pilot, Qwen3 verbalized and log-probability agree on 80 % of decisions and on correctness for 88 % of rows), so DeLong's shared-outcome variance does not apply.

**The test.** A two-sided paired bootstrap clustered by text (`paired_difference_ci`: each resample draws texts once and scores both methods on them), 10,000 resamples, seed 2026, with a percentile p-value from the same resamples: 2 × min(1 + #{Δ* ≤ 0}, 1 + #{Δ* ≥ 0}) / (B + 1), capped at 1, where B counts only the resamples in which both AUROCs are defined (the others are counted and reported, not used). The p-value function is added with tests before the freeze (§12). **Holm** across every test in the table below at family-wise α = 0.05. A test is **resolved** when its Holm-adjusted p is below 0.05 and its difference has the predicted sign.

| id | comparison | dataset | predicted sign | counts as support for |
|---|---|---|---|---|
| T1 | Qwen3: log-probability − verbalized | BANKING77 | + | H1-lp, with T2 |
| T2 | the same | CLINC150 | + | H1-lp, with T1 |
| T3, T4 | Qwen3: self-consistency − verbalized | BANKING77, CLINC150 | + (see D1) | H1-sc for Qwen3, both needed |
| T5, T6 | Gemini: self-consistency − verbalized | BANKING77, CLINC150 | + (see D1) | H1-sc for Gemini, both needed |
| T7 | Jev − Qwen3's best method | CLINC150 | + | H2 for Qwen3 |
| T8 | Jev − Gemini's best method | CLINC150 | + | H2 for Gemini |

- **"Best method"** of a chat model is the one with the highest AUROC point estimate on **BANKING77**; T7–T8 then test it on **CLINC150** only, so the choice and the test never see the same rows.
- **H1** is supported for a model only when every test listed for it is resolved; **H2** is reported per model.
- **Predictions.** T1, T2 and T7, T8: positive and resolved. T3–T6: at k = 5 the pilot's ties (82 % of Qwen3's rows unanimous) turn a latent advantage of 0.05 into an observed deficit of 0.014–0.019 in the power model (§ B), so at k = 5 self-consistency is predicted **not** to beat verbalized, for reasons of resolution, not of the model; this is the prediction for T5–T6 (Gemini, k = 5) and for T3–T4 if the §5b rule keeps k = 5. If it adopts k = 10, T3–T4's prediction is stated in the same commit that sets the constants from the k = 10 run, before the freeze.
- **Secondary, not confirmatory:** accuracy (Wilson; McNemar on discordant rows); ECE (10 equal-width bins) and MCE, paired by the same bootstrap; AURC; Brier; NLL (infinite counts printed); zero-error coverage; certified coverage at risk (§7) per judge and method, reported side by side without a test; cost and latency. No composite score. Everything not in the table above is exploratory and labelled so.

## 7. Certification

`coverage_at_risk_crossfit`: two halves split by text group, **seed 2026** (the spread over seeds 2027–2036 is reported as secondary); on each, the threshold is certified on one half with an exact one-sided 95 % bound and applied unchanged to the other, and the test halves are pooled.

What the pilot suggests (train rows, planning only; the committed source is the top-slice table of [v05-pilot-estimates.md](v05-pilot-estimates.md)): at the top of each ranking (the smallest set of whole tie levels holding at least 10 % of the rows) no read-out erred below 5 %. Jev: 8 of 142 (5.6 %, two-sided 95 % interval 2.5–10.8 %); Qwen3 log-probability, compared exactly: 2 of 31 (6.5 %, 0.8–21.4 %); Qwen3 verbalized: 12 of 71 (16.9 %); Qwen3 self-consistency: 80 of 253 (31.6 %). Certifying 1 % or 2 % is therefore unlikely for any judge.

Rows one set must hold to certify, with 0 / 1 / 2 / 5 errors (exact, one-sided 95 %; `rows_to_certify` in `scripts/v05_power.py`): 1 %: 299 / 473 / 628 / 1,049 · 2 %: 149 / 236 / 313 / 523 · 5 %: 59 / 93 / 124 / 208 · 10 %: 29 / 46 / 61 / 103.

- **D2 (decided) — targets:** **1 %, 2 %, 5 % and 10 % in one table**, every row printed with its plain reading ("at most 1 in 10 automated decisions wrong" next to 10 %), none singled out as the headline.
- **D3 (decided) — where the fixed sequence starts.** As implemented (#98), the walk starts at the smallest cut that could pass and stops at the first failure; with continuous confidences it certifies with probability (1 − r′)^m₀, about 47 % when the true rate r′ is a quarter of the target ([power § A2](v05-power.md)). Decided: start at the first cut holding the rows needed to certify with **2 errors** (628 / 313 / 124 / 61). The start depends only on row counts, never on labels, so the guarantee is unchanged; it becomes a pre-registered parameter of `coverage_at_risk`, implemented with tests and A2 rerun on it before the freeze (§12). The #98 start is **not** reported as a second read-out. Consequence: at 1 % a CLINC150 half (950 rows) cannot certify by construction (628 rows is more than the 503 a half can automate at 1 % in A2's setting); the table says so rather than printing 0 %.

## 8. Smallest detectable differences (declared before the runs)

From [v05-power.md](v05-power.md) on the pilot's constants, 80 % power, α = 0.05 before Holm, one method pair per row. **Holm makes each larger:** at its first step a test is judged at α/m, which multiplies every MDE by (z₁₋α/2m + z₀.₈) / (z₀.₉₇₅ + z₀.₈) = **1.28** with the 8 tests of §6; the worst H1-lp cell then goes from 0.040 to about 0.050 on BANKING77 and from 0.050 to about 0.064 on CLINC150, and H2's CLINC150 MDE to about 0.064. These come from DeLong's variance on one shared set of decisions; the confirmatory test (§6) scores each method on its own decisions, so they are approximations.

| tests | pair and model cell | BANKING77 (n = 3,079) | CLINC150 (n = 1,900) |
|---|---|---:|---:|
| T1, T2 (H1-lp) | verbalized vs log-probability: no ties (the model has no tied-vs-continuous cell), accuracy 62–64 %. The registered latent ρ is 0.47 (→ 0.45); compared exactly, without the protocol's 1e-6 rounding, it is 0.36 [0.19, 0.52] (the estimates' sensitivity table, a deviation found after the constants were set). Declared: the ρ 0.40 cell, slightly optimistic against the exact 0.36 (interpolating the ρ 0.40 and 0.45 cells gives about 0.032 on BANKING77), and the ρ 0 cell as the bound | 0.031 (ρ 0.40) to 0.039–0.040 (ρ 0) | 0.039–0.040 (ρ 0.40) to 0.050 (ρ 0) |
| T3–T6 (H1-sc) | verbalized vs self-consistency: 4 and 5 levels, accuracy 62–64 %, latent ρ 0.40 | 0.029 | 0.036–0.037 |
| T7, T8 (H2) | different judges, ρ unknown: no ties, ρ 0 (the conservative cell), accuracy 62–64 % | — | 0.050 |
| any, conservative | accuracy 69 % (Wilson upper bound), ρ 0 | 0.035 (tied) / 0.041 (no ties) | 0.045 / 0.052 |
| paired ECE (secondary) | design gaps 0.05 / 0.08, verbalized distribution from the pilot, ρ_C 0.3–0.7 | 0.017–0.021 | 0.022–0.026 |

Stated with the numbers: in the tied H1-sc cells the modelled gap itself is negative (−0.014 to −0.019), so at k = 5 those tests are sized for a difference that points the other way (D1). The accuracies are Qwen3's on train; a more accurate judge has fewer errors and a larger MDE.

## 9. Cost ceiling and time

Per-call costs from committed checkpoints: Gemini, from its 21 pilot rows before the quota stop (`docs/runs/v05-pilot/llm-gemini-3.6-flash.ckpt.jsonl`: 857 input and 24.5 visible output tokens, $0.000318 per call at list price); Jev, $0.0133 for 308 rows (`jev.ckpt.jsonl`). Gemini may bill reasoning tokens that the recorded usage does not show; the provider's billing console is the check and is reported next to the checkpoint's cost.

| item | calls | estimate |
|---|---:|---:|
| Gemini verbalized, both datasets | 4,980 | $1.58 |
| Gemini self-consistency, k = 5 | 24,900 | $7.92 |
| Jev, primary (4,980 rows) + 2 exploratory repeats on BANKING77 (6,160) | 11,140 | $0.48 |

- **D6 (decided) — ceiling: $30** (three times the $9.98 Gemini + Jev estimate, for unseen reasoning tokens). A run that would cross it stops; going on needs a dated amendment.
- **Local time**, from the pilot's per-row latencies on the maintainer's 16 GB machine, sequential: verbalized ≈ 5.5 h, self-consistency k = 5 ≈ 13.0 h, log-probability ≈ 13.3 h, Laya ≈ 0.5 h, the two exploratory Qwen3 repeats ≈ 6.9 h: about 39 h; k = 10 adds about 13 h. The log-probability self-check's uncached reference path needed about 12 GB and swapped on 16 GB ([v05-pilot.md](v05-pilot.md) §4.1); the check runs on 5 rows.

## 10. Execution and stopping rules

- Order: local runs first (no cost), then Jev, then Gemini; each through `scripts/audit_resumable.py`, checkpoints committed under `docs/runs/v05/`.
- The pilot's stop rules apply per run: more than 5 % unparsed rows among the first 40 (or failed samples among the first 200), or a failed `logprob_selfcheck.py`, stops the run pending an amendment.
- A provider that fails for good (quota, deprecation) leaves its rows missing; they are counted, and its tests are run on the rows it answered only if it answered at least 95 % of a dataset; otherwise its tests are reported as not run.

## 11. Deviations

Dated amendments, committed before the call they govern. None yet.

## 12. Before the freeze

1. ~~The maintainer settles D1–D6~~ (done 2026-09-29).
2. Code, with tests, reviewed: the percentile p-value from `paired_difference_ci`'s resamples and Holm (§6); D3's start parameter for `coverage_at_risk`, and power § A2 rerun on it (§7).
3. D1: the k = 10 pilot run ([v05-pilot.md](v05-pilot.md) §5b), its estimates, and the constants commit its rule prescribes; T3–T4's prediction stated with it.
4. Gemini's quota: the provider account must allow the ~29,900 calls (billing enabled); its billing-console figure for the pilot reported in `docs/runs/v05-pilot/run-notes.json`.
5. An external human reviewer is sought. **None has read this plan yet**; if none does before the first study call, the published report says so.

## Decisions (settled by the maintainer, 2026-09-29)

| id | question | decision |
|---|---|---|
| D1 | self-consistency k | measure k = 10 on the 308 pilot rows first ([v05-pilot.md](v05-pilot.md) §5b, amended before the run); its pre-registered rule fixes k for Qwen3; hosted models keep k = 5 |
| D2 | certification targets | 1 %, 2 %, 5 % and 10 % in one table, each with its plain reading, none as the headline |
| D3 | where the fixed sequence starts | at the 2-error cut, a pre-registered parameter; power § A2 rerun on it before the freeze |
| D4 | label noise | not measured before the runs; bounds stated as including it; the #86 relabel after the runs as a sensitivity analysis |
| D5 | Claude | out of this study |
| D6 | cost ceiling | $30 |
