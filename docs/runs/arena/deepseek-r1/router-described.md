# Audit report — llm

**n=120** · accuracy **79.2%** · ECE **0.1478**
· cost **$0.4660** · p50 **4.089s** · p99 **28.476s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T15:21:30+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 6 |
| 25% | 60.0% | 0.95 | 30 |
| 45% | 74.1% | 0.95 | 54 |
| 65% | 76.9% | 0.95 | 78 |
| 85% | 81.4% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 100.0% | 3 |
| 0.8-0.9 | 0.806 | 62.5% | 8 |
| 0.9-1.0 | 0.952 | 81.3% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
