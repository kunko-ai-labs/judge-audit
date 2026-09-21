# Audit report — llm

**n=120** · accuracy **55.0%** · ECE **0.3980**
· cost **$0.0355** · p50 **0.874s** · p99 **1.277s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-21T10:00:53+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `1956ef71fea3…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 0.99 | 6 |
| 25% | 76.7% | 0.98 | 30 |
| 45% | 72.2% | 0.98 | 54 |
| 65% | 56.4% | 0.95 | 78 |
| 85% | 50.0% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.700 | 100.0% | 3 |
| 0.8-0.9 | 0.820 | 75.0% | 20 |
| 0.9-1.0 | 0.964 | 49.5% | 97 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
