# Audit report — llm

**n=120** · accuracy **93.3%** [87.4, 97.6] · confidence known **120/120** · ECE **0.0266** [0.0035, 0.0827] · ECE (equal-mass) **0.0836** [0.0461, 0.1412] · Brier **0.0581** [0.0222, 0.1085]
· cost **$0.0000** · p50 **20.298s** · p99 **53.378s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-21T19:29:07+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/gemma4.r2.input.jsonl` · 120 rows · sha256 `ab827da374f3…`_
_regenerated 2026-09-24T15:20:27+00:00 from `docs/runs/jury/router-described/gemma4.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 92.7] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 11.7% | 92.9% | 0.99 | 14 |
| 33.3% | 97.5% | 0.98 | 40 |
| 87.5% | 99.1% | 0.95 | 105 |
| 98.3% | 93.2% | 0.90 | 118 |
| 100.0% | 93.3% | 0.80 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.825 | 100.0% | 2 |
| 0.9-1.0 | 0.956 | 93.2% | 118 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
