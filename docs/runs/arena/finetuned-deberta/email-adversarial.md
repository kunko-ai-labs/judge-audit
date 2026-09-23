# Audit report — finetuned

**n=200** · accuracy **97.0%** [94.4, 99.0] · ECE **0.4961** [0.4702, 0.5220] · ECE (equal-mass) **0.4961** [0.4693, 0.5220] · Brier **0.2798** [0.2568, 0.3033]
· cost **$0.0000** · p50 **0.017s** · p99 **0.155s**

_judge `finetuned:deberta-v3-base-ft-email-routing` · model `deberta-v3-base-ft-email-routing` · seed 2026 · run 2026-09-22T03:13:44+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/arena/finetuned-deberta/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **97.0%** [94.4, 99.0] (194 decisions, confidence ≥ 0.1694).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.75 | 10 |
| 10.5% | 100.0% | 0.66 | 21 |
| 15.0% | 100.0% | 0.63 | 30 |
| 20.0% | 100.0% | 0.60 | 40 |
| 25.0% | 100.0% | 0.56 | 50 |
| 30.0% | 100.0% | 0.55 | 60 |
| 35.0% | 100.0% | 0.54 | 70 |
| 40.0% | 100.0% | 0.53 | 80 |
| 45.0% | 100.0% | 0.52 | 90 |
| 50.0% | 100.0% | 0.51 | 100 |
| 55.0% | 100.0% | 0.48 | 110 |
| 60.0% | 100.0% | 0.45 | 120 |
| 65.0% | 100.0% | 0.43 | 130 |
| 70.5% | 100.0% | 0.40 | 141 |
| 75.0% | 100.0% | 0.38 | 150 |
| 80.0% | 100.0% | 0.35 | 160 |
| 85.0% | 100.0% | 0.30 | 170 |
| 90.0% | 100.0% | 0.22 | 180 |
| 95.0% | 100.0% | 0.20 | 190 |
| 100.0% | 97.0% | 0.14 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.160 | 40.0% | 10 |
| 0.2-0.3 | 0.228 | 100.0% | 21 |
| 0.3-0.4 | 0.364 | 100.0% | 30 |
| 0.4-0.5 | 0.449 | 100.0% | 33 |
| 0.5-0.6 | 0.541 | 100.0% | 70 |
| 0.6-0.7 | 0.647 | 100.0% | 20 |
| 0.7-0.8 | 0.740 | 100.0% | 16 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
