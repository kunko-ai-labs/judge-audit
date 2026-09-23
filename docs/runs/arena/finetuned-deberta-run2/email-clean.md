# Audit report — finetuned

**n=100** · accuracy **100.0%** [96.4, 100.0]† · ECE **0.0169** [0.0160, 0.0177]
· cost **$0.0000** · p50 **0.017s** · p99 **0.669s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:16:56+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_
_regenerated 2026-09-23T13:30:30+00:00 from `docs/runs/arena/finetuned-deberta-run2/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=100 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

Zero observed errors through the most confident **100.0%** [96.4, 100.0]† (100 decisions, confidence ≥ 0.9754).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.99 | 5 |
| 10.0% | 100.0% | 0.99 | 10 |
| 15.0% | 100.0% | 0.99 | 15 |
| 20.0% | 100.0% | 0.99 | 20 |
| 25.0% | 100.0% | 0.99 | 25 |
| 30.0% | 100.0% | 0.98 | 30 |
| 40.0% | 100.0% | 0.98 | 40 |
| 45.0% | 100.0% | 0.98 | 45 |
| 50.0% | 100.0% | 0.98 | 50 |
| 55.0% | 100.0% | 0.98 | 55 |
| 60.0% | 100.0% | 0.98 | 60 |
| 65.0% | 100.0% | 0.98 | 65 |
| 70.0% | 100.0% | 0.98 | 70 |
| 75.0% | 100.0% | 0.98 | 75 |
| 80.0% | 100.0% | 0.98 | 80 |
| 86.0% | 100.0% | 0.98 | 86 |
| 90.0% | 100.0% | 0.98 | 90 |
| 95.0% | 100.0% | 0.98 | 95 |
| 100.0% | 100.0% | 0.98 | 100 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.983 | 100.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
