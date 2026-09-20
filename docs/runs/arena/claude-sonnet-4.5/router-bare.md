# Audit report — llm

**n=120** · accuracy **60.8%** · ECE **0.2370**
· cost **$0.5004** · p50 **6.166s** · p99 **10.21s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-20T18:40:35+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 50.0% | 0.99 | 6 |
| 25% | 80.0% | 0.95 | 30 |
| 45% | 87.0% | 0.95 | 54 |
| 65% | 78.2% | 0.85 | 78 |
| 85% | 68.6% | 0.75 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 6 |
| 0.6-0.7 | 0.650 | 50.0% | 2 |
| 0.7-0.8 | 0.733 | 26.3% | 19 |
| 0.8-0.9 | 0.850 | 43.5% | 23 |
| 0.9-1.0 | 0.952 | 81.4% | 70 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
