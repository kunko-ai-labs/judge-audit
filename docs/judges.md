# Judges: what plugs in and how

judge-audit audits anything that maps `(state, questions) -> (decision, confidence)`. Five adapters ship; writing a sixth is ~30 lines.

| `--judge` | What it audits | Confidence comes from | Needs |
|---|---|---|---|
| `jev` | TypeSafe Jev, a purpose-built judgment model | the per-option probability the model returns | `AI_GATEWAY_API_KEY` + Node (gateway) **or** `JEV_BACKEND=typesafe` + `TYPESAFE_API_KEY` |
| `jev` + `JEV_ENDPOINT` | any Jev-compatible server: [OpenJev](https://github.com/ekzhang/openjev-sglang), other open re-implementations of the `/v1/systemone` API | same — the server's probability distribution | `JEV_BACKEND=typesafe JEV_ENDPOINT=http://host/v1/systemone` (key optional) |
| `llm` | a chat model with a "classify and say how sure you are" prompt — what most production judges actually are | **verbalized**: the model writes a number | Anthropic: `pip install 'judge-audit[anthropic]'` + `ANTHROPIC_API_KEY` · OpenAI-compatible (OpenAI, Ollama, vLLM, LM Studio): `LLM_PROVIDER=openai-compatible LLM_BASE_URL=… LLM_MODEL=…` |
| `nli` | a small zero-shot encoder (DeBERTa-class cross-encoder) — the **control** row: small, instruction-immune, real softmax confidence; not a competitor | **NLI entailment softmax** over the options: a real probability, computed locally | `pip install 'kunko-judge-audit[nli]'`; optional `NLI_MODEL`, `NLI_HYPOTHESIS`, `NLI_DEVICE` |
| `finetuned` | **your own classifier**: a DeBERTa-class encoder fine-tuned on your labelled rows (`scripts/train_classifier.py`) — the "isn't a judgment model just a classifier?" row | **softmax probability of the chosen option** from the classification head; reads only the state text | `pip install 'kunko-judge-audit[nli]'` + `FINETUNED_MODEL_DIR`; optional `FINETUNED_DEVICE`, `FINETUNED_MAX_LEN` |
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

## Confidence intervals

Every headline number — accuracy, ECE, zero-error coverage, and the majority accuracy of a jury — is a statistic of a few hundred rows at most, so each one is published with a 95 % interval in the compact form `66.7% [52.5, 80.3]` (Jev on the bare-label router): how far the number would move on another sample of the same size, drawn the same way. Two methods produce those intervals — a clustered bootstrap by default, and the exact binomial interval at the boundary where the bootstrap degenerates — and every table says which one it printed.

**Method.** Percentile bootstrap (`judge_audit.metrics.calibration.bootstrap_ci`): the data is resampled with replacement 2,000 times with `random.Random(0)`, the statistic is recomputed on each resample (ECE with its bins rebuilt, zero-error coverage with its prefix re-sorted, a jury's majority recomputed per resampled row), and the interval is the 2.5th and 97.5th percentile of those 2,000 values — linear interpolation between order statistics, the same cut as `statistics.quantiles(method="inclusive")`, rounded to four decimals. Pure Python, no NumPy; the seed is fixed so a published interval recomputes to the digit from its checkpoint, on every supported Python version.

**What gets resampled: distinct texts, not rows.** The datasets repeat states. The task router has 61 distinct texts in its 120 rows, and only 14 behind the 40 hard rows; the adversarial email set has 189 in 200. Two judgments of the same text are not two independent observations of the judge, so the published intervals are a **cluster bootstrap**: whole texts are drawn with replacement and all of their rows come along (`bootstrap_ci(..., groups=[...])`; the reports and the CLI pass the row's `state`, and a round-2 deliberation record is indexed against the same source dataset, so both rounds cluster on the original state, never on the prompt built around it). `groups=None` gives the ordinary row-i.i.d. bootstrap; it stays in the API and under test, but it is not what the repo publishes, because on the router it would advertise a precision this benchmark does not have — the hard-task majority reads 15 % [5.0, 27.5] row-wise and 15 % [0.0, 34.2] by text.

**Where the bootstrap degenerates: the exact interval (†).** A bootstrap cannot move when the statistic cannot. Ten rows all correct resample to ten correct every time, so the interval read `[100.0, 100.0]` — a claim of certainty from ten observations, published 186 times before v0.4.0 in a repository about not overstating confidence. The clustered bootstrap is still computed first, because it is the one that honours the repeated texts; only when it comes back with **zero width** does a **proportion** (accuracy, zero-error coverage, a jury's majority accuracy, accuracy under prompt injection or social engineering) fall back to the **Clopper–Pearson exact binomial** interval: the inversion of the binomial test, `[Beta(k, n−k+1)_{0.025}, Beta(k+1, n−k)_{0.975}]`, computed in pure Python from `math.lgamma` and a bisection (`judge_audit.metrics.calibration.clopper_pearson`). 0/10 → `[0.0, 30.9]`, 10/10 → `[69.2, 100.0]`, 8/10 → `[44.4, 97.5]`, 0/200 → `[0.0, 1.8]`. Every such interval is marked **†** in the tables, and the JSON says which machinery produced each one in an `<name>_ci_method` field (`clopper-pearson` or `bootstrap`) next to the pair.

**0 % is not automatically exact.** What decides is whether the resamples move, not whether the point estimate sits on the boundary. Claude Sonnet 4.5's zero-error coverage under attack is 0 % because two of its 24 answers tied at confidence 1.0 are wrong — but a resample of the texts that misses both covers everything, so the bootstrap has width and `0 % [0.0, 90.9]` is what gets published. Gemini 3 Flash's 0 % on the same dataset is not like that: its five top-confidence errors survive 99 % of resamples, the percentile cut closes on zero, and the exact `0 % [0.0, 1.8]†` replaces it. The rule keeps the clustering wherever the clustering still has something to say.

**A † interval is a lower bound on the width.** Clopper–Pearson counts rows, not texts: it assumes 200 independent observations where the adversarial set has 189 distinct emails, and 120 where the router has 61. It is therefore *narrower* than an honest clustered interval would be, and is read correctly as "at least this wide". It is published where the bootstrap degenerates because the alternative there is not a wider interval but no interval at all: zero width is an artefact of a statistic that cannot move, and a conservative exact bound is the smallest honest thing that can be said.

**Degenerate bootstrap (‡).** ECE is not a proportion — there is no k out of n to invert — so it keeps the clustered bootstrap whatever it returns. When every resample gives the same ECE (a judge that says one confidence and is right every time), the interval has zero width; the reports then print the point estimate followed by **‡** and no brackets, rather than a `[x, x]` that would read as precision. Six cells carry a ‡ today, all of them the temperature-scaled fine-tuned run.

**Reading it.** Two judges whose intervals overlap are not separated by this data. Zero-error coverage hinges on its most-confident errors, so its interval can be very wide (Claude Sonnet 4.5 under attack: 0 % [0.0, 90.9]). That width is sampling, not tie order: 24 of its 200 answers are tied at confidence 1.0 and two of them are wrong, so the coverage depends on whether a resample of the texts keeps either — 87 % keep one and score zero, and the top of the interval is the 5 % of resamples that miss both. A percentile bootstrap says nothing about bias either: a synthetic dataset with a template leak stays a floor however narrow its interval.

**Zero-error coverage and ties.** The prefix is cut at whole confidence groups: rows are walked from the most confident down in groups of equal confidence, and a group counts only when every row in it is right and no error was seen above it. A tie is one threshold — you cannot automate half of the rows that say 0.95 — so the point estimate is the same whatever order the rows come in (`tests/test_calibration.py` shuffles the input and asserts the result does not move). `threshold` is the lowest confidence in the covered prefix, `None` when nothing is covered. A chat model that says 1.0 to most of a dataset and gets one of those wrong therefore scores 0 %: that is what a deployment at its own threshold would have seen. Before v0.4.0 the prefix was cut at the first error in a sorted list, so a tie's internal order decided the number.

**Cost.** 200 rows × 2,000 resamples × three statistics takes about 0.2 s; regenerating the Arena, consensus and jury reports takes about 7 s in total.

**Skipping it.** `judge-audit run --no-ci`, or `JUDGE_AUDIT_BOOTSTRAP=0` in the environment, leaves the `*_ci` fields out of the JSON and the brackets out of the report. `check --drift` compares point estimates and is unaffected.
