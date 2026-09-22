# Audit report — llm

**n=120** · accuracy **61.7%** · ECE **0.3098**
· cost **$0.0000** · p50 **17.144s** · p99 **28.337s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · recomputed 2026-09-21T18:52:47+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/gemma4.r2.input.jsonl` · 120 rows · sha256 `6f5b14b5cbc2…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **0.0%** (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 50.0% | 0.98 | 6 |
| 25% | 70.0% | 0.95 | 30 |
| 45% | 66.7% | 0.95 | 54 |
| 65% | 61.5% | 0.90 | 78 |
| 85% | 61.8% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.733 | 66.7% | 3 |
| 0.8-0.9 | 0.848 | 50.0% | 10 |
| 0.9-1.0 | 0.939 | 62.6% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
