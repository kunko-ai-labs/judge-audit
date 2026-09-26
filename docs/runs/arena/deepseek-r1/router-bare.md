# Audit report — llm

**n=120** · accuracy **55.8%** [42.5, 68.2] · confidence known **119/120** · ECE **0.3766** [0.2645, 0.5004] · ECE (equal-mass) **0.3613** [0.2501, 0.4881] · Brier **0.3830** [0.2746, 0.4955] · NLL **∞** (18 answers declared certain and wrong)
· cost **$0.4379** · p50 **4.24s** · p99 **20.586s** · slowest **21.882s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T15:10:27+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-09-24T15:48:07+00:00 from `docs/runs/arena/deepseek-r1/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 15.1% | 0.0% | 1.00 | 18 |
| 22.7% | 33.3% | 0.99 | 27 |
| 63.0% | 54.7% | 0.95 | 75 |
| 76.5% | 51.6% | 0.90 | 91 |
| 79.8% | 52.6% | 0.85 | 95 |
| 84.9% | 53.5% | 0.80 | 101 |
| 95.8% | 57.0% | 0.70 | 114 |
| 100.0% | 56.3% | 0.20 | 119 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.3-0.4 | 0.300 | 0.0% | 1 |
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.6-0.7 | 0.600 | 100.0% | 2 |
| 0.7-0.8 | 0.700 | 84.6% | 13 |
| 0.8-0.9 | 0.820 | 70.0% | 10 |
| 0.9-1.0 | 0.955 | 51.6% | 91 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
