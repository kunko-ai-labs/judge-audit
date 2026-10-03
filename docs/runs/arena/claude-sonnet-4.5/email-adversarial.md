# Audit report — llm

**n=200** · accuracy **96.5%** [93.9, 99.0] · confidence known **200/200** · ECE **0.0159** [0.0049, 0.0397] · ECE (equal-mass) **0.0439** [0.0264, 0.0702] · Brier **0.0307** [0.0116, 0.0528] · NLL **∞** (2 answers declared certain and wrong)
· cost **$0.4538** · p50 **3.48s** · p99 **5.556s** · slowest **7.067s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-20T18:29:03+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-10-03T17:18:07+00:00 from `docs/runs/arena/claude-sonnet-4.5/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

| at most this error | in plain words | automate (certified) | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | 1 in 100 automated decisions wrong | not certified: needs 628 texts with a confidence to certify 1%; has 189 | — | — |
| 2% | 1 in 50 automated decisions wrong | not certified: needs 313 texts with a confidence to certify 2%; has 189 | — | — |
| 5% | 1 in 20 automated decisions wrong | 90.5% (171 of 189 texts; 3 wrong, bound 4.5%) | 0.95 | not checkable: a half holds at most 95 texts with a confidence; the target needs 124 |
| 10% | 1 in 10 automated decisions wrong | 100.0% (189 of 189 texts; 7 wrong, bound 6.8%) | 0.5 | 95.8% automated, 2.8% wrong |

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled texts (same mix, same judge version), with the labels taken as right: a label error counts as a judge error. Each row is its own 95% statement; choose the target before reading the table. "Automate" is the share of the labelled texts the threshold covers; "out of sample" is the same procedure with the threshold chosen on half of them and applied to the other half (seed 0), the estimate to plan with. One unit per distinct text; a decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that certifies with 2 errors (docs/judges.md § The automation certificate)._

Zero observed errors through the most confident **0.0%** [0.0, 90.9] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 12.0% | 91.7% | 1.00 | 24 |
| 29.5% | 96.6% | 0.99 | 59 |
| 30.0% | 96.7% | 0.98 | 60 |
| 91.0% | 98.4% | 0.95 | 182 |
| 99.5% | 97.0% | 0.85 | 199 |
| 100.0% | 96.5% | 0.50 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.8-0.9 | 0.850 | 91.7% | 12 |
| 0.9-1.0 | 0.963 | 97.3% | 187 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
