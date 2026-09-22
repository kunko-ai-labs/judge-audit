# Judges: what plugs in and how

judge-audit audits anything that maps `(state, questions) -> (decision, confidence)`. Four adapters ship; writing a fifth is ~30 lines.

| `--judge` | What it audits | Confidence comes from | Needs |
|---|---|---|---|
| `jev` | TypeSafe Jev, a purpose-built judgment model | the per-option probability the model returns | `AI_GATEWAY_API_KEY` + Node (gateway) **or** `JEV_BACKEND=typesafe` + `TYPESAFE_API_KEY` |
| `jev` + `JEV_ENDPOINT` | any Jev-compatible server: [OpenJev](https://github.com/ekzhang/openjev-sglang), other open re-implementations of the `/v1/systemone` API | same — the server's probability distribution | `JEV_BACKEND=typesafe JEV_ENDPOINT=http://host/v1/systemone` (key optional) |
| `llm` | a chat model with a "classify and say how sure you are" prompt — what most production judges actually are | **verbalized**: the model writes a number | Anthropic: `pip install 'judge-audit[anthropic]'` + `ANTHROPIC_API_KEY` · OpenAI-compatible (OpenAI, Ollama, vLLM, LM Studio): `LLM_PROVIDER=openai-compatible LLM_BASE_URL=… LLM_MODEL=…` |
| `nli` | a small zero-shot encoder (DeBERTa-class cross-encoder) — the classic "small model" baseline; cannot follow instructions by design | **NLI entailment softmax** over the options: a real probability, computed locally | `pip install 'kunko-judge-audit[nli]'`; optional `NLI_MODEL`, `NLI_HYPOTHESIS`, `NLI_DEVICE` |
| `simulated` | nothing real — a seeded simulator to see the pipeline | drawn from a distribution | nothing; output is stamped SIMULATED |

## Same dataset, several judges = the Arena

Every adapter records `describe()` (model, backend, endpoint, confidence method) into the report's provenance, so runs are comparable and attributable:

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

## Why an NLI baseline

`nli` is a ~180M-parameter encoder that scores each option as a hypothesis against the state and returns the softmax over options. It cannot follow instructions, so prompt injection cannot reach it by construction; its probabilities are real, not written; it runs on a laptop for free. It also cannot reason and reads a short context. That is the point: it is the baseline any judgment model or LLM judge has to beat, and the row that tells you whether a task needed a bigger model at all. Option descriptions, when present, are used as the hypotheses — the same lever the router ablation tests.

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

Every headline number — accuracy, ECE, zero-error coverage, and the majority accuracy of a jury — is a statistic of a few hundred rows at most, so each one is published with a 95 % interval in the compact form `66.7% [55.8, 75.0]`: how far the number would move on another sample of the same size from the same judge.

**Method.** Percentile bootstrap over rows (`judge_audit.metrics.calibration.bootstrap_ci`): the rows are resampled with replacement 2,000 times with `random.Random(0)`, the statistic is recomputed on each resample (ECE with its bins rebuilt, zero-error coverage with its prefix re-sorted, a jury's majority per resampled row), and the interval is the 2.5th and 97.5th percentile of those 2,000 values (linear interpolation between order statistics, rounded to four decimals). Rows, never bins, are the unit — so any statistic of rows can be bootstrapped the same way. Pure Python, no NumPy; the seed is fixed so a published interval recomputes to the digit from its checkpoint, on every supported Python version. 200 rows × 2,000 resamples × three statistics takes about 0.2 s; regenerating the whole Arena, consensus and jury reports takes about 6 s.

**Reading it.** Two judges whose intervals overlap are not separated by this data. On 40 hard rows an interval is about ±15 points wide, which is why the jury tables carry it next to every majority accuracy. Zero-error coverage hinges on the single most-confident error, so its interval can be very wide (Claude Sonnet 4.5 under attack: 2 % [0.0, 91.5]) — that width is the finding, not a defect of the method. A percentile bootstrap says nothing about bias, only about sampling noise; a synthetic dataset with a template leak stays a floor however narrow its interval.

**Skipping it.** `judge-audit run --no-ci`, or `JUDGE_AUDIT_BOOTSTRAP=0` in the environment, leaves the `*_ci` fields out of the JSON and the brackets out of the report. `check --drift` compares point estimates and is unaffected.
