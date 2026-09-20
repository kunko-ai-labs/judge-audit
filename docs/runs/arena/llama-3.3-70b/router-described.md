# Audit report — llm

**n=120** · accuracy **86.7%** · ECE **0.0433**
· cost **$0.0314** · p50 **0.809s** · p99 **0.997s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-20T19:09:23+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **0.8%** (1 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 33.3% | 1.00 | 6 |
| 25% | 56.7% | 0.90 | 30 |
| 45% | 75.9% | 0.90 | 54 |
| 65% | 82.0% | 0.90 | 78 |
| 85% | 86.3% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 50.0% | 4 |
| 0.9-1.0 | 0.914 | 87.9% | 116 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
