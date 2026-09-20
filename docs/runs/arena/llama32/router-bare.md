# Audit report — llm

**n=120** · accuracy **65.8%** · ECE **0.3958**
· cost **$0.0000** · p50 **0.75s** · p99 **0.962s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-20T17:04:59+00:00 (original run time not recorded) · judge-audit 0.3.0_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **2.5%** (3 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 1.00 | 6 |
| 25% | 50.0% | 1.00 | 30 |
| 45% | 53.7% | 1.00 | 54 |
| 65% | 60.3% | 1.00 | 78 |
| 85% | 60.8% | 1.00 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 100.0% | 13 |
| 0.9-1.0 | 1.000 | 61.7% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
