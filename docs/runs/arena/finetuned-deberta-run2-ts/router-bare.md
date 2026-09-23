# Audit report — finetuned

**n=60** · accuracy **100.0%** [94.0, 100.0]† · ECE **0.0000** ‡
· cost **$0.0000** · p50 **0.026s** · p99 **0.187s**

_judge `finetuned:deberta-v3-base-ft-task-routing-run2` · model `deberta-v3-base-ft-task-routing-run2` · seed 2026 · run 2026-09-22T08:17:35+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `e2efb9e1baec…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=60 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [94.0, 100.0]† (60 decisions, confidence ≥ 1.0).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 50.0% | 100.0% | 1.00 | 30 |
| 66.7% | 100.0% | 1.00 | 40 |
| 70.0% | 100.0% | 1.00 | 42 |
| 75.0% | 100.0% | 1.00 | 45 |
| 80.0% | 100.0% | 1.00 | 48 |
| 86.7% | 100.0% | 1.00 | 52 |
| 90.0% | 100.0% | 1.00 | 54 |
| 96.7% | 100.0% | 1.00 | 58 |
| 100.0% | 100.0% | 1.00 | 60 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 1.000 | 100.0% | 60 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
