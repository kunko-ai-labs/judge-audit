> ⚠️ **SIMULATED — not a real vendor audit**

# Audit report — llm

**n=200** · accuracy **100.0%** · ECE **0.0047**
· cost **$0.0246** · p50 **2.074s** · p99 **61.984s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-20T18:11:22+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (200 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 10 |
| 25% | 100.0% | 1.00 | 50 |
| 45% | 100.0% | 1.00 | 90 |
| 65% | 100.0% | 1.00 | 130 |
| 85% | 100.0% | 1.00 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.995 | 100.0% | 200 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
