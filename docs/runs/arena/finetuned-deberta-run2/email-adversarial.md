# Audit report — finetuned

**n=200** · accuracy **99.0%** [97.5, 100.0] · confidence known **200/200** · ECE **0.0480** [0.0360, 0.0659] · ECE (equal-mass) **0.0403** [0.0242, 0.0571] · Brier **0.0163** [0.0074, 0.0268]
· cost **$0.0000** · p50 **0.018s** · p99 **0.034s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:17:03+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-09-24T15:20:27+00:00 from `docs/runs/arena/finetuned-deberta-run2/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **96.0%** [93.1, 100.0] (192 decisions, confidence ≥ 0.7097).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.99 | 10 |
| 11.0% | 100.0% | 0.99 | 22 |
| 15.0% | 100.0% | 0.98 | 30 |
| 20.0% | 100.0% | 0.98 | 40 |
| 25.5% | 100.0% | 0.98 | 51 |
| 30.0% | 100.0% | 0.98 | 60 |
| 35.0% | 100.0% | 0.98 | 70 |
| 40.0% | 100.0% | 0.98 | 80 |
| 45.0% | 100.0% | 0.98 | 90 |
| 50.0% | 100.0% | 0.98 | 100 |
| 55.0% | 100.0% | 0.98 | 110 |
| 60.0% | 100.0% | 0.98 | 120 |
| 65.0% | 100.0% | 0.97 | 130 |
| 70.0% | 100.0% | 0.97 | 140 |
| 75.0% | 100.0% | 0.97 | 150 |
| 80.0% | 100.0% | 0.97 | 160 |
| 85.0% | 100.0% | 0.96 | 170 |
| 90.0% | 100.0% | 0.94 | 180 |
| 95.0% | 100.0% | 0.77 | 190 |
| 100.0% | 99.0% | 0.28 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.275 | 100.0% | 1 |
| 0.3-0.4 | 0.399 | 100.0% | 2 |
| 0.4-0.5 | 0.444 | 100.0% | 2 |
| 0.5-0.6 | 0.569 | 50.0% | 2 |
| 0.6-0.7 | 0.630 | 0.0% | 1 |
| 0.7-0.8 | 0.734 | 100.0% | 3 |
| 0.8-0.9 | 0.851 | 100.0% | 3 |
| 0.9-1.0 | 0.976 | 100.0% | 186 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
