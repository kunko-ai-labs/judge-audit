> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **74.2%** · ECE **0.1811**
· cost **$0.0025** · p50 **0.633s** · p99 **0.818s**

_judge `jev` · model `jev-latest` · backend `typesafe` · recomputed 2026-09-21T09:59:33+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-bare/jev.r2.input.jsonl` · 120 rows · sha256 `1beedff1e08c…`_

## Can I automate this?

Zero observed errors through the most confident **2.5%** (3 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 83.3% | 1.00 | 6 |
| 25% | 90.0% | 1.00 | 30 |
| 45% | 94.4% | 1.00 | 54 |
| 65% | 87.2% | 0.97 | 78 |
| 85% | 79.4% | 0.78 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.510 | 33.3% | 3 |
| 0.6-0.7 | 0.666 | 50.0% | 8 |
| 0.7-0.8 | 0.753 | 40.0% | 10 |
| 0.8-0.9 | 0.839 | 50.0% | 12 |
| 0.9-1.0 | 0.992 | 85.1% | 87 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
