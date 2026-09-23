# Audit report — llm

**n=120** · accuracy **59.2%** [45.5, 73.0] · ECE **0.4292** [0.2939, 0.5691]
· cost **$0.0000** · p50 **0.878s** · p99 **1.038s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:06:30+00:00 · judge-audit 0.3.0_
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
| 95.8% | 57.4% | 1.00 | 115 |
| 100.0% | 59.2% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 100.0% | 5 |
| 0.9-1.0 | 1.000 | 57.4% | 115 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
