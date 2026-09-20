# Audit report — llm

**n=200** · accuracy **96.5%** · ECE **0.0159**
· cost **$0.4538** · p50 **3.489s** · p99 **5.956s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-20T18:29:03+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **2.0%** (4 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 80.0% | 1.00 | 10 |
| 25% | 96.0% | 0.99 | 50 |
| 45% | 97.8% | 0.95 | 90 |
| 65% | 98.5% | 0.95 | 130 |
| 85% | 98.2% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.8-0.9 | 0.850 | 91.7% | 12 |
| 0.9-1.0 | 0.963 | 97.3% | 187 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
