# Fine-tuned classifier baseline — September 2026

**Status: scored.** 0 of 3 testable pre-registered predictions hold; P3 untestable (no wrong attacked row) — scored mechanically below. Recompute: `python scripts/heldout_report.py`.

## The question

"Isn't a judgment model just a classifier? A DeBERTa fine-tuned on my own labels would do this cheaper." This report answers with numbers: a `microsoft/deberta-v3-base` sequence classifier fine-tuned on one half of each published dataset, evaluated on the other half, next to every Arena judge scored on **the same held-out rows**. The zero-shot NLI encoder in the Arena is a *control* (small, instruction-immune, real softmax confidence), not a competitor; this is the competitor.

## Protocol (pre-registered)

- **Split** (`scripts/split_heldout.py`, seed 2026): label-stratified 50/50 over row indices, committed as `examples/email-routing/split-heldout.json` (train 100, held-out 100) and `examples/task-routing/split-heldout.json` (train 60, held-out 60; the router stratum also fixes difficulty and attack flag, so each half holds 20 hard tasks and 20 cost-inflation attacks). The two router files share states row for row and so share one split. CI regenerates both files and fails on any difference.
- **Training** (`scripts/train_classifier.py`): `microsoft/deberta-v3-base` (chosen because it downloaded in 16 s; the local zero-shot backbone was the fallback) with a fresh classification head, train half only, seed 2026, at most 10 epochs, lr 2e-5, batch 8, max 256 tokens, laptop MPS. Emails: 10 labels. Router: one model on the task text with 2 labels; the option descriptions of `labels-described.jsonl` are **not** an input — a classifier has no place to put them — so the described run re-uses the bare model. Every hyper-parameter, the loss curve, wall time, hardware and the sha256 of the train rows are in `docs/runs/finetuned/<dataset>.train.json`.
- **Evaluation**: `scripts/audit_resumable.py --rows <split>:heldout` judges only the held-out indices; the checkpoint header records the split file and its sha256. Email-adversarial is judged **in full** (no adversarial row is a training row by index; text-level overlap with the training emails is counted next to every n below) and labelled a robustness test. Every other judge is re-scored from its committed Arena checkpoint on the identical row indices.
- **Metrics**: accuracy, ECE, zero-error coverage, mean confidence when right / wrong, no-answer count (decision outside the options), cost, p50 latency — separate, never combined. Accuracy, ECE and zero-error coverage carry a 95 % percentile-bootstrap interval (2,000 resamples, seed 0) clustered by distinct text.

## Prediction (written before training)

- **P1.** On the clean held-out email half the fine-tuned classifier's accuracy is strictly higher than every other judge's on the same rows. — **does not hold**
- **P2.** It is calibrated by softmax on that half: ECE <= 0.10. — **does not hold**
- **P3.** It is overconfident under attack: on email-adversarial rows whose attack is prompt_injection or social_engineering, mean confidence when wrong >= 0.80. — **untestable, counted as not holding**
- **P4.** It cannot use option descriptions on the router: its decisions on the router-described held-out half are identical to those on the router-bare half, and its router-described held-out accuracy is below Jev's on the same rows. — **does not hold**

Scoring: P1: fine-tuned 100.0% vs best other Jev (TypeSafe) 100.0%; P2: ECE 0.458; P3: mean confidence on the 0 wrong attacked rows — (no wrong prompt-injection or social-engineering row, so the clause is untestable and counted as not holding); P4: decisions identical = True, described held-out 100.0% vs Jev 98.3%.

## Amendment, after the first run: convergence and temperature scaling (post hoc)

Written after run 1 was scored (commit `475e97b`) and committed before run 2 was trained. Two things an auditor asks of a classifier you own, neither pre-registered: the prediction above stays scored on run 1; run 2 is exploratory and is published with the same evidence.

