# Audit report — llm

**n=120** · accuracy **94.2%** [86.4, 100.0] · ECE **0.1349** [0.0839, 0.1974]
· cost **$0.0000** · p50 **1.149s** · p99 **1.352s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-21T20:15:03+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/llama32.r2.input.jsonl` · 120 rows · sha256 `d6c7faf60dab…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **51.7%** [39.5, 100.0] (62 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 20.8% | 100.0% | 0.95 | 25 |
| 51.7% | 100.0% | 0.90 | 62 |
| 82.5% | 96.0% | 0.80 | 99 |
| 99.2% | 95.0% | 0.50 | 119 |
| 100.0% | 94.2% | 0.00 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 1 |
| 0.5-0.6 | 0.500 | 90.0% | 20 |
| 0.8-0.9 | 0.800 | 89.2% | 37 |
| 0.9-1.0 | 0.923 | 100.0% | 62 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
