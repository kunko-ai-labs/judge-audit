# Audit report — finetuned

**n=60** · accuracy **100.0%** [94.0, 100.0]† · confidence known **60/60** · ECE **0.0000** ‡ · ECE (equal-mass) **0.0000** ‡ · Brier **0.0000** ‡ · NLL **0.0000** ‡
· cost **$0.0000** · p50 **0.022s** · p99 **0.099s** · slowest **0.183s**

_judge `finetuned:deberta-v3-base-ft-task-routing-run2` · model `deberta-v3-base-ft-task-routing-run2` · seed 2026 · run 2026-09-22T08:17:41+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `c2811e2a8cde…`_
_regenerated 2026-10-03T17:18:07+00:00 from `docs/runs/arena/finetuned-deberta-run2-ts/router-described.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=60 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number._

## Can I automate this?

| at most this error | in plain words | automate (certified) | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | 1 in 100 automated decisions wrong | not certified: needs 628 texts with a confidence to certify 1%; has 44 | — | — |
| 2% | 1 in 50 automated decisions wrong | not certified: needs 313 texts with a confidence to certify 2%; has 44 | — | — |
| 5% | 1 in 20 automated decisions wrong | not certified: needs 124 texts with a confidence to certify 5%; has 44 | — | — |
| 10% | 1 in 10 automated decisions wrong | not certified: needs 61 texts with a confidence to certify 10%; has 44 | — | — |

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled texts (same mix, same judge version), with the labels taken as right: a label error counts as a judge error. Each row is its own 95% statement; choose the target before reading the table. "Automate" is the share of the labelled texts the threshold covers; "out of sample" is the same procedure with the threshold chosen on half of them and applied to the other half (seed 0), the estimate to plan with. One unit per distinct text; a decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that certifies with 2 errors (docs/judges.md § The automation certificate)._

Zero observed errors through the most confident **100.0%** [94.0, 100.0]† (60 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 50.0% | 100.0% | 1.00 | 30 |
| 66.7% | 100.0% | 1.00 | 40 |
| 70.0% | 100.0% | 1.00 | 42 |
| 75.0% | 100.0% | 1.00 | 45 |
| 80.0% | 100.0% | 1.00 | 48 |
| 86.7% | 100.0% | 1.00 | 52 |
| 90.0% | 100.0% | 1.00 | 54 |
| 96.7% | 100.0% | 1.00 | 58 |
| 100.0% | 100.0% | 1.00 | 60 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 1.000 | 100.0% | 60 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
