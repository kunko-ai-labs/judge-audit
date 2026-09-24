# Audit report — llm

**n=120** · accuracy **89.2%** [82.3, 94.6] · confidence known **120/120** · ECE **0.0507** [0.0158, 0.1118] · ECE (equal-mass) **0.0567** [0.0255, 0.1208] · Brier **0.0821** [0.0417, 0.1332]
· cost **$0.4408** · p50 **4.536s** · p99 **15.991s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T19:39:01+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `c0ed19f9c960…`_
_regenerated 2026-09-24T15:20:27+00:00 from `docs/runs/jury/router-described/deepseek-r1.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 34.1] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 8.3% | 90.0% | 1.00 | 10 |
| 15.8% | 94.7% | 0.99 | 19 |
| 25.8% | 96.8% | 0.98 | 31 |
| 85.8% | 95.2% | 0.95 | 103 |
| 91.7% | 93.6% | 0.90 | 110 |
| 97.5% | 91.5% | 0.80 | 117 |
| 100.0% | 89.2% | 0.60 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.600 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 0.0% | 2 |
| 0.8-0.9 | 0.807 | 57.1% | 7 |
| 0.9-1.0 | 0.959 | 93.6% | 110 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