- **Run 2 — train to convergence.** Same split, same seed (2026), same backbone, lr, batch and max length; early stopping on the epoch's mean training loss (stop when it is below 0.05, or when it has not improved for 3 consecutive epochs), hard cap 40 epochs, linear schedule laid out over the 40-epoch cap with 10 % warm-up. One difference in the data, forced by the second point: run 2 trains on 80 % of the train half and keeps the other 20 % as a validation slice (label-stratified, `random.Random(2026)`, the first ceil(20 %) of each stratum after shuffling the train indices; the indices are listed in `docs/runs/finetuned/<dataset>.train-run2.json`). Emails: 80 train / 20 validation; router: 48 / 12. The held-out half is not touched. Model under `~/.cache/judge-audit/finetuned/<dataset>-run2/`, never committed. Evaluated exactly as run 1: slug `finetuned-deberta-run2`, held-out rows only, email-adversarial in full.
- **Run 2 + temperature scaling** (Guo et al. 2017). One scalar temperature T per model, fitted by minimising the negative log-likelihood of the validation slice's logits divided by T. NLL is convex in 1/T, so the fit is a golden-section search on log T, bounded to T ∈ [0.1, 10]: if the validation slice is classified perfectly the NLL has no minimum (T → 0 would push every confidence to 1): the search stops where the NLL is numerically zero or at the bound, the fitted T is **not identified**, and the record and this report say so — the temperature-scaled row is then reported as what the standard recipe produces on a slice this small, not as a calibrated model. `judge-audit.json` next to the model carries `temperature` and the `finetuned` judge divides the logits by it before the softmax. Temperature scaling changes no decision, only the confidence, so accuracy is identical to run 2 by construction. Evaluated as a separate slug, `finetuned-deberta-run2-ts`, on the same rows; the run-2 row is the same model with `FINETUNED_TEMPERATURE=1` (scaling off), so both rows are direct runs with their own checkpoints. This is the standard calibration step for a classifier you own; a vendor judge exposes no such knob.
- **What to compare**: ECE, zero-error coverage and mean confidence right / wrong on the held-out rows, run 1 vs run 2 vs run 2 + TS, in the side-by-side table below; the loss curves and wall times in the training table.

## Training runs

| run | dataset | backbone | revision | train rows | epochs (stop) | final train loss | wall time | temperature (val NLL before → after) | hardware | train rows sha256 |
|---|---|---|---|---|---|---|---|---|---|---|
| run 1 (pre-registered, 10 epochs) | email-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 100 | 10 (epoch cap) | 0.847 | 216 s | — | Apple M4 (Darwin 25.6.0), device mps | `ccb4964c89c4…` |
| run 1 (pre-registered, 10 epochs) | task-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 60 | 10 (epoch cap) | 0.174 | 1069 s | — | Apple M4 (Darwin 25.6.0), device mps | `a2058c563b31…` |
| run 2 (to convergence, post hoc) | email-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 80 | 19 (train loss < 0.05) | 0.043 | 109 s | 0.304 **not identified: validation classified perfectly** (0.017 → 0.000, n=20, val acc 100%) | Apple M4 (Darwin 25.6.0), device mps | `8788e082643c…` |
| run 2 (to convergence, post hoc) | task-routing | `microsoft/deberta-v3-base` | `8ccc9b6f3619` | 48 | 15 (train loss < 0.05) | 0.013 | 62 s | 0.188 **not identified: validation classified perfectly** (0.007 → 0.000, n=12, val acc 100%) | Apple M4 (Darwin 25.6.0), device mps | `1d8be83b9595…` |

## Business emails, clean — held-out half (n=100) — GT-1 constructed

