# Audit report — llm

**n=120** · accuracy **65.0%** · ECE **0.2333**
· cost **$0.0258** · p50 **0.795s** · p99 **1.007s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-20T19:07:50+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 6 |
| 25% | 20.0% | 0.90 | 30 |
| 45% | 48.1% | 0.90 | 54 |
| 65% | 62.8% | 0.80 | 78 |
| 85% | 63.7% | 0.80 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 70.5% | 44 |
| 0.9-1.0 | 0.932 | 61.8% | 76 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
