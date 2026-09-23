# Audit report — llm

**n=120** · accuracy **61.7%** [48.4, 74.3] · ECE **0.3098** [0.1924, 0.4460] · ECE (equal-mass) **0.3152** [0.1977, 0.4414] · Brier **0.3299** [0.2222, 0.4410]
· cost **$0.0000** · p50 **17.144s** · p99 **28.337s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-21T18:52:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/gemma4.r2.input.jsonl` · 120 rows · sha256 `6f5b14b5cbc2…`_
_regenerated 2026-09-23T13:41:20+00:00 from `docs/runs/jury/router-bare/gemma4.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 13.3] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 17.5% | 85.7% | 0.98 | 21 |
| 58.3% | 67.1% | 0.95 | 70 |
| 89.2% | 62.6% | 0.90 | 107 |
| 90.0% | 62.0% | 0.88 | 108 |
| 96.7% | 61.2% | 0.85 | 116 |
| 100.0% | 61.7% | 0.70 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.733 | 66.7% | 3 |
| 0.8-0.9 | 0.848 | 50.0% | 10 |
| 0.9-1.0 | 0.939 | 62.6% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
