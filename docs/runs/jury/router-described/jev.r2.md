> **REAL VENDOR AUDIT** — TypeSafe Jev via Vercel AI Gateway (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **100.0%** · ECE **0.0462**
· cost **$0.0029** · p50 **0.637s** · p99 **0.819s**

_judge `jev` · model `jev-latest` · backend `typesafe` · recomputed 2026-09-21T10:00:51+00:00 (original run time not recorded) · judge-audit 0.3.2_
_dataset `/Users/altostratus_1/Documents/Vane/kunko/judge-audit/docs/runs/jury/router-described/jev.r2.input.jsonl` · 120 rows · sha256 `3bd5574c93f1…`_

## Can I automate this?

Zero observed errors through the most confident **100.0%** (120 decisions, confidence ≥ 0.64).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5% | 100.0% | 1.00 | 6 |
| 25% | 100.0% | 1.00 | 30 |
| 45% | 100.0% | 1.00 | 54 |
| 65% | 100.0% | 0.98 | 78 |
| 85% | 100.0% | 0.88 | 102 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.640 | 100.0% | 1 |
| 0.7-0.8 | 0.739 | 100.0% | 7 |
| 0.8-0.9 | 0.865 | 100.0% | 16 |
| 0.9-1.0 | 0.988 | 100.0% | 96 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
