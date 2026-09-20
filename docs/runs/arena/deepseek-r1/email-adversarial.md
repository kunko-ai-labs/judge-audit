# Audit report — llm

**n=200** · accuracy **76.5%** · ECE **0.0740**
· cost **$0.5032** · p50 **3.23s** · p99 **12.755s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-20T19:21:51+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **0.5%** (1 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 30.0% | 1.00 | 10 |
| 25% | 70.0% | 0.95 | 50 |
| 45% | 81.1% | 0.95 | 90 |
| 65% | 84.6% | 0.95 | 130 |
| 85% | 88.2% | 0.80 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 19 |
| 0.2-0.3 | 0.200 | 0.0% | 2 |
| 0.3-0.4 | 0.300 | 0.0% | 2 |
| 0.8-0.9 | 0.800 | 60.0% | 10 |
| 0.9-1.0 | 0.951 | 88.0% | 167 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
