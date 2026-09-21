# Audit report — llm

**n=120** · accuracy **56.7%** · ECE **0.3525**
· cost **$0.0000** · p50 **19.53s** · p99 **38.226s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-21T09:44:36+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/gemma4.r2.input.jsonl` · 120 rows · sha256 `cbb33e0a8043…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 50.0% | 0.98 | 6 |
| 25% | 73.3% | 0.95 | 30 |
| 45% | 68.5% | 0.95 | 54 |
| 65% | 60.3% | 0.90 | 78 |
| 85% | 56.9% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.717 | 66.7% | 3 |
| 0.8-0.9 | 0.841 | 52.9% | 17 |
| 0.9-1.0 | 0.939 | 57.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
