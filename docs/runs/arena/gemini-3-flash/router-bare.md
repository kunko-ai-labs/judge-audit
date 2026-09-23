# Audit report — llm

**n=120** · accuracy **66.7%** [53.5, 79.5] · ECE **0.3154** [0.1892, 0.4413]
· cost **$0.0161** · p50 **2.423s** · p99 **62.701s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T10:36:15+00:00 · judge-audit 0.3.2_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-09-23T13:30:30+00:00 from `docs/runs/arena/gemini-3-flash/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 75.0% | 75.6% | 1.00 | 90 |
| 90.8% | 70.6% | 0.95 | 109 |
| 99.2% | 67.2% | 0.90 | 119 |
| 100.0% | 66.7% | 0.80 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 0.0% | 1 |
| 0.9-1.0 | 0.984 | 67.2% | 119 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
