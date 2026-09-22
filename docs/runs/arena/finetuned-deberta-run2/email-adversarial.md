# Audit report — finetuned

**n=200** · accuracy **99.0%** · ECE **0.0480**
· cost **$0.0000** · p50 **0.018s** · p99 **0.039s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · recomputed 2026-09-22T08:17:03+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

## Can I automate this?

Zero observed errors through the most confident **96.0%** (192 decisions, confidence ≥ 0.7097).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 0.99 | 10 |
| 25% | 100.0% | 0.98 | 50 |
| 45% | 100.0% | 0.98 | 90 |
| 65% | 100.0% | 0.97 | 130 |
| 85% | 100.0% | 0.96 | 170 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.275 | 100.0% | 1 |
| 0.3-0.4 | 0.399 | 100.0% | 2 |
| 0.4-0.5 | 0.444 | 100.0% | 2 |
| 0.5-0.6 | 0.569 | 50.0% | 2 |
| 0.6-0.7 | 0.630 | 0.0% | 1 |
| 0.7-0.8 | 0.734 | 100.0% | 3 |
| 0.8-0.9 | 0.851 | 100.0% | 3 |
| 0.9-1.0 | 0.976 | 100.0% | 186 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
