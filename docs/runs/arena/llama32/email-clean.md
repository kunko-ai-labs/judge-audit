# Audit report — llm

**n=200** · accuracy **90.0%** [77.8, 100.0] · confidence known **200/200** · ECE **0.0340** [0.0245, 0.1431] · ECE (equal-mass) **0.0340** [0.0245, 0.1431] · Brier **0.0892** [0.0182, 0.1743] · NLL **0.3205** [0.1377, 0.5408]
· cost **$0.0000** · p50 **0.703s** · p99 **0.931s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:00:06+00:00 · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/arena/llama32/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 100.0] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 66.0% | 93.2% | 0.90 | 132 |
| 100.0% | 90.0% | 0.80 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 83.8% | 68 |
| 0.9-1.0 | 0.900 | 93.2% | 132 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
