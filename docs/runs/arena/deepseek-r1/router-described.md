# Audit report — llm

**n=120** · accuracy **79.2%** [69.9, 86.9] · ECE **0.1478** [0.0744, 0.2369]
· cost **$0.4660** · p50 **4.089s** · p99 **28.476s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T15:21:30+00:00 · judge-audit 0.3.2_
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
| 8.3% | 0.0% | 1.00 | 10 |
| 17.5% | 52.4% | 0.99 | 21 |
| 77.5% | 79.6% | 0.95 | 93 |
| 89.2% | 81.3% | 0.90 | 107 |
| 90.0% | 81.5% | 0.85 | 108 |
| 95.8% | 80.0% | 0.80 | 115 |
| 100.0% | 79.2% | 0.00 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 100.0% | 3 |
| 0.8-0.9 | 0.806 | 62.5% | 8 |
| 0.9-1.0 | 0.952 | 81.3% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
