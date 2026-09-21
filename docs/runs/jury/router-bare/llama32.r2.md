# Audit report — llm

**n=120** · accuracy **60.8%** · ECE **0.3462**
· cost **$0.0000** · p50 **1.006s** · p99 **1.254s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-21T10:24:28+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/llama32.r2.input.jsonl` · 120 rows · sha256 `9cb47a50ffb2…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 16.7% | 0.95 | 6 |
| 25% | 53.3% | 0.90 | 30 |
| 45% | 50.0% | 0.80 | 54 |
| 65% | 52.6% | 0.80 | 78 |
| 85% | 56.9% | 0.50 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 3 |
| 0.5-0.6 | 0.500 | 96.2% | 26 |
| 0.7-0.8 | 0.750 | 100.0% | 1 |
| 0.8-0.9 | 0.803 | 50.0% | 58 |
| 0.9-1.0 | 0.929 | 56.2% | 32 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
