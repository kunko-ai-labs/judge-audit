# v0.5 pilot on the BANKING77 train sample — protocol

**Issue:** [#91](https://github.com/kunko-ai-labs/judge-audit/issues/91) · **Status:** committed before the first model call of the pilot. Nothing in this pilot is a result about any judge.

## 1. Why

[`docs/v05-power.md`](v05-power.md) sizes the v0.5 study on assumed shapes: the accuracy of the judges, how strongly two confidence methods agree on which rows are hard (ρ), and how tied the confidences are. The pilot measures those three things on data the study never scores, so that `scripts/v05_power.py` runs on estimates rather than guesses before `docs/v05-plan.md` fixes n, the certification targets and the smallest detectable differences. It also measures throughput, parse failures and the token log-probability judge's `option_mass`, which the plan needs for time and cost.

The pilot does **not** test H1 or H2. With 308 rows it could not, and a comparison on it would contaminate the pre-registration. Its per-judge accuracies are planning inputs, published only as such, next to this caveat.

## 2. Data

- `examples/banking77/labels-pilot.jsonl`, sha256 `488ee2258027c6f4901600f6adfce55d33e620d63ff9fa69178fe04cd0a5f7ed`: 308 queries from the BANKING77 **train** split, 4 per intent, one `intent` question with the 77 label names as options. The study scores the test split only.
- Caveats (from the file header): public since 2020, probably in pretraining data; about 14 % of train queries flagged as possibly mislabelled by automated detection (Ying & Thomas 2022); label names without definitions, some misleading. Label noise is not measured here.

## 3. Judges

All local, on one Apple M4 with 16 GB, one MLX model in memory at a time. One chat model, read three ways from the **same checkpoint**:

| Run (checkpoint slug) | Judge | Model and pin | Settings |
|---|---|---|---|
| `laya` | `laya` | `convaiinnovations/laya` at `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` (laya 0.3.20) | `LAYA_HEAD_MAX_LEN=640`, `LAYA_MAX_LEN=1024` (see below); device: Laya's choice, recorded |
| `logprob-qwen3-8b` | `logprob` | `mlx-community/Qwen3-8B-4bit` at `545dc4251c05440727734bcd94334791f6ab0192` (Apache-2.0) | `LOGPROB_REVISION` = that commit, `LOGPROB_LABEL=qwen3-8b-4bit`, thinking off (the judge's default) |
| `llm-qwen3-8b` | `llm`, verbalized | the same checkpoint, served by `mlx_lm.server` | temperature 0, one call per row |
| `llm-qwen3-8b-sc5` | `llm`, self-consistency | the same | `LLM_SAMPLES=5`, `LLM_TEMPERATURE=1` |

**Serving the chat model.** `HF_HUB_OFFLINE=1 python -m mlx_lm.server --model mlx-community/Qwen3-8B-4bit --host 127.0.0.1 --port 8080 --chat-template-args '{"enable_thinking": false}'`, with mlx-lm 0.31.3 and mlx 0.32.2. The server's other sampling defaults apply and are recorded here because the judge does not send them: top-p 1.0, top-k off, min-p off, at most 512 generated tokens. Offline mode and the cache's `refs/main` (checked equal to the pinned commit before the server starts) make the served weights the pinned ones. The judge runs with `LLM_PROVIDER=openai-compatible`, `LLM_BASE_URL=http://127.0.0.1:8080/v1`, `LLM_MODEL=mlx-community/Qwen3-8B-4bit`, `LLM_MODEL_LABEL=qwen3-8b-4bit`. Thinking is off in all three read-outs, so each reads a direct answer. Sampling on the server is not seeded: the self-consistency checkpoint, not a rerun, is the evidence.

**Laya's budgets.** With the checkpoint's own budgets (`head_max_len` 192, `max_len` 512) Laya cannot read this question: its 77 options need up to 553 tokens, so 64 of them would be cut to 3 tokens and the adapter refuses to score (measured with Laya's tokenizer on all 308 rows; the longest instructions are 19 tokens and the longest state 56). The pilot raises the budgets to 640 and 1,024 so nothing is cut. Those budgets are outside what the checkpoint shipped with, and Laya's own README calls its base checkpoints near chance on typed decisions zero-shot; the Laya row is a measurement of that configuration and says so wherever it is quoted.

**Hosted judges (optional, not run without the maintainer's approval of the cost).** Jev, `claude-sonnet-5` and `gemini-3.6-flash` on the same 308 rows, verbalized and self-consistency (k = 5, temperature 1), after `scripts/logprob_smoke.py`. Estimate at about 750 input and 40 output tokens per call: Claude verbalized ≈ $0.60, self-consistency ≈ $2.90; Gemini ≈ $0.10 and $0.50; Jev ≈ $0.01. They would add hosted accuracies and tie shares; they are not needed for the constants below, which come from the local runs.

## 4. Order, checks and stopping rules

1. `LOGPROB_MODEL=mlx-community/Qwen3-8B-4bit LOGPROB_REVISION=… python scripts/logprob_selfcheck.py examples/banking77/labels-pilot.jsonl --rows 20`. **Stop** the `logprob` run if it exits 1 (a probability off by more than 1e-3, or a decision that changes); the check's output is reported either way.
2. `laya`, then `logprob-qwen3-8b`, then (server up) `llm-qwen3-8b`, then `llm-qwen3-8b-sc5`, each with `scripts/audit_resumable.py … --checkpoint docs/runs/v05-pilot/<slug>.ckpt.jsonl`, in the background, polling the row count. The drivers' own Markdown and JSON reports go to a scratch directory and are not committed: they would read as scores.
3. **Stop** an `llm` run, and amend this protocol in a commit before changing anything, if more than 5 % of its first 40 rows have no parsed answer. No prompt, setting or model changes mid-run.
4. A run that dies is resumed by the driver (it refuses to resume under a different configuration). A row that keeps failing is left missing and counted.

## 5. What is estimated, and how (fixed now, before any row is seen)

A committed, deterministic script (`scripts/v05_pilot.py`, no model call, seeded) reads the four checkpoints and writes `docs/v05-pilot-estimates.md` and `.json`; CI regenerates them. Each estimate is printed with its n and, where stated, a 95 % interval.

| Estimate | Definition | Feeds `scripts/v05_power.py` |
|---|---|---|
| Accuracy per run | decision equal to the label, case ignored; a row with no parsed answer counts as wrong and is counted separately; Wilson 95 % interval | `ACCURACIES` ← the distinct accuracies of the three Qwen3 read-outs, rounded to 0.01 |
| Tie shares | share of rows at each distinct confidence value (rounded to 1e-6), lowest to highest, per run | `TIE_SHARES` ← the self-consistency run's shares (the coarsest method H1 compares) |
| Verbalized distribution | the verbalized run's confidences rounded to 0.05; levels holding under 1 % of rows pooled into the nearest kept level | `CONF_VALUES`, `CONF_WEIGHTS` (part C) |
| Rank agreement → ρ | for each pair of the three Qwen3 read-outs: Spearman correlation (average ranks) of the two confidences on the rows **both** got right; ρ is the latent correlation that reproduces it under the power script's model (bivariate normal noise, each method cut into its own observed tie levels), solved by bisection on 100,000 simulated pairs with seed 2026; 95 % percentile bootstrap interval of the Spearman correlation (2,000 resamples, seed 2026), mapped the same way. The rows both got wrong are reported too, not used | `RHOS` ← the point estimates for the two H1 pairs (verbalized–self-consistency, verbalized–log-probability), rounded to 0.05, plus the lower interval bound of the smaller one (the conservative cell) |
| AUROC per run | AUROC of confidence for correctness, ties counted as half, with a DeLong 95 % interval | `AUROC_A` ← the verbalized run's AUROC rounded to 0.05 and capped at 0.90; `AUROC_B` = `AUROC_A` + 0.05 (the design gap is unchanged) |
| Also reported, not fed back | overconfidence (mean confidence − accuracy) per run; no-answer and parse-status counts; `option_mass` quartiles of the log-probability run; Laya's clamped softmax temperatures; rows per minute and tokens per call per run | — |

`GAP_A`, `GAP_B` (the ECE design gap), `AUTOMATABLE`, `REST_ERROR` and the grid of n stay as they are: they are design choices, not quantities the pilot measures. The plan names the power-analysis cell the pilot matches and states its MDE.

## 6. What happens next

The constants are changed in one reviewed commit that cites `docs/v05-pilot-estimates.json`, `docs/v05-power.md` is regenerated, and `docs/v05-plan.md` is drafted from it and reviewed before the study's first call. Estimates are published whether or not they are convenient: if ρ is low or accuracy high, the MDEs grow, and the plan says so.
