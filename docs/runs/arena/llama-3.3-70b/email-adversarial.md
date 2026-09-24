# Audit report — llm

**n=200** · accuracy **90.5%** [86.1, 94.5] · confidence known **200/200** · ECE **0.0155** [0.0052, 0.0598] · ECE (equal-mass) **0.1325** [0.1028, 0.1741] · Brier **0.0850** [0.0510, 0.1213] · NLL **∞** (12 answers declared certain and wrong)
· cost **$0.0411** · p50 **0.811s** · p99 **1.589s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · run 2026-09-20T19:04:55+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-09-24T15:30:23+00:00 from `docs/runs/arena/llama-3.3-70b/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 1.8]† (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 6.0% | 0.0% | 1.00 | 12 |
| 11.5% | 47.8% | 0.99 | 23 |
| 91.5% | 92.3% | 0.90 | 183 |
| 98.5% | 91.9% | 0.80 | 197 |
| 100.0% | 90.5% | 0.00 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 2 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.8-0.9 | 0.800 | 85.7% | 14 |
| 0.9-1.0 | 0.912 | 92.3% | 183 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
