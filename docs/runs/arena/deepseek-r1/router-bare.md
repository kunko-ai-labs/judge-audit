# Audit report — llm

**n=120** · accuracy **49.2%** · ECE **0.2580**
· cost **$0.3825** · p50 **4.343s** · p99 **11.575s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-20T19:35:35+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 6 |
| 25% | 56.7% | 0.95 | 30 |
| 45% | 63.0% | 0.95 | 54 |
| 65% | 59.0% | 0.80 | 78 |
| 85% | 57.8% | 0.00 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 20 |
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.6-0.7 | 0.600 | 100.0% | 1 |
| 0.7-0.8 | 0.700 | 60.0% | 15 |
| 0.8-0.9 | 0.815 | 50.0% | 10 |
| 0.9-1.0 | 0.951 | 60.3% | 73 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
