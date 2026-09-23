# Audit report — llm

**n=120** · accuracy **95.0%** [90.3, 98.5] · ECE **0.0322** [0.0127, 0.0821]
· cost **$0.3998** · p50 **4.56s** · p99 **6.916s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-20T18:53:06+00:00 · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 12.5% | 73.3% | 1.00 | 15 |
| 15.0% | 77.8% | 0.99 | 18 |
| 87.5% | 94.3% | 0.95 | 105 |
| 100.0% | 95.0% | 0.85 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.850 | 100.0% | 15 |
| 0.9-1.0 | 0.958 | 94.3% | 105 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
