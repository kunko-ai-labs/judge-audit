# Audit report — finetuned

**n=60** · accuracy **100.0%** · ECE **0.0000**
· cost **$0.0000** · p50 **0.023s** · p99 **0.183s**

_judge `finetuned:deberta-v3-base-ft-task-routing-run2` · model `deberta-v3-base-ft-task-routing-run2` · seed 2026 · recomputed 2026-09-22T08:17:41+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `c2811e2a8cde…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **100.0%** (60 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 3 |
| 25% | 100.0% | 1.00 | 15 |
| 45% | 100.0% | 1.00 | 27 |
| 65% | 100.0% | 1.00 | 39 |
| 85% | 100.0% | 1.00 | 51 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 1.000 | 100.0% | 60 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
