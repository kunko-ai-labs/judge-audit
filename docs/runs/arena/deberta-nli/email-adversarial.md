# Audit report — nli

**n=200** · accuracy **59.5%** [51.7, 66.7] · ECE **0.1247** [0.0876, 0.2007] · ECE (equal-mass) **0.1106** [0.0911, 0.2002] · Brier **0.2049** [0.1696, 0.2420]
· cost **$0.0000** · p50 **0.355s** · p99 **0.841s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:51:52+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/arena/deberta-nli/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **8.0%** [3.9, 16.0] (16 decisions, confidence ≥ 0.9319).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 6.5% | 100.0% | 0.96 | 13 |
| 10.0% | 95.0% | 0.93 | 20 |
| 15.0% | 83.3% | 0.90 | 30 |
| 20.0% | 77.5% | 0.86 | 40 |
| 25.0% | 74.0% | 0.84 | 50 |
| 30.0% | 73.3% | 0.80 | 60 |
| 35.0% | 75.7% | 0.78 | 70 |
| 40.0% | 77.5% | 0.75 | 80 |
| 45.0% | 77.8% | 0.72 | 90 |
| 50.0% | 75.0% | 0.67 | 100 |
| 55.0% | 73.6% | 0.64 | 110 |
| 60.0% | 71.7% | 0.61 | 120 |
| 65.0% | 70.8% | 0.59 | 130 |
| 70.0% | 70.7% | 0.56 | 140 |
| 75.0% | 70.0% | 0.51 | 150 |
| 80.0% | 68.8% | 0.48 | 160 |
| 85.0% | 67.7% | 0.42 | 170 |
| 90.0% | 64.4% | 0.34 | 180 |
| 95.0% | 61.6% | 0.30 | 190 |
| 100.0% | 59.5% | 0.20 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.199 | 0.0% | 1 |
| 0.2-0.3 | 0.252 | 22.2% | 9 |
| 0.3-0.4 | 0.345 | 11.1% | 18 |
| 0.4-0.5 | 0.463 | 45.0% | 20 |
| 0.5-0.6 | 0.562 | 64.5% | 31 |
| 0.6-0.7 | 0.650 | 48.3% | 29 |
| 0.7-0.8 | 0.756 | 86.7% | 30 |
| 0.8-0.9 | 0.848 | 64.7% | 34 |
| 0.9-1.0 | 0.945 | 85.7% | 28 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
