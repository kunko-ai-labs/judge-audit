# Audit report — llm

**n=120** · accuracy **77.5%** · ECE **0.1800**
· cost **$0.0000** · p50 **13.315s** · p99 **31.39s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-20T18:54:55+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 16.7% | 1.00 | 6 |
| 25% | 36.7% | 0.95 | 30 |
| 45% | 61.1% | 0.95 | 54 |
| 65% | 69.2% | 0.95 | 78 |
| 85% | 76.5% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.955 | 77.5% | 120 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
