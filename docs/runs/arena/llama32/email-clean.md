# Audit report — llm

**n=200** · accuracy **90.0%** · ECE **0.0340**
· cost **$0.0000** · p50 **0.704s** · p99 **0.96s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-20T17:00:06+00:00 (original run time not recorded) · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **5.5%** (11 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.90 | 10 |
| 25% | 94.0% | 0.90 | 50 |
| 45% | 92.2% | 0.90 | 90 |
| 65% | 93.1% | 0.90 | 130 |
| 85% | 91.8% | 0.80 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 83.8% | 68 |
| 0.9-1.0 | 0.900 | 93.2% | 132 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
