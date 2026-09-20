# Audit report — llm

**n=120** · accuracy **71.7%** · ECE **0.0563**
· cost **$0.3884** · p50 **3.76s** · p99 **11.28s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-20T19:45:16+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 33.3% | 1.00 | 6 |
| 25% | 80.0% | 0.95 | 30 |
| 45% | 83.3% | 0.95 | 54 |
| 65% | 88.5% | 0.90 | 78 |
| 85% | 84.3% | 0.00 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 23 |
| 0.7-0.8 | 0.700 | 100.0% | 1 |
| 0.8-0.9 | 0.800 | 90.0% | 10 |
| 0.9-1.0 | 0.947 | 88.4% | 86 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
