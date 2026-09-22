# Audit report — llm

**n=120** · accuracy **66.7%** · ECE **0.2816**
· cost **$0.0000** · p50 **1.014s** · p99 **1.326s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · recomputed 2026-09-21T19:27:02+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/llama32.r2.input.jsonl` · 120 rows · sha256 `d201d92e237e…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **1.7%** (2 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 50.0% | 0.95 | 6 |
| 25% | 66.7% | 0.90 | 30 |
| 45% | 59.3% | 0.80 | 54 |
| 65% | 62.8% | 0.80 | 78 |
| 85% | 61.8% | 0.50 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 95.2% | 21 |
| 0.7-0.8 | 0.750 | 100.0% | 1 |
| 0.8-0.9 | 0.802 | 53.2% | 62 |
| 0.9-1.0 | 0.925 | 72.2% | 36 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
