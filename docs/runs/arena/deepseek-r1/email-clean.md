# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0486**
· cost **$0.3859** · p50 **3.062s** · p99 **10.822s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-20T19:10:58+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 10 |
| 25% | 100.0% | 0.95 | 50 |
| 45% | 100.0% | 0.95 | 90 |
| 65% | 100.0% | 0.95 | 130 |
| 85% | 100.0% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.951 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
