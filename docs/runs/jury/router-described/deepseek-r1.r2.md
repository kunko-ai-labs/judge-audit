# Audit report — llm

**n=120** · accuracy **89.2%** · ECE **0.0507**
· cost **$0.4408** · p50 **4.543s** · p99 **16.27s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T19:39:01+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `c0ed19f9c960…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **5.8%** (7 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 96.7% | 0.98 | 30 |
| 45% | 96.3% | 0.95 | 54 |
| 65% | 94.9% | 0.95 | 78 |
| 85% | 95.1% | 0.95 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.600 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 0.0% | 2 |
| 0.8-0.9 | 0.807 | 57.1% | 7 |
| 0.9-1.0 | 0.959 | 93.6% | 110 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