Text overlap with the training half: 20 of 100 rows equal a training text, 0 more contain one verbatim → **unseen-text rows n=80** (last column; same rows for every judge).

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | cost | p50 latency | acc on unseen-text rows |
|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% [96.4, 100.0]† | 0.458 [0.424, 0.495] | 100.0% [96.4, 100.0]† | 0.542 / — | 0 | $0.000 | 0.02 s | 100.0% (n=80) |
| **DeBERTa-v3-base fine-tuned — run 2 (to convergence, post hoc)** | softmax probability of the chosen option | 100.0% [96.4, 100.0]† | 0.017 [0.016, 0.018] | 100.0% [96.4, 100.0]† | 0.983 / — | 0 | $0.000 | 0.02 s | 100.0% (n=80) |
| **DeBERTa-v3-base fine-tuned — run 2 + temperature scaling (post hoc)** | softmax probability of the chosen option ÷ T (T=0.30) | 100.0% [96.4, 100.0]† | 0.000 ‡ | 100.0% [96.4, 100.0]† | 1.000 / — | 0 | $0.000 | 0.02 s | 100.0% (n=80) |
| Jev (TypeSafe) | option probability | 100.0% [96.4, 100.0]† | 0.002 [0.000, 0.005] | 100.0% [96.4, 100.0]† | 0.998 / — | 0 | $0.002 | 0.87 s | 100.0% (n=80) |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 100.0% [96.4, 100.0]† | 0.027 [0.022, 0.033] | 100.0% [96.4, 100.0]† | 0.973 / — | 0 | $0.191 | 2.97 s | 100.0% (n=80) |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 87.0% [79.4, 93.4] | 0.173 [0.126, 0.260] | 56.0% [43.4, 70.2] | 0.739 / 0.516 | 0 | $0.000 | 0.32 s | 83.8% (n=80) |
| deepseek-r1 | verbalized (model-reported probability) | 100.0% [96.4, 100.0]† | 0.050 [0.046, 0.054] | 100.0% [96.4, 100.0]† | 0.950 / — | 0 | $0.194 | 3.03 s | 100.0% (n=80) |
| gemini-3-flash-preview | verbalized (model-reported probability) | 100.0% [96.4, 100.0]† | 0.004 [0.002, 0.006] | 100.0% [96.4, 100.0]† | 0.996 / — | 0 | $0.012 | 2.05 s | 100.0% (n=80) |
| gemma4:e4b | verbalized (model-reported probability) | 100.0% [96.4, 100.0]† | 0.024 [0.018, 0.030] | 100.0% [96.4, 100.0]† | 0.976 / — | 0 | $0.000 | 9.44 s | 100.0% (n=80) |
| llama-3.3-70b | verbalized (model-reported probability) | 100.0% [96.4, 100.0]† | 0.090 [0.083, 0.095] | 100.0% [96.4, 100.0]† | 0.910 / — | 0 | $0.020 | 0.80 s | 100.0% (n=80) |
| llama3.2:3b | verbalized (model-reported probability) | 90.0% [76.7, 100.0] | 0.044 [0.013, 0.165] | 0.0% [0.0, 3.6]† | 0.872 / 0.830 | 0 | $0.000 | 0.70 s | 100.0% (n=80) |

## Task router, bare option labels — held-out half (n=60) — GT-1 constructed

Text overlap with the training half: 40 of 60 rows equal a training text, 15 more contain one verbatim → **unseen-text rows n=5** (last column; same rows for every judge).

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | hard → strong | cost-inflation attacks that land | cost | acc on unseen-text rows |
|---|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% [94.0, 100.0]† | 0.133 [0.072, 0.191] | 100.0% [94.0, 100.0]† | 0.867 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| **DeBERTa-v3-base fine-tuned — run 2 (to convergence, post hoc)** | softmax probability of the chosen option | 100.0% [94.0, 100.0]† | 0.005 [0.003, 0.009] | 100.0% [94.0, 100.0]† | 0.995 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| **DeBERTa-v3-base fine-tuned — run 2 + temperature scaling (post hoc)** | softmax probability of the chosen option ÷ T (T=0.19) | 100.0% [94.0, 100.0]† | 0.000 ‡ | 100.0% [94.0, 100.0]† | 1.000 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| Jev (TypeSafe) | option probability | 66.7% [51.6, 82.5] | 0.315 [0.167, 0.457] | 0.0% [0.0, 6.0]† | 0.982 / 0.930 | 0 | 0 / 20 | 0 / 20 | $0.001 | 60.0% (n=5) |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 66.7% [52.4, 81.7] | 0.228 [0.102, 0.356] | 0.0% [0.0, 6.0]† | 0.935 / 0.813 | 0 | 2 / 20 | 2 / 20 | $0.250 | 60.0% (n=5) |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 50.0% [33.3, 65.6] | 0.419 [0.300, 0.572] | 0.0% [0.0, 6.0]† | 0.607 / 0.830 | 0 | 20 / 20 | 20 / 20 | $0.000 | 80.0% (n=5) |
| deepseek-r1 | verbalized (model-reported probability) | 60.0% [44.4, 73.0] | 0.333 [0.222, 0.468] | 0.0% [0.0, 6.0]† | 0.891 / 0.829 | 1 | 12 / 20 | 15 / 20 | $0.248 | 60.0% (n=5) |
| gemini-3-flash-preview | verbalized (model-reported probability) | 66.7% [50.8, 81.0] | 0.317 [0.177, 0.468] | 0.0% [0.0, 6.0]† | 0.991 / 0.968 | 0 | 1 / 20 | 1 / 20 | $0.008 | 60.0% (n=5) |
| gemma4:e4b | verbalized (model-reported probability) | 65.0% [50.8, 77.6] | 0.285 [0.159, 0.441] | 0.0% [0.0, 6.0]† | 0.921 / 0.962 | 0 | 17 / 20 | 18 / 20 | $0.000 | 100.0% (n=5) |
| llama-3.3-70b | verbalized (model-reported probability) | 63.3% [48.1, 76.7] | 0.250 [0.117, 0.410] | 0.0% [0.0, 6.0]† | 0.868 / 0.909 | 0 | 13 / 20 | 15 / 20 | $0.013 | 40.0% (n=5) |
| llama3.2:3b | verbalized (model-reported probability) | 66.7% [51.6, 82.5] | 0.392 [0.246, 0.540] | 0.0% [0.0, 6.0]† | 0.912 / 1.000 | 0 | 0 / 20 | 0 / 20 | $0.000 | 60.0% (n=5) |

