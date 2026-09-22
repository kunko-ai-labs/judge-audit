> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **72.5%** · ECE **0.2083**
· cost **$0.0025** · p50 **0.61s** · p99 **2.946s**

_judge `jev` · model `jev-latest` · backend `typesafe` · recomputed 2026-09-21T18:52:47+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/jev.r2.input.jsonl` · 120 rows · sha256 `b2887a8c3706…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **2.5%** (3 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 1.00 | 6 |
| 25% | 90.0% | 1.00 | 30 |
| 45% | 94.4% | 1.00 | 54 |
| 65% | 89.7% | 0.98 | 78 |
| 85% | 78.4% | 0.82 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.577 | 33.3% | 3 |
| 0.6-0.7 | 0.642 | 40.0% | 5 |
| 0.7-0.8 | 0.757 | 37.5% | 8 |
| 0.8-0.9 | 0.846 | 53.8% | 13 |
| 0.9-1.0 | 0.989 | 81.3% | 91 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
