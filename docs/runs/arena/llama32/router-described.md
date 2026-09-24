# Audit report — llm

**n=120** · accuracy **59.2%** [45.5, 73.0] · confidence known **120/120** · ECE **0.4292** [0.2939, 0.5691] · ECE (equal-mass) **0.4292** [0.2939, 0.5691] · Brier **0.4188** [0.2817, 0.5553] · NLL **∞** (49 answers declared certain and wrong)
· cost **$0.0000** · p50 **0.877s** · p99 **1.031s** · slowest **1.048s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:06:30+00:00 · judge-audit 0.3.0_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_
_regenerated 2026-09-24T15:48:07+00:00 from `docs/runs/arena/llama32/router-described.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 95.8% | 57.4% | 1.00 | 115 |
| 100.0% | 59.2% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 100.0% | 5 |
| 0.9-1.0 | 1.000 | 57.4% | 115 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
