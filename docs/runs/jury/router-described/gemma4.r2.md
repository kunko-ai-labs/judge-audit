# Audit report — llm

**n=120** · accuracy **93.3%** · ECE **0.0266**
· cost **$0.0000** · p50 **20.327s** · p99 **53.809s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-21T19:29:07+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/gemma4.r2.input.jsonl` · 120 rows · sha256 `ab827da374f3…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **3.3%** (4 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 0.99 | 6 |
| 25% | 96.7% | 0.98 | 30 |
| 45% | 98.2% | 0.95 | 54 |
| 65% | 98.7% | 0.95 | 78 |
| 85% | 99.0% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.825 | 100.0% | 2 |
| 0.9-1.0 | 0.956 | 93.2% | 118 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
