# v0.6 pilot on the MASSIVE 1.1 dev sample — protocol and provenance

**Issue:** [#132](https://github.com/kunko-ai-labs/judge-audit/issues/132) · **Status:** committed before the first pilot call written to this directory (the commit time in the git log, the first call in each checkpoint header).

## 1. Why

The pilot runs the v0.6 judges on MASSIVE **dev** items to size the v0.6 study: accuracy, how much of each judge's confidence is known, parse failures, throughput and cost, measured on items the study never scores. It is a planning input, not a result. **No judge is called on a test row (`labels-test-*`) by this pilot.** Like every pilot row, these checkpoints are not a score: the drivers' own Markdown and JSON reports go to a scratch directory and are not committed.

## 2. Data

| file | rows | sha256 |
|---|---:|---|
| `examples/massive/labels-pilot-en-US.jsonl` | 230 | `91332858c78227ae4aa27d20abdc312735a46815b7cff2f3081680a8e50e0889` |
| `examples/massive/labels-pilot-es-ES.jsonl` | 230 | `0d4ccb0fc92f5e55067113eded12a28896b46a29a90c71668492987fa880a0e0` |
| `examples/massive/labels-pilot-ca-ES.jsonl` | 230 | `7972fdec8972ea049215e36d5f120a19837f090ed4bbe8dcc56b80e238801017` |

Up to 4 dev utterances per intent, seed 2026, the same items in the three locales (row *k* is the same MASSIVE `id` in every file); one `intent` question with the 60 intents as options, English instructions in every locale. Caveats from the file headers: translated parallel data, not native traffic; public since 2022, probably in the judges' pretraining data; 1, 8 and 6 pilot texts also occur in test (`_meta.text_in_test`). See [`examples/massive/README.md`](../../../examples/massive/README.md).

## 3. Judges

One Apple M4 with 16 GB, one local model in memory at a time; Python 3.12.8, torch 2.14.0, transformers 5.17.0, laya 0.3.20, mlx 0.32.2 installed. Checkpoint slug `<slug>-<locale>.ckpt.jsonl`.

| slug | judge | model and pin | device and precision | settings |
|---|---|---|---|---|
| `decision2-kai-0.6b` | `decision2` | `vllm-sr/Decision-2.0-Kai-0.6B` at `cd49ea3813fd8ba0928a9a23ef6c9a0f2f0cd764` | CPU, float32 (the runtime's default; reference check against the card's outputs) | defaults |
| `laya-multilingual` | `laya` | `convaiinnovations/laya-multilingual` at `1720e3e3357cfe1e281542e223f8273b0890ca34` | MPS, float32 (Laya's choice) | `LAYA_REVISION` as the pin; `LAYA_HEAD_MAX_LEN=384`, `LAYA_MAX_LEN=1024` (below) |
| `jev` | `jev` | `jev-latest`, `JEV_BACKEND=typesafe` | hosted | native probability of the chosen option, one call per row |
| `decider-2b` (exploratory) | `decider` | `Mapika/decider-2b` at `533964dae8be954c5b5e19fa4948e48408094c1e` | MPS, float16, `mlx_loaded` true, one question per request (recorded in the header); MPS has no recorded reference outputs, so the header says `unchecked` | `DECIDER_DEVICE=mps` |
| `strands-decider-2b` (exploratory) | `strands` | `StrandsAgents/strands-decider-2B-hobson-v19` at `bb282d786bc251fd4e3068de3ada9ddbb38127cd`, strands-decider 0.1.0 | MPS, bfloat16 (reference check against the card) | defaults |

Not run: Clef-flash (about 19 GB in bf16, does not fit the 16 GB machine); `gemini-3.6-flash` (optional, exploratory) only if run time and quota allow, and then listed here before its call.

**Laya's budgets.** With the checkpoint's own head budget (256 tokens) the 60 options need 291 tokens, so every question would be recorded as not sent (`max_length_exceeded`). The options and instructions are the same on every row, so the pilot raises `head_max_len` to 384 and `max_len` to 1,024, which fits every row with nothing cut. These budgets are outside what the checkpoint shipped with and are recorded in each header.

**Why decider runs on MPS.** On the CPU it takes about 16 s per row here (about three hours for the three locales); on MPS it takes under 1 s. MPS answers in half precision depend on whether mlx is imported and, in a multi-question request, on the other questions; the adapter records `mlx_loaded` and sends one question per request on MPS.

## 4. Order, checks and stopping rules

1. Before this protocol was committed, each local adapter was run on 5 pilot rows into a scratch directory (load, pin, reference check, latency), and Laya on all 230 rows of each locale with the budgets above, to confirm that no row is cut. Those scratch files are not evidence and are not committed. The 230-row Laya scratch runs were read only for their count of not-sent questions (0 in each locale); no accuracy, confidence or other figure was read from them. Nothing in them changes the settings above beyond what is stated.
2. Runs, one at a time, in the background: `decision2-kai-0.6b`, `laya-multilingual`, `jev`, then the exploratory `decider-2b` and `strands-decider-2b`, each locale in turn, with `scripts/audit_resumable.py examples/massive/labels-pilot-<locale>.jsonl --judge <judge> --checkpoint docs/runs/v06-pilot/<slug>-<locale>.ckpt.jsonl`, polling the row count.
3. **Quality gate,** checked on every finished checkpoint before it is committed: the share of rows with a blank answer, and `scripts/reparse_checkpoints.py --dry-run` reporting 0 changed judgments. A run with more than 5 % unparsed or blank rows among its first 40 is stopped and this protocol amended in a commit before anything changes.
4. A run that dies is resumed by the driver (it refuses to resume under a different configuration). A row that keeps failing is left missing and counted.
5. Hosted cost: Jev at v0.5's recorded rate (about $0.013 for 308 rows) is about $0.03 for 690 rows; the checkpoint's `cost_usd` total is reported.

## 5. What the runs recorded

**Precision not in two headers.** The `decision2` and `laya` adapters record the device but not the precision, so the headers of `decision2-kai-0.6b-*` and `laya-multilingual-*` carry none (decider's and Strands Decider's record `dtype`). The headers are left as the runs wrote them: a header is what the run recorded at the time of its calls, and adding a field afterwards would make it claim what the run did not write. The precision is recorded here instead, from loading each pinned model with the same library versions, offline, after the runs and without judging any row: Kai-0.6B on CPU, parameters float32 (the runtime autocasts to bf16 on CUDA only, per its code); Laya multilingual on MPS, parameters float32. Recording the precision in these two adapters' headers is left to a later change, before the study's runs.

All 15 runs finished on 2026-10-07 (first call 06:52Z, last 07:30Z; times in each header), with no restart. Every checkpoint holds the 230 rows of its locale once; no row has a blank answer, none was not sent (Laya's budgets above held), every judgment parsed, and `scripts/reparse_checkpoints.py --dry-run` reports 0 changed judgments. `scripts/check_complete.py` covers them.

| slug | rows per locale (en-US / es-ES / ca-ES) | blank or not sent | reference check | cost |
|---|---|---|---|---|
| `decision2-kai-0.6b` | 230 / 230 / 230 | 0 | passed (CPU) | $0 (local) |
| `laya-multilingual` | 230 / 230 / 230 | 0 | — (none recorded for Laya) | $0 (local) |
| `jev` | 230 / 230 / 230 | 0 | — (hosted; served `jev-1.13.0`) | $0.0229 in all, from the checkpoints' `cost_usd` |
| `decider-2b` (exploratory) | 230 / 230 / 230 | 0 | unchecked (MPS) | $0 (local) |
| `strands-decider-2b` (exploratory) | 230 / 230 / 230 | 0 | passed (MPS) | $0 (local) |

`gemini-3.6-flash` was not run in the pilot. No accuracy or calibration figure is published from these checkpoints: they are planning inputs.
