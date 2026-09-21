# Audit report — llm

**n=120** · accuracy **50.0%** · ECE **0.3542**
· cost **$0.4039** · p50 **3.583s** · p99 **7.61s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T10:02:38+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `3d5d792c3c6f…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 50.0% | 0.99 | 6 |
| 25% | 66.7% | 0.95 | 30 |
| 45% | 57.4% | 0.95 | 54 |
| 65% | 56.4% | 0.95 | 78 |
| 85% | 53.9% | 0.75 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 12 |
| 0.7-0.8 | 0.736 | 85.7% | 7 |
| 0.8-0.9 | 0.850 | 16.7% | 6 |
| 0.9-1.0 | 0.953 | 55.8% | 95 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
