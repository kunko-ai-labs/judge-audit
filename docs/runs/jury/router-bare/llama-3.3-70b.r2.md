# Audit report — llm

**n=120** · accuracy **55.0%** · ECE **0.3903**
· cost **$0.0366** · p50 **0.914s** · p99 **2.779s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · recomputed 2026-09-21T19:08:47+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `c786038b2a7d…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 66.7% | 0.99 | 6 |
| 25% | 93.3% | 0.99 | 30 |
| 45% | 68.5% | 0.98 | 54 |
| 65% | 55.1% | 0.92 | 78 |
| 85% | 51.0% | 0.80 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.700 | 100.0% | 2 |
| 0.8-0.9 | 0.813 | 72.0% | 25 |
| 0.9-1.0 | 0.967 | 49.5% | 93 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
