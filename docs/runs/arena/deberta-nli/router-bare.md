# Audit report — nli

**n=120** · accuracy **47.5%** [33.6, 61.2] · confidence known **120/120** · ECE **0.4027** [0.2999, 0.5539] · ECE (equal-mass) **0.4350** [0.3685, 0.5900] · Brier **0.4462** [0.3697, 0.5365] · NLL **1.5753** [1.2542, 1.9543]
· cost **$0.0000** · p50 **0.094s** · p99 **0.766s** · slowest **1.456s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:53:15+00:00 · judge-audit 0.3.1_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-10-07T07:06:26+00:00 from `docs/runs/arena/deberta-nli/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 120.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 61).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 120 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 120 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 120 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 63 decisions with 43 errors (bound 77.9% > 10%) | — | — |

_Valid only for: judge `nli:deberta-v3-base-zeroshot-v2.0` · model `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` · data `examples/task-routing/labels.jsonl` · sha256 `27250d78eda6…` · measured 2026-09-20T18:53:15+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 35 | 35 | 100.0% | 100.0% |
| ≥ 0.95 | 27 | 27 | 100.0% | 100.0% |
| ≥ 0.99 | 9 | 9 | 100.0% | 100.0% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 0.0% | 0.99 | 6 |
| 10.0% | 0.0% | 0.98 | 12 |
| 15.8% | 0.0% | 0.97 | 19 |
| 20.0% | 0.0% | 0.96 | 24 |
| 25.0% | 0.0% | 0.94 | 30 |
| 30.0% | 0.0% | 0.90 | 36 |
| 35.8% | 7.0% | 0.79 | 43 |
| 40.0% | 16.7% | 0.68 | 48 |
| 45.0% | 25.9% | 0.65 | 54 |
| 50.0% | 28.3% | 0.64 | 60 |
| 55.0% | 34.8% | 0.62 | 66 |
| 60.0% | 40.3% | 0.60 | 72 |
| 66.7% | 38.8% | 0.58 | 80 |
| 71.7% | 39.5% | 0.56 | 86 |
| 76.7% | 40.2% | 0.55 | 92 |
| 80.8% | 40.2% | 0.53 | 97 |
| 85.8% | 43.7% | 0.52 | 103 |
| 90.0% | 44.4% | 0.51 | 108 |
| 95.0% | 47.4% | 0.50 | 114 |
| 100.0% | 47.5% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.545 | 63.0% | 54 |
| 0.6-0.7 | 0.651 | 85.7% | 21 |
| 0.7-0.8 | 0.760 | 100.0% | 5 |
| 0.8-0.9 | 0.887 | 0.0% | 5 |
| 0.9-1.0 | 0.965 | 0.0% | 35 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
