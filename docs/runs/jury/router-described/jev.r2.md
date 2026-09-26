> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **100.0%** [97.0, 100.0]† · confidence known **120/120** · ECE **0.0436** [0.0235, 0.0684] · ECE (equal-mass) **0.0436** [0.0235, 0.0684] · Brier **0.0076** [0.0026, 0.0145] · NLL **0.0481** [0.0253, 0.0775]
· cost **$0.0030** · p50 **0.589s** · p99 **0.771s** · slowest **0.949s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-21T19:06:02+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/jev.r2.input.jsonl` · 120 rows · sha256 `c00355b6ede7…`_
_regenerated 2026-09-24T15:48:07+00:00 from `docs/runs/jury/router-described/jev.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [97.0, 100.0]† (120 decisions, confidence ≥ 0.63).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 56.7% | 100.0% | 1.00 | 68 |
| 60.8% | 100.0% | 0.99 | 73 |
| 65.0% | 100.0% | 0.98 | 78 |
| 70.8% | 100.0% | 0.96 | 85 |
| 75.8% | 100.0% | 0.93 | 91 |
| 82.5% | 100.0% | 0.91 | 99 |
| 86.7% | 100.0% | 0.90 | 104 |
| 90.8% | 100.0% | 0.87 | 109 |
| 95.0% | 100.0% | 0.78 | 114 |
| 100.0% | 100.0% | 0.63 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.630 | 100.0% | 1 |
| 0.7-0.8 | 0.752 | 100.0% | 8 |
| 0.8-0.9 | 0.866 | 100.0% | 7 |
| 0.9-1.0 | 0.981 | 100.0% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
