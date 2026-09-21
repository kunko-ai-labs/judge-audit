# Audit report — llm

**n=120** · accuracy **65.8%** · ECE **0.1903**
· cost **$0.7134** · p50 **8.285s** · p99 **11.943s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-21T09:44:32+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/claude-sonnet-4.5.r2.input.jsonl` · 120 rows · sha256 `c1eca62b4244…`_

## Can I automate this?

Zero observed errors through the most confident **29.2%** (35 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 6 |
| 25% | 100.0% | 0.98 | 30 |
| 45% | 96.3% | 0.95 | 54 |
| 65% | 78.2% | 0.85 | 78 |
| 85% | 73.5% | 0.75 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 6 |
| 0.6-0.7 | 0.650 | 25.0% | 4 |
| 0.7-0.8 | 0.746 | 37.5% | 16 |
| 0.8-0.9 | 0.854 | 64.3% | 28 |
| 0.9-1.0 | 0.960 | 81.8% | 66 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
