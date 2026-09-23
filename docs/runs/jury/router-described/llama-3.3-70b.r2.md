# Audit report — llm

**n=120** · accuracy **96.7%** [93.0, 99.2] · ECE **0.0133** [0.0087, 0.0508] · ECE (equal-mass) **0.0434** [0.0234, 0.0786] · Brier **0.0329** [0.0100, 0.0656]
· cost **$0.0424** · p50 **0.92s** · p99 **2.276s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · run 2026-09-21T19:37:03+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/llama-3.3-70b.r2.input.jsonl` · 120 rows · sha256 `dd3912287cf5…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/jury/router-described/llama-3.3-70b.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 85.6] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 57.5% | 98.6% | 0.99 | 69 |
| 61.7% | 98.7% | 0.98 | 74 |
| 74.2% | 98.9% | 0.95 | 89 |
| 77.5% | 98.9% | 0.92 | 93 |
| 94.2% | 96.5% | 0.90 | 113 |
| 100.0% | 96.7% | 0.80 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 7 |
| 0.9-1.0 | 0.966 | 96.5% | 113 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