## Task router, described options — held-out half (n=60) — GT-1 constructed

Text overlap with the training half: 40 of 60 rows equal a training text, 15 more contain one verbatim → **unseen-text rows n=5** (last column; same rows for every judge).

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | hard → strong | cost-inflation attacks that land | cost | acc on unseen-text rows |
|---|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 100.0% [94.0, 100.0]† | 0.133 [0.072, 0.191] | 100.0% [94.0, 100.0]† | 0.867 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| **DeBERTa-v3-base fine-tuned — run 2 (to convergence, post hoc)** | softmax probability of the chosen option | 100.0% [94.0, 100.0]† | 0.005 [0.003, 0.009] | 100.0% [94.0, 100.0]† | 0.995 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| **DeBERTa-v3-base fine-tuned — run 2 + temperature scaling (post hoc)** | softmax probability of the chosen option ÷ T (T=0.19) | 100.0% [94.0, 100.0]† | 0.000 ‡ | 100.0% [94.0, 100.0]† | 1.000 / — | 0 | 20 / 20 | 0 / 20 | $0.000 | 100.0% (n=5) |
| Jev (TypeSafe) | option probability | 98.3% [94.8, 100.0] | 0.056 [0.030, 0.098] | 95.0% [89.1, 100.0] | 0.933 / 0.600 | 0 | 19 / 20 | 0 / 20 | $0.001 | 100.0% (n=5) |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 96.7% [91.5, 100.0] | 0.023 [0.014, 0.072] | 0.0% [0.0, 6.0]† | 0.943 / 0.975 | 0 | 20 / 20 | 2 / 20 | $0.200 | 100.0% (n=5) |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 50.0% [34.4, 65.5] | 0.179 [0.116, 0.365] | 0.0% [0.0, 6.0]† | 0.605 / 0.673 | 0 | 20 / 20 | 19 / 20 | $0.000 | 40.0% (n=5) |
| deepseek-r1 | verbalized (model-reported probability) | 86.7% [76.8, 94.5] | 0.058 [0.021, 0.146] | 0.0% [0.0, 6.0]† | 0.930 / 0.738 | 1 | 20 / 20 | 7 / 20 | $0.225 | 100.0% (n=5) |
| gemini-3-flash-preview | verbalized (model-reported probability) | 96.7% [91.5, 100.0] | 0.015 [0.002, 0.062] | 73.3% [60.0, 100.0] | 0.987 / 0.825 | 0 | 20 / 20 | 2 / 20 | $0.009 | 100.0% (n=5) |
| gemma4:e4b | verbalized (model-reported probability) | 80.0% [67.8, 90.5] | 0.149 [0.040, 0.277] | 0.0% [0.0, 6.0]† | 0.943 / 0.975 | 0 | 20 / 20 | 12 / 20 | $0.000 | 100.0% (n=5) |
| llama-3.3-70b | verbalized (model-reported probability) | 88.3% [78.6, 95.5] | 0.022 [0.008, 0.126] | 0.0% [0.0, 6.0]† | 0.898 / 0.957 | 0 | 20 / 20 | 7 / 20 | $0.016 | 100.0% (n=5) |
| llama3.2:3b | verbalized (model-reported probability) | 65.0% [50.0, 80.7] | 0.392 [0.245, 0.540] | 0.0% [0.0, 6.0]† | 0.936 / 1.000 | 0 | 0 / 20 | 1 / 20 | $0.000 | 60.0% (n=5) |

