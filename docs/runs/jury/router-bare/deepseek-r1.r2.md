# Audit report — llm

**n=120** · accuracy **55.0%** [41.7, 68.2] · ECE **0.3787** [0.2557, 0.5132]
· cost **$0.4499** · p50 **3.873s** · p99 **15.999s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T19:10:50+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `7d2bb8dc595f…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 8.3% | 40.0% | 1.00 | 10 |
| 15.8% | 68.4% | 0.99 | 19 |
| 22.5% | 77.8% | 0.98 | 27 |
| 25.0% | 73.3% | 0.96 | 30 |
| 84.2% | 55.5% | 0.95 | 101 |
| 86.7% | 54.8% | 0.90 | 104 |
| 94.2% | 55.8% | 0.80 | 113 |
| 95.8% | 55.6% | 0.75 | 115 |
| 100.0% | 55.0% | 0.00 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.7-0.8 | 0.717 | 50.0% | 6 |
| 0.8-0.9 | 0.817 | 66.7% | 9 |
| 0.9-1.0 | 0.960 | 54.8% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
