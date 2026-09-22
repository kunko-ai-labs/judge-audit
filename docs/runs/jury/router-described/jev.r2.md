> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **100.0%** · ECE **0.0436**
· cost **$0.0030** · p50 **0.589s** · p99 **0.778s**

_judge `jev` · model `jev-latest` · backend `typesafe` · recomputed 2026-09-21T19:06:02+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/jev.r2.input.jsonl` · 120 rows · sha256 `c00355b6ede7…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

## Can I automate this?

Zero observed errors through the most confident **100.0%** (120 decisions, confidence ≥ 0.63).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 1.00 | 30 |
| 45% | 100.0% | 1.00 | 54 |
| 65% | 100.0% | 0.98 | 78 |
| 85% | 100.0% | 0.90 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.630 | 100.0% | 1 |
| 0.7-0.8 | 0.752 | 100.0% | 8 |
| 0.8-0.9 | 0.866 | 100.0% | 7 |
| 0.9-1.0 | 0.981 | 100.0% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
