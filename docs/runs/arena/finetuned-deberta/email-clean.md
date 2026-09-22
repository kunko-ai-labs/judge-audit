# Audit report — finetuned

**n=100** · accuracy **100.0%** · ECE **0.4581**
· cost **$0.0000** · p50 **0.016s** · p99 **0.978s**

_judge `finetuned:deberta-v3-base-ft-email-routing` · model `deberta-v3-base-ft-email-routing` · seed 2026 · recomputed 2026-09-22T03:13:37+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

## Can I automate this?

Zero observed errors through the most confident **100.0%** (100 decisions, confidence ≥ 0.1885).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.75 | 5 |
| 25% | 100.0% | 0.66 | 25 |
| 45% | 100.0% | 0.57 | 45 |
| 65% | 100.0% | 0.51 | 65 |
| 85% | 100.0% | 0.40 | 85 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.193 | 100.0% | 3 |
| 0.2-0.3 | 0.227 | 100.0% | 8 |
| 0.3-0.4 | 0.384 | 100.0% | 5 |
| 0.4-0.5 | 0.459 | 100.0% | 16 |
| 0.5-0.6 | 0.547 | 100.0% | 32 |
| 0.6-0.7 | 0.643 | 100.0% | 16 |
| 0.7-0.8 | 0.737 | 100.0% | 20 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
