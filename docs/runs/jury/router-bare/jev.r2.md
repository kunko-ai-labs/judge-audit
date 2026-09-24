> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **72.5%** [58.8, 84.5] · confidence known **120/120** · ECE **0.2083** [0.1110, 0.3396] · ECE (equal-mass) **0.2083** [0.1057, 0.3393] · Brier **0.2149** [0.1186, 0.3279] · NLL **∞** (3 answers declared certain and wrong)
· cost **$0.0025** · p50 **0.609s** · p99 **2.884s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-21T18:52:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/jev.r2.input.jsonl` · 120 rows · sha256 `b2887a8c3706…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/jury/router-bare/jev.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 64.2] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 50.0% | 95.0% | 1.00 | 60 |
| 60.8% | 90.4% | 0.99 | 73 |
| 65.0% | 89.7% | 0.98 | 78 |
| 72.5% | 85.1% | 0.94 | 87 |
| 75.0% | 82.2% | 0.92 | 90 |
| 80.0% | 78.1% | 0.86 | 96 |
| 85.0% | 78.4% | 0.82 | 102 |
| 90.0% | 75.9% | 0.76 | 108 |
| 95.0% | 73.7% | 0.67 | 114 |
| 100.0% | 72.5% | 0.56 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.577 | 33.3% | 3 |
| 0.6-0.7 | 0.642 | 40.0% | 5 |
| 0.7-0.8 | 0.757 | 37.5% | 8 |
| 0.8-0.9 | 0.846 | 53.8% | 13 |
| 0.9-1.0 | 0.989 | 81.3% | 91 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
