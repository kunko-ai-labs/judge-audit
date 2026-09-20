# Audit report — nli

**n=200** · accuracy **86.5%** · ECE **0.1765**
· cost **$0.0000** · p50 **0.321s** · p99 **0.768s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · recomputed 2026-09-20T18:50:38+00:00 (original run time not recorded) · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_

## Can I automate this?

Zero observed errors through the most confident **51.5%** (103 decisions, confidence ≥ 0.7368).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.98 | 10 |
| 25% | 100.0% | 0.90 | 50 |
| 45% | 100.0% | 0.75 | 90 |
| 65% | 95.4% | 0.64 | 130 |
| 85% | 91.8% | 0.48 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.236 | 88.9% | 9 |
| 0.3-0.4 | 0.369 | 54.5% | 11 |
| 0.4-0.5 | 0.462 | 33.3% | 15 |
| 0.5-0.6 | 0.555 | 87.5% | 24 |
| 0.6-0.7 | 0.650 | 80.0% | 30 |
| 0.7-0.8 | 0.748 | 94.3% | 35 |
| 0.8-0.9 | 0.841 | 100.0% | 27 |
| 0.9-1.0 | 0.954 | 100.0% | 49 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
