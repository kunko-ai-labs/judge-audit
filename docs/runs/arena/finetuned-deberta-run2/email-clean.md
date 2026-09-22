# Audit report — finetuned

**n=100** · accuracy **100.0%** · ECE **0.0169**
· cost **$0.0000** · p50 **0.017s** · p99 **0.669s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · recomputed 2026-09-22T08:16:56+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

## Can I automate this?

Zero observed errors through the most confident **100.0%** (100 decisions, confidence ≥ 0.9754).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 5 |
| 25% | 100.0% | 0.99 | 25 |
| 45% | 100.0% | 0.98 | 45 |
| 65% | 100.0% | 0.98 | 65 |
| 85% | 100.0% | 0.98 | 85 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.983 | 100.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
