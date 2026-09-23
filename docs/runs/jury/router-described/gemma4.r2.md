# Audit report — llm

**n=120** · accuracy **93.3%** [87.4, 97.6] · ECE **0.0266** [0.0035, 0.0827]
· cost **$0.0000** · p50 **20.327s** · p99 **53.809s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-21T19:29:07+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/gemma4.r2.input.jsonl` · 120 rows · sha256 `ab827da374f3…`_
_regenerated 2026-09-23T13:30:30+00:00 from `docs/runs/jury/router-described/gemma4.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **0.0%** [0.0, 92.7] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 11.7% | 92.9% | 0.99 | 14 |
| 33.3% | 97.5% | 0.98 | 40 |
| 87.5% | 99.1% | 0.95 | 105 |
| 98.3% | 93.2% | 0.90 | 118 |
| 100.0% | 93.3% | 0.80 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.825 | 100.0% | 2 |
| 0.9-1.0 | 0.956 | 93.2% | 118 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
