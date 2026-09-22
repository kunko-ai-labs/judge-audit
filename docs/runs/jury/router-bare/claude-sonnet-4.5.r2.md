# Audit report — llm

**n=120** · accuracy **70.0%** · ECE **0.2311**
· cost **$0.7151** · p50 **7.851s** · p99 **11.985s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · recomputed 2026-09-21T18:52:47+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/claude-sonnet-4.5.r2.input.jsonl` · 120 rows · sha256 `3b895b46200d…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **33.3%** (40 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 0.98 | 30 |
| 45% | 92.6% | 0.95 | 54 |
| 65% | 79.5% | 0.92 | 78 |
| 85% | 72.5% | 0.85 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.650 | 83.3% | 6 |
| 0.7-0.8 | 0.743 | 33.3% | 9 |
| 0.8-0.9 | 0.855 | 55.6% | 18 |
| 0.9-1.0 | 0.960 | 75.9% | 87 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
