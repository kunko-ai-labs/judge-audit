# Audit report — nli

**n=120** · accuracy **49.2%** [34.9, 62.8] · ECE **0.1952** [0.1376, 0.3548]
· cost **$0.0000** · p50 **0.105s** · p99 **1.024s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:53:38+00:00 · judge-audit 0.3.1_
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
| 5.8% | 0.0% | 0.85 | 7 |
| 10.8% | 0.0% | 0.82 | 13 |
| 15.8% | 0.0% | 0.79 | 19 |
| 21.7% | 11.5% | 0.76 | 26 |
| 25.8% | 16.1% | 0.72 | 31 |
| 30.0% | 22.2% | 0.70 | 36 |
| 36.7% | 27.3% | 0.62 | 44 |
| 41.7% | 36.0% | 0.61 | 50 |
| 45.0% | 38.9% | 0.60 | 54 |
| 50.0% | 40.0% | 0.59 | 60 |
| 55.0% | 40.9% | 0.59 | 66 |
| 60.0% | 45.8% | 0.58 | 72 |
| 65.8% | 45.6% | 0.57 | 79 |
| 70.0% | 46.4% | 0.57 | 84 |
| 75.0% | 46.7% | 0.57 | 90 |
| 81.7% | 49.0% | 0.54 | 98 |
| 86.7% | 49.0% | 0.54 | 104 |
| 90.8% | 48.6% | 0.51 | 109 |
| 95.8% | 51.3% | 0.51 | 115 |
| 100.0% | 49.2% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.554 | 55.6% | 63 |
| 0.6-0.7 | 0.624 | 76.2% | 21 |
| 0.7-0.8 | 0.745 | 42.1% | 19 |
| 0.8-0.9 | 0.839 | 0.0% | 17 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
