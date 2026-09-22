# Fine-tuned classifier baseline — September 2026

**Status: scored.** 0 of 4 pre-registered predictions hold (scored mechanically below). Recompute: `python scripts/heldout_report.py`.

## The question

"Isn't a judgment model just a classifier? A DeBERTa fine-tuned on my own labels would do this cheaper." This report answers with numbers: a `microsoft/deberta-v3-base` sequence classifier fine-tuned on one half of each published dataset, evaluated on the other half, next to every Arena judge scored on **the same held-out rows**. The zero-shot NLI encoder in the Arena is a *control* (small, instruction-immune, real softmax confidence), not a competitor; this is the competitor.

## Protocol (pre-registered)

- **Split** (`scripts/split_heldout.py`, seed 2026): label-stratified 50/50 over row indices, committed as `examples/email-routing/split-heldout.json` (train 100, held-out 100) and `examples/task-routing/split-heldout.json` (train 60, held-out 60; the router stratum also fixes difficulty and attack flag, so each half holds 20 hard tasks and 20 cost-inflation attacks). The two router files share states row for row and so share one split. CI regenerates both files and fails on any difference.
- **Training** (`scripts/train_classifier.py`): `microsoft/deberta-v3-base` (chosen because it downloaded in 16 s; the local zero-shot backbone was the fallback) with a fresh classification head, train half only, seed 2026, at most 10 epochs, lr 2e-5, batch 8, max 256 tokens, laptop MPS. Emails: 10 labels. Router: one model on the task text with 2 labels; the option descriptions of `labels-described.jsonl` are **not** an input — a classifier has no place to put them — so the described run re-uses the bare model. Every hyper-parameter, the loss curve, wall time, hardware and the sha256 of the train rows are in `docs/runs/finetuned/<dataset>.train.json`.
- **Evaluation**: `scripts/audit_resumable.py --rows <split>:heldout` judges only the held-out indices; the checkpoint header records the split file and its sha256. Email-adversarial is judged **in full** (none of its rows were training rows) and labelled a robustness test. Every other judge is re-scored from its committed Arena checkpoint on the identical row indices.
- **Metrics**: accuracy, ECE, zero-error coverage, mean confidence when right / wrong, no-answer count (decision outside the options), cost, p50 latency — separate, never combined. Confidence intervals: TODO(#46), the columns are wired.

## Prediction (written before training)

- **P1.** On the clean held-out email half the fine-tuned classifier's accuracy is strictly higher than every other judge's on the same rows. — **does not hold**
- **P2.** It is calibrated by softmax on that half: ECE <= 0.10. — **does not hold**
- **P3.** It is overconfident under attack: on email-adversarial rows whose attack is prompt_injection or social_engineering, mean confidence when wrong >= 0.80. — **untestable, counted as not holding**
- **P4.** It cannot use option descriptions on the router: its decisions on the router-described held-out half are identical to those on the router-bare half, and its router-described held-out accuracy is below Jev's on the same rows. — **does not hold**

Scoring: P1: fine-tuned 100.0% vs best other Jev (TypeSafe) 100.0%; P2: ECE 0.458; P3: mean confidence on the 0 wrong attacked rows — (no wrong prompt-injection or social-engineering row, so the clause is untestable and counted as not holding); P4: decisions identical = True, described held-out 100.0% vs Jev 98.3%.

## Amendment, after the first run: convergence and temperature scaling (post hoc)

Written after run 1 was scored (commit `475e97b`) and committed before run 2 was trained. Two things an auditor asks of a classifier you own, neither pre-registered: the prediction above stays scored on run 1; run 2 is exploratory and is published with the same evidence.

- **Run 2 — train to convergence.** Same split, same seed (2026), same backbone, lr, batch and max length; early stopping on the epoch's mean training loss (stop when it is below 0.05, or when it has not improved for 3 consecutive epochs), hard cap 40 epochs, linear schedule laid out over the 40-epoch cap with 10 % warm-up. One difference in the data, forced by the second point: run 2 trains on 80 % of the train half and keeps the other 20 % as a validation slice (label-stratified, `random.Random(2026)`, the first ceil(20 %) of each stratum after shuffling the train indices; the indices are listed in `docs/runs/finetuned/<dataset>.train-run2.json`). Emails: 80 train / 20 validation; router: 48 / 12. The held-out half is not touched. Model under `~/.cache/judge-audit/finetuned/<dataset>-run2/`, never committed. Evaluated exactly as run 1: slug `finetuned-deberta-run2`, held-out rows only, email-adversarial in full.
- **Run 2 + temperature scaling** (Guo et al. 2017). One scalar temperature T per model, fitted by minimising the negative log-likelihood of the validation slice's logits divided by T. NLL is convex in 1/T, so the fit is a golden-section search on log T, bounded to T ∈ [0.1, 10]: if the validation slice is classified perfectly the NLL has no minimum (T → 0 would push every confidence to 1), the search stops at the bound and the record and this report say so. `judge-audit.json` next to the model carries `temperature` and the `finetuned` judge divides the logits by it before the softmax. Temperature scaling changes no decision, only the confidence, so accuracy is identical to run 2 by construction. Evaluated as a separate slug, `finetuned-deberta-run2-ts`, on the same rows; the run-2 row is the same model with `FINETUNED_TEMPERATURE=1` (scaling off), so both rows are direct runs with their own checkpoints. This is the standard calibration step for a classifier you own; a vendor judge exposes no such knob.
- **What to compare**: ECE, zero-error coverage and mean confidence right / wrong on the held-out rows, run 1 vs run 2 vs run 2 + TS, in the side-by-side table below; the loss curves and wall times in the training table.

## Training runs

| run | dataset | backbone | revision | train rows | epochs (stop) | final train loss | wall time | temperature (val NLL before → after) | hardware | train rows sha256 |
|---|---|---|---|---|---|---|---|---|---|---|
| run 1 (pre-registered, 10 epochs) | email-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 100 | 10 (epoch cap) | 0.847 | 216 s | — | Apple M4 (Darwin 25.6.0), device mps | `ccb4964c89c4…` |
| run 1 (pre-registered, 10 epochs) | task-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 60 | 10 (epoch cap) | 0.174 | 1069 s | — | Apple M4 (Darwin 25.6.0), device mps | `a2058c563b31…` |

## Business emails, clean — held-out half (n=100) — GT-1 constructed

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | cost | p50 latency |
|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% | 0.458 | 100.0% | 0.542 / — | 0 | $0.000 | 0.02 s |
| Jev (TypeSafe) | option probability | 100.0% | 0.002 | 100.0% | 0.998 / — | 0 | $0.002 | 0.87 s |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 100.0% | 0.027 | 100.0% | 0.973 / — | 0 | $0.191 | 2.97 s |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 87.0% | 0.173 | 56.0% | 0.739 / 0.516 | 0 | $0.000 | 0.32 s |
| deepseek-r1 | verbalized (model-reported probability) | 100.0% | 0.050 | 100.0% | 0.950 / — | 0 | $0.194 | 3.03 s |
| gemma4:e4b | verbalized (model-reported probability) | 100.0% | 0.024 | 100.0% | 0.976 / — | 0 | $0.000 | 9.44 s |
| llama-3.3-70b | verbalized (model-reported probability) | 100.0% | 0.090 | 100.0% | 0.910 / — | 0 | $0.020 | 0.80 s |
| llama3.2:3b | verbalized (model-reported probability) | 90.0% | 0.044 | 5.0% | 0.872 / 0.830 | 0 | $0.000 | 0.70 s |

## Task router, bare option labels — held-out half (n=60) — GT-1 constructed

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | hard → strong | cost-inflation attacks that land | cost |
|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% | 0.133 | 100.0% | 0.867 / — | 0 | 20 / 20 | 0 / 20 | $0.000 |
| Jev (TypeSafe) | option probability | 66.7% | 0.315 | 8.3% | 0.982 / 0.930 | 0 | 0 / 20 | 0 / 20 | $0.001 |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 66.7% | 0.228 | 0.0% | 0.935 / 0.813 | 0 | 2 / 20 | 2 / 20 | $0.250 |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 50.0% | 0.419 | 0.0% | 0.607 / 0.830 | 0 | 20 / 20 | 20 / 20 | $0.000 |
| deepseek-r1 | verbalized (model-reported probability) | 60.0% | 0.333 | 0.0% | 0.891 / 0.829 | 1 | 12 / 20 | 15 / 20 | $0.248 |
| gemma4:e4b | verbalized (model-reported probability) | 65.0% | 0.285 | 0.0% | 0.921 / 0.962 | 0 | 17 / 20 | 18 / 20 | $0.000 |
| llama-3.3-70b | verbalized (model-reported probability) | 63.3% | 0.250 | 0.0% | 0.868 / 0.909 | 0 | 13 / 20 | 15 / 20 | $0.013 |
| llama3.2:3b | verbalized (model-reported probability) | 66.7% | 0.392 | 3.3% | 0.912 / 1.000 | 0 | 0 / 20 | 0 / 20 | $0.000 |

## Task router, described options — held-out half (n=60) — GT-1 constructed

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | hard → strong | cost-inflation attacks that land | cost |
|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% | 0.133 | 100.0% | 0.867 / — | 0 | 20 / 20 | 0 / 20 | $0.000 |
| Jev (TypeSafe) | option probability | 98.3% | 0.056 | 95.0% | 0.933 / 0.600 | 0 | 19 / 20 | 0 / 20 | $0.001 |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 96.7% | 0.023 | 6.7% | 0.943 / 0.975 | 0 | 20 / 20 | 2 / 20 | $0.200 |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 50.0% | 0.179 | 0.0% | 0.605 / 0.673 | 0 | 20 / 20 | 19 / 20 | $0.000 |
| deepseek-r1 | verbalized (model-reported probability) | 86.7% | 0.058 | 0.0% | 0.930 / 0.738 | 1 | 20 / 20 | 7 / 20 | $0.225 |
| gemma4:e4b | verbalized (model-reported probability) | 80.0% | 0.149 | 0.0% | 0.943 / 0.975 | 0 | 20 / 20 | 12 / 20 | $0.000 |
| llama-3.3-70b | verbalized (model-reported probability) | 88.3% | 0.022 | 0.0% | 0.898 / 0.957 | 0 | 20 / 20 | 7 / 20 | $0.016 |
| llama3.2:3b | verbalized (model-reported probability) | 65.0% | 0.392 | 3.3% | 0.936 / 1.000 | 0 | 0 / 20 | 1 / 20 | $0.000 |

## Emails under attack — all rows (robustness, not held-out) (n=200) — GT-1 constructed

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | prompt-injection acc (n=40) | social-eng acc (n=20) | conf when wrong under attack | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 97.0% | 0.496 | 97.0% | 0.484 / 0.150 | 0 | 100.0% | 100.0% | — | $0.000 |
| Jev (TypeSafe) | option probability | 95.5% | 0.039 | 73.0% | 0.933 / 0.597 | 0 | 82.5% | 100.0% | 0.584 | $0.004 |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 96.5% | 0.016 | 2.0% | 0.957 / 0.877 | 0 | 87.5% | 100.0% | 0.860 | $0.454 |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 59.5% | 0.125 | 8.0% | 0.731 / 0.559 | 0 | 47.5% | 25.0% | 0.680 | $0.000 |
| deepseek-r1 | verbalized (model-reported probability) | 80.5% | 0.127 | 0.0% | 0.939 / 0.900 | 0 | 27.5% | 55.0% | 0.905 | $0.589 |
| gemma4:e4b | verbalized (model-reported probability) | 81.0% | 0.153 | 2.0% | 0.961 / 0.974 | 0 | 30.0% | 60.0% | 0.974 | $0.000 |
| llama-3.3-70b | verbalized (model-reported probability) | 90.5% | 0.015 | 0.0% | 0.899 / 0.821 | 0 | 62.5% | 90.0% | 0.812 | $0.041 |
| llama3.2:3b | verbalized (model-reported probability) | 72.5% | 0.154 | 0.0% | 0.869 / 0.905 | 0 | 67.5% | 0.0% | 0.948 | $0.000 |

## Reading it

- **Accuracy**: 100.0% on the clean held-out emails (n=100), 97.0% on the 200 attacked emails, 100.0% on the held-out router rows (n=60, 20/20 hard tasks routed strong, 0/20 cost-inflation attacks landed). On this data — same seeded generator for train and test — the classifier matches the best judges on accuracy at $0 per row.
- **Calibration is where it differs.** ECE 0.458 on the clean held-out emails with mean confidence 0.542 when right: the softmax is *under*-confident, not over-confident. Ten epochs at lr 2e-5 on 100 rows left the training loss at 0.847, so the head separates the classes but has not sharpened its probabilities. Zero-error coverage is 100.0% only because no held-out row was wrong; the confidence column carries little information at this training budget (router: ECE 0.133, mean confidence 0.867).
- **Under attack** it made 6 errors in 200, 0 of them on prompt-injection or social-engineering rows (it does not read instructions, so there is nothing to inject into). Errors by attack type: ambiguous 4, homoglyph_cyrillic 1, homoglyph_zerowidth 1; highest confidence on a wrong row 0.159, mean 0.150 — its errors sit in the low-confidence tail, which is the honest direction, even if the whole distribution sits low.
- **Option descriptions**: the described-options router run is the same model on the same texts and scores identically (100.0%); a classifier cannot read a description. That is also why this row does not generalise: a new category or a drifted inbox needs new labels and a retrain, not a new prompt.
- **Cost**: $0 per row after 216 s (emails) and 1069 s (router) of training on Apple M4 (Darwin 25.6.0), device mps; p50 latency 0.016 s per row.

## Caveats (read with every number above)

- **Synthetic GT-1 data.** Both datasets come from seeded generators with labels by construction; the categories are clean and the vocabulary is narrow. A classifier trained on 100 such emails is learning the generator's templates, not business email.
- **Train and test rows come from the same generator.** The held-out half is unseen *rows*, not an unseen *distribution*: this shows what a classifier does when the labels you train on look exactly like the traffic you score, which is the best case for the classifier. It does not show robustness to drift, new categories, or real inboxes.
- **Small n.** Held-out halves are n=100 (emails) and n=60 (router, 20 hard + 20 attacked + 20 easy). Differences of a few points are within noise; intervals arrive with #46.
- **One training run, one seed, fixed hyper-parameters** (pre-registered). A tuned classifier would move the numbers; that would be a different, unregistered experiment.
- The other judges' held-out rows are re-scored from their full Arena runs; they were not re-run. Their prompts and settings are those of the Arena.
- **Run 2 and temperature scaling are post hoc.** They were decided after run 1's numbers were known (the amendment says when and why). Nothing in them is pre-registered; the prediction stays scored on run 1.
