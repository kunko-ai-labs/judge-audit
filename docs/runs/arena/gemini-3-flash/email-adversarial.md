> ⚠️ **SIMULATED — not a real vendor audit**

# Audit report — llm

**n=200** · accuracy **97.0%** · ECE **0.0151**
· cost **$0.0263** · p50 **2.454s** · p99 **63.072s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T10:23:13+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **11.5%** (23 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 10 |
| 25% | 94.0% | 1.00 | 50 |
| 45% | 95.6% | 1.00 | 90 |
| 65% | 96.2% | 0.99 | 130 |
| 85% | 97.1% | 0.95 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.825 | 100.0% | 2 |
| 0.9-1.0 | 0.983 | 97.0% | 198 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
