# Audit report — llm

**n=120** · accuracy **94.2%** [86.4, 100.0] · confidence known **119/120** · ECE **0.1361** [0.0848, 0.1999] · ECE (equal-mass) **0.1361** [0.0848, 0.1999] · Brier **0.0782** [0.0446, 0.1182] · NLL **0.2746** [0.1931, 0.3712]
· cost **$0.0000** · p50 **1.147s** · p99 **1.348s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-21T20:15:03+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/llama32.r2.input.jsonl` · 120 rows · sha256 `d6c7faf60dab…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/jury/router-described/llama32.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **52.1%** [39.8, 100.0] (62 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 21.0% | 100.0% | 0.95 | 25 |
| 52.1% | 100.0% | 0.90 | 62 |
| 83.2% | 96.0% | 0.80 | 99 |
| 100.0% | 95.0% | 0.50 | 119 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 90.0% | 20 |
| 0.8-0.9 | 0.800 | 89.2% | 37 |
| 0.9-1.0 | 0.923 | 100.0% | 62 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
