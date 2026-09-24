# Audit report — llm

**n=120** · accuracy **66.7%** [52.5, 80.3] · confidence known **120/120** · ECE **0.2816** [0.1483, 0.4128] · ECE (equal-mass) **0.2816** [0.1570, 0.4128] · Brier **0.2856** [0.1948, 0.3760] · NLL **0.8253** [0.5880, 1.0692]
· cost **$0.0000** · p50 **1.014s** · p99 **1.324s** · slowest **3.615s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-21T19:27:02+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/llama32.r2.input.jsonl` · 120 rows · sha256 `d201d92e237e…`_
_regenerated 2026-09-24T15:48:07+00:00 from `docs/runs/jury/router-bare/llama32.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.8%** [0.0, 3.1] (1 decisions, confidence ≥ 0.99).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 14.2% | 64.7% | 0.95 | 17 |
| 30.0% | 72.2% | 0.90 | 36 |
| 81.7% | 60.2% | 0.80 | 98 |
| 100.0% | 66.7% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 95.2% | 21 |
| 0.7-0.8 | 0.750 | 100.0% | 1 |
| 0.8-0.9 | 0.802 | 53.2% | 62 |
| 0.9-1.0 | 0.925 | 72.2% | 36 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
