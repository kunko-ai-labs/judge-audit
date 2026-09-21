# Audit report — llm

**n=120** · accuracy **55.8%** · ECE **0.3734**
· cost **$0.4379** · p50 **4.249s** · p99 **21.268s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T15:10:27+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 6 |
| 25% | 33.3% | 0.95 | 30 |
| 45% | 48.1% | 0.95 | 54 |
| 65% | 55.1% | 0.90 | 78 |
| 85% | 53.9% | 0.70 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.3-0.4 | 0.300 | 0.0% | 1 |
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.6-0.7 | 0.600 | 100.0% | 2 |
| 0.7-0.8 | 0.700 | 84.6% | 13 |
| 0.8-0.9 | 0.820 | 70.0% | 10 |
| 0.9-1.0 | 0.955 | 51.6% | 91 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
