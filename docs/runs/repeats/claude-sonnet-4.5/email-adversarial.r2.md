# Audit report — llm

**n=200** · accuracy **96.5%** [93.9, 99.0] · confidence known **200/200** · ECE **0.0144** [0.0044, 0.0383] · ECE (equal-mass) **0.0294** [0.0115, 0.0549] · Brier **0.0311** [0.0118, 0.0535] · NLL **∞** (2 answers declared certain and wrong)
· cost **$0.4606** · p50 **3.488s** · p99 **6.295s** · slowest **10.174s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-26T07:49:14+00:00 · judge-audit 0.4.0_
_served as reported by the provider: no version reported · 200 decisions without a version_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 33.5] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 14.5% | 93.1% | 1.00 | 29 |
| 30.5% | 96.7% | 0.99 | 61 |
| 92.5% | 97.3% | 0.95 | 185 |
| 99.5% | 97.0% | 0.85 | 199 |
| 100.0% | 96.5% | 0.50 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.8-0.9 | 0.850 | 90.9% | 11 |
| 0.9-1.0 | 0.964 | 97.3% | 188 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
