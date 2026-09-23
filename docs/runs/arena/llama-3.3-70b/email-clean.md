# Audit report — llm

**n=200** · accuracy **100.0%** [98.2, 100.0]† · ECE **0.0909** [0.0858, 0.0960] · ECE (equal-mass) **0.0909** [0.0858, 0.0960] · Brier **0.0094** [0.0086, 0.0103]
· cost **$0.0397** · p50 **0.805s** · p99 **1.074s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · run 2026-09-20T19:02:12+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/arena/llama-3.3-70b/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [98.2, 100.0]† (200 decisions, confidence ≥ 0.8).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 12.0% | 100.0% | 0.99 | 24 |
| 98.0% | 100.0% | 0.90 | 196 |
| 100.0% | 100.0% | 0.80 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 4 |
| 0.9-1.0 | 0.911 | 100.0% | 196 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
