# Audit report — llm

**n=120** · accuracy **55.0%** · ECE **0.3787**
· cost **$0.4499** · p50 **3.873s** · p99 **15.999s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · recomputed 2026-09-21T19:10:50+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `7d2bb8dc595f…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 33.3% | 1.00 | 6 |
| 25% | 73.3% | 0.96 | 30 |
| 45% | 61.1% | 0.95 | 54 |
| 65% | 56.4% | 0.95 | 78 |
| 85% | 55.9% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.7-0.8 | 0.717 | 50.0% | 6 |
| 0.8-0.9 | 0.817 | 66.7% | 9 |
| 0.9-1.0 | 0.960 | 54.8% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
