# Audit report — llm

**n=120** · accuracy **98.3%** [95.5, 100.0] · confidence known **120/120** · ECE **0.0121** [0.0013, 0.0335] · ECE (equal-mass) **0.0071** [0.0019, 0.0298] · Brier **0.0124** [0.0006, 0.0330] · NLL **0.0496** [0.0119, 0.1157]
· cost **$0.0185** · p50 **2.452s** · p99 **20.593s** · slowest **32.725s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T11:06:43+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_
_regenerated 2026-10-03T17:18:07+00:00 from `docs/runs/arena/gemini-3-flash/router-described.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

| at most this error | in plain words | automate (certified) | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | 1 in 100 automated decisions wrong | not certified: needs 628 texts with a confidence to certify 1%; has 61 | — | — |
| 2% | 1 in 50 automated decisions wrong | not certified: needs 313 texts with a confidence to certify 2%; has 61 | — | — |
| 5% | 1 in 20 automated decisions wrong | not certified: needs 124 texts with a confidence to certify 5%; has 61 | — | — |
| 10% | 1 in 10 automated decisions wrong | 100.0% (61 of 61 texts; 2 wrong, bound 10.0%) | 0.7 | not checkable: a half holds at most 31 texts with a confidence; the target needs 61 |

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled texts (same mix, same judge version), with the labels taken as right: a label error counts as a judge error. Each row is its own 95% statement; choose the target before reading the table. "Automate" is the share of the labelled texts the threshold covers; "out of sample" is the same procedure with the threshold chosen on half of them and applied to the other half (seed 0), the estimate to plan with. One unit per distinct text; a decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that certifies with 2 errors (docs/judges.md § The automation certificate)._

Zero observed errors through the most confident **72.5%** [60.6, 100.0] (87 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 72.5% | 100.0% | 1.00 | 87 |
| 96.7% | 99.1% | 0.95 | 116 |
| 100.0% | 98.3% | 0.70 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.700 | 0.0% | 1 |
| 0.9-1.0 | 0.985 | 99.2% | 119 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
