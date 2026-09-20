# Audit report — llm

**n=120** · accuracy **88.3%** · ECE **0.0339**
· cost **$0.3998** · p50 **4.56s** · p99 **6.916s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-20T18:53:06+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **3.3%** (4 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 1.00 | 6 |
| 25% | 86.7% | 0.95 | 30 |
| 45% | 90.7% | 0.95 | 54 |
| 65% | 92.3% | 0.95 | 78 |
| 85% | 94.1% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 8 |
| 0.8-0.9 | 0.850 | 100.0% | 14 |
| 0.9-1.0 | 0.959 | 93.9% | 98 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
