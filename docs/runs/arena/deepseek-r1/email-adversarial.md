# Audit report — llm

**n=200** · accuracy **80.5%** [74.8, 85.6] · confidence known **200/200** · ECE **0.1265** [0.0764, 0.1839] · ECE (equal-mass) **0.1340** [0.0847, 0.1929] · Brier **0.1693** [0.1219, 0.2189]
· cost **$0.5890** · p50 **3.097s** · p99 **22.739s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T14:55:24+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-09-24T15:20:27+00:00 from `docs/runs/arena/deepseek-r1/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 1.8]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 10.0% | 20.0% | 1.00 | 20 |
| 80.5% | 81.4% | 0.95 | 161 |
| 94.0% | 83.0% | 0.90 | 188 |
| 97.0% | 82.5% | 0.80 | 194 |
| 100.0% | 80.5% | 0.10 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.100 | 0.0% | 1 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.7-0.8 | 0.700 | 25.0% | 4 |
| 0.8-0.9 | 0.800 | 66.7% | 6 |
| 0.9-1.0 | 0.949 | 83.0% | 188 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
