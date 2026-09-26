> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=200** · accuracy **96.0%** [93.0, 98.5] · confidence known **200/200** · ECE **0.0426** [0.0354, 0.0702] · ECE (equal-mass) **0.0428** [0.0282, 0.0699] · Brier **0.0340** [0.0224, 0.0486] · NLL **0.1207** [0.0863, 0.1628]
· cost **$0.0032** · p50 **0.259s** · p99 **0.399s** · slowest **0.442s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-26T07:46:29+00:00 · judge-audit 0.4.0_
_served as reported by the provider: `jev-1.13.0` × 200 decisions_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **68.5%** [62.2, 95.5] (137 decisions, confidence ≥ 0.94).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 54.0% | 100.0% | 1.00 | 108 |
| 59.5% | 100.0% | 0.99 | 119 |
| 62.5% | 100.0% | 0.98 | 125 |
| 65.0% | 100.0% | 0.97 | 130 |
| 71.0% | 99.3% | 0.93 | 142 |
| 75.0% | 99.3% | 0.88 | 150 |
| 80.5% | 99.4% | 0.85 | 161 |
| 85.0% | 99.4% | 0.80 | 170 |
| 90.5% | 99.5% | 0.66 | 181 |
| 95.5% | 97.4% | 0.56 | 191 |
| 100.0% | 96.0% | 0.51 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.552 | 56.2% | 16 |
| 0.6-0.7 | 0.665 | 100.0% | 10 |
| 0.7-0.8 | 0.748 | 100.0% | 4 |
| 0.8-0.9 | 0.849 | 100.0% | 23 |
| 0.9-1.0 | 0.990 | 99.3% | 147 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
