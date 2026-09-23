# Audit report — llm

**n=120** · accuracy **59.2%** [46.2, 71.2] · ECE **0.3446** [0.2223, 0.4761] · ECE (equal-mass) **0.3446** [0.2388, 0.4816] · Brier **0.3778** [0.2686, 0.4940]
· cost **$0.0000** · p50 **13.268s** · p99 **32.085s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-20T18:26:26+00:00 · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/arena/gemma4/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 25.0% | 0.0% | 1.00 | 30 |
| 62.5% | 56.0% | 0.95 | 75 |
| 92.5% | 60.4% | 0.90 | 111 |
| 100.0% | 59.2% | 0.80 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 44.4% | 9 |
| 0.9-1.0 | 0.947 | 60.4% | 111 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
