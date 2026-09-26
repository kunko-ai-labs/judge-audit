> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=200** · accuracy **97.0%** [94.4, 99.0] · confidence known **200/200** · ECE **0.0530** [0.0344, 0.0790] · ECE (equal-mass) **0.0530** [0.0310, 0.0796] · Brier **0.0349** [0.0233, 0.0488] · NLL **0.1220** [0.0882, 0.1622]
· cost **$0.0032** · p50 **0.261s** · p99 **0.377s** · slowest **0.575s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-26T07:45:35+00:00 · judge-audit 0.4.0_
_served as reported by the provider: `jev-1.13.0` × 200 decisions_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **70.5%** [64.5, 94.4] (141 decisions, confidence ≥ 0.92).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 53.5% | 100.0% | 1.00 | 107 |
| 59.0% | 100.0% | 0.99 | 118 |
| 63.5% | 100.0% | 0.98 | 127 |
| 66.0% | 100.0% | 0.97 | 132 |
| 70.0% | 100.0% | 0.93 | 140 |
| 75.0% | 99.3% | 0.88 | 150 |
| 81.0% | 99.4% | 0.84 | 162 |
| 85.0% | 99.4% | 0.77 | 170 |
| 90.0% | 99.4% | 0.66 | 180 |
| 95.0% | 97.9% | 0.60 | 190 |
| 100.0% | 97.0% | 0.50 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.530 | 80.0% | 10 |
| 0.6-0.7 | 0.642 | 80.0% | 15 |
| 0.7-0.8 | 0.740 | 100.0% | 7 |
| 0.8-0.9 | 0.849 | 100.0% | 21 |
| 0.9-1.0 | 0.990 | 99.3% | 147 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
