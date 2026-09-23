# Audit report — llm

**n=200** · accuracy **100.0%** [98.2, 100.0]† · ECE **0.0519** [0.0488, 0.0548]
· cost **$0.3848** · p50 **2.906s** · p99 **10.363s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T14:44:52+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [98.2, 100.0]† (200 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 8.0% | 100.0% | 0.99 | 16 |
| 89.5% | 100.0% | 0.95 | 179 |
| 100.0% | 100.0% | 0.90 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.948 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
