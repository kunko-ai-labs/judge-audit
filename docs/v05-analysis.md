# v0.5 — analysis of the repository and recommended plan

> **Status: analysis and proposal, 2026-09-26.** This is not the pre-registration. It reviews v0.4.0 as it stands on `main`, weighs an external review of it, and recommends how v0.5 ([#94](https://github.com/kunko-ai-labs/judge-audit/issues/94)) should proceed. The pre-registration (`docs/v05-plan.md`, [#91](https://github.com/kunko-ai-labs/judge-audit/issues/91)) is written from it and committed before the first API call.
>
> **Numbers.** Every number this page derives itself (errors behind the headline, exact bounds, AUROC precision, cost projection) is printed by `python scripts/v05_numbers.py` from the committed evidence or from a stated formula. External numbers (a paper's result, a dataset's size, a vendor's claim) are cited to their source and not recomputed; claims that come only from a vendor or from secondary sources are marked as such. Planning figures, not results: nothing here measures a judge on v0.5 data.

## 0. Summary

1. **The instrument is strong; the evidence is thinner than it looks, and not only because n = 200.** The shortest honesty test in the Arena, confidence when right against confidence when wrong, rests on **6 errors** for Gemini 3 Flash, 7 for Claude Sonnet 4.5 and 9 for Jev under attack. The effective sample of a calibration claim is the number of errors, not the number of rows.
2. **The v0.4 headline metric will not survive real data.** Zero-error coverage shrinks mechanically as n grows and collapses under label noise; on a human-labelled set with a few percent of wrong labels every judge will likely read 0 %, which says something about the labels, not the judges. The headline metric has to change before the first call: coverage at a target risk, with the threshold chosen on one split and checked on another, plus AUROC.
3. **Fair confidence ([#89](https://github.com/kunko-ai-labs/judge-audit/issues/89)) is narrower than the story assumes.** The Claude Messages API has no log-probability parameter and OpenAI's reasoning models return none; for the newest Gemini models the only report found says they return none either. All three methods per model are feasible on open-weight models run locally or on a host that returns log-probabilities; the closed models get verbalized confidence and self-consistency.
4. **The fine-tuned DeBERTa is neither removed nor tuned to win.** It is redone properly on the official train split, with its recipe pre-registered, and published with what it costs in labels.
5. **There is a verifiable, free second judgment model (Laya, open weights), and a public Jev audit on BANKING77 that measures no calibration.** That gap is where v0.5 adds something nobody has published.

## 1. What was reviewed

- `main` at `3cee4bc` (v0.4.0 plus #96 and #97): `README.md`, `docs/ROADMAP.md`, `docs/ground-truth.md`, `docs/judges.md`, `docs/arena-2026-09.md`, `docs/consensus-2026-09.md`, `docs/jury-consensus-plan.md`, `docs/repeats-2026-09.md`, `docs/repeat-runs-plan.md`, `docs/robustness-distinct-2026-09.md`, `docs/finetuned-baseline-2026-09.md`, `docs/vision.md`, `docs/landscape-brief.md`, `src/judge_audit/metrics/calibration.py`, `src/judge_audit/judges/llm.py`, the Arena checkpoints.
- The epic [#94](https://github.com/kunko-ai-labs/judge-audit/issues/94), its kickoff comment, and stories #86–#93, #80, #12.
- **Branches.** Every branch other than `main` and the working branches of this analysis is the head of a closed pull request whose squash commit is on `main`: 22 branches, each tip identical to its PR's head (`feat/arena` #35, `chore/claude-agents` #48, `feat/ground-truth-tiers` #50, `feature/logo` #30, `fix/json-extract-scan` #49, `fix/json-mode-timeout-fallback` #42, `fix/llm-json-trailing-garbage` #44, `fix/llm-wall-clock-deadline` #43, `fix/transient-connection-errors` #41, `feat/bootstrap-ci` #55, `feat/error-correlation` #52, `feat/finetuned-classifier` #53, `feat/prerelease-fixes` #60, `feat/release-hardening` #57, `feature/jury-consensus-audit` #40, `feat/brier-equal-mass-ece` #69, `feat/coverage-ties` #64, `feat/release-hygiene` #63, `fix/consensus-frozen-panel` #68, `docs/readme-evidence` #72, `feat/unknown-confidence-v2` #71, `release/v0.4.0` #95). None holds unmerged work; `docs/RELEASING.md` step 5 says to delete the release branch after the release, and the tag `v0.4.0` exists. They can all be deleted; deleting a branch that is the base of an open PR would close that PR, and none is.

## 2. What is solid

The honesty infrastructure is the moat, and it is rare: predictions committed before the run and published whether or not they hold, raw checkpoints for every number, intervals on every number (exact where the bootstrap degenerates), ground-truth tiers printed next to every accuracy, three calibration numbers never combined, unknown confidence never imputed, the served model version recorded. The findings v0.4 does support, on its data: the chat models' verbalized confidence barely separates their right answers from their wrong ones; vote share is not a confidence score; on the bare-label router, deliberation amplified what the prompt contained; who sits on a jury moves its accuracy a long way.

## 3. The external review, point by point

An external review (another AI assistant, shared by the maintainer) made six recommendations. Where this analysis agrees, disagrees or adds:

| External review | This analysis |
|---|---|
| All evidence is GT-1 synthetic at n = 200/120; without #86 there is no publishable headline | **Agree**, and sharpen it: what matters is the number of errors (§ 4.1) and a metric that survives n ≥ 1,000 (§ 4.2). |
| The star comparison is asymmetric (probability vs written number); don't publish Jev vs Gemini until best-vs-best | **Agree on the confound.** The as-deployed comparison stays legitimate for a buyer, labelled as such; but log-probabilities do not exist for most closed models (§ 4.5), so "best vs best" means self-consistency for them. |
| The fine-tuned DeBERTa rows are dangerous to the thesis; keep them as a capped control | **Disagree with the framing** (§ 5). Hiding a strong baseline because it hurts a narrative is the selective reporting this repository exists to prevent; the thesis is "this can be audited", not "Jev wins". |
| Order: #93 now, #91 with a named reviewer and 2–3 datasets in depth, #89 before any ranking | **Agree.** Add: the power analysis should come from a simulation on the v0.4 checkpoints and a pilot, because the literature does not report effect sizes in this repository's units (zero-error coverage is not a standard metric). |
| Add a second Jev-type judge (OpenJev, Laya) | **Agree strongly.** Laya is open, free and runs on a laptop (§ 4.8). |
| One headline for v0.5: replicate the honesty test on human data, n ≥ 1,000 | **Agree on one headline, not on this one**: replicated as is, the zero-error headline will most likely read 0 % for everyone (§ 4.2). Proposed headline in § 6. |
| The jury composition result (0 % → 92.5 %) is the most original finding | **Disagree.** It rests on 14 distinct hard texts, and panel composition is an active 2026 literature (§ 4.6). Keep it exploratory. |
| Scope discipline; decide the OpenAI key now; put dates on the epic | **Agree.** Plan with dates in § 11. |

## 4. Findings

### 4.1 The effective sample is the number of errors

Emails under attack, from `docs/arena-2026-09.json` (GT-1 synthetic, n = 200):

| judge | accuracy | errors | confidence right / wrong |
|---|---|---|---|
| Jev | 95.5 % | 9 | 0.93 / 0.60 |
| Claude Sonnet 4.5 | 96.5 % | 7 | 0.96 / 0.88 |
| Gemini 3 Flash | 97.0 % | 6 | 0.98 / 0.98 |

Every "confidence when wrong" is a mean over 6 to 9 answers. A benchmark should choose tasks on which the judges are *not* at ceiling, so that each judge makes hundreds of errors: BANKING77 zero-shot is such a task (§ 7).

### 4.2 Zero-error coverage does not scale; use coverage at a target risk

Zero-error coverage is the largest most-confident share of decisions with **no** observed error. The chance of observing no error among the m most confident rows, when their true error rate is p:

| m | p = 0.2 % | p = 0.5 % | p = 1 % | p = 3 % |
|---|---|---|---|---|
| 100 | 0.819 | 0.606 | 0.366 | 0.048 |
| 300 | 0.548 | 0.222 | 0.049 | 0.000 |
| 1,000 | 0.135 | 0.007 | 0.000 | 0.000 |

Two consequences. With more rows the number falls towards the region where the true error is exactly zero, which for a real judge on real data is close to empty; and a wrong *label* counts as an error, so label noise alone drives it to zero. Ying & Thomas (2022) estimate that over 1,400 of BANKING77's 10,003 training utterances (14 %) may be mislabelled. The v0.4 metric is also **retrospective**: the threshold is chosen on the same rows it is scored on, which flatters it.

The standard framing is selective classification with a guaranteed risk (Geifman & El-Yaniv, NeurIPS 2017): choose the confidence threshold on a calibration split so that the risk above it is at most r with probability 1 − δ, then report the coverage and the realised risk on a separate split. *Trust or Escalate* (Jung, Brahman & Choi, ICLR 2025, oral) applies exactly this to LLM judges, with a provable guarantee of human agreement. judge-audit does not cite it yet, and it is the work closest to its thesis.

What exact bounds say about the sizes involved (Clopper–Pearson):

- zero errors in k automated rows bound the risk, two-sided 95 %, at 3.62 % (k = 100), 1.83 % (200), 1.22 % (300), 0.74 % (500), 0.37 % (1,000); a one-sided 95 % bound below 1 % needs k ≥ 299, as #91 states;
- with some errors allowed, the one-sided 95 % upper bound is 1.25 % for 2 errors in 500, 1.05 % for 5 in 1,000, 1.69 % for 10 in 1,000, 1.45 % for 20 in 2,000.

**Proposal for the pre-registration.** Primary selective metric: coverage at risk ≤ r (r fixed in the plan, e.g. 2 %; one-sided δ = 0.05), threshold chosen on one half of the evaluation rows and scored on the other, both ways (two-fold cross-fitting), clustered by distinct text. Primary discrimination metric: AUROC of confidence as a predictor of correctness, with the risk–coverage curve and its area (AURC). Zero-error coverage stays in the reports as a secondary column. MCE ([#12](https://github.com/kunko-ai-labs/judge-audit/issues/12)) is reported with each bin's count, as a proposal, never as a legal requirement.

### 4.3 Compare judges on the same rows, not by overlapping intervals

"Two judges whose intervals overlap are not separated" is conservative: examining the overlap of two confidence intervals rejects less often than a test of the difference, both when the null is true and when it is false (Schenker & Gentleman 2001). The judges answer the same rows, so the right tools are **paired**: a bootstrap of the *difference* with the same resample of distinct texts for both judges; McNemar's test for accuracy; DeLong's test for AUROC. Pairing is what makes n ≈ 3,000 enough. Approximate precision of an AUROC of 0.75 (Hanley & McNeil 1982), and the smallest difference two judges must show to be told apart at 5 % / 80 % power:

| n | accuracy | errors | SE | detectable difference, unpaired | paired (r = 0.5) |
|---|---|---|---|---|---|
| 200 | 95.5 % | 9 | 0.096 | 0.379 | 0.268 |
| 1,000 | 90 % | 100 | 0.029 | 0.115 | 0.081 |
| 1,000 | 80 % | 200 | 0.021 | 0.084 | 0.059 |
| 3,080 | 92 % | 246 | 0.018 | 0.073 | 0.052 |
| 3,080 | 80 % | 616 | 0.012 | 0.048 | 0.034 |

An order of magnitude for planning; #91 replaces it with a simulation on pilot data. One primary hypothesis is confirmatory; secondary ones carry a Holm correction; everything else is labelled exploratory.

### 4.4 What the literature says about verbalized confidence

`docs/judges.md` said verbalized confidence is "what the literature finds worst calibrated". The literature does not say that, and this branch corrects the page:

- For RLHF-tuned chat models, verbalized confidence was typically *better* calibrated than conditional token probabilities on TriviaQA, SciQ and TruthfulQA, often cutting ECE by a relative 50 % (Tian et al., EMNLP 2023).
- Verbalized confidence is overconfident, mostly between 80 % and 100 % and often in multiples of 5; calibration and failure prediction improve with scale but stay far from ideal (Xiong et al., ICLR 2024).
- The verbalized-versus-token comparison depends on measurement choices rarely written down: which answer string is scored, how the score is read from its tokens, under which context (Kim & Kang 2026, arXiv:2605.27752).

The question is open, which is why it can carry a headline, and why the log-probability protocol must be pre-registered in detail (§ 9.3).

### 4.5 Which judges expose log-probabilities

| Judge / path | Token log-probabilities | Basis | Status |
|---|---|---|---|
| Claude (Messages API) | **No** | The Create Message reference lists no log-probability parameter | verified in the official API reference |
| OpenAI reasoning models (GPT-5 family) | **No** | OpenAI developer forum | community source |
| Gemini 3.1 Pro, 3.6 Flash | reported **no** | a Google developer-forum thread | unverified in official docs; smoke test |
| Gemini, older models | parameter exists (`responseLogprobs`) | API docs as summarised by search | smoke test per model |
| Open-weight models, local: Ollama ≥ 0.12.11 | **Yes** (native and OpenAI-compatible APIs, `top_logprobs` 0–20) | Ollama release notes | verified by release notes |
| Open-weight models, local: MLX / llama.cpp | **Yes** (a forward pass returns the logits) | by construction | — |
| Together AI (hosted open models) | **Yes** (`logprobs`, not with streaming) | Together docs | verified by docs |
| OpenRouter | depends on the upstream endpoint; about a quarter return them | Chauvin et al. 2025 (arXiv:2512.03816), as reported | check per endpoint |
| Groq | **No** (400 on `logprobs`) | Groq OpenAI-compatibility docs, as reported | — |
| The private hosted provider (`hosted-api`), gpt-oss and Llama | unknown | — | the #88 smoke test decides |

Consequence for [#89](https://github.com/kunko-ai-labs/judge-audit/issues/89): verbalized confidence and self-consistency for every chat model; token log-probability only where this table says yes. A model without log-probabilities says so; the method is never imputed.

### 4.6 The jury result is exploratory

The spread of three-judge juries on the 40 hard routing tasks (0 % to 92.5 % majority accuracy) rests on 14 distinct texts, and the jury report says its neighbouring rankings are not separated. Panel composition is also an active 2026 literature: for example, Zhu, Xie & Rao (arXiv:2608.19802) treat judge-panel design as allocating copies, complements and specialists, and stop adding judges when validation gain falls below a threshold. Keep the jury study as exploratory, cite that literature, and re-test composition on v0.5 data only if the budget allows.

### 4.7 The public Jev audits

- **BANKING77** (Simon Smith, 2026-09-18, `simonmesmith/jev-banking77-experiment`): `jev-1.13.0` on the 3,080 official test messages, **92.40 %** (2,846 correct) with category definitions and 24 BM25-retrieved training examples per prediction; 79.22 % (122 of 154) on a screening set with definitions and no examples; published fine-tuned BERT 93.66 % (Casanueva et al. 2020); test cost about $0.44. **No calibration metric is reported.** Its caveats: 25 test messages whose normalised text also appears in training; labels possibly noisy.
- The manual email benchmark cited in `docs/vision.md` (1,565 emails) and the confidence-field analysis linked from the README: to be compared in #93 with the same care.

Running v0.5's primary study on BANKING77's official test split makes the comparison direct: same rows, and judge-audit adds what is missing, calibration and selective prediction.

### 4.8 A second judgment model

- **Laya** (Convai Innovations, released 2026-09-18, Apache 2.0, weights on Hugging Face as `convaiinnovations/laya`): according to secondary sources, a 421M-parameter decision model (a ModernBERT-large backbone with a decision head and an act/escalate head) that returns typed answers with probabilities. Its vendor reports ECE 0.466 as shipped and 0.081 after temperature fitting. None of this was checked here (the model card could not be opened from this environment). It runs on a laptop for $0, so anyone can reproduce its row, and its escalate head is a native abstention signal to test against a confidence threshold. **Recommended for v0.5.**
- **OpenJev** (`ekzhang/openjev-sglang`): a Jev-compatible HTTP server over an open model (Qwen3.6-35B-A3B, served with SGLang), whose probabilities come from constrained log-probabilities. It is "an open chat model plus the log-probability method" behind Jev's own API, the cleanest lever to separate method from model; it needs a GPU host. v0.6, unless hosting turns out cheap.

### 4.9 Cost

Mean tokens per row measured on the 200 emails under attack: Claude Sonnet 4.5 259 in / 100 out ($3 / $15 per million, from its checkpoint header); Gemini 3 Flash 241 in / 24 out ($0.30 / $2.50). Assuming 2,000 input tokens per row once 77 labels and their definitions are in the prompt (a pilot replaces the assumption), on BANKING77's 3,080 test rows:

| judge | one verbalized run | self-consistency, k = 10 |
|---|---|---|
| Claude Sonnet 4.5 | $23.08 | $230.77 |
| Gemini 3 Flash | $2.03 | $20.30 |

Times templates and repeats, the kickoff's "tens of dollars" becomes hundreds. Proposal: self-consistency for the expensive models on a pre-registered, stratified subset of 1,000 rows; a cost ceiling around $150 written in the plan; local and cheap judges on the full split.

### 4.10 Label noise, contamination, the "hidden" slice

- **Label noise.** Relabel a random, stratified sample of about 500 test rows with two annotators blind to the dataset label and to the judges; publish their agreement (Cohen's κ) and the disagreement rate with the original labels; adjudicate to a GT-4 subset. Never pick the rows to relabel from where the judges disagree with the label: that biases the "clean" set towards the judges.
- **Contamination and the hidden slice.** BANKING77 (2020) and CLINC150 (2019) are public and almost certainly in pretraining corpora. A held-out slice drawn from them is hidden from judge vendors, not from pretraining. Either say exactly that, or collect about 300 new queries written by people and labelled by two annotators; the second is v0.6 unless time allows.
- **Label definitions.** Written from the train split only and committed in the plan: some BANKING77 label names mislead (`get_physical_card` holds questions about the PIN, per the Smith audit).

### 4.11 Hygiene

- The kickoff comment on #94 names the cloud platform behind the hosted Claude, Llama and DeepSeek models; `CLAUDE.md` forbids that in issues. Edit it.
- `docs/landscape-brief.md` says "the category is empty" and "no public leaderboard ranks judges by calibration". Re-verify before saying it in public; there is a 2026 literature on judge calibration and panels (§ 4.6).
- Delete the 22 merged branches (§ 1).

## 5. The fine-tuned DeBERTa: keep it, redo it properly

Removing it because it beats the judges would be selective reporting, and readers will ask anyway: the public BANKING77 audit already compares Jev with a fine-tuned BERT. Tuning it to win would be the mirror error. What v0.5 does instead:

1. **Train on the official train split with a pre-registered recipe**: v0.4's run 2 recipe (to convergence, temperature scaling on a validation slice carved from train) written into the plan before training. Run 1 missed 0 of 3 testable predictions and run 2 was post hoc; that cannot happen twice.
2. **A learning curve in labels per class** (for example 10, 25, 100, all), because the buyer's question is "how many labels until my own classifier beats a judge I can call today?". Its "$0 per decision" is always printed next to the labels it needed.
3. **CLINC150 out-of-scope queries**: a closed-set classifier must detect "none of these" by a threshold; this is where its limits are tested fairly.
4. It stays in its own group of rows ("your own classifier: requires N labels"), not in the hero chart unless the chart carries its label cost.

## 6. The v0.5 headline

- **H1, primary, paired, within model.** For the same model on the same rows, verbalized confidence supports less automation at risk ≤ r, and has a lower AUROC, than self-consistency (every chat model) and than token log-probability (models that expose it).
- **H2, secondary.** Judgment models with a native probability (Jev, Laya) against each chat model's best-performing confidence method, as a paired comparison.
- **Everything else is exploratory**: templates, repeats, the fine-tuned learning curve, deliberation.

H1 does not depend on any vendor, which strengthens the independent-auditor position; it is an open question in the literature (§ 4.4); and it answers the question this repository asks: can a judge's declared confidence decide what to automate?

## 7. Datasets

| role | dataset | licence (checked) | size | why |
|---|---|---|---|---|
| **primary** | BANKING77 (Casanueva et al. 2020) | CC BY 4.0 (Hugging Face card) | 13,083 queries, 77 intents; 10,003 train / 3,080 test | Customer-support routing, the task family of v0.4; direct comparison with the public Jev audit; zero-shot accuracy near 80 % means hundreds of errors per judge |
| **secondary** | CLINC150 (Larson et al. 2019) | CC BY 3.0 (the repository's `LICENSE`) | 150 intents in 10 domains, 30 test queries each (4,500) + 1,000 out-of-scope test queries | Abstention: does confidence drop when no option applies? |
| exploratory / v0.6 | HelpSteer3-Preference (Wang et al. 2025) | CC-BY-4.0 | 40,476 pairwise preferences, up to three annotators each | LLM-as-judge on real preferences: does a judge's confidence fall where humans disagree? |
| v0.6 | MASSIVE (FitzGerald et al. 2022) | CC BY 4.0 | about 1M utterances, 51 languages including es-ES, 60 intents | The Spanish-language wedge |
| not chosen | MT-Bench human judgments (Zheng et al. 2023) | to verify | 3.3K expert votes on only 80 questions | 80 distinct questions are too few clusters |
| not chosen | LLMBar (Zeng et al. 2023) | — | 419 pairs | too small alone |

Conditions: the relabelled sample and definitions of § 4.10. **#87 reduced**: instead of a v2 synthetic generator, inject v1's attack templates into real BANKING77 texts; the intent label stays human and the duplicate-text problem disappears. If time is short, #87 moves to v0.6. CLINC150 option lists: 150 intents in one prompt is long; the plan fixes either the full list or a subset of domains plus the out-of-scope queries, before any call.

## 8. Roster and confidence methods

| judge | verbalized | self-consistency | log-probability | native probability | runs where |
|---|---|---|---|---|---|
| Jev | — | — | — | yes | vendor API |
| Laya | — | — | — | yes (per vendor) | local |
| Claude Sonnet, Claude Haiku 4.5 | yes | yes | no | — | hosted |
| Gemini Flash (current) | yes | yes | smoke test | — | vendor API |
| an OpenAI non-reasoning model, if a key exists | yes | yes | if the model returns them | — | vendor API |
| gpt-oss-120b, Llama 3.3 70B | yes | yes | smoke test | — | private hosted provider, or a host with log-probabilities |
| gpt-oss-20b and a 7–9B open model | yes | yes | yes | — | local (§ 9) |
| DeBERTa NLI (control) | — | — | — | yes | local |
| DeBERTa fine-tuned (learning curve) | — | — | — | yes | local |

Dropped from v0.5: DeepSeek R1 (reasoning tokens make it the most expensive row, and it was weak on these tasks); the guardrail classifier (a safety classifier on banking intents measures nothing; it returns in v0.6 with a safety dataset). If no OpenAI key materialises, the plan says so and the roster degrades to gpt-oss, as the kickoff proposes.

## 9. Compute under the maintainer's constraints

The runs happen on two laptops (Apple M4 Pro with 16 GB and Apple M5 with 24 GB of unified memory), no discrete GPU, plus hosted APIs.

### 9.1 Memory

macOS lets the GPU wire roughly 65–75 % of unified memory by default (`recommendedMaxWorkingSetSize`), about 11 GB of 16 GB and about 16–18 GB of 24 GB; `sudo sysctl iogpu.wired_limit_mb=…` raises the cap until the next reboot, and several gigabytes should stay free for macOS. Weights at 4 bits take about half a byte per parameter plus the KV cache.

| model | fits on 16 GB (M4 Pro) | fits on 24 GB (M5) |
|---|---|---|
| Laya (421M), DeBERTa-v3 (184M) | yes, easily | yes |
| a 7–9B chat model, 4-bit (about 5 GB) | yes | yes |
| a 12–14B chat model, 4-bit (about 8–9 GB) | tight | yes |
| gpt-oss-20b (21B mixture of experts, about 3.6B active, MXFP4, about 12 GB on disk; OpenAI states 16 GB as the floor) | only with the wired limit raised, and slow | yes |
| 27–35B models, 4-bit | no | tight to no |
| Llama 3.3 70B, gpt-oss-120b | no | no: hosted |

### 9.2 Recommended split of work

- **M5, 24 GB**: gpt-oss-20b and one 7–9B open model with all three confidence methods; Laya.
- **M4 Pro, 16 GB**: DeBERTa fine-tuning and its learning curve (v0.4 trained 80 rows for 19 epochs in 109 s on an M4, so BANKING77's 10,003 rows are a matter of hours, to be measured), the NLI control, Laya.
- **Hosted**: Jev; Claude and Gemini (verbalized and self-consistency); Llama 3.3 70B and gpt-oss-120b through the private hosted provider if its smoke test returns log-probabilities, otherwise through a host that does (Together, or an OpenRouter endpoint checked to return them). Free tiers are for the pilot only: OpenRouter's free models allow 20 requests per minute and 50 per day below $10 of lifetime purchases (1,000 per day above), while self-consistency at k = 10 on 1,000 rows is 10,000 calls per model.

### 9.3 How to read an option's probability from an open model

- **Score every option, don't parse a number.** A forward pass returns the logits; the log-likelihood of each option's tokens given the prompt (teacher forcing) gives a full distribution over the options, the same object Jev returns. This is how lm-evaluation-harness scores multiple choice. Summed log-likelihood favours short options (its `acc` versus length-normalised `acc_norm`), so give each option a short code of equal token length (for example two-digit numbers, checking the tokenizer) or pre-register the normalisation.
- **First-token log-probabilities** from an API (Ollama, Together) are the cheap variant: ask for the option code as the first token and read `top_logprobs`. With at most 20 alternatives per position, 77 options cannot all be covered; the probability of the chosen code always is. An option absent from the returned list is unknown, never zero, except where the protocol says otherwise, as JudgeArena's AlpacaEval parser does (§ 10).
- **Put the fixed part first.** Instructions and the 77 options first, the row's text last, so that the key-value cache of the prefix is computed once and reused (`mlx_lm.cache_prompt` and the Python API in mlx-lm; llama.cpp does the same). mlx-lm has an open report of prompt caching returning different logits for repeated prompts (issue #259): the pilot checks that a cached and an uncached run give the same probabilities before any published run.

### 9.4 Time and energy

Throughput depends on the model, the quantisation and the prompt; the pilot measures rows per hour on each Mac before the plan fixes n, and the plan prints the measured figure. Energy is small: Notebookcheck measured the M4 Pro's GPU at about 32 W under heavy CPU and GPU load, so an overnight run stays well under one kilowatt-hour. `sudo powermetrics` records it if the report wants the number.

## 10. What JudgeArena does, and what to borrow

Two projects carry the name. **`OpenEuroLLM/JudgeArena`** (Apache-2.0, active in September 2026) benchmarks models with swappable LLM judges on Arena-Hard, AlpacaEval, MT-Bench and multilingual Arena-Hard, and meta-evaluates a judge against human arena votes (LMArena 100k/140k, ComparIA). Judges run on vLLM, llama.cpp (Apple Metal included), or remotely through Together, OpenRouter or OpenAI, and its judge configurations come from Salinas, Swelam & Hutter (ICML 2025). **`atla-ai/judge-arena`** is a Gradio space where people vote between two judges' outputs, ranked by Elo; last commit July 2025; it measures preference for judges, not their calibration.

JudgeArena ranks models with judges and measures a judge's agreement with humans; it does not audit calibration or selective prediction. Complementary, not a competitor. Five things to borrow:

1. **Log-probability verdicts.** Its AlpacaEval parser reads the first token's `top_logprobs` over the two verdict tokens and renormalises; a token missing from the list counts as probability zero and both missing is unparseable. judge-audit's rule differs on the first point (unknown is never imputed), so the plan states which rule applies.
2. **Position swap** (`--judge.swap_mode both`) against position bias. The classification analogue is permuting the option order: a principled second template for [#92](https://github.com/kunko-ai-labs/judge-audit/issues/92).
3. **Calibration fitted on a separate human-labelled sample** (its maximum-likelihood temperature on human battles): the same discipline as the calibration/test split of § 4.2.
4. **An inference cache keyed by the rendered input and the model settings, and usage reported as complete, partial or unavailable**: the same honesty as "unknown confidence is never imputed", applied to cost.
5. **Human arena votes as a source** for an LLM-as-judge dataset in v0.6, after checking their licences.

## 11. Plan with dates (target: 16 November 2026)

| week | work | needs keys? |
|---|---|---|
| 28 Sep – 4 Oct | #93 literature (judges.md corrected on this branch); metrics PR: AUROC, AURC, coverage at risk with a calibration/test split, paired differences, MCE (#12), #80; dataset loaders and licences in `docs/runs/README.md`; Laya adapter; option-scoring judge for local models; smoke-test code for log-probabilities per provider | no |
| 5 – 11 Oct | relabel 500 test rows (two annotators); pilot on **train-split rows only** (tokens, throughput, accuracy, variance, cache determinism); power analysis by simulation; draft `docs/v05-plan.md`; ask an external reviewer; run the smoke tests | the smoke tests |
| 12 – 18 Oct | freeze the pre-registration (tag), the cost ceiling and the fine-tuning recipe | no |
| 19 Oct – 1 Nov | runs with the `audit-runner` agent: hosted judges with the maintainer's keys, local judges on the two Macs; repeats (#90) only for the H1 cells | yes |
| 2 – 8 Nov | reports, independent review, release QA | no |
| 9 – 16 Nov | README rewritten around the new headline; release v0.5.0 | no |

Cut first if the schedule slips: #92 reduced to two templates (the second an option permutation) on the H1 models only; #87 to v0.6; HelpSteer3 to v0.6; OpenJev to v0.6. Out of scope, as the epic says: the leaderboard and the AI Act dossier.

## 12. Decisions for the maintainer

1. An OpenAI key or not; if not, write the degraded roster into the plan now.
2. The cost ceiling (proposal: about $150 for hosted calls).
3. A named external reviewer for the pre-registration, or the plan says none was found.
4. The risk target r for the primary metric (proposal: 2 %).
5. Delete the 22 merged branches, and edit the kickoff comment on #94.

## 13. Sources

Papers: Guo et al. 2017 (ICML), *On Calibration of Modern Neural Networks*; Geifman & El-Yaniv 2017 (NeurIPS), [Selective Classification for Deep Neural Networks](https://proceedings.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html); Jung, Brahman & Choi 2025 (ICLR), [Trust or Escalate](https://arxiv.org/abs/2407.18370); Tian et al. 2023 (EMNLP), [Just Ask for Calibration](https://aclanthology.org/2023.emnlp-main.330/); Xiong et al. 2024 (ICLR), [Can LLMs Express Their Uncertainty?](https://openreview.net/forum?id=gjeQKFxFpZ); Kim & Kang 2026, [arXiv:2605.27752](https://arxiv.org/abs/2605.27752); Schenker & Gentleman 2001, [The American Statistician 55(3)](https://www.tandfonline.com/doi/abs/10.1198/000313001317097960); Hanley & McNeil 1982 (Radiology), the standard error of the area under the ROC curve; DeLong et al. 1988 (Biometrics), comparing correlated ROC curves; Zheng et al. 2023, [MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685); Zeng et al. 2023, [LLMBar](https://arxiv.org/abs/2310.07641); Shao 2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543); Huang et al. 2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653); Zhu, Xie & Rao 2026, [arXiv:2608.19802](https://arxiv.org/abs/2608.19802); Salinas, Swelam & Hutter 2025 (ICML), [arXiv:2501.17178](https://arxiv.org/abs/2501.17178); Chauvin et al. 2025, [arXiv:2512.03816](https://arxiv.org/abs/2512.03816).

Datasets: [BANKING77](https://huggingface.co/datasets/PolyAI/banking77); Ying & Thomas 2022, [Label Errors in BANKING77](https://aclanthology.org/2022.insights-1.19/); [CLINC150 / oos-eval](https://github.com/clinc/oos-eval); [HelpSteer3-Preference](https://arxiv.org/abs/2505.11475); [MASSIVE](https://arxiv.org/abs/2204.08582); [MT-Bench human judgments](https://huggingface.co/datasets/lmsys/mt_bench_human_judgments).

Judges and audits: [Jev on BANKING77](https://github.com/simonmesmith/jev-banking77-experiment); [Laya](https://huggingface.co/convaiinnovations/laya) and [a secondary summary](https://aiweekly.co/alerts/convai-ships-laya-a-421m-modernbert-decision-model-apache-20); [openjev-sglang](https://github.com/ekzhang/openjev-sglang); [OpenEuroLLM/JudgeArena](https://github.com/OpenEuroLLM/JudgeArena); [atla-ai/judge-arena](https://github.com/atla-ai/judge-arena).

APIs and tools: [Claude Create Message reference](https://platform.claude.com/docs/en/api/messages/create); [OpenAI forum on GPT-5 log-probabilities](https://community.openai.com/t/logprobs-deprecated-for-gpt-5-models/1355427); [Gemini log-probabilities thread](https://discuss.ai.google.dev/t/176557); [Ollama v0.12.11](https://newreleases.io/project/github/ollama/ollama/release/v0.12.11); [Together log-probabilities](https://docs.together.ai/docs/inference/chat/logprobs); [Groq logprobs request](https://community.groq.com/t/add-support-for-logprobs-in-model-api-response/193); [OpenRouter free-model limits](https://fast.io/resources/openrouter-rate-limit/); [mlx-lm](https://github.com/ml-explore/mlx-lm) and [issue #259](https://github.com/ml-explore/mlx-lm/issues/259); [lm-evaluation-harness task guide](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md) and [multiple-choice normalisation](https://blog.eleuther.ai/multiple-choice-normalization/); [recommendedMaxWorkingSetSize](https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize); [iogpu.wired_limit_mb](https://modelpiper.com/blog/iogpu-wired-limit-mb-mac); [gpt-oss-20b on a 16 GB Mac](https://smeltcore.com/recipes/gpt-oss-20b-m2-pro/); [M4 Pro power (Notebookcheck)](https://www.notebookcheck.net/Apple-M4-Pro-analysis-Extremely-fast-but-not-as-efficient.915270.0.html).
