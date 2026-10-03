# Audit report — llm

**n=200** · accuracy **100.0%** [98.2, 100.0]† · confidence known **200/200** · ECE **0.0258** [0.0204, 0.0307] · ECE (equal-mass) **0.0258** [0.0204, 0.0307] · Brier **0.0013** [0.0010, 0.0016] · NLL **0.0264** [0.0210, 0.0315]
· cost **$0.0000** · p50 **9.452s** · p99 **16.952s** · slowest **36.987s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-20T17:08:07+00:00 · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-10-03T17:18:07+00:00 from `docs/runs/arena/gemma4/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

| at most this error | in plain words | automate (certified) | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | 1 in 100 automated decisions wrong | not certified: needs 628 texts with a confidence to certify 1%; has 161 | — | — |
| 2% | 1 in 50 automated decisions wrong | not certified: needs 313 texts with a confidence to certify 2%; has 161 | — | — |
| 5% | 1 in 20 automated decisions wrong | 100.0% (161 of 161 texts; 0 wrong, bound 1.8%) | 0.9 | not checkable: a half holds at most 81 texts with a confidence; the target needs 124 |
| 10% | 1 in 10 automated decisions wrong | 100.0% (161 of 161 texts; 0 wrong, bound 1.8%) | 0.9 | 99.4% automated, 0.0% wrong |

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled texts (same mix, same judge version), with the labels taken as right: a label error counts as a judge error. Each row is its own 95% statement; choose the target before reading the table. "Automate" is the share of the labelled texts the threshold covers; "out of sample" is the same procedure with the threshold chosen on half of them and applied to the other half (seed 0), the estimate to plan with. One unit per distinct text; a decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that certifies with 2 errors (docs/judges.md § The automation certificate)._

Zero observed errors through the most confident **100.0%** [98.2, 100.0]† (200 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 49.0% | 100.0% | 1.00 | 98 |
| 99.5% | 100.0% | 0.95 | 199 |
| 100.0% | 100.0% | 0.90 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.974 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
