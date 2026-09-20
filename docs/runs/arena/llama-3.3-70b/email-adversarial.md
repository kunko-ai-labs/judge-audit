# Audit report — llm

**n=200** · accuracy **90.5%** · ECE **0.0155**
· cost **$0.0411** · p50 **0.812s** · p99 **7.172s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-20T19:04:55+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 0.0% | 1.00 | 10 |
| 25% | 76.0% | 0.90 | 50 |
| 45% | 86.7% | 0.90 | 90 |
| 65% | 90.8% | 0.90 | 130 |
| 85% | 91.8% | 0.90 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 2 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.8-0.9 | 0.800 | 85.7% | 14 |
| 0.9-1.0 | 0.912 | 92.3% | 183 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
