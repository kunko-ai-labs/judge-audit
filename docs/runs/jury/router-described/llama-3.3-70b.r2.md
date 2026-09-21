# Audit report — llm

**n=120** · accuracy **95.8%** · ECE **0.0144**
· cost **$0.0412** · p50 **0.931s** · p99 **2.227s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-21T10:26:31+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `4eb39a7da7be…`_

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 0.99 | 6 |
| 25% | 96.7% | 0.99 | 30 |
| 45% | 98.2% | 0.98 | 54 |
| 65% | 97.4% | 0.95 | 78 |
| 85% | 97.1% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 87.5% | 16 |
| 0.9-1.0 | 0.966 | 97.1% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
