# Audit report — llm

**n=120** · accuracy **90.0%** · ECE **0.0539**
· cost **$0.0000** · p50 **18.831s** · p99 **37.696s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-21T10:26:30+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/gemma4.r2.input.jsonl` · 120 rows · sha256 `f2952fd0ba64…`_

## Can I automate this?

Zero observed errors through the most confident **31.7%** (38 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 6 |
| 25% | 100.0% | 0.98 | 30 |
| 45% | 98.2% | 0.95 | 54 |
| 65% | 96.2% | 0.95 | 78 |
| 85% | 96.1% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 1 |
| 0.9-1.0 | 0.952 | 89.9% | 119 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
