# Audit report — llm

**n=200** · accuracy **81.0%** · ECE **0.1534**
· cost **$0.0000** · p50 **12.235s** · p99 **30.737s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-20T17:40:56+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **2.0%** (4 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 90.0% | 1.00 | 10 |
| 25% | 70.0% | 1.00 | 50 |
| 45% | 67.8% | 0.95 | 90 |
| 65% | 76.9% | 0.95 | 130 |
| 85% | 81.8% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 50.0% | 4 |
| 0.9-1.0 | 0.967 | 81.6% | 196 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
