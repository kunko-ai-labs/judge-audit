# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0519**
· cost **$0.3848** · p50 **2.906s** · p99 **10.363s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T14:44:52+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 10 |
| 25% | 100.0% | 0.95 | 50 |
| 45% | 100.0% | 0.95 | 90 |
| 65% | 100.0% | 0.95 | 130 |
| 85% | 100.0% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.948 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
