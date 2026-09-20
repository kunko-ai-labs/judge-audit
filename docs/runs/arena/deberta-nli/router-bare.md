# Audit report — nli

**n=120** · accuracy **47.5%** · ECE **0.4027**
· cost **$0.0000** · p50 **0.094s** · p99 **0.826s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · recomputed 2026-09-20T18:53:15+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 0.99 | 6 |
| 25% | 0.0% | 0.94 | 30 |
| 45% | 25.9% | 0.65 | 54 |
| 65% | 39.7% | 0.58 | 78 |
| 85% | 43.1% | 0.52 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.545 | 63.0% | 54 |
| 0.6-0.7 | 0.651 | 85.7% | 21 |
| 0.7-0.8 | 0.760 | 100.0% | 5 |
| 0.8-0.9 | 0.887 | 0.0% | 5 |
| 0.9-1.0 | 0.965 | 0.0% | 35 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
