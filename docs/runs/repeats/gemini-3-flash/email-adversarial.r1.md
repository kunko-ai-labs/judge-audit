# Audit report — llm

**n=200** · accuracy **97.0%** [94.4, 99.0] · confidence known **200/200** · ECE **0.0150** [0.0015, 0.0413] · ECE (equal-mass) **0.0430** [0.0244, 0.0692] · Brier **0.0300** [0.0103, 0.0558] · NLL **∞** (5 answers declared certain and wrong)
· cost **$0.0261** · p50 **2.012s** · p99 **122.919s** · slowest **248.148s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-26T07:44:41+00:00 · judge-audit 0.4.0_
_served as reported by the provider: `gemini-3-flash-preview` × 200 decisions_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 1.8]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 63.5% | 96.1% | 1.00 | 127 |
| 69.0% | 96.4% | 0.99 | 138 |
| 70.0% | 96.4% | 0.98 | 140 |
| 98.5% | 97.5% | 0.95 | 197 |
| 100.0% | 97.0% | 0.80 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 100.0% | 1 |
| 0.9-1.0 | 0.984 | 97.0% | 199 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
