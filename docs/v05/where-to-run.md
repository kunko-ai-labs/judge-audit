# What runs where

**Short version.** Local judges (Laya, the token log-probability judge, local chat models, the fine-tuned classifier) run on your own computer: Apple silicon (CPU or Apple GPU) or Linux. Hosted judges (Claude, Gemini, Jev, hosted open models) run from any machine that holds the keys. CI runs no real model: it recomputes every published number from the committed checkpoints (its only model is a tiny random one that tests the MLX code path).

## The judges

| Judge | What it is | Where it runs | Needs |
|---|---|---|---|
| `laya` | Laya, an open judgment model (421M-parameter ModernBERT-large encoder, per Laya's code at v0.3.20) | **your computer** (CPU or Apple GPU); any Linux box that can download it | the `[laya]` extra (from source until v0.5 is on PyPI), `LAYA_REVISION` pinned |
| `logprob` | An open chat model's own probability of each option (MLX) | **Apple silicon**; Linux CPU works but is slow | the `[mlx]` extra (from source until v0.5), `LOGPROB_MODEL`, `LOGPROB_REVISION` |
| `llm` via a local server | An open chat model, verbalized or self-consistency | **your computer** (a local OpenAI-compatible server such as Ollama) | `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL` |
| `finetuned` | Your own classifier trained on your labels (`scripts/train_classifier.py`) | **your computer** (training and inference) | the `[nli]` extra, `FINETUNED_MODEL_DIR` |
| `nli` | A small zero-shot encoder, the control | anywhere, CPU is enough | the `[nli]` extra |
| `llm` hosted | Claude, Gemini, hosted open models | anywhere with the key | `ANTHROPIC_API_KEY`, or `LLM_BASE_URL` + `LLM_API_KEY`, or the private provider module |
| `jev` | Jev through its API | anywhere with the key | the Jev key |
| `simulated` | A seeded simulator, always tagged SIMULATED | anywhere, CI | nothing |

So the answer to "what must run locally?" is: **Laya, the log-probability judge, the local chat models and the fine-tuned classifier.** The hosted judges can run from the same computer, or from any machine with the keys, including a CI job with secrets (see [use it in your workflow](use-in-your-workflow.md)).

## Sizing

Apple silicon shares memory between CPU and GPU, and macOS caps how much of it the GPU can use (Metal reports it as `recommendedMaxWorkingSetSize`). A rule of thumb, not a measurement, for 4-bit models by the memory available:

| Memory | Comfortable | Tight |
|---|---|---|
| 16 GB | Laya; 7–8B chat models (about 5 GB) | 12–14B (about 8–9 GB) |
| 24 GB | Laya; up to 14B; a 20B model in 4-bit (about 12 GB) | larger |

Before any published `logprob` run, `python scripts/logprob_selfcheck.py <labels.jsonl> --rows 20` checks on the real model that the cached scoring equals a full forward pass, and measures rows per minute. mlx-lm has an open report of prompt caching returning different logits, so this is not optional.

## Long runs

`scripts/audit_resumable.py` writes one checkpoint row per decision and resumes where it stopped. It refuses to resume a checkpoint recorded with a different judge, row subset, gateway routing, model, confidence method, temperature, number of samples or prompt. Run it in the background and watch the row count. Checkpoints are committed; every published number is recomputed from them.

`--max-usd X` sets a cost ceiling: above $0, up to $1,000,000, to 6 decimal places (anything else is a usage error). Before each request the driver sums the `cost_usd` the checkpoint records, rows from earlier sessions of the same checkpoint included; once that sum is at or above X it stops before the next request with `cost ceiling reached: $… recorded of $X` and exit code 3. Because the check comes before each request, the last row sent can take the total past X by its own cost. A judgment recorded with unknown cost also stops the run under `--max-usd`, since the ceiling can no longer be enforced; local judges record $0 and run on. The rows already written stay a valid checkpoint. The header records the ceiling as `max_usd`, the value the driver enforces, and a checkpoint resumes under that ceiling. Going past it needs a dated amendment: resume with the new `--max-usd` and `--ceiling-amendment "<ref>"` (one printable line, for example `"v06-plan amendment 2026-10-20"`). A run stopped on an unknown cost continues the same way under the same `--max-usd`: the amendment acknowledges the unknown costs recorded so far, and a later one stops the run again. The driver then rewrites only the header line: `max_usd` becomes the new ceiling, and `max_usd_history` gains an entry with the previous ceiling, the rows judged under it (`until_rows`), the unknown-cost judgments recorded by then (`unknown_cost_judgments`), the reference and the time of the change (`changed_utc`). The other lines keep their bytes, the file keeps its mode, and the rows already judged are not paid for again; if the rewrite fails, the checkpoint is left as it was. Refused: a different ceiling without an amendment, an amendment that changes nothing, a reference already recorded, and resuming without `--max-usd` a checkpoint that has one (an amendment changes a ceiling, it does not remove it). A stopped run that is kept is declared in `run-notes.json` beside its checkpoint (`stopped` and `rows`), so the completeness check accepts its missing tail. **The ceiling is checked against recorded cost, which can be below the provider's bill** (pricing multipliers, reasoning tokens the usage does not itemise): set it with that margin and compare with the billing console.

## What CI does, and does not

- **Does:** lint, types and tests on Python 3.10–3.12. It regenerates every published report from its checkpoints and fails on any difference. It checks that the datasets rebuild byte-identically from their pinned sources. It runs the MLX scoring path on a tiny random model (Linux CPU) and the power analysis.
- **Does not:** call any real model. No key is stored in CI, and no published number comes from a CI run.

## The cloud environment that wrote this code

The v0.5 code was written and tested in a Linux container without a GPU and without access to model hubs. Every model-dependent path is therefore tested there on tiny random models or fakes, and cross-checked against the libraries' own code where possible. Each real model is first run locally, starting with the pilot.
