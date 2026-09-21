# Audit report — llm

**n=120** · accuracy **90.0%** · ECE **0.0526**
· cost **$0.7366** · p50 **8.11s** · p99 **10.829s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-21T10:10:32+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/claude-sonnet-4.5.r2.input.jsonl` · 120 rows · sha256 `5549b926d342…`_

## Can I automate this?

Zero observed errors through the most confident **78.3%** (94 decisions, confidence ≥ 0.85).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 0.98 | 30 |
| 45% | 100.0% | 0.95 | 54 |
| 65% | 100.0% | 0.92 | 78 |
| 85% | 98.0% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 6 |
| 0.6-0.7 | 0.650 | 0.0% | 1 |
| 0.7-0.8 | 0.743 | 57.1% | 7 |
| 0.8-0.9 | 0.851 | 90.5% | 21 |
| 0.9-1.0 | 0.961 | 100.0% | 85 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
