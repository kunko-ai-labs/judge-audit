# Audit report — finetuned

**n=100** · accuracy **100.0%** [96.4, 100.0]† · confidence known **100/100** · ECE **0.0000** ‡ · ECE (equal-mass) **0.0000** ‡ · Brier **0.0000** ‡ · NLL **0.0000** ‡
· cost **$0.0000** · p50 **0.017s** · p99 **0.057s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:17:21+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/arena/finetuned-deberta-run2-ts/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=100 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [96.4, 100.0]† (100 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 1.00 | 5 |
| 10.0% | 100.0% | 1.00 | 10 |
| 15.0% | 100.0% | 1.00 | 15 |
| 20.0% | 100.0% | 1.00 | 20 |
| 25.0% | 100.0% | 1.00 | 25 |
| 32.0% | 100.0% | 1.00 | 32 |
| 35.0% | 100.0% | 1.00 | 35 |
| 40.0% | 100.0% | 1.00 | 40 |
| 45.0% | 100.0% | 1.00 | 45 |
| 50.0% | 100.0% | 1.00 | 50 |
| 55.0% | 100.0% | 1.00 | 55 |
| 60.0% | 100.0% | 1.00 | 60 |
| 65.0% | 100.0% | 1.00 | 65 |
| 70.0% | 100.0% | 1.00 | 70 |
| 77.0% | 100.0% | 1.00 | 77 |
| 80.0% | 100.0% | 1.00 | 80 |
| 85.0% | 100.0% | 1.00 | 85 |
| 90.0% | 100.0% | 1.00 | 90 |
| 95.0% | 100.0% | 1.00 | 95 |
| 100.0% | 100.0% | 1.00 | 100 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 1.000 | 100.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
