# Audit report — nli

**n=120** · accuracy **49.2%** [34.9, 62.8] · confidence known **120/120** · ECE **0.1952** [0.1376, 0.3548] · ECE (equal-mass) **0.2131** [0.2425, 0.4501]◊ · Brier **0.3238** [0.2755, 0.3803] · NLL **0.8796** [0.7616, 1.0161]
· cost **$0.0000** · p50 **0.105s** · p99 **0.897s** · slowest **1.348s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:53:38+00:00 · judge-audit 0.3.1_
_dataset `examples/task-routing/labels-described.jsonl` · 120 rows · sha256 `4571c9661a0c…`_
_regenerated 2026-10-04T19:08:48+00:00 from `docs/runs/arena/deberta-nli/router-described.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**◊** the point estimate lies outside its own percentile-bootstrap interval: on this sample the resampled statistic is biased away from it (a binned calibration error tends to rise when texts are resampled), so read the interval as the spread of the number, not as a range around it._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 120.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 61).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 120 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 120 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 120 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 62 decisions with 38 errors (bound 71.7% > 10%) | — | — |

_Valid only for: judge `nli:deberta-v3-base-zeroshot-v2.0` · model `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` · data `examples/task-routing/labels-described.jsonl` · sha256 `4571c9661a0c…` · measured 2026-09-20T18:53:38+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.8% | 0.0% | 0.85 | 7 |
| 10.8% | 0.0% | 0.82 | 13 |
| 15.8% | 0.0% | 0.79 | 19 |
| 21.7% | 11.5% | 0.76 | 26 |
| 25.8% | 16.1% | 0.72 | 31 |
| 30.0% | 22.2% | 0.70 | 36 |
| 36.7% | 27.3% | 0.62 | 44 |
| 41.7% | 36.0% | 0.61 | 50 |
| 45.0% | 38.9% | 0.60 | 54 |
| 50.0% | 40.0% | 0.59 | 60 |
| 55.0% | 40.9% | 0.59 | 66 |
| 60.0% | 45.8% | 0.58 | 72 |
| 65.8% | 45.6% | 0.57 | 79 |
| 70.0% | 46.4% | 0.57 | 84 |
| 75.0% | 46.7% | 0.57 | 90 |
| 81.7% | 49.0% | 0.54 | 98 |
| 86.7% | 49.0% | 0.54 | 104 |
| 90.8% | 48.6% | 0.51 | 109 |
| 95.8% | 51.3% | 0.51 | 115 |
| 100.0% | 49.2% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.554 | 55.6% | 63 |
| 0.6-0.7 | 0.624 | 76.2% | 21 |
| 0.7-0.8 | 0.745 | 42.1% | 19 |
| 0.8-0.9 | 0.839 | 0.0% | 17 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
