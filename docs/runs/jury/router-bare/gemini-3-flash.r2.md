# Audit report — llm

**n=120** · accuracy **66.7%** · ECE **0.3047**
· cost **$0.0242** · p50 **3.236s** · p99 **68.358s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · recomputed 2026-09-21T18:54:18+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/gemini-3-flash.r2.input.jsonl` · 120 rows · sha256 `bb3c4bd85d5e…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **5.0%** (6 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 90.0% | 1.00 | 30 |
| 45% | 92.6% | 1.00 | 54 |
| 65% | 80.8% | 0.95 | 78 |
| 85% | 68.6% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.750 | 100.0% | 4 |
| 0.8-0.9 | 0.845 | 50.0% | 10 |
| 0.9-1.0 | 0.973 | 67.0% | 106 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
