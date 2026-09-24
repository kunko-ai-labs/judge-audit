# Audit report — finetuned

**n=200** · accuracy **99.0%** [97.5, 100.0] · confidence known **200/200** · ECE **0.0170** [0.0050, 0.0331] · ECE (equal-mass) **0.0004** [0.0003, 0.0169] · Brier **0.0116** [0.0017, 0.0255] · NLL **0.0365** [0.0063, 0.0773]
· cost **$0.0000** · p50 **0.019s** · p99 **0.056s** · slowest **0.234s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:17:27+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-09-24T15:48:07+00:00 from `docs/runs/arena/finetuned-deberta-run2-ts/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **96.0%** [93.2, 100.0] (192 decisions, confidence ≥ 0.9861).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 1.00 | 10 |
| 10.0% | 100.0% | 1.00 | 20 |
| 15.0% | 100.0% | 1.00 | 30 |
| 20.0% | 100.0% | 1.00 | 40 |
| 25.0% | 100.0% | 1.00 | 50 |
| 30.0% | 100.0% | 1.00 | 60 |
| 35.0% | 100.0% | 1.00 | 70 |
| 40.0% | 100.0% | 1.00 | 80 |
| 45.0% | 100.0% | 1.00 | 90 |
| 50.0% | 100.0% | 1.00 | 100 |
| 55.0% | 100.0% | 1.00 | 110 |
| 60.0% | 100.0% | 1.00 | 120 |
| 65.0% | 100.0% | 1.00 | 130 |
| 70.0% | 100.0% | 1.00 | 140 |
| 75.0% | 100.0% | 1.00 | 150 |
| 80.0% | 100.0% | 1.00 | 160 |
| 85.0% | 100.0% | 1.00 | 170 |
| 90.0% | 100.0% | 1.00 | 180 |
| 95.0% | 100.0% | 1.00 | 190 |
| 100.0% | 99.0% | 0.46 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.4-0.5 | 0.459 | 100.0% | 1 |
| 0.6-0.7 | 0.658 | 100.0% | 2 |
| 0.7-0.8 | 0.780 | 100.0% | 2 |
| 0.8-0.9 | 0.893 | 0.0% | 1 |
| 0.9-1.0 | 0.999 | 99.5% | 194 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
