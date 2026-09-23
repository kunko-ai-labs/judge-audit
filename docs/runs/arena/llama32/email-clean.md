# Audit report — llm

**n=200** · accuracy **90.0%** [77.8, 100.0] · ECE **0.0340** [0.0245, 0.1431]
· cost **$0.0000** · p50 **0.704s** · p99 **0.96s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:00:06+00:00 · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-09-23T13:30:30+00:00 from `docs/runs/arena/llama32/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 100.0] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 66.0% | 93.2% | 0.90 | 132 |
| 100.0% | 90.0% | 0.80 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 83.8% | 68 |
| 0.9-1.0 | 0.900 | 93.2% | 132 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
