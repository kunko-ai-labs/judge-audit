# Audit report — llm

**n=120** · accuracy **59.2%** · ECE **0.4292**
· cost **$0.0000** · p50 **0.878s** · p99 **1.038s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-20T17:06:30+00:00 (original run time not recorded) · judge-audit 0.3.0_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **2.5%** (3 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 1.00 | 6 |
| 25% | 43.3% | 1.00 | 30 |
| 45% | 46.3% | 1.00 | 54 |
| 65% | 55.1% | 1.00 | 78 |
| 85% | 55.9% | 1.00 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 100.0% | 5 |
| 0.9-1.0 | 1.000 | 57.4% | 115 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
