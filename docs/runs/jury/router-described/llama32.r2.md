# Audit report — llm

**n=120** · accuracy **94.2%** [86.4, 100.0] · confidence known **119/120** · ECE **0.1361** [0.0848, 0.1999] · ECE (equal-mass) **0.1361** [0.0848, 0.1999] · Brier **0.0782** [0.0446, 0.1182] · NLL **0.2746** [0.1931, 0.3712]
· cost **$0.0000** · p50 **1.147s** · p99 **1.348s** · slowest **3.6s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-21T20:15:03+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-described/llama32.r2.input.jsonl` · 120 rows · sha256 `d6c7faf60dab…`_
_regenerated 2026-10-04T07:03:39+00:00 from `docs/runs/jury/router-described/llama32.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to certify 5%; has 119.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once: at this target, none (needs 124 texts with a confidence to certify 5%; has 61).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to certify 1%; has 119 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to certify 2%; has 119 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to certify 5%; has 119 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | 99.2% (119 of 120 decisions; 6 wrong, error bound 9.7%) | 0.5 | 0.0% automated (seeds 0–9: 0.0%–48.3%) |

_Valid only for: judge `llm:llama3.2:3b` · model `llama3.2:3b` · data `docs/runs/jury/router-described/llama32.r2.input.jsonl` · sha256 `7d5124bffb67…` · measured 2026-09-21T20:15:03+00:00. Review by 2026-12-20, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target was set before the run (`--target`, here 5%); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **52.1%** [39.8, 100.0] (62 decisions, confidence ≥ 0.9).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 21.0% | 100.0% | 0.95 | 25 |
| 52.1% | 100.0% | 0.90 | 62 |
| 83.2% | 96.0% | 0.80 | 99 |
| 100.0% | 95.0% | 0.50 | 119 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 90.0% | 20 |
| 0.8-0.9 | 0.800 | 89.2% | 37 |
| 0.9-1.0 | 0.923 | 100.0% | 62 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