## Emails under attack — all rows (robustness, not held-out) (n=200) — GT-1 constructed

Text overlap with the training half: 13 of 200 rows equal a training text, 36 more contain one verbatim → **unseen-text rows n=151** (last column; same rows for every judge).

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | no answer | prompt-injection acc (n=40) | social-eng acc (n=20) | conf when wrong under attack | cost | acc on unseen-text rows |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)** | softmax probability of the chosen option | 97.0% [94.4, 99.0] | 0.496 [0.470, 0.522] | 97.0% [94.4, 99.0] | 0.484 / 0.150 | 0 | 100.0% | 100.0% | — | $0.000 | 96.0% (n=151) |
| **DeBERTa-v3-base fine-tuned — run 2 (to convergence, post hoc)** | softmax probability of the chosen option | 99.0% [97.5, 100.0] | 0.048 [0.036, 0.066] | 96.0% [93.1, 100.0] | 0.953 / 0.614 | 0 | 100.0% | 100.0% | — | $0.000 | 98.7% (n=151) |
| **DeBERTa-v3-base fine-tuned — run 2 + temperature scaling (post hoc)** | softmax probability of the chosen option ÷ T (T=0.30) | 99.0% [97.5, 100.0] | 0.017 [0.005, 0.033] | 96.0% [93.2, 100.0] | 0.991 / 0.918 | 0 | 100.0% | 100.0% | — | $0.000 | 98.7% (n=151) |
| Jev (TypeSafe) | option probability | 95.5% [92.5, 98.0] | 0.039 [0.028, 0.066] | 73.0% [67.0, 94.0] | 0.933 / 0.597 | 0 | 82.5% | 100.0% | 0.584 | $0.004 | 94.7% (n=151) |
| claude-sonnet-4.5 | verbalized (model-reported probability) | 96.5% [93.9, 99.0] | 0.016 [0.005, 0.040] | 0.0% [0.0, 1.8]† | 0.957 / 0.877 | 0 | 87.5% | 100.0% | 0.860 | $0.454 | 96.7% (n=151) |
| deberta-v3-base-zeroshot-v2.0 | NLI entailment softmax over options | 59.5% [51.7, 66.7] | 0.125 [0.088, 0.201] | 8.0% [3.9, 16.0] | 0.731 / 0.559 | 0 | 47.5% | 25.0% | 0.680 | $0.000 | 62.9% (n=151) |
| deepseek-r1 | verbalized (model-reported probability) | 80.5% [74.8, 85.6] | 0.127 [0.076, 0.184] | 0.0% [0.0, 1.8]† | 0.939 / 0.900 | 0 | 27.5% | 55.0% | 0.905 | $0.589 | 85.4% (n=151) |
| gemini-3-flash-preview | verbalized (model-reported probability) | 97.0% [94.5, 99.0] | 0.015 [0.002, 0.040] | 0.0% [0.0, 1.8]† | 0.982 / 0.983 | 0 | 87.5% | 100.0% | 1.000 | $0.026 | 97.4% (n=151) |
| gemma4:e4b | verbalized (model-reported probability) | 81.0% [75.5, 86.4] | 0.153 [0.100, 0.211] | 0.0% [0.0, 1.8]† | 0.961 / 0.974 | 0 | 30.0% | 60.0% | 0.974 | $0.000 | 85.4% (n=151) |
| llama-3.3-70b | verbalized (model-reported probability) | 90.5% [86.1, 94.5] | 0.015 [0.005, 0.060] | 0.0% [0.0, 1.8]† | 0.899 / 0.821 | 0 | 62.5% | 90.0% | 0.812 | $0.041 | 93.4% (n=151) |
| llama3.2:3b | verbalized (model-reported probability) | 72.5% [65.2, 79.7] | 0.154 [0.085, 0.231] | 0.0% [0.0, 1.8]† | 0.869 / 0.905 | 0 | 67.5% | 0.0% | 0.948 | $0.000 | 84.1% (n=151) |

## Reading it

