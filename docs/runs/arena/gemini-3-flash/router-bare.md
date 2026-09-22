> ⚠️ **SIMULATED — not a real vendor audit**

# Audit report — llm

**n=120** · accuracy **66.7%** · ECE **0.3154**
· cost **$0.0161** · p50 **2.423s** · p99 **62.701s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T10:36:15+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_

## Can I automate this?

Zero observed errors through the most confident **2.5%** (3 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 1.00 | 6 |
| 25% | 63.3% | 1.00 | 30 |
| 45% | 74.1% | 1.00 | 54 |
| 65% | 73.1% | 1.00 | 78 |
| 85% | 71.6% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 0.0% | 1 |
| 0.9-1.0 | 0.984 | 67.2% | 119 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
