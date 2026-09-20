# Audit report — nli

**n=120** · accuracy **49.2%** · ECE **0.1952**
· cost **$0.0000** · p50 **0.105s** · p99 **1.024s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · recomputed 2026-09-20T18:53:38+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 0.85 | 6 |
| 25% | 16.7% | 0.72 | 30 |
| 45% | 38.9% | 0.60 | 54 |
| 65% | 46.2% | 0.57 | 78 |
| 85% | 50.0% | 0.54 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.554 | 55.6% | 63 |
| 0.6-0.7 | 0.624 | 76.2% | 21 |
| 0.7-0.8 | 0.745 | 42.1% | 19 |
| 0.8-0.9 | 0.839 | 0.0% | 17 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
