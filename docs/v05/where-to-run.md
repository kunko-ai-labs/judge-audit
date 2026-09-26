# What runs where

**Short version.** Local judges (Laya, the token log-probability judge, local chat models, the fine-tuned classifier) run on the maintainer's laptops, two Apple-silicon Macs with 16 GB and 24 GB. Hosted judges (Claude, Gemini, Jev, hosted open models) run from any machine that holds the keys. CI runs no model at all: it recomputes every published number from the committed checkpoints.

## The judges

| Judge | What it is | Where it runs | Needs |
|---|---|---|---|
| `laya` | Laya, an open judgment model (421M-parameter encoder) | **your Mac** (CPU or Apple GPU); any Linux box that can download it | `pip install 'kunko-judge-audit[laya]'`, `LAYA_REVISION` pinned |
| `logprob` | An open chat model's own probability of each option (MLX) | **your Mac**; Linux CPU works but is slow | `pip install 'kunko-judge-audit[mlx]'`, `LOGPROB_MODEL`, `LOGPROB_REVISION` |
| `llm` via a local server | An open chat model, verbalized or self-consistency | **your Mac** (a local OpenAI-compatible server such as Ollama) | `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL` |
| `finetuned` | Your own classifier trained on your labels (`scripts/train_classifier.py`) | **your Mac** (training and inference) | the `[nli]` extra, `FINETUNED_MODEL_DIR` |
| `nli` | A small zero-shot encoder, the control | anywhere, CPU is enough | the `[nli]` extra |
| `llm` hosted | Claude, Gemini, hosted open models | anywhere with the key | `ANTHROPIC_API_KEY`, or `LLM_BASE_URL` + `LLM_API_KEY`, or the private provider module |
| `jev` | Jev through its API | anywhere with the key | the Jev key |
| `simulated` | A seeded simulator, always tagged SIMULATED | anywhere, CI | nothing |

So the answer to "what must I run on my Mac?" is: **Laya, the log-probability judge, the local chat models and the fine-tuned classifier.** The hosted judges can run from the Mac too, or from any machine with the keys, including a CI job with secrets (see [use it in your workflow](use-in-your-workflow.md)); the Mac is simply where the keys already are.

## Sizing on the two Macs

Apple silicon shares memory between CPU and GPU; macOS lets the GPU wire roughly two thirds to three quarters of it by default. As a rule of thumb for 4-bit models:

| Machine | Comfortable | Tight |
|---|---|---|
| 16 GB | Laya; 7–8B chat models (about 5 GB) | 12–14B (about 8–9 GB) |
| 24 GB | Laya; up to 14B; a 20B model in 4-bit (about 12 GB) | larger |

Before any published `logprob` run, `python scripts/logprob_selfcheck.py <labels.jsonl> --rows 20` checks on the real model that the cached scoring equals a full forward pass, and measures rows per minute. mlx-lm has an open report of prompt caching returning different logits, so this is not optional.

## Long runs

`scripts/audit_resumable.py` writes one checkpoint row per decision and resumes where it stopped. It refuses to resume a checkpoint recorded with a different model, confidence method, temperature, number of samples, prompt or gateway routing. Run it in the background and watch the row count. Checkpoints are committed; every published number is recomputed from them.

## What CI does, and does not

- **Does:** lint, types and tests on Python 3.10–3.12. It regenerates every published report from its checkpoints and fails on any difference. It checks that the datasets rebuild byte-identically from their pinned sources. It runs the MLX scoring path on a tiny random model (Linux CPU) and the power analysis.
- **Does not:** call any real model. No key is stored in CI, and no published number comes from a CI run.

## The cloud environment that wrote this code

The v0.5 code was written and tested in a Linux container without a GPU and without access to model hubs. Every model-dependent path is therefore tested there on tiny random models or fakes, and cross-checked against the libraries' own code where possible. The first run of each real model happens on the maintainer's Mac, starting with the pilot.
