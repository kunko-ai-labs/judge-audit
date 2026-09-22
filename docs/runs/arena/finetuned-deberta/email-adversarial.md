# Audit report — finetuned

**n=200** · accuracy **97.0%** · ECE **0.4961**
· cost **$0.0000** · p50 **0.017s** · p99 **0.155s**

_judge `finetuned:deberta-v3-base-ft-email-routing` · model `deberta-v3-base-ft-email-routing` · seed 2026 · recomputed 2026-09-22T03:13:44+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

## Can I automate this?

Zero observed errors through the most confident **97.0%** (194 decisions, confidence ≥ 0.1694).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.75 | 10 |
| 25% | 100.0% | 0.56 | 50 |
| 45% | 100.0% | 0.52 | 90 |
| 65% | 100.0% | 0.43 | 130 |
| 85% | 100.0% | 0.30 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.160 | 40.0% | 10 |
| 0.2-0.3 | 0.228 | 100.0% | 21 |
| 0.3-0.4 | 0.364 | 100.0% | 30 |
| 0.4-0.5 | 0.449 | 100.0% | 33 |
| 0.5-0.6 | 0.541 | 100.0% | 70 |
| 0.6-0.7 | 0.647 | 100.0% | 20 |
| 0.7-0.8 | 0.740 | 100.0% | 16 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
