# Audit report — llm

**n=120** · accuracy **65.8%** [51.9, 78.7] · confidence known **120/120** · ECE **0.2353** [0.1216, 0.3629] · ECE (equal-mass) **0.2363** [0.1402, 0.3686] · Brier **0.2462** [0.1578, 0.3426] · NLL **∞** (3 answers declared certain and wrong)
· cost **$0.5004** · p50 **6.158s** · p99 **10.156s** · slowest **10.725s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-20T18:40:35+00:00 · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-10-03T17:18:07+00:00 from `docs/runs/arena/claude-sonnet-4.5/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

| at most this error | in plain words | automate (certified) | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | 1 in 100 automated decisions wrong | not certified: needs 628 texts with a confidence to certify 1%; has 61 | — | — |
| 2% | 1 in 50 automated decisions wrong | not certified: needs 313 texts with a confidence to certify 2%; has 61 | — | — |
| 5% | 1 in 20 automated decisions wrong | not certified: needs 124 texts with a confidence to certify 5%; has 61 | — | — |
| 10% | 1 in 10 automated decisions wrong | not certified: no threshold passes: the first cut tested holds 61 texts with 20 errors (bound 44.0% > 10%) | — | — |

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled texts (same mix, same judge version), with the labels taken as right: a label error counts as a judge error. Each row is its own 95% statement; choose the target before reading the table. "Automate" is the share of the labelled texts the threshold covers; "out of sample" is the same procedure with the threshold chosen on half of them and applied to the other half (seed 0), the estimate to plan with. One unit per distinct text; a decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that certifies with 2 errors (docs/judges.md § The automation certificate)._

Zero observed errors through the most confident **0.0%** [0.0, 10.3] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 9.2% | 72.7% | 0.99 | 11 |
| 11.7% | 78.6% | 0.98 | 14 |
| 58.3% | 90.0% | 0.95 | 70 |
| 63.3% | 82.9% | 0.90 | 76 |
| 82.5% | 73.7% | 0.85 | 99 |
| 91.7% | 70.0% | 0.75 | 110 |
| 95.0% | 68.4% | 0.72 | 114 |
| 100.0% | 65.8% | 0.65 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.650 | 50.0% | 2 |
| 0.7-0.8 | 0.733 | 26.3% | 19 |
| 0.8-0.9 | 0.850 | 43.5% | 23 |
| 0.9-1.0 | 0.953 | 82.9% | 76 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
