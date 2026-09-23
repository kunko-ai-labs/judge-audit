# Audit report — llm

**n=120** · accuracy **99.2%** [97.2, 100.0] · ECE **0.0236** [0.0051, 0.0391]
· cost **$0.0254** · p50 **3.139s** · p99 **27.575s**

_judge `llm:gemini-3-flash-preview` · model `gemini-3-flash-preview` · run 2026-09-21T19:07:14+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/gemini-3-flash.r2.input.jsonl` · 120 rows · sha256 `59fd7ce735e5…`_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

Zero observed errors through the most confident **89.2%** [81.7, 100.0] (107 decisions, confidence ≥ 0.95).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 46.7% | 100.0% | 1.00 | 56 |
| 50.0% | 100.0% | 0.98 | 60 |
| 89.2% | 100.0% | 0.95 | 107 |
| 98.3% | 99.2% | 0.90 | 118 |
| 100.0% | 99.2% | 0.85 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.850 | 100.0% | 2 |
| 0.9-1.0 | 0.970 | 99.2% | 118 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._
