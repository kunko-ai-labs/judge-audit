# Audit report — llm

**n=120** · accuracy **96.7%** · ECE **0.0133**
· cost **$0.0424** · p50 **0.92s** · p99 **2.276s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-21T19:37:03+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `dd3912287cf5…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **0.8%** (1 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 0.99 | 6 |
| 25% | 96.7% | 0.99 | 30 |
| 45% | 98.2% | 0.99 | 54 |
| 65% | 98.7% | 0.95 | 78 |
| 85% | 97.1% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 7 |
| 0.9-1.0 | 0.966 | 96.5% | 113 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
