# Audit report — llm

**n=120** · accuracy **83.3%** · ECE **0.0112**
· cost **$0.4149** · p50 **4.193s** · p99 **9.484s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T10:28:34+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `9b5b4c3f706b…`_

## Can I automate this?

Zero observed errors through the most confident **6.7%** (8 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 96.7% | 0.98 | 30 |
| 45% | 98.2% | 0.95 | 54 |
| 65% | 96.2% | 0.95 | 78 |
| 85% | 96.1% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 15 |
| 0.7-0.8 | 0.700 | 50.0% | 2 |
| 0.8-0.9 | 0.847 | 100.0% | 6 |
| 0.9-1.0 | 0.959 | 95.9% | 97 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
