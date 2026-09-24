# Audit report — llm

**n=120** · accuracy **70.0%** [56.4, 82.1] · confidence known **120/120** · ECE **0.2311** [0.1249, 0.3553] · ECE (equal-mass) **0.2213** [0.1247, 0.3566] · Brier **0.2421** [0.1482, 0.3471] · NLL **0.7407** [0.4590, 1.0556]
· cost **$0.7151** · p50 **7.831s** · p99 **11.982s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-21T18:52:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/claude-sonnet-4.5.r2.input.jsonl` · 120 rows · sha256 `3b895b46200d…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/jury/router-bare/claude-sonnet-4.5.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **32.5%** [19.5, 47.1] (39 decisions, confidence ≥ 0.98).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 10.0% | 100.0% | 1.00 | 12 |
| 32.5% | 100.0% | 0.98 | 39 |
| 57.5% | 87.0% | 0.95 | 69 |
| 72.5% | 75.9% | 0.92 | 87 |
| 75.0% | 74.4% | 0.88 | 90 |
| 87.5% | 72.4% | 0.85 | 105 |
| 93.3% | 69.6% | 0.75 | 112 |
| 95.0% | 69.3% | 0.72 | 114 |
| 100.0% | 70.0% | 0.65 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.6-0.7 | 0.650 | 83.3% | 6 |
| 0.7-0.8 | 0.743 | 33.3% | 9 |
| 0.8-0.9 | 0.855 | 55.6% | 18 |
| 0.9-1.0 | 0.960 | 75.9% | 87 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
