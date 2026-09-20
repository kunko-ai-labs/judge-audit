# Audit report — nli

**n=200** · accuracy **59.5%** · ECE **0.1247**
· cost **$0.0000** · p50 **0.355s** · p99 **0.841s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · recomputed 2026-09-20T18:51:52+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_

## Can I automate this?

Zero observed errors through the most confident **8.0%** (16 decisions, confidence ≥ 0.9319).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.96 | 10 |
| 25% | 74.0% | 0.84 | 50 |
| 45% | 77.8% | 0.72 | 90 |
| 65% | 70.8% | 0.59 | 130 |
| 85% | 67.7% | 0.42 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.199 | 0.0% | 1 |
| 0.2-0.3 | 0.252 | 22.2% | 9 |
| 0.3-0.4 | 0.345 | 11.1% | 18 |
| 0.4-0.5 | 0.463 | 45.0% | 20 |
| 0.5-0.6 | 0.562 | 64.5% | 31 |
| 0.6-0.7 | 0.650 | 48.3% | 29 |
| 0.7-0.8 | 0.756 | 86.7% | 30 |
| 0.8-0.9 | 0.848 | 64.7% | 34 |
| 0.9-1.0 | 0.945 | 85.7% | 28 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
