# Audit report — llm

**n=120** · accuracy **83.3%** · ECE **0.0893**
· cost **$0.0000** · p50 **1.172s** · p99 **1.542s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-21T11:06:38+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/llama32.r2.input.jsonl` · 120 rows · sha256 `cafcc339a9f2…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 33.3% | 0.99 | 6 |
| 25% | 80.0% | 0.90 | 30 |
| 45% | 88.9% | 0.90 | 54 |
| 65% | 88.5% | 0.80 | 78 |
| 85% | 84.3% | 0.50 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 81.0% | 21 |
| 0.7-0.8 | 0.750 | 100.0% | 2 |
| 0.8-0.9 | 0.800 | 74.4% | 39 |
| 0.9-1.0 | 0.923 | 89.7% | 58 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
