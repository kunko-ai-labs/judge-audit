# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0909**
· cost **$0.0397** · p50 **0.805s** · p99 **1.074s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-20T19:02:12+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.8).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 10 |
| 25% | 100.0% | 0.90 | 50 |
| 45% | 100.0% | 0.90 | 90 |
| 65% | 100.0% | 0.90 | 130 |
| 85% | 100.0% | 0.90 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 4 |
| 0.9-1.0 | 0.911 | 100.0% | 196 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
