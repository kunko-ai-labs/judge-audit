# Audit report — llm

**n=120** · accuracy **66.7%** [52.2, 79.7] · confidence known **120/120** · ECE **0.3047** [0.1870, 0.4372] · ECE (equal-mass) **0.2887** [0.1740, 0.4314] · Brier **0.2924** [0.1824, 0.4137]
· cost **$0.0242** · p50 **3.236s** · p99 **68.358s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T18:54:18+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/gemini-3-flash.r2.input.jsonl` · 120 rows · sha256 `bb3c4bd85d5e…`_
_regenerated 2026-09-23T18:32:04+00:00 from `docs/runs/jury/router-bare/gemini-3-flash.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 54.5] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 46.7% | 92.9% | 1.00 | 56 |
| 80.0% | 72.9% | 0.95 | 96 |
| 88.3% | 67.0% | 0.90 | 106 |
| 95.8% | 66.1% | 0.85 | 115 |
| 100.0% | 66.7% | 0.75 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.750 | 100.0% | 4 |
| 0.8-0.9 | 0.845 | 50.0% | 10 |
| 0.9-1.0 | 0.973 | 67.0% | 106 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
