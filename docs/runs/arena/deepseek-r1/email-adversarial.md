# Audit report — llm

**n=200** · accuracy **80.5%** · ECE **0.1265**
· cost **$0.5890** · p50 **3.101s** · p99 **27.752s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T14:55:24+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 20.0% | 1.00 | 10 |
| 25% | 68.0% | 0.95 | 50 |
| 45% | 77.8% | 0.95 | 90 |
| 65% | 80.8% | 0.95 | 130 |
| 85% | 82.3% | 0.90 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.100 | 0.0% | 1 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 25.0% | 4 |
| 0.8-0.9 | 0.800 | 66.7% | 6 |
| 0.9-1.0 | 0.949 | 83.0% | 188 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
