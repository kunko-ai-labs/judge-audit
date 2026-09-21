# Audit report — llm

**n=120** · accuracy **98.3%** · ECE **0.0121**
· cost **$0.0185** · p50 **2.452s** · p99 **21.669s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T11:06:43+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

## Can I automate this?

Zero observed errors through the most confident **85.0%** (102 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 1.00 | 30 |
| 45% | 100.0% | 1.00 | 54 |
| 65% | 100.0% | 1.00 | 78 |
| 85% | 100.0% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.700 | 0.0% | 1 |
| 0.9-1.0 | 0.985 | 99.2% | 119 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
