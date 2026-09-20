# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0290**
· cost **$0.3798** · p50 **2.914s** · p99 **4.747s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-20T18:17:43+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.85).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 10 |
| 25% | 100.0% | 1.00 | 50 |
| 45% | 100.0% | 0.99 | 90 |
| 65% | 100.0% | 0.95 | 130 |
| 85% | 100.0% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.850 | 100.0% | 1 |
| 0.9-1.0 | 0.972 | 100.0% | 199 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
