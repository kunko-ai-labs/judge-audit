# Audit report — llm

**n=120** · accuracy **98.3%** · ECE **0.0371**
· cost **$0.0284** · p50 **3.219s** · p99 **71.984s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · recomputed 2026-09-21T14:00:19+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/gemini-3-flash.r2.input.jsonl` · 120 rows · sha256 `b0ea82b37189…`_

## Can I automate this?

Zero observed errors through the most confident **95.8%** (115 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 1.00 | 30 |
| 45% | 100.0% | 1.00 | 54 |
| 65% | 100.0% | 0.95 | 78 |
| 85% | 100.0% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.850 | 60.0% | 5 |
| 0.9-1.0 | 0.972 | 100.0% | 115 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
