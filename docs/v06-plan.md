# v0.6 study — pre-registered plan

**Issue:** [#132](https://github.com/kunko-ai-labs/judge-audit/issues/132) · Epic [#130](https://github.com/kunko-ai-labs/judge-audit/issues/130) · **Status: FROZEN on 2026-10-12 (§12).** The maintainer settled D1–D6 on 2026-10-05, D7–D8 on 2026-10-10 and D9–D11 on 2026-10-11 and 2026-10-12 (table at the end). Nothing here governs a run until the pilot (§9) has sized the study, and the plan is frozen (§12) before the study's first call. Until then no judge is run on any test row of the datasets below.

<!-- Relative links and paths in this file are written for its published location, judge-audit docs/v06-plan.md (§12). -->
Method notes carried over from v0.5: [v05-plan.md](v05-plan.md) (rows without a usable answer, threshold validation, resampling), [docs/v05/](v05/README.md).

## 1. Question

> When a decision model says "95 %", does that still mean 95 % in Spanish and Catalan? And a confidence threshold validated on English traffic: does it keep its error when the same decisions arrive in another language?

The study measures three primary judges, each with a different kind of confidence (a decision model's native probability, a hosted decision API's per-option probabilities, a chat model's verbalized confidence), on the **same items in three languages**, so that any difference is the language, not the task. A secondary Spanish banking case (§3.2) reports the same judges on banking messages, without a confirmatory test.

## 2. Hypotheses

- **H1 (primary, transfer).** A confidence threshold validated on English rows at a 5 % target error (a threshold with an exact error bound), applied unchanged to the **same decisions** in Catalan, admits an error above 5 %. Tested per primary judge (Jev, gpt-6-luna, claude-sonnet-4.5; §6, T1–T3); the Spanish counterpart is T4–T6.
- **H2 (secondary, overconfidence).** Each primary judge's overconfidence (mean declared confidence minus accuracy, on the same items) is larger in Spanish than in English and larger in Catalan than in Spanish.
- **E1 (exploratory).** A vendor's own `confidence` field ranks the model's errors differently from P(chosen option): for gpt-6-luna, the Decisions API's `confidence` (undefined in its documentation, kept in `raw.native_confidence`); for Decision 2.0 Kai-0.6B, its `confidence` field (normalised entropy, `1 − H(p)/log K`, per its code); for Microsoft-Decision-1, the route's `confidence` field; for unsloth-decision-4b, the `confidence` field of Unsloth's `predict`; for Clef-flash, the API's `confidence` field. Each is kept in `raw.native_confidence`. Reported as the paired AUROC difference, no test.

Results are published whether or not the predictions hold; a difference the test does not resolve is reported as not resolved, not as no difference.

## 3. Datasets, rows and labels

| dataset | role | locales | rows per locale | options | ground truth | licence |
|---|---|---|---:|---:|---|---|
| MASSIVE 1.1 test (`examples/massive/`, #140) | **primary**: H1, H2, every T-test | `en-US`, `es-ES`, `ca-ES` | 2,974 | 60 (`cooking_query` is never the label in test) | public human annotation | CC BY 4.0 (archive pinned by sha256) |
| es-banking-v1b (synthetic, not published with this plan) | **secondary**: no T-test; secondary metrics only (not applied: rule (a) not met, §3.2, 2026-10-10) | `es-ES` | 500 | 15 | by construction, checked on a sealed sample of 150 rows | ours, synthetic |

### 3.1 MASSIVE (primary)

- **Parallel items.** The three locales are the same items, aligned by MASSIVE `id`: no id missing in any locale and no intent differing across locales (#140). Every resample and every validation split is **by item**, so an item's three languages always fall on the same side.
- **Questions and option descriptions in English** in the primary arm (Galtea's Spanish/Catalan study found translated rubric questions cost Jev up to 13 points of accuracy). A translated-criteria arm is decision D3.
- **Labels** are MASSIVE's, carried from SLURP's annotation through localisation; a label or localisation error counts as a judge error in every locale it affects. The upstream card identifies localisers and judges by crowd-worker IDs, and `ca-ES` was added in 1.1 without a published localisation method: the report does not call the data professionally translated. Caveat printed with every table: translated parallel data, not native traffic.
- **Localisation check.** MASSIVE keeps three judges per localised row ("does the sentence match the intent?"). A majority answered no for 0 `es-ES` and 19 `ca-ES` test rows (at least one no: 76 and 120). Primary: every row. Sensitivity, declared here: every metric and test recomputed without the majority-no rows of any locale, removing the item in all three locales.
- **Repeated texts** (repository normalisation): distinct texts per locale `en-US` 2,970, `es-ES` 2,944, `ca-ES` 2,933; `ca-ES` rows 17 and 1426 share a text with two labels (`calendar_query`, `datetime_query`). Resampling is by item; a repeated text is not merged across items.
- Rows without a usable answer follow v0.5 §3.

### 3.2 es-banking-v1b (secondary banking case)

- **What it is.** 500 Spanish messages a retail-bank customer could write, 15 intents, drafted by two hosted LLMs from invented customer profiles and plans, then given injected noise (typos, casing, punctuation), de-duplicated and capped. Synthetic: no customer data. Generated on 2026-10-08, so it cannot be in any judge's training data; it is not native traffic, and LLM-drafted text may be easier or harder for an LLM judge than real messages.
- **Ground truth by construction:** the intent each draft was generated for, sealed in an answer key. It is never corrected by a human label, and no human label replaces it.
- **Audit sample.** One blind annotator labels a sealed stratified sample of 150 rows, following a written labelling guide, without the key. The sample's design is fixed in a sealed file the annotator never sees. Reported: the share of rows where the person and the intended intent agree, with its exact two-sided 95 % (Clopper–Pearson) interval; the same share with discards not counted; agreement per intent and the disagreements as `intended -> person`.
- **Rules for the audit, fixed here before the audit sheet is scored:**
  - **(a) Label quality.** The agreement that governs is the share with **discards counted as disagreements**. If it is below 90 %, or its exact 95 % lower bound is below 0.85, es-banking-v1b is reported only as "label quality insufficient", with the audit numbers, and **no per-judge metric is published on it**. With 150 rows, 136 of 150 (90.7 %) has a lower bound of 84.8 % and fails; 137 of 150 (91.3 %, lower bound 85.6 %) is the smallest count that passes.
  - **(b) No relabelling.** A disagreement is never relabelled and its row is never dropped: the intended intent stays the ground truth on all 500 rows. Any sensitivity run without the disagreeing rows is labelled as such, beside the primary numbers, never in their place.
  - **(c) Order.** The annotator labels the audit sample before seeing any judge output on es-banking-v1b; no judge is run on it until the audit sheet is filled in and committed.
  - **(d) Single vs multi-intent.** Agreement is also reported split by single-intent and multi-intent rows. Which rows have a second intent follows the generator's plan, which is sealed: the report gives the split's counts and agreement only, never which rows fall on either side.
  - **(e) Why one share stands for the dataset.** The intents are balanced by construction, so the stratified sample's agreement estimates the whole dataset's without reweighting. This holds only for that reason; it is said next to the number.
  - **(f) One annotator.** The 150 rows are labelled by one person; there is no inter-annotator reliability on them. The only reliability evidence is the labelling pilot below.
- **Labelling pilot, reported on its own and never pooled:** 30 rows, two independent annotators, key not opened; inclusive Cohen's kappa 0.822 (bootstrap 95 % 0.67–0.96), raw agreement 83 %, n = 30. The guide was clarified after it.
- **What is reported** (if the rule passes) (not applied: rule (a) not met, see the 2026-10-10 note): per primary judge, accuracy (Wilson), validated coverage at 5 % (as §7, cross-fit by row; about 250 rows per half, so a judge may find no validated threshold: then it is reported as "none validated", with the reason, never as 0 %) and the high-confidence error rate of #134 (merged 2026-10-07, PR #149). **No T-test, no Holm, no transfer test** on this dataset. Every table carries: *ground truth by construction, checked by one human on 150 rows, agreement X % (exact 95 % CI L–U)*. It is never called "human-labelled".
- Question and option descriptions in English, as in MASSIVE's primary arm (not applied: rule (a) not met, 2026-10-10).
- **Rule (a) applied, 2026-10-10.** The audit (a sealed stratified sample of 150 rows, one blind annotator) was scored on 2026-10-10, after its sha256 was recorded. Agreement with discards counted as disagreements: **131 / 150 = 87.3 %** (exact 95 % CI 80.9–92.2 %), below the pre-registered 137 / 150; discards excluded, 131 / 148 = 88.5 % (82.2–93.2 %). Rule (a) is not met: es-banking-v1b is reported only as "label quality insufficient", with these audit numbers. **No judge is run or scored on it.** The rules above are unchanged; the confirmatory study rests on MASSIVE alone, as it already did.
- **Nothing from the labelling kit enters this plan**: no row, text, id or intended label. Its sealed files are never opened by a judge run.

## 4. Roster and confidence

| judge | where | confidence audited | role |
|---|---|---|---|
| Jev (`jev-latest`, TypeSafe endpoint) | hosted | native P(chosen option) | **primary**: H1, H2 |
| `gpt-6-luna` (OpenAI Decisions API, judge-audit `--judge openai-decisions`) | hosted | P(chosen option) from the per-option probabilities the API returns; the API's own `confidence` kept in `raw.native_confidence` for E1, never audited in its place | **primary**: H1, H2, E1 |
| `claude-sonnet-4.5` (chat model, judge-audit `llm`, provider `hosted-api`) | hosted | verbalized, T = 0, the v0.5 prompt | **primary**: H1, H2 |
| Decision 2.0 Kai-0.6B, pinned `cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764` (#131) | local, CPU | P(chosen option); the `confidence` field kept for E1 | exploratory |
| Laya multilingual (mmBERT backbone), pinned `1720e3e3357cfe1e281542e223f8273b0890ca34` (laya 0.3.20) | local, GPU | P(chosen option) | exploratory |
| `gemini-3.6-flash` (verbalized, T = 0, v0.5 prompt) | hosted | verbalized | exploratory (D4) |
| `deepseek-r1` (verbalized, T = 0, v0.5 prompt) | hosted | verbalized | exploratory |
| Clef-flash (`--judge clef-hosted`, Workers AI) | hosted | P(chosen option); the API's `confidence` kept in raw | exploratory |
| decider-2b, Strands Decider 2B | local, GPU | P(chosen option) | exploratory, MASSIVE only (see below) |
| Microsoft-Decision-1 (`--judge microsoft-decision`, OpenRouter's Decisions route, served version `microsoft/microsoft-decision-1-20261009`, provider pinned, no fallbacks; #164) | hosted | P(chosen option) from the per-option probabilities; the route's `confidence` kept for E1 | exploratory (D9) |
| unsloth-decision-4b (#166): LoRA adapter and decision head over `unsloth/Qwen3.5-4B` at `3764fa359b9082ea5a1e4a5e3ac3aaf6e9671636`, 4-bit, trained by Kunko from Unsloth's public notebook without changing the recipe; artifact sha256 `fe13d15957422d75fd49244b446b54aefb8e7d9010780705217ad7a4bfc88f56` | hosted notebook, CUDA GPU; runner outside judge-audit, writing standard checkpoints | P(chosen option) from `predict`'s per-option probabilities, with the recipe's per-type temperatures; `predict`'s `confidence` kept for E1 | exploratory (D9); an audit subject only, never shipped or recommended |

**Exploratory** judges are reported with "exploratory" next to every number, are not in any T-test or in Holm, and run on MASSIVE only. decider-2b and Strands Decider 2B **stay exploratory** because they are already cheap: both ran the full pilot locally at $0 (§9) with adapters already in judge-audit, and on the GPU take under 1 s per row. decider-4b is not run. Microsoft-Decision-1 and unsloth-decision-4b are exploratory (D9): each passed a 40-row `en-US` dev pilot under a dated amendment committed before its first call (judge-audit `docs/runs/v06-pilot/README.md` §7 and §8). Every unsloth-decision-4b number is labelled "trained by Kunko following the vendor's public notebook, a methods demo", and "not independently reproducible" until both its weights (with their sha256) and the runner that calls it are published; its runner lives outside judge-audit and writes standard checkpoints (judge-audit pilot README §7, item 3).

**Device and precision are fixed per model at the freeze and recorded in every checkpoint**, because decisions can depend on them (decider-2b's own card example picks a different option in fp16 on GPU than in bf16 on CPU; Decision 2.0 autocasts to bf16 on some GPU backends only, per its code). Fixed here, as used in the pilot: Kai-0.6B on CPU, float32; Laya multilingual on GPU, float32; decider-2b on GPU, float16, with the same libraries loaded as in the pilot; Strands Decider 2B on GPU, bfloat16; torch 2.14.0, transformers 5.17.0; one local model in memory at a time. **Over-length inputs:** a row the model's runtime would truncate is never sent; its question is `no_answer` (`max_length_exceeded`), counted against the judge, and the run continues (decision2, decider, strands, clef). `laya` follows the same rule since #142 (merged 2026-10-06), so every local judge does. Laya multilingual's own head budget (256 tokens) cannot hold the 60 options (291 tokens): every question would be not sent, so its budgets are fixed here at `head_max_len` 384 and `max_len` 1,024, as in the pilot, where no row was cut; outside what the checkpoint shipped with, and recorded in every header. **On GPU, decider sends one question per request**: its half-precision answers there depend on the other questions in the request (0.5122 alone vs 0.5155 together on its card example); CPU is unaffected. The exact device and library versions of every pilot run are recorded in the pilot README (`docs/runs/v06-pilot/README.md`) and in each checkpoint header; the study uses the same. The hosted decision APIs also send one question per request (the adapter's default, recorded as `questions_per_request`).

**Hosted models.** Each checkpoint records the model id the response says it served (`raw.served`). A hosted model cannot be pinned to a revision: a served id that changes during the study is reported, and rows before and after the change are reported separately.

**Training-data overlap with MASSIVE** (from model cards and published code, 2026-10-05; details and pinned links in `docs/judges.md`; "not documented" is not "unseen"):

| judge | MASSIVE in its documented training or calibration | consequence here |
|---|---|---|
| decider-0.8b / -2b | **English intent train split is in training** | its English is in-distribution: an English-validated threshold is optimistic, so its transfer gap mixes language with training exposure; reported with that caveat, never as a language effect alone |
| decider-4b | "MASSIVE (multilingual)" in training, languages not listed | not run in this study |
| Strands Decider 2B | English intent held out of training but **used to fit its temperatures** | same caveat as decider for English |
| Decision 2.0 | not documented; the team's earlier models list MASSIVE among source families | stated as unknown |
| Laya multilingual | not documented; MASSIVE is its card's own benchmark | stated as unknown |
| Jev, Clef, gemini-3.6-flash, deepseek-r1 | not documented | stated as unknown |
| gpt-6-luna, claude-sonnet-4.5 | not documented | stated as unknown |
| Microsoft-Decision-1 | not documented (#164) | stated as unknown; read as possibly in-distribution |
| unsloth-decision-4b | its fine-tuning data, `LocalLLaMA/typed-decisions` (config `all`, revision `6a7927fa3c8ac114e29f5300eacb86f6f37a6447`), does not list MASSIVE among its sources; the base model's data is not documented; text overlap of typed-decisions with MASSIVE not yet measured (#166) | stated as unknown until the overlap table of #166, which is printed next to its numbers |

**Sensitivity, declared here:** every metric and test is also computed without the test items whose text appears in MASSIVE train or dev in any locale (26 `en-US`, 156 `es-ES`, 206 `ca-ES` texts, #140), the item removed in all three locales.

Every local model is pinned to a revision sha recorded in its checkpoint header; a model the vendor changes after the freeze is not updated without an amendment. A model run quantized to fit is labelled as that variant.

## 5. Repeats

Local decision models are deterministic (Kai: identical outputs across calls in the plumbing check); one run each. Every primary judge has one primary run. Jev: between-run spread from v0.5 applies. gpt-6-luna and claude-sonnet-4.5: between-run spread measured in their pilot (§9) on the first 40 `en-US` pilot items sent twice: the same decision on 40 of 40 for both; mean absolute confidence change 0 for gpt-6-luna and 0.0013 for claude-sonnet-4.5, largest 0.05. That is 40 items in one locale, so a rough input: one primary run each, and the spread is reported with the results. Exploratory: Microsoft-Decision-1's pilot repeat (40 `en-US` items, 2026-10-12) gave the same decision on 40 of 40, with a mean absolute confidence change of 0.0064 and 0.0957 for the item that changed most, so its confidences are not identical between runs; one run, spread reported. unsloth-decision-4b runs as the recipe ships it; its pilot adapter answers equalled direct `predict` calls on the rows checked; one run.

## 6. Confirmatory tests (MASSIVE only)

**Transfer test (H1).** Items are split in two halves by item, seed 2026. On half A, the English rows validate a threshold at a 5 % target (`coverage_at_risk`, exact one-sided 95 %, start rule D3 of v0.5). On half B, the rows at or above that threshold are counted in the target language; the error among them gets an exact one-sided 95 % **lower** bound. Then the halves swap and the two half-B counts are pooled. **Resolved** when the pooled lower bound exceeds 5 %, after Holm across the six tests T1–T6 (3 primary judges × {`ca-ES`, `es-ES`}) at family-wise α = 0.05. English half-B rows above the same threshold are reported beside it as the control. **Pre-registered secondary:** for every T1–T6, the exact one-sided 95 % **upper** bound on the pooled target-language error above the English threshold, so a test that is not resolved still reports how large the error could be; never used to call a test resolved.

| id | judge | target locale | prediction |
|---|---|---|---|
| T1 | Jev | `ca-ES` | resolved (error above 5 %) |
| T2 | gpt-6-luna | `ca-ES` | resolved (error above 5 %) |
| T3 | claude-sonnet-4.5 | `ca-ES` | not resolved |
| T4 | Jev | `es-ES` | resolved (error above 5 %) |
| T5 | gpt-6-luna | `es-ES` | not resolved |
| T6 | claude-sonnet-4.5 | `es-ES` | not resolved |

**Prediction rule (one rule for all six tests).** For each test, take the pilot's target-language error above the judge's English 5 % threshold (the point estimate on the 230 pilot items, §8) as the true error, and the pilot's share above that threshold times 2,974 as m (§8). The test is predicted **resolved** when the study's power to resolve it at α = 0.05/6 (Holm's first step) is at least 0.5, and **not resolved** otherwise; that is, the prediction is the outcome the pilot makes more likely than not.

| id | pilot error above the English threshold (errors / rows) | m at 2,974 | power at α = 0.05/6 | prediction |
|---|---|---:|---:|---|
| T1 Jev `ca-ES` | 6.2 % (11 / 177) | 2,289 | 0.56 | resolved |
| T2 gpt-6-luna `ca-ES` | 10.2 % (17 / 167) | 2,159 | 1.00 | resolved |
| T3 claude-sonnet-4.5 `ca-ES` | 5.0 % (9 / 181) | 2,340 | 0.01 | not resolved |
| T4 Jev `es-ES` | 6.2 % (12 / 193) | 2,496 | 0.58 | resolved |
| T5 gpt-6-luna `es-ES` | 5.5 % (9 / 165) | 2,134 | 0.08 | not resolved |
| T6 claude-sonnet-4.5 `es-ES` | 3.8 % (7 / 186) | 2,405 | 0.00 | not resolved |

Five of the six pilot errors are within about 1.2 points of 5 %, so most of these predictions are close calls: T1 and T4 sit just above the rule's power line of 0.5 (0.56 and 0.58); T3 (pilot error 5.0 %) and T5 sit below it. T5's pilot error, 5.45 % (9 / 165), is above 5 %, but its power, 0.08, is below the line. The rule is kept as written; a test predicted not resolved is not a prediction that the threshold holds (§6, upper bound). *The predictions above are set from the pilot (§9: Jev 2026-10-07, gpt-6-luna and claude-sonnet-4.5 2026-10-10; rough, n = 230 per locale; planning inputs, not results). They are the values frozen with this plan and are not changed after.* If English validates no threshold for a judge at 5 %, its tests are reported as not run, with the reason. Holm keeps m = 6 fixed: a test that is not run counts as not resolved (the conservative choice), and the other tests are adjusted as if it had run and failed.

**Overconfidence (H2).** Per primary judge, overconfidence = mean confidence − accuracy on usable rows; the paired differences es − en and ca − es, each with a two-sided bootstrap interval clustered by item (10,000 resamples, seed 2026). Secondary, no Holm: reported as resolved when the interval excludes 0.

**Secondary, not confirmatory:** per locale and judge (primary and exploratory), accuracy (Wilson), AUROC, ECE and MCE, Brier, validated coverage at 1 / 2 / 5 / 10 % (v0.5 D2), the high-confidence error rate of #134 (merged 2026-10-07, PR #149), cost and latency. No composite score.

## 7. Threshold validation

As v0.5 §7 (cross-fit, seed 2026, targets 1 / 2 / 5 / 10 %, start at the 2-error cut), run separately per locale. With about 1,487 items per half, 1 % cannot be validated by construction (628 rows needed at 2 errors is more than a 1 % automation of a half allows in v0.5's A2 setting); the table says so rather than printing 0 %.

## 8. Smallest detectable differences

From the pilot (§9; checkpoints `docs/runs/v06-pilot/` in judge-audit, run 2026-10-07; Jev hosted). Planning inputs, not evidence; n = 230 items per locale, so every input below is rough. MASSIVE only: es-banking-v1b has no judge runs (rule (a) not met, 2026-10-10, §3.2). gpt-6-luna and claude-sonnet-4.5 from their pilot of 2026-10-10 (judge-audit commit `67ab843`, README §6 there). gpt-6-luna's 3 refusals per locale count as wrong with no confidence, so they are never above a threshold.

**Transfer test (H1).** The test is resolved when the exact one-sided lower bound on the pooled target-language error above the English threshold exceeds 5 %. With m pooled target rows above the threshold, the rows needed for 80 % power when the true error there is p:

| true error above the English threshold | m at α = 0.05/6 (Holm, first step) | m at α = 0.05 (Holm, last step) |
|---|---:|---:|
| 7.5 % | 952 | 572 |
| 10 % | 278 | 169 |

Computed exactly: for each m, the smallest error count whose exact one-sided (Clopper–Pearson) lower bound at 1 − α exceeds 5 %, then the binomial probability of reaching it at the true error p; the cell is the smallest m with power ≥ 0.8. Power is not monotone in m (the count is discrete): it stays at or above 0.8 from 1,008 / 628 (7.5 %) and 300 / 191 (10 %) on.

m is the share of target rows at or above the English threshold times the items per locale. The pilot's English 5 % threshold, walked on all 230 items (the study walks each half), gives these shares and the power at the study's 2,974 items per locale:

| judge | English threshold (pilot) | target share above it: es / ca | m at 2,974: es / ca | power at 7.5 %, α = 0.05/6: es / ca | power at 10 %: es / ca |
|---|---|---|---|---|---|
| Jev | 0.76 (194 of 230, 3 errors) | 83.9 % / 77.0 % | 2,496 / 2,289 | > 0.99 / > 0.99 | 1.00 / 1.00 |
| gpt-6-luna | 0.54 (178 of 230, 3 errors) | 71.7 % / 72.6 % | 2,134 / 2,159 | 0.99 / 0.99 | 1.00 / 1.00 |
| claude-sonnet-4.5 | 0.92 (191 of 230, 4 errors) | 80.9 % / 78.7 % | 2,405 / 2,340 | > 0.99 / > 0.99 | 1.00 / 1.00 |

**Reading.** 2,974 items per locale are enough for all three primary judges at 7.5 % and 10 %: each validates an English threshold at 5 % on the pilot, and the share above it gives m between 2,134 and 2,496 in both target locales, above the 952 the 7.5 % cell needs (power stays at or above 0.8 from 1,008 on). Power is low only when the true error is close to 5 %, which is where the pilot puts claude-sonnet-4.5 (both locales), gpt-6-luna in `es-ES`, and Jev in both locales (pilot error 6.2 %, power 0.56 `ca-ES` / 0.58 `es-ES`, close calls) (§6); an unresolved test is reported with its upper bound (§6), never as "the threshold held". claude-sonnet-4.5's verbalized confidences take few values, so its threshold falls on a tie group and its share can move by a whole group between halves.

**Overconfidence (H2).** Paired per-item difference in (confidence − correct), SD from the pilot; minimum detectable difference at 2,974 items, two-sided 0.05, 80 % power (2.80 · SD / √n; the clustered bootstrap may be a little wider; items with no confidence in either locale are left out of the pair, 5 and 4 of 230 for gpt-6-luna):

| judge | es − en: SD, MDE | ca − es: SD, MDE |
|---|---|---|
| Jev | 0.28, 1.4 points | 0.28, 1.5 points |
| gpt-6-luna | 0.31, 1.6 points | 0.37, 1.9 points |
| claude-sonnet-4.5 | 0.25, 1.3 points | 0.29, 1.5 points |

**Exploratory note (Kai-0.6B, Laya multilingual; no test).** Their pilot inputs are kept for planning only. Kai: at the pre-registered start (the 2-error cut, 124 rows at 5 %), English validates no threshold at 5 % on the pilot: the first cut holding 124 rows has 6 errors. Its transfer reading is therefore reported as not run, with that reason, unless the study's English rows validate a threshold, as for Laya. (*Not the plan's rule, for reference only:* started at the first cut, 59 rows, the pilot would give 0.778, 67 of 230 rows, 0 errors.) Kai is **under**confident in all three locales (mean confidence minus accuracy −0.14, −0.18, −0.14); paired SD 0.41 (es − en) and 0.44 (ca − es). Laya: English validates no threshold at 5 % on the pilot (accuracy 56 %), so its transfer reading is reported as not run unless the study's English rows validate one; paired SD 0.46 and 0.48.

## 9. Pilot (before the freeze, dev rows only)

The 230 pilot items committed in #140 (up to 4 per intent from MASSIVE **dev**, seed 2026, the same items in the three locales; dev, not train, so a classifier later trained on train has never seen them). Used only to size §8 and to set the T1–T6 predictions; no pilot number is evidence for or against a hypothesis. Its protocol, checkpoints and estimates are committed before the freeze, as in v0.5 (`docs/runs/v06-pilot/`).

- **Done, 2026-10-07:** Jev, Kai-0.6B, Laya multilingual, and the exploratory decider-2b and Strands Decider 2B (15 runs, 3,450 judgments, all parsed; Jev $0.0229 in all, from the checkpoints' `cost_usd`).
- **Done, 2026-10-10:** gpt-6-luna and claude-sonnet-4.5 on the same 230 items × 3 locales, under the dated amendment to the pilot protocol committed before their first call (judge-audit commit `67ab843`, `docs/runs/v06-pilot/README.md` §6): 6 runs and two 40-row `en-US` repeats, `check_complete` 0 gaps; gpt-6-luna 3 refusals per locale (1.3 %), claude-sonnet-4.5 none; $0.0483 and $1.9642 from the checkpoints' `cost_usd`, plus $0.0028 and $0.1064 for the repeats. They set T2, T3, T5, T6 (§6), their §8 rows and §5.
- **Done, 2026-10-12:** the exploratory unsloth-decision-4b and Microsoft-Decision-1, 40 `en-US` dev items each, under dated amendments committed before their first calls (judge-audit `docs/runs/v06-pilot/README.md` §7, #168, and §8, #171): 0 unparsed, blank or not-sent rows, `check_complete` 0 gaps; Microsoft-Decision-1 also once repeated (§5); $0 and $0.0013 from the checkpoints' `cost_usd`. They set no prediction and no §8 row.
- es-banking-v1b has no judge pilot: its labelling pilot (§3.2) is about the labels, not the judges, and the judges are not run on it before the freeze.

## 10. Cost ceiling and time

Estimates, except where marked measured. MASSIVE study rows: 3 locales × 2,974 = **8,922 rows** per judge; pilot: 690 rows.

| judge | price (USD per million tokens, input / output) | where the price comes from | tokens per row assumed | study (8,922 rows) | pilot (690 rows) |
|---|---|---|---|---:|---:|
| Jev | v0.6 pilot's recorded rate, $0.0229 per 690 rows | v0.6 pilot checkpoints (`cost_usd`) | — | about $0.30 (measured pilot rate × 8,922 / 690) | $0.0229 (measured) |
| gpt-6-luna | $0.10 / none (output not billed) | judge-audit `DECISIONS_PRICE_PER_MTOK` and `docs/judges.md` (documented base rate, 2026-10-07) | measured in its pilot | about $0.62 (measured pilot rate × 8,922 / 690) | $0.0483 (measured) |
| claude-sonnet-4.5 | $3 / $15 | judge-audit Arena checkpoints of this model (`docs/runs/arena/claude-sonnet-4.5/`, header `prices_usd_per_mtok`) | measured in its pilot | about $25.4 (measured pilot rate × 8,922 / 690) | $1.9642 (measured) |

- **gpt-6-luna**: the price is the base rate; regional and long-context multipliers may apply and are not seen by the adapter, so the bill can be above the computed cost (as `docs/judges.md` says).
- **claude-sonnet-4.5**: its pilot recorded a known cost on every row (`priced`); the study scale-up assumes the same prompt length per row as the pilot.
- **es-banking-v1b**: no runs and no cost. Rule (a) of §3.2 was applied on 2026-10-10 and not met (131 / 150).
- **Exploratory**, same 8,922 rows: gemini-3.6-flash about $3.2 ($0.30 / $2.50, judge-audit `PRICES`); Clef-flash about $0.6 ($0.09 input, judge-audit `docs/judges.md`, 2026-10-07); Microsoft-Decision-1 about $0.15 (measured pilot rate, $0.000658 per 40 rows, × 8,922 / 40; $0.042 per million input tokens, output not billed); unsloth-decision-4b $0 (hosted notebook GPU, no charge); deepseek-r1 about $38 ($1.35 / $5.40, Arena checkpoint headers `docs/runs/arena/deepseek-r1/`; assumed 620 input tokens per row, as claude-sonnet-4.5's pilot prompt, and 640 output tokens, the largest per-row mean of its four Arena runs; its reasoning length can exceed this). Local models: $0.
- **Cost ceiling per judge, fixed here.** Rule: the study estimate above (measured pilot rate where there is one) × 1.5, rounded up to the next whole dollar, or to the next $0.50 below $5. A run that reaches its ceiling stops, and continues only after a dated amendment (§12). Primary: Jev $0.50, gpt-6-luna $1, claude-sonnet-4.5 $39. Exploratory: gemini-3.6-flash $5, Clef-flash $1, Microsoft-Decision-1 $0.50, deepseek-r1 $58, **provisional** (from the estimate above, which rests on assumed token counts). deepseek-r1 has no v0.6 pilot, so it runs only after a 40-row pilot on the MASSIVE dev pilot items sets its ceiling by the same rule; that pilot and the ceiling it gives are recorded in a dated amendment (§12) before the study's deepseek-r1 run. A run that stops at its ceiling reports the rows it completed, labelled as such. Local models and unsloth-decision-4b: no ceiling ($0).
- **Study budget and automatic stop (D10).** The approved budget for the study is $115 in recorded cost, deepseek-r1's pilot included. The ceilings above add up to $105. Every run of a paid hosted API is started with `scripts/audit_resumable.py --max-usd <its ceiling>` (judge-audit #172), which sums the checkpoint's recorded `cost_usd` before each request, across resumed sessions, stops the run when the ceiling is reached, stops when a hosted reply's cost is unknown, and writes the ceiling to the checkpoint header. If deepseek-r1's pilot sets a ceiling that would take the total above $115, its ceiling is the remainder ($115 minus the other ceilings and minus the recorded cost of deepseek-r1's pilot), recorded in the same amendment. Recorded cost can be below the provider's bill (gpt-6-luna's multipliers, deepseek-r1's reasoning tokens), so the billing console is also checked after each hosted run, as in v0.5.
- **Time.** Local models: Kai at about 0.15 s per request is about 25 minutes for the three locales on CPU; decider-2b and Strands Decider 2B under 1 s per row on the GPU. Hosted judges are paced by their rate limits; their time is measured in the pilot.

## 11. Execution and stopping rules

As v0.5 §10: local runs first, then hosted; `scripts/audit_resumable.py`; checkpoints under `docs/runs/v06/`; more than 5 % unparsed rows among the first 40 stops a run pending an amendment; every run of a paid hosted API carries `--max-usd` at its ceiling (§10); `scripts/check_complete.py`, which also checks each checkpoint's dataset hash (judge-audit #80), reports 0 gaps before a checkpoint is committed. es-banking-v1b: rule (a) of §3.2 was applied on 2026-10-10, after the audit sheet's sha256 was recorded and the sheet scored, and it was not met (131 / 150 = 87.3 %), so no judge is run on it.

## 12. Freeze and deviations

**Freeze (D9).** The plan is frozen when all of these hold: (1) D9–D11 are committed in this file; (2) judge-audit #172 (`--max-usd`) and #80 (`check_complete` dataset hash) are merged on judge-audit `main`; (3) the maintainer has read this text. Nothing else gates the freeze.

- **The freeze commit** changes this file's status line from draft to frozen, with the date, and changes nothing else. The sha256 of the file's bytes at that commit is the plan's hash.
- **Public commitment.** That hash is committed in judge-audit as `docs/v06-plan.sha256`, and the commit is tagged `v06-plan-freeze` there; the text itself is not published at the freeze. The file in the maintainer's working repository is tagged `v06-plan-freeze` too. judge-audit's tag ruleset protects the tag from deletion and moves. The public commit timestamps the plan before the first test-row call (the checkpoint headers carry the time of each call).
- **Code.** Every study run uses judge-audit's code at the commit tagged `v06-plan-freeze` (which contains #172 and #80). Each run's line in the study record (`docs/runs/v06/README.md`) names that commit with the checkpoint's sha256, because checkpoint headers record the package version only. A code change needed after the freeze is a deviation (below).
- **At the release**, the text is published in judge-audit as `docs/v06-plan.md`, unchanged, and anyone can check that it matches the hash committed at the freeze. Relative links and paths in this file (`v05-plan.md`, `v05/README.md`, `docs/runs/…`, `examples/…`, `scripts/…`) are written for that location; issue and PR numbers are judge-audit's.

**Deviations.** Dated amendments, each committed before the call it governs. After the freeze, each amendment's sha256 is also committed in public judge-audit, one dated line per amendment in `docs/v06-amendments.sha256`, before that call, and the amendment texts are published with the plan at the release. An amendment written directly in judge-audit's public pilot record (`docs/runs/v06-pilot/README.md`) is already public and needs no separate hash.

## Decisions (settled by the maintainer)

| id | date | question | decision |
|---|---|---|---|
| D1 | 2026-10-05 | primary target error for H1 | **5 %** (a threshold can be validated at about 1,487 items per half); 1 %, 2 % and 10 % stay secondary |
| D2 | 2026-10-05 | decider-2b, Strands Decider 2B, Clef-flash | **exploratory** in this study, reported with "exploratory" next to every number; primary in the next study once their adapters are reviewed |
| D3 | 2026-10-05 | a translated-criteria arm | **exploratory, Spanish only**, translated by the maintainer and marked as such in the criteria `origin`; Catalan only with a native reviewer |
| D4 | 2026-10-05 | a chat model with verbalized confidence | **one, exploratory: `gemini-3.6-flash`**, as in v0.5, as a known reference |
| D5 | 2026-10-05 | 27B models (Vega-27B, Clef) | **out of this study**; a later amendment (rented GPU in bf16, the vendor's own API, or a quantized variant labelled as such) |
| D6 | 2026-10-05 | external human reviewer | **no external reviewer was found.** The maintainer read the plan before the freeze; the report says so, and never calls it an external review |
| D7 | 2026-10-10 | the primary roster | **Jev, gpt-6-luna, claude-sonnet-4.5**, one per kind of confidence (native, a decision API's per-option probabilities, verbalized). Kai-0.6B and Laya multilingual move to exploratory, with gemini-3.6-flash, deepseek-r1, Clef-flash (now hosted, `clef-hosted`), decider-2b and Strands Decider 2B. T1–T6 are 3 primary judges × {`ca-ES`, `es-ES`}, Holm across 6 with m = 6 fixed. claude-sonnet-4.5 is the primary chat model and gemini-3.6-flash stays the exploratory reference. **D7 supersedes D4 on this point**: D4's "one chat model, exploratory" no longer holds; it also supersedes D2's roster where they differ |
| D8 | 2026-10-10 | dataset roles | **MASSIVE 1.1 primary** (every T-test). **es-banking-v1b secondary**: ground truth by construction, checked by one blind annotator on a sealed stratified sample of 150 rows, secondary metrics only, with the audit rules (a)–(f) of §3.2 fixed before the audit sheet is scored. **2026-10-10:** rule (a) applied and not met (131 / 150 = 87.3 %, exact 95 % CI 80.9–92.2 %); es-banking-v1b is reported only as "label quality insufficient", no judge is run or scored on it, and MASSIVE alone carries the study |
| D9 | 2026-10-11, 2026-10-12 | freeze publication mode; roster additions | **hash only at the freeze, full text at the release** (§12; 2026-10-11). **deepseek-r1 is kept**, exploratory, with its budget raised; it runs after a 40-row dev pilot under a dated amendment sets its ceiling (§10; 2026-10-11). **Microsoft-Decision-1 (#164) and unsloth-decision-4b (#166) are added as exploratory** (2026-10-12), after their 40-row dev pilots were merged (judge-audit #171, #168); Microsoft-Decision-1's adapter is in judge-audit (#170), unsloth-decision-4b's runner is outside it. unsloth-decision-4b is an audit subject only, never shipped or recommended |
| D10 | 2026-10-11 | budget | **$115 for the study in recorded cost, with an automatic stop per run at each judge's ceiling** (`--max-usd`, judge-audit #172; §10) |
| D11 | 2026-10-12 | calendar | **no calendar dates**: freeze when the §12 preconditions hold, then run the study at once |
