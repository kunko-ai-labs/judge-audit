# Audit report — llm

**n=120** · accuracy **55.0%** [41.1, 69.0] · confidence known **120/120** · ECE **0.3903** [0.2646, 0.5292] · ECE (equal-mass) **0.3994** [0.2783, 0.5367] · Brier **0.4032** [0.2800, 0.5247]
· cost **$0.0366** · p50 **0.913s** · p99 **2.713s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · run 2026-09-21T19:08:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `c786038b2a7d…`_
_regenerated 2026-09-24T15:20:27+00:00 from `docs/runs/jury/router-bare/llama-3.3-70b.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 33.0] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 29.2% | 94.3% | 0.99 | 35 |
| 49.2% | 67.8% | 0.98 | 59 |
| 50.0% | 66.7% | 0.96 | 60 |
| 62.5% | 57.3% | 0.95 | 75 |
| 75.0% | 47.8% | 0.92 | 90 |
| 82.5% | 49.5% | 0.85 | 99 |
| 98.3% | 54.2% | 0.80 | 118 |
| 100.0% | 55.0% | 0.70 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.700 | 100.0% | 2 |
| 0.8-0.9 | 0.813 | 72.0% | 25 |
| 0.9-1.0 | 0.967 | 49.5% | 93 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
