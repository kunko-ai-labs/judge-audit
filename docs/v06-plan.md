# v0.6 study — pre-registered plan (DRAFT)

**Issue:** [#132](https://github.com/kunko-ai-labs/judge-audit/issues/132) · Epic [#130](https://github.com/kunko-ai-labs/judge-audit/issues/130) · **Status: DRAFT, not frozen.** Nothing here governs a run until the maintainer settles the decisions at the end, the pilot (§9) has sized the study, and the plan is tagged `v06-plan-freeze` before the study's first call. Until then no judge is run on any test row of the datasets below.

Method notes carried over from v0.5: [v05-plan.md](v05-plan.md) (rows without a usable answer, certification, resampling), [docs/v05/](v05/README.md).

## 1. Question

> When a decision model says "95 %", does that still mean 95 % in Spanish and Catalan? And a confidence threshold certified on English traffic: does it keep its error when the same decisions arrive in another language?

The study measures the open decision models released since September 2026 and Jev on the **same items in three languages**, so that any difference is the language, not the task.

## 2. Hypotheses

- **H1 (primary, transfer).** A confidence threshold certified on English rows at a 5 % target error, applied unchanged to the **same decisions** in Catalan, admits an error above 5 %. Tested per judge (§6, T1–T3); the Spanish counterpart is T4–T6.
- **H2 (secondary, overconfidence).** Each judge's overconfidence (mean declared confidence minus accuracy, on the same items) is larger in Spanish than in English and larger in Catalan than in Spanish.
- **E1 (exploratory).** For Decision 2.0, the vendor's `confidence` field (normalised entropy, `1 − H(p)/log K`, per its code) ranks the model's errors differently from P(chosen option); reported as the paired AUROC difference, no test.

Results are published whether or not the predictions hold; a difference the test does not resolve is reported as not resolved, not as no difference.

## 3. Datasets, rows and labels

| dataset | locales | rows per locale | options | licence |
|---|---|---:|---:|---|
| MASSIVE 1.1 test (`examples/massive/`, #133 / #140) | `en-US`, `es-ES`, `ca-ES` | 2,974 | 60 (`cooking_query` is never the label in test) | CC BY 4.0 (archive pinned by sha256) |

- **Parallel items.** The three locales are the same items, aligned by MASSIVE `id`: no id missing in any locale and no intent differing across locales (#140). Every resample and every certification split is **by item**, so an item's three languages always fall on the same side.
- **Questions and option descriptions in English** in the primary arm (Galtea's Spanish/Catalan study found translated rubric questions cost Jev up to 13 points of accuracy). A translated-criteria arm is decision D3.
- **Labels** are MASSIVE's, carried from SLURP's annotation through localisation; a label or localisation error counts as a judge error in every locale it affects. The upstream card identifies localisers and judges by crowd-worker IDs, and `ca-ES` was added in 1.1 without a published localisation method: the report does not call the data professionally translated. Caveat printed with every table: translated parallel data, not native traffic.
- **Localisation check.** MASSIVE keeps three judges per localised row ("does the sentence match the intent?"). A majority answered no for 0 `es-ES` and 19 `ca-ES` test rows (at least one no: 76 and 120). Primary: every row. Sensitivity, declared here: every metric and test recomputed without the majority-no rows of any locale, removing the item in all three locales.
- **Repeated texts** (repository normalisation): distinct texts per locale `en-US` 2,970, `es-ES` 2,944, `ca-ES` 2,933; `ca-ES` rows 17 and 1426 share a text with two labels (`calendar_query`, `datetime_query`). Resampling is by item; a repeated text is not merged across items.
- Rows without a usable answer follow v0.5 §3.

## 4. Roster and confidence

| judge | where | confidence audited | role |
|---|---|---|---|
| Decision 2.0 Kai-0.6B, pinned `cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764` (#131) | maintainer's 16 GB machine | P(chosen option); the `confidence` field kept for E1 | H1, H2, E1 |
| Laya multilingual (mmBERT backbone), pinned at freeze | maintainer's machine | P(chosen option) | H1, H2 |
| Jev (`jev-latest`, TypeSafe endpoint) | hosted | native P(chosen option) | H1, H2 |
| decider-2b, Strands Decider 2B, Clef-flash (#137) | 16 / 24 GB machines | P(chosen option) | D2: primary or exploratory |
| a chat model (verbalized confidence) | hosted | verbalized | D4 |

Every local model is pinned to a revision sha recorded in its checkpoint header; a model the vendor changes after the freeze is not updated without an amendment. A model run quantized to fit is labelled as that variant.

## 5. Repeats

Local decision models are deterministic (Kai: identical outputs across calls in the plumbing check); one run each. Jev: one primary run; between-run spread from v0.5 applies.

## 6. Confirmatory tests

**Transfer test (H1).** Items are split in two halves by item, seed 2026. On half A, the English rows certify a threshold at a 5 % target (`coverage_at_risk`, exact one-sided 95 %, start rule D3 of v0.5). On half B, the rows at or above that threshold are counted in the target language; the error among them gets an exact one-sided 95 % **lower** bound. Then the halves swap and the two half-B counts are pooled. **Resolved** when the pooled lower bound exceeds 5 %, after Holm across T1–T6 at family-wise α = 0.05. English half-B rows above the same threshold are reported beside it as the control.

| id | judge | target locale | prediction |
|---|---|---|---|
| T1 | Kai-0.6B | `ca-ES` | resolved (error above 5 %) |
| T2 | Laya multilingual | `ca-ES` | not resolved |
| T3 | Jev | `ca-ES` | resolved |
| T4 | Kai-0.6B | `es-ES` | not resolved |
| T5 | Laya multilingual | `es-ES` | not resolved |
| T6 | Jev | `es-ES` | not resolved |

*These predictions are placeholders until the pilot (§9); they are fixed at the freeze and not changed after.* If English certifies no threshold for a judge at 5 %, its tests are reported as not run, with the reason.

**Overconfidence (H2).** Per judge, overconfidence = mean confidence − accuracy on usable rows; the paired differences es − en and ca − es, each with a two-sided bootstrap interval clustered by item (10,000 resamples, seed 2026). Secondary, no Holm: reported as resolved when the interval excludes 0.

**Secondary, not confirmatory:** per locale, accuracy (Wilson), AUROC, ECE and MCE, Brier, certified coverage at 1 / 2 / 5 / 10 % (v0.5 D2), the high-confidence error rate of #134 if merged before the freeze, cost and latency. No composite score.

## 7. Certification

As v0.5 §7 (cross-fit, seed 2026, targets 1 / 2 / 5 / 10 %, start at the 2-error cut), run separately per locale. With about 1,487 items per half, 1 % cannot certify by construction (628 rows needed at 2 errors is more than a 1 % automation of a half allows in v0.5's A2 setting); the table says so rather than printing 0 %.

## 8. Smallest detectable differences

Filled from the pilot (§9) before the freeze: rows needed for the transfer test to resolve an error of 7.5 % and 10 % above an English threshold at 5 %, and the paired MDE for H2.

## 9. Pilot (before the freeze, train rows only)

The 230 pilot items committed in #140 (up to 4 per intent from MASSIVE **dev**, seed 2026, the same items in the three locales; dev, not train, so a classifier later trained on train has never seen them), every primary judge. Used only to size §8 and to settle D2–D4; no pilot number is evidence for or against a hypothesis. Its protocol, checkpoints and estimates are committed before the freeze, as in v0.5 (`docs/runs/v06-pilot/`).

## 10. Cost ceiling and time

Jev at v0.5's recorded rate ($0.13 per 3,080 rows) on 3 × the test rows is about $0.40; the pilot adds about $0.04. Local models: Kai at about 0.15 s per request is about 25 minutes for the three locales on the 16 GB machine. A chat model in the roster (D4) and any rented GPU (D5) add their own lines, with a ceiling fixed at the freeze.

## 11. Execution and stopping rules

As v0.5 §10: local runs first, then hosted; `scripts/audit_resumable.py`; checkpoints under `docs/runs/v06/`; more than 5 % unparsed rows among the first 40 stops a run pending an amendment.

## 12. Deviations

Dated amendments, committed before the call they govern.

## Decisions for the maintainer (open)

| id | question | recommendation |
|---|---|---|
| D1 | primary target error for H1 | 5 % (certifiable at about 1,487 items per half; 1 % and 2 % stay secondary) |
| D2 | decider-2b, Strands Decider, Clef-flash: primary or exploratory | exploratory in this study; primary in the next, once their adapters are reviewed |
| D3 | a translated-criteria arm | exploratory, Spanish only, translated by the maintainer and marked as such; Catalan only with a native reviewer |
| D4 | a chat model with verbalized confidence | one, exploratory (gemini-3.6-flash, as in v0.5), so decision models are read against a known reference |
| D5 | 27B models (Vega-27B, Clef) | out of this study; a later amendment with a rented GPU in bf16, or a labelled quantized variant on the 24 GB machine |
| D6 | external human reviewer | sought before the freeze; if none reads it, the report says so |
