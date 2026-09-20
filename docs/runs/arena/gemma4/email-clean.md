# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0258**
· cost **$0.0000** · p50 **9.488s** · p99 **18.068s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-20T17:08:07+00:00 (original run time not recorded) · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 10 |
| 25% | 100.0% | 1.00 | 50 |
| 45% | 100.0% | 1.00 | 90 |
| 65% | 100.0% | 0.95 | 130 |
| 85% | 100.0% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.974 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
