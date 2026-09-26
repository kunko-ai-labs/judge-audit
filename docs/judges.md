# Judges: what plugs in and how

judge-audit audits anything that maps `(state, questions) -> (decision, confidence)`. Six adapters ship; writing a seventh is ~30 lines.

| `--judge` | What it audits | Confidence comes from | Needs |
|---|---|---|---|
| `jev` | TypeSafe Jev, a purpose-built judgment model | the per-option probability the model returns | `AI_GATEWAY_API_KEY` + Node (gateway) **or** `JEV_BACKEND=typesafe` + `TYPESAFE_API_KEY` |
| `jev` + `JEV_ENDPOINT` | any Jev-compatible server: [OpenJev](https://github.com/ekzhang/openjev-sglang), other open re-implementations of the `/v1/systemone` API | same — the server's probability distribution | `JEV_BACKEND=typesafe JEV_ENDPOINT=http://host/v1/systemone` (key optional) |
| `llm` | a chat model with a "classify and say how sure you are" prompt — what most production judges actually are | **verbalized**: the model writes a number | Anthropic: `pip install 'judge-audit[anthropic]'` + `ANTHROPIC_API_KEY` · OpenAI-compatible (OpenAI, Ollama, vLLM, LM Studio): `LLM_PROVIDER=openai-compatible LLM_BASE_URL=… LLM_MODEL=…` |
| `nli` | a small zero-shot encoder (DeBERTa-class cross-encoder) — the **control** row: small, instruction-immune, real softmax confidence; not a competitor | **NLI entailment softmax** over the options: a real probability, computed locally | `pip install 'kunko-judge-audit[nli]'`; optional `NLI_MODEL`, `NLI_HYPOTHESIS`, `NLI_DEVICE` |
| `finetuned` | **your own classifier**: a DeBERTa-class encoder fine-tuned on your labelled rows (`scripts/train_classifier.py`) — the "isn't a judgment model just a classifier?" row | **softmax probability of the chosen option** from the classification head; reads only the state text | `pip install 'kunko-judge-audit[nli]'` + `FINETUNED_MODEL_DIR`; optional `FINETUNED_DEVICE`, `FINETUNED_MAX_LEN` |
| `laya` | Laya, an open-weight judgment model (Convai Innovations, Apache-2.0) run locally: an encoder that scores every option in one forward pass | **the probability of the chosen option**, after the checkpoint's softmax temperature; never Laya's entropy-based `confidence` field | `pip install 'kunko-judge-audit[laya]'`; `LAYA_REVISION` recommended; optional `LAYA_MODEL`, `LAYA_DEVICE`, `LAYA_MAX_LEN`, `LAYA_HEAD_MAX_LEN` |
| `simulated` | nothing real — a seeded simulator to see the pipeline | drawn from a distribution | nothing; output is stamped SIMULATED |

## Same dataset, several judges = the Arena

Every adapter records `describe()` (model, backend, endpoint, confidence method) into the report's provenance, so runs are comparable and attributable. Two fields say whether two runs asked the same question in the same way:

- **`temperature`** — every judge declares it, and a judge that has no such parameter declares `"n/a"` rather than leaving it out. Both `llm` paths (the Anthropic SDK and the OpenAI-compatible endpoint) send `temperature: 0`: an audit has to be reproducible, and a confidence measured at one sampling temperature says nothing about another. Jev returns a distribution rather than a sample, and the NLI encoder does not sample, so both are `"n/a"`.
- **`prompt_sha256`** — the digest of what the `llm` judge is actually shown: the `SYSTEM` prompt plus the render template. Edit either and the digest moves, so a report cannot silently change the question it asked. Jev has no text prompt; it records `criteria_version` instead, the version of the criteria map built from each question's options and descriptions. `judge-audit check` warns (it does not fail) when the baseline's prompt hash differs from the current one.


```bash
# Jev via gateway
judge-audit run examples/email-routing-adversarial/labels.jsonl --judge jev --json jev.json

# OpenJev, self-hosted
JEV_BACKEND=typesafe JEV_ENDPOINT=https://my-openjev/v1/systemone JEV_NAME=openjev \
  judge-audit run examples/email-routing-adversarial/labels.jsonl --judge jev --json openjev.json

# Claude, verbalized confidence
LLM_MODEL=claude-opus-5 judge-audit run examples/email-routing-adversarial/labels.jsonl --judge llm --json claude.json

# A local open model through Ollama
LLM_PROVIDER=openai-compatible LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.1 \
  judge-audit run examples/email-routing-adversarial/labels.jsonl --judge llm --json llama.json
```

Compare `ece`, `zero_error_coverage` and the prompt-injection confidence drop across the JSON files. The Judge Arena (roadmap v0.5) is this table, published and continuously updated.

## Laya: a second judgment model, open and local

Jev is one judgment model; a result about "judgment models" needs more than one. `laya` runs Laya (Convai Innovations, Apache-2.0, weights public) on your machine: a ModernBERT-class encoder with a decision head, 421M parameters in its English checkpoint, that returns a probability per option in one forward pass. Because the weights are public, anyone can reproduce its row at no cost. What the adapter records, from Laya's own code (v0.3.20):

- **Confidence is `probabilities[choice]`**, the probability of the chosen option (Laya also returns it as `answer_confidence`). Laya's `confidence` field is a normalised entropy, 1 − H(p)/log k, on another scale; its documentation says it is not calibrated. It is kept in `raw` as `entropy_confidence` and never used, for the same reason Jev's API `confidence` field is not used.
- **The checkpoint's softmax temperatures, shipped and applied.** Laya divides the logits by a temperature per question type and number of options that ships with the checkpoint, and the library clamps values outside [0.5, 5]. The shipped value for choices with 11 or more options sharpens the logits roughly tenfold; the library applies 0.5 instead. Both values change every probability, so both are in the provenance (`softmax_temperature`), with the package version and the checkpoint revision.
- **Token budgets.** A question's options share `head_max_len` tokens (192 in the shipped config), and options that do not fit make Laya raise rather than truncate. BANKING77's 77 intent names need more; raising `LAYA_HEAD_MAX_LEN` runs Laya outside the budget it was trained with, and Laya's own alternative is to shortlist options with a separate embedding model first. Which one v0.5 uses is a pre-registration decision.
- **The act head.** `act_probability`, Laya's own act-or-escalate signal, is kept in `raw` for an abstention analysis.

## Why an NLI control

`nli` is a ~180M-parameter encoder that scores each option as a hypothesis against the state and returns the softmax over options. It cannot follow instructions, so prompt injection cannot reach it by construction; its probabilities are real, not written; it runs on a laptop for free. It also cannot reason and reads a short context. It is a **control**, not a competitor: the row that shows what "small, instruction-immune, real softmax" looks like before any training, so the fine-tuned row and the LLM rows can be read against it. Option descriptions, when present, are used as the hypotheses — the same lever the router ablation tests.

## The fine-tuned classifier: your own classifier as a row

`finetuned` answers the CTO's question — "isn't Jev just a classifier? I could fine-tune one on my labels" — with numbers instead of opinions. `scripts/train_classifier.py --dataset email-routing` fine-tunes `microsoft/deberta-v3-base` as a sequence classifier on the **train half** of a pre-registered split (`examples/<dataset>/split-heldout.json`, seed 2026, label-stratified, committed before any training run) and writes the model under `~/.cache/judge-audit/finetuned/<dataset>/` (never committed) plus `docs/runs/finetuned/<dataset>.train.json` (hyper-parameters, seed, per-epoch loss, wall time, backbone and revision, sha256 of the train rows, hardware — committed). The judge then runs like any other:

```bash
FINETUNED_MODEL_DIR=~/.cache/judge-audit/finetuned/email-routing \
  judge-audit run examples/email-routing/labels.jsonl --judge finetuned --json ft.json
```

What it is, by construction — and what every report using it says next to the numbers:

- **Confidence is the softmax probability of the chosen option** from the classification head, over the labels it was trained on. Options are mapped by label id (`config.json` → `id2label`); an option the model never saw is ignored and listed in `raw.ignored_options`; a question with no trained option is an error, never a guess.
- **It cannot follow instructions.** The only input is the state text; the question, its instructions and the option descriptions never reach the model. Prompt injection cannot *instruct* it, but text that resembles another category can still mislead it — and the softmax does not know it is under attack.
- **It cannot use option descriptions.** On the task router the bare and described files share texts, so one model serves both and must score identically; the gap to a judge that reads the descriptions is what the descriptions are worth.
- **It only knows its training distribution.** Its held-out numbers (docs/finetuned-baseline-2026-09.md) come from an index-level split of the *same seeded generator* — the best case for a classifier — and say nothing about drift, new categories or real inboxes. The generators repeat texts, so the report counts, next to every n, the held-out rows whose text equals or contains a training text and scores the unseen-text rows separately ([#54](https://github.com/kunko-ai-labs/judge-audit/issues/54)).
- **Temperature scaling is the knob you own.** `scripts/train_classifier.py --run 2` fits one temperature on a validation slice carved from the train half (never the held-out half) and writes it to `judge-audit.json`; the judge divides the logits by it before the softmax, `FINETUNED_TEMPERATURE=1` switches it off. A vendor judge exposes no such knob. It changes confidence, never decisions — and when the validation slice is classified perfectly the temperature is not identified, which the record and the report say.
- `describe()` records the backbone and revision, the training-set digest, the split file, the seed and the sha256 of `config.json`, so a run is attributable to one trained artefact.

Evaluate it only on rows it did not train on: `scripts/audit_resumable.py … --rows examples/<dataset>/split-heldout.json:heldout` judges the held-out indices alone and records the split and its sha256 in the checkpoint header.

## Why two kinds of confidence

A judgment model returns a probability distribution over options; the confidence *is* the probability of the chosen option. A chat model has no such distribution exposed — it says "0.9" in text. Verbalized confidence is what almost everyone deploys and what the literature finds worst calibrated; auditing it is not a limitation of the tool, it is the audit people need.

## Writing an adapter

```python
from judge_audit import Judge, Question, Judgment

class MyJudge(Judge):
    name = "my-judge"

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        # call your model; return the probability of the option you chose as confidence
        return [Judgment(question=q.name, decision="spam", confidence=0.93,
                         latency_s=0.2, cost_usd=0.0001, raw={...}) for q in questions]

    def describe(self) -> dict:          # lands in every report's provenance line
        return {"name": self.name, "model": "my-model-v3"}
```

Register it in `src/judge_audit/cli.py` (`JUDGES` + `_judge`), add a test with the network mocked (see `tests/test_llm_judge.py`), and send a PR.

## MCP

`judge-audit-mcp` exposes the same engine to any MCP client (`run_audit`, `check_drift`, `list_judges`), so an agent can audit the judge it is about to rely on from inside its own session. Setup for Claude Code and Cursor in [integrations.md](integrations.md).

## Token budgets and unparseable replies

A reply the adapter cannot parse counts as a wrong, zero-confidence decision — the house rule — and the raw text is kept in the checkpoint. Two causes seen in the Arena, and what to do about them:

- **Reasoning models that spend the budget before answering.** DeepSeek R1 returned an empty reply on 20–23 router rows because a 1,024-token budget was consumed by its reasoning channel. Give reasoning models at least 4,096 output tokens (`LLM_MAX_TOKENS` for the Anthropic SDK path and the private-provider example; the OpenAI-compatible path leaves the endpoint's default). A checkpoint whose `raw.text` is empty with `output_tokens` at the budget is a truncation, not an opinion.
- **JSON wrapped in prose.** Claude Sonnet 4.5 sometimes answers with a fenced JSON object followed by a "Reasoning" paragraph, or prose containing `{'a': 1}` before the object. The parser now scans every candidate object and prefers one with an `answers` key. Because raw text is kept, `python scripts/reparse_checkpoints.py` recomputes decisions offline when the parser improves, and records the reparse in the checkpoint header.

## Three calibration numbers

Every report prints three numbers for "is the confidence honest?", and a fourth, log loss, next to them. They answer slightly different questions, so they sit side by side and are never combined into one score. Lower is better for all of them; 0 is perfect.

- **ECE** (expected calibration error, `expected_calibration_error`) — sort the answers into ten fixed confidence ranges (0.0–0.1, …, 0.9–1.0), compare the average confidence with the share that was right in each range, and average the gaps weighted by how many answers fell there. It is the number people know, and every ECE published before this release is computed exactly this way (a test pins every one of them). Its weakness is small samples that pile up: when a judge says 0.9–1.0 on nearly every row, nine ranges are empty and the whole number is decided by one crowded range, where confident mistakes and cautious right answers can average each other out.
- **ECE (equal-mass)** (`expected_calibration_error(..., binning="equal_mass")`) — the same gap, but the ten groups are cut so each holds about a tenth of the answers instead of a tenth of the 0–1 scale. **The tie rule used here:** sort the answers by confidence; the ideal cuts fall after answers n/10, 2n/10, …; a cut may only fall between two *different* confidences, so a cut that lands inside a run of equal confidences moves to the nearer end of that run (to the lower end when both are equally near), and cuts that land on the same place merge. Answers with the same confidence therefore always share a group, groups can be larger than a tenth and there can be fewer than ten (a judge that says 1.0 on 125 of 200 rows gets one group of 125), and the value never depends on row order. **This number is sensitive to the tie rule when a judge uses few distinct confidences** (roughly seven or fewer; under attack the Arena's chat models use 3 to 9): another defensible rule — cut at the confidence quantiles and let a tied run join the lower group, as scikit-learn's quantile strategy does — gives different groups and a different number. Under attack (n=200) it gives Claude Sonnet 4.5 0.031, Gemini 3 Flash 0.037 and Jev 0.037, where the rule used here gives 0.044, 0.044 and 0.037. The robust check is Brier, which has no groups at all.
  Worked example, Llama 3.3 70B on the emails under attack (n=200): it said 0.9 on 160 answers (98.8 % right: *under*-confident), 0.99 on 11 (all right) and 1.0 on 12 (all wrong). The fixed 0.9–1.0 range pools all 183 into one average (confidence 0.912, accuracy 92.3 %), where the under-confidence of the 160 and the over-confidence of the 23 cancel, and the ECE reads **0.015 [0.005, 0.060]**. The equal-mass groups put the 160 answers at 0.9 in one group and the 23 at 0.99–1.0 in another (confidence 0.995, 47.8 % right), so they stop cancelling: the 0.9 group contributes 0.070 and the top group 0.059, and the equal-mass ECE reads **0.133 [0.103, 0.174]**. That one survives the tie rule (0.1335 with the quantile rule) and Brier agrees: 0.085 [0.051, 0.121] against about 0.03 for Sonnet 4.5 and Gemini 3 Flash.
- **Brier** (`brier_score`) — for every answer, the squared distance between the stated confidence and what happened (1 if right, 0 if wrong), averaged. It needs no groups at all, so no grouping choice can move it. It is a *proper scoring rule*: a judge cannot improve it by misreporting its confidence. But it also rewards being right, so it is not a calibration number alone — of two equally honest judges, the more accurate one has the lower Brier. Read it next to accuracy.

**NLL (log loss), never clipped** (`negative_log_likelihood`). The other standard proper score: the average of −ln(probability the judge gave to what happened). It punishes a confident mistake far harder than Brier — a wrong 0.99 costs 4.6, a wrong 0.6 costs 0.92. It is infinite as soon as a judge says 1.0 and is wrong (Llama 3.3 70B above does that 12 times, and chat models say 1.0 often). The usual fix is to clip 1.0 to something like 0.9999 first, but that replaces the confidence the judge declared with one it never gave — imputation, which this repository does not do. So a report prints the number when it is finite, and otherwise **∞** with the count of answers declared certain and wrong (`nll_infinite`), with no interval. That count is itself the finding: no confidence threshold can separate those answers from the judge's certain answers that were right.

**The metrics refuse a NaN; they do not clamp it.** The three calibration numbers, and every path that reads a confidence from a checkpoint (`runner.clamp_confidence`), stop with an error naming the row when a confidence is not a finite number (NaN, ±infinity). Clamping it into [0, 1] would turn NaN into 1.0, a full-confidence answer the judge never gave. One gap remains: the chat-model adapter (`judges/llm.py`) still clamps a model that *writes* `"confidence": "NaN"` to 1.0 when it parses the reply, before the metrics see it. Its handling of NaN and missing confidences is addressed in #70.

Each number carries the same 95 % interval as the others (§ Confidence intervals below): the clustered bootstrap over distinct texts, bins rebuilt on every resample. In the Arena the three numbers do not order the judges the same way, and most of those reversals are within overlapping intervals; the Arena report counts them under its tables and leaves the rankings separate. A point estimate that lies outside its own percentile-bootstrap interval is marked **◊**. This happens when a binned ECE's resamples are biased away from it on that sample: DeBERTa NLI's equal-mass ECE on the described-options router is 0.2131, and its interval is [0.2425, 0.4501].

## Latency percentiles

p50 and p99 are interpolated between order statistics (Hyndman–Fan type 7: numpy's default, `statistics.quantiles(method="inclusive")`), the same rule the bootstrap uses to cut its interval. With 200 rows a p99 sits between the second- and third-slowest rows, so one or two stalled calls barely move it: every report that prints a p99 (run reports, the adversarial audit, the Action's PR comment) therefore prints the slowest call next to it.

## Confidence intervals

Every headline number — accuracy, ECE, zero-error coverage, and the majority accuracy of a jury — is a statistic of a few hundred rows at most, so each one is published with a 95 % interval in the compact form `66.7% [52.5, 80.3]` (Jev on the bare-label router): how far the number would move on another sample of the same size, drawn the same way. Two methods produce those intervals — a clustered bootstrap by default, and the exact binomial interval at the boundary where the bootstrap degenerates — and every table says which one it printed.

**Method.** Percentile bootstrap (`judge_audit.metrics.calibration.bootstrap_ci`): the data is resampled with replacement 2,000 times with `random.Random(0)`, the statistic is recomputed on each resample (ECE with its bins rebuilt, zero-error coverage with its prefix re-sorted, a jury's majority recomputed per resampled row), and the interval is the 2.5th and 97.5th percentile of those 2,000 values — linear interpolation between order statistics, the same cut as `statistics.quantiles(method="inclusive")`, rounded to four decimals. Pure Python, no NumPy; the seed is fixed so a published interval recomputes to the digit from its checkpoint, on every supported Python version.

**What gets resampled: distinct texts, not rows.** The datasets repeat states. The task router has 61 distinct texts in its 120 rows, and only 14 behind the 40 hard rows; the adversarial email set has 189 in 200. Two judgments of the same text are not two independent observations of the judge, so the published intervals are a **cluster bootstrap**: whole texts are drawn with replacement and all of their rows come along (`bootstrap_ci(..., groups=[...])`; the reports and the CLI pass the row's `state`, and a round-2 deliberation record is indexed against the same source dataset, so both rounds cluster on the original state, never on the prompt built around it). `groups=None` gives the ordinary row-i.i.d. bootstrap; it stays in the API and under test, but it is not what the repo publishes, because on the router it would advertise a precision this benchmark does not have — the hard-task majority reads 15 % [5.0, 27.5] row-wise and 15 % [0.0, 34.2] by text.

**Where the bootstrap degenerates: the exact interval (†).** A bootstrap cannot move when the statistic cannot. Ten rows all correct resample to ten correct every time, so the interval read `[100.0, 100.0]` — a claim of certainty from ten observations, published 186 times before v0.4.0 in a repository about not overstating confidence. The clustered bootstrap is still computed first, because it is the one that honours the repeated texts; only when it comes back with **zero width** does a **proportion** (accuracy, zero-error coverage, a jury's majority accuracy, accuracy under prompt injection or social engineering) fall back to the **Clopper–Pearson exact binomial** interval: the inversion of the binomial test, `[Beta(k, n−k+1)_{0.025}, Beta(k+1, n−k)_{0.975}]`, computed in pure Python from `math.lgamma` and a bisection (`judge_audit.metrics.calibration.clopper_pearson`). 0/10 → `[0.0, 30.9]`, 10/10 → `[69.2, 100.0]`, 8/10 → `[44.4, 97.5]`, 0/200 → `[0.0, 1.8]`. Every such interval is marked **†** in the tables, and the JSON says which machinery produced each one in an `<name>_ci_method` field (`clopper-pearson` or `bootstrap`) next to the pair.

**0 % is not automatically exact.** What decides is whether the resamples move, not whether the point estimate sits on the boundary. Claude Sonnet 4.5's zero-error coverage under attack is 0 % because two of its 24 answers tied at confidence 1.0 are wrong — but a resample of the texts that misses both covers everything, so the bootstrap has width and `0 % [0.0, 90.9]` is what gets published. Gemini 3 Flash's 0 % on the same dataset is not like that: its five top-confidence errors survive 99 % of resamples, the percentile cut closes on zero, and the exact `0 % [0.0, 1.8]†` replaces it. The rule keeps the clustering wherever the clustering still has something to say. That width also moves between runs of the same judge: in three pre-registered repeats Sonnet changed none of its decisions, but its tied group at 1.0 held 27, 29 and 32 answers (two wrong each time) and the upper bound read 33.5 %, 33.5 % and 90.9 % ([repeat runs](repeats-2026-09.md)).

**A † interval is a lower bound on the width.** Clopper–Pearson counts rows, not texts: it assumes 200 independent observations where the adversarial set has 189 distinct emails, and 120 where the router has 61. It is therefore *narrower* than an honest clustered interval would be, and is read correctly as "at least this wide". It is published where the bootstrap degenerates because the alternative there is not a wider interval but no interval at all: zero width is an artefact of a statistic that cannot move, and a conservative exact bound is the smallest honest thing that can be said.

**Degenerate bootstrap (‡).** ECE is not a proportion — there is no k out of n to invert — so it keeps the clustered bootstrap whatever it returns. When every resample gives the same ECE (a judge that says one confidence and is right every time), the interval has zero width; the reports then print the point estimate followed by **‡** and no brackets, rather than a `[x, x]` that would read as precision. Six cells carry a ‡ today, all of them the temperature-scaled fine-tuned run.

**Reading it.** Two judges whose intervals overlap are not separated by this data. Zero-error coverage hinges on its most-confident errors, so its interval can be very wide (Claude Sonnet 4.5 under attack: 0 % [0.0, 90.9]). That width is sampling, not tie order: 24 of its 200 answers are tied at confidence 1.0 and two of them are wrong, so the coverage depends on whether a resample of the texts keeps either — 87 % keep one and score zero, and the top of the interval is the 5 % of resamples that miss both. A percentile bootstrap says nothing about bias either: a synthetic dataset with a template leak stays a floor however narrow its interval.

**Zero-error coverage, accuracy-coverage and ties.** Both selective-coverage metrics obey the same rule: rows are walked from the most confident down in groups of equal confidence, and a coverage point is only reported at a cut that includes a *whole* group. A tie is one threshold — you cannot automate half of the rows that say 0.95 — so a group is all in or all out, never split by whichever order the rows happened to sort in. `zero_error_coverage` uses it to find the largest clean prefix: a group counts only when every row in it is right and no error was seen above it; `threshold` is the lowest confidence in the covered prefix, `None` when nothing is covered. `accuracy_coverage` uses it to place every point of its curve: each of the 20 target coverage levels snaps *up* to the end of the group it falls inside (several targets landing inside the same group collapse to that group's single point, so a judge with few distinct confidence values publishes a short curve rather than a padded one), and `min_confidence` is the covered group's own confidence; reports print every point of it. A confidence that is not a finite number (NaN, ±inf) is refused with an error rather than placed somewhere in the order: unknown confidence is never imputed. Both point estimates are the same whatever order the rows come in (`tests/test_calibration.py` shuffles the input, 50 times for zero-error coverage and 1,000 times for accuracy-coverage, and asserts the result does not move). A chat model that says 1.0 to most of a dataset and gets one of those wrong therefore scores 0 % zero-error coverage: that is what a deployment at its own threshold would have seen. Before v0.4.0 both metrics cut at a row index instead of a group boundary, so a tie's internal order could decide the number.

**Cost.** 200 rows × 2,000 resamples × five statistics (accuracy, the three calibration numbers, zero-error coverage) takes about 0.4 s; regenerating the Arena, consensus and jury reports takes about 13 s in total, and the 54 per-judge reports under `docs/runs/` (`scripts/runs_report.py`) about 17 s.

**Skipping it.** `judge-audit run --no-ci`, or `JUDGE_AUDIT_BOOTSTRAP=0` in the environment, leaves the `*_ci` fields out of the JSON and the brackets out of the report. `check --drift` compares point estimates and is unaffected.
