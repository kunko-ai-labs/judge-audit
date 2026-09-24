# Audit report — nli

**n=200** · accuracy **86.5%** [80.8, 91.6] · confidence known **200/200** · ECE **0.1765** [0.1244, 0.2416] · ECE (equal-mass) **0.1630** [0.1174, 0.2348] · Brier **0.1288** [0.0970, 0.1696]
· cost **$0.0000** · p50 **0.321s** · p99 **0.768s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:50:38+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-09-23T18:32:04+00:00 from `docs/runs/arena/deberta-nli/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **51.5%** [41.4, 64.1] (103 decisions, confidence ≥ 0.7368).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.98 | 10 |
| 10.0% | 100.0% | 0.97 | 20 |
| 16.0% | 100.0% | 0.96 | 32 |
| 20.0% | 100.0% | 0.92 | 40 |
| 25.0% | 100.0% | 0.90 | 50 |
| 30.5% | 100.0% | 0.85 | 61 |
| 35.0% | 100.0% | 0.81 | 70 |
| 40.0% | 100.0% | 0.79 | 80 |
| 45.0% | 100.0% | 0.75 | 90 |
| 51.0% | 100.0% | 0.74 | 102 |
| 55.0% | 98.2% | 0.70 | 110 |
| 60.0% | 96.7% | 0.67 | 120 |
| 65.0% | 95.4% | 0.64 | 130 |
| 70.0% | 94.3% | 0.61 | 140 |
| 75.0% | 94.7% | 0.56 | 150 |
| 80.0% | 93.8% | 0.54 | 160 |
| 85.0% | 91.8% | 0.48 | 170 |
| 90.0% | 88.3% | 0.42 | 180 |
| 95.0% | 86.8% | 0.35 | 190 |
| 100.0% | 86.5% | 0.23 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.236 | 88.9% | 9 |
| 0.3-0.4 | 0.369 | 54.5% | 11 |
| 0.4-0.5 | 0.462 | 33.3% | 15 |
| 0.5-0.6 | 0.555 | 87.5% | 24 |
| 0.6-0.7 | 0.650 | 80.0% | 30 |
| 0.7-0.8 | 0.748 | 94.3% | 35 |
| 0.8-0.9 | 0.841 | 100.0% | 27 |
| 0.9-1.0 | 0.954 | 100.0% | 49 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
