# Audit report — llm

**n=200** · accuracy **72.5%** · ECE **0.1540**
· cost **$0.0000** · p50 **0.747s** · p99 **0.939s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-20T17:02:29+00:00 (original run time not recorded) · judge-audit 0.3.0_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 10 |
| 25% | 54.0% | 0.90 | 50 |
| 45% | 65.6% | 0.90 | 90 |
| 65% | 71.5% | 0.90 | 130 |
| 85% | 72.4% | 0.80 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 75.0% | 60 |
| 0.9-1.0 | 0.913 | 71.4% | 140 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
