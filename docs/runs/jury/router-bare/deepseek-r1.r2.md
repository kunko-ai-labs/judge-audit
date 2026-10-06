# Audit report — llm

**n=120** · accuracy **55.0%** [41.7, 68.2] · confidence known **119/120** · ECE **0.3819** [0.2531, 0.5275] · ECE (equal-mass) **0.3861** [0.2557, 0.5286] · Brier **0.3947** [0.2788, 0.5231] · NLL **∞** (6 answers declared certain and wrong)
· cost **$0.4499** · p50 **3.83s** · p99 **15.984s** · slowest **32.826s**

_judge `llm:deepseek-r1` · model `deepseek-r1` · run 2026-09-21T19:10:50+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/deepseek-r1.r2.input.jsonl` · 120 rows · sha256 `7d2bb8dc595f…`_
_regenerated 2026-10-06T21:13:06+00:00 from `docs/runs/jury/router-bare/deepseek-r1.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 119.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 61).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 119 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 119 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 119 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 101 decisions with 45 errors (bound 53.2% > 10%) | — | — |

_Valid only for: judge `llm:deepseek-r1` · model `deepseek-r1` · data `docs/runs/jury/router-bare/deepseek-r1.r2.input.jsonl` · sha256 `d463c86a5496…` · measured 2026-09-21T19:10:50+00:00. Review by 2026-12-20, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 8.4% | 40.0% | 1.00 | 10 |
| 16.0% | 68.4% | 0.99 | 19 |
| 22.7% | 77.8% | 0.98 | 27 |
| 24.4% | 75.9% | 0.97 | 29 |
| 84.9% | 55.5% | 0.95 | 101 |
| 89.9% | 55.1% | 0.85 | 107 |
| 95.0% | 55.8% | 0.80 | 113 |
| 100.0% | 55.5% | 0.70 | 119 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.717 | 50.0% | 6 |
| 0.8-0.9 | 0.817 | 66.7% | 9 |
| 0.9-1.0 | 0.960 | 54.8% | 104 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