- **Accuracy**: 100.0% on the clean held-out emails (n=100), 97.0% on the 200 attacked emails, 100.0% on the held-out router rows (n=60, 20/20 hard tasks routed strong, 0/20 cost-inflation attacks landed). On the rows whose text is not in the training half: emails 100.0% (n=80), router 100.0% (n=5). On this data — same seeded generator for train and test — the classifier matches the best judges on accuracy at $0 per row.
- **Calibration is where it differs (run 1).** ECE 0.458 on the clean held-out emails with mean confidence 0.542 when right: the softmax is *under*-confident, not over-confident. Ten epochs at lr 2e-5 on 100 rows left the training loss at 0.847, so the head separates the classes but has not sharpened its probabilities. Zero-error coverage is 100.0% only because no held-out row was wrong; the confidence column carries little information at this training budget (router: ECE 0.133, mean confidence 0.867).
- **Under attack** it made 6 errors in 200, 0 of them on prompt-injection or social-engineering rows. Two explanations, and the data cannot separate them: it does not read instructions, so there is nothing to inject into — and every social-engineering row and 11 of 40 prompt injections embed a training email verbatim, so memorised text would give the same result. On the 151 attacked rows with no training text it scores 96.0%. Errors by attack type: ambiguous 4, homoglyph_cyrillic 1, homoglyph_zerowidth 1; highest confidence on a wrong row 0.159, mean 0.150 — its errors sit in the low-confidence tail, which is the honest direction, even if the whole distribution sits low.
- **Option descriptions**: the described-options router run is the same model on the same texts and scores identically (100.0%); a classifier cannot read a description. That is also why this row does not generalise: a new category or a drifted inbox needs new labels and a retrain, not a new prompt.
- **Cost**: $0 per row after 216 s (emails) and 1069 s (router) of training on Apple M4 (Darwin 25.6.0), device mps; p50 latency 0.016 s per row.

- **Run 2 (post hoc, trained to convergence)**: 19 epochs for the emails and 15 for the router, each stopped by `train loss < 0.05`, on 80 / 48 rows (80 % of the train half). The confidence column becomes informative: clean-email ECE 0.458 → 0.017 with mean confidence when right 0.542 → 0.983; router ECE 0.133 → 0.005. Under attack: accuracy 97.0% → 99.0% (unseen-text rows 96.0% → 98.7%), ECE 0.496 → 0.048, confidence when wrong 0.150 → 0.614, zero-error coverage 97.0% → 96.0%. Convergence bought calibration on the clean half and accuracy under attack, at the price of a smaller gap between right and wrong.
- **Run 2 + temperature scaling (post hoc)**: email-routing T=0.30, task-routing T=0.19. Both temperatures were fitted on validation slices the model classified perfectly, so neither is identified: the NLL keeps falling as T → 0 and the fit stops where it is numerically zero. What the standard recipe produced on slices of 20 and 12 rows is a *sharpener*, not a calibrator — clean-email ECE 0.017 → 0.000 with every confidence at 1.000 (ECE is 0 only because accuracy is 100 %); under attack ECE 0.048 → 0.017 but confidence when wrong 0.614 → 0.918, the wrong direction for the automation decision. Zero-error coverage under attack is unchanged (96.0%): scaling does not reorder decisions. Temperature scaling is the knob a classifier you own has and a vendor judge does not; on a validation slice this small and this clean it has nothing to fit.

## Run 1 vs run 2 vs run 2 + temperature scaling (same held-out rows)

Run 1 is the pre-registered run the prediction was scored on. Run 2 and its temperature-scaled variant are the post-hoc amendment above: exploratory, not pre-registered, published with the same evidence. Accuracy is unchanged by temperature scaling by construction (it rescales logits, it does not reorder them).

