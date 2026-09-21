# Audit report — llm

**n=120** · accuracy **66.7%** · ECE **0.3029**
· cost **$0.0225** · p50 **3.175s** · p99 **25.025s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · recomputed 2026-09-21T13:51:16+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/gemini-3-flash.r2.input.jsonl` · 120 rows · sha256 `13926948b105…`_

## Can I automate this?

Zero observed errors through the most confident **4.2%** (5 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 1.00 | 6 |
| 25% | 90.0% | 1.00 | 30 |
| 45% | 90.7% | 1.00 | 54 |
| 65% | 79.5% | 0.95 | 78 |
| 85% | 69.6% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.750 | 100.0% | 3 |
| 0.8-0.9 | 0.841 | 45.5% | 11 |
| 0.9-1.0 | 0.975 | 67.9% | 106 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
