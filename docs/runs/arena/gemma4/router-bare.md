# Audit report — llm

**n=120** · accuracy **59.2%** · ECE **0.3446**
· cost **$0.0000** · p50 **13.268s** · p99 **32.085s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-20T18:26:26+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 6 |
| 25% | 0.0% | 1.00 | 30 |
| 45% | 40.7% | 0.95 | 54 |
| 65% | 56.4% | 0.90 | 78 |
| 85% | 59.8% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 44.4% | 9 |
| 0.9-1.0 | 0.947 | 60.4% | 111 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
