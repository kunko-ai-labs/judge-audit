# Audit report — llm

**n=120** · accuracy **95.0%** [90.3, 98.5] · confidence known **120/120** · ECE **0.0484** [0.0313, 0.0893] · ECE (equal-mass) **0.0467** [0.0308, 0.0914] · Brier **0.0371** [0.0140, 0.0672] · NLL **0.1331** [0.0734, 0.2119]
· cost **$0.7224** · p50 **7.706s** · p99 **10.196s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-21T19:21:35+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/claude-sonnet-4.5.r2.input.jsonl` · 120 rows · sha256 `159c8bc820fe…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/jury/router-described/claude-sonnet-4.5.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **84.2%** [75.2, 95.8] (101 decisions, confidence ≥ 0.88).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 21.7% | 100.0% | 1.00 | 26 |
| 39.2% | 100.0% | 0.98 | 47 |
| 71.7% | 100.0% | 0.95 | 86 |
| 81.7% | 100.0% | 0.92 | 98 |
| 95.8% | 97.4% | 0.85 | 115 |
| 100.0% | 95.0% | 0.75 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.750 | 40.0% | 5 |
| 0.8-0.9 | 0.854 | 81.2% | 16 |
| 0.9-1.0 | 0.966 | 100.0% | 99 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