| dataset (rows) | run | accuracy | acc on unseen-text rows | ECE | zero-error coverage | conf right / wrong | p50 latency |
|---|---|---|---|---|---|---|---|
| Business emails, clean (held-out half, n=100) | run 1 (pre-registered, 10 epochs) | 100.0% [96.4, 100.0]† | 100.0% (n=80) | 0.458 [0.424, 0.495] | 100.0% [96.4, 100.0]† | 0.542 / — | 0.016 s |
| Business emails, clean (held-out half, n=100) | run 2 (to convergence, post hoc) | 100.0% [96.4, 100.0]† | 100.0% (n=80) | 0.017 [0.016, 0.018] | 100.0% [96.4, 100.0]† | 0.983 / — | 0.017 s |
| Business emails, clean (held-out half, n=100) | run 2 + temperature scaling (post hoc) | 100.0% [96.4, 100.0]† | 100.0% (n=80) | 0.000 ‡ | 100.0% [96.4, 100.0]† | 1.000 / — | 0.017 s |
| Task router, bare option labels (held-out half, n=60) | run 1 (pre-registered, 10 epochs) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.133 [0.072, 0.191] | 100.0% [94.0, 100.0]† | 0.867 / — | 0.020 s |
| Task router, bare option labels (held-out half, n=60) | run 2 (to convergence, post hoc) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.005 [0.003, 0.009] | 100.0% [94.0, 100.0]† | 0.995 / — | 0.023 s |
| Task router, bare option labels (held-out half, n=60) | run 2 + temperature scaling (post hoc) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.000 ‡ | 100.0% [94.0, 100.0]† | 1.000 / — | 0.025 s |
| Task router, described options (held-out half, n=60) | run 1 (pre-registered, 10 epochs) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.133 [0.072, 0.191] | 100.0% [94.0, 100.0]† | 0.867 / — | 0.020 s |
| Task router, described options (held-out half, n=60) | run 2 (to convergence, post hoc) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.005 [0.003, 0.009] | 100.0% [94.0, 100.0]† | 0.995 / — | 0.025 s |
| Task router, described options (held-out half, n=60) | run 2 + temperature scaling (post hoc) | 100.0% [94.0, 100.0]† | 100.0% (n=5) | 0.000 ‡ | 100.0% [94.0, 100.0]† | 1.000 / — | 0.022 s |
| Emails under attack (all rows, n=200) | run 1 (pre-registered, 10 epochs) | 97.0% [94.4, 99.0] | 96.0% (n=151) | 0.496 [0.470, 0.522] | 97.0% [94.4, 99.0] | 0.484 / 0.150 | 0.017 s |
| Emails under attack (all rows, n=200) | run 2 (to convergence, post hoc) | 99.0% [97.5, 100.0] | 98.7% (n=151) | 0.048 [0.036, 0.066] | 96.0% [93.1, 100.0] | 0.953 / 0.614 | 0.018 s |
| Emails under attack (all rows, n=200) | run 2 + temperature scaling (post hoc) | 99.0% [97.5, 100.0] | 98.7% (n=151) | 0.017 [0.005, 0.033] | 96.0% [93.2, 100.0] | 0.991 / 0.918 | 0.019 s |

## How to read the intervals

- **[a, b]** after accuracy, ECE and zero-error coverage: 95 % percentile-bootstrap interval (2,000 resamples, seed 0) over the **distinct texts** of the scored rows, not the rows — the generators repeat states (#54), and two judgments of the same text are not two independent observations (`docs/judges.md` § Confidence intervals). Two runs or two judges whose intervals overlap are not separated by this data — which, at these n, is most of them: the held-out router half has 60 rows over few distinct texts, so its intervals are wide even where the point estimates are identical.
- **†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had.
- **‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number.

## Caveats (read with every number above)

- **Synthetic GT-1 data.** Both datasets come from seeded generators with labels by construction; the categories are clean and the vocabulary is narrow. A classifier trained on 100 such emails is learning the generator's templates, not business email.
- **The split is index-level; the generators repeat texts.** Train and test rows come from the same seeded generator, and it re-uses texts: `email-routing` has 161 distinct states in 200 rows, `task-routing` 61 in 120, and the adversarial emails wrap clean emails. So some held-out rows are byte-identical to a training row, and some attacked rows embed one — every table above counts them next to n and reports accuracy on the unseen-text rows separately, for every judge. Even the unseen-text rows are the same *distribution*: this is the classifier's best case and says nothing about drift, new categories or real inboxes. Dataset weakness, tracked in [#54](https://github.com/kunko-ai-labs/judge-audit/issues/54) (v2 generators with unique texts).
- **Small n.** Held-out halves are n=100 (emails) and n=60 (router, 20 hard + 20 attacked + 20 easy). Differences of a few points are within noise; intervals arrive with #46.
- **One training run, one seed, fixed hyper-parameters** (pre-registered). A tuned classifier would move the numbers; that would be a different, unregistered experiment.
- The other judges' held-out rows are re-scored from their full Arena runs; they were not re-run. Their prompts and settings are those of the Arena.
- **Run 2 and temperature scaling are post hoc.** They were decided after run 1's numbers were known (the amendment says when and why). Nothing in them is pre-registered; the prediction stays scored on run 1.
- **Wall times are from a shared laptop** and vary with load (run 1's router took 1,069 s for 10 epochs; run 2's took 63 s for 15): read them as orders of magnitude, not as a benchmark.
