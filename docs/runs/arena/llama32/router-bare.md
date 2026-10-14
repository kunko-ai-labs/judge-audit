# Audit report — llm

**n=120** · accuracy **65.8%** [51.6, 79.2] · confidence known **120/120** · ECE **0.3958** [0.2614, 0.5287] · ECE (equal-mass) **0.3958** [0.2614, 0.5287] · Brier **0.3688** [0.2380, 0.5044] · NLL **∞** (41 answers declared certain and wrong)
· cost **$0.0000** · p50 **0.749s** · p99 **0.953s** · slowest **0.975s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:04:59+00:00 · judge-audit 0.3.0_
_dataset `examples/task-routing/labels.jsonl` · 120 rows · sha256 `27250d78eda6…`_
_regenerated 2026-10-14T13:25:02+00:00 from `docs/runs/arena/llama32/router-bare.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.6.0rc2_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Validated on held-out decisions, at a 5% error target: none** — needs 124 decisions with a confidence to bound the error at 5%; has 120.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 61).

| error target | in plain words | validated on held-out decisions | deploy at confidence ≥ | on all labelled decisions |
|---|---|---|---|---|
| 1% | a target of 1 wrong in every 100 automated decisions | none: needs 628 decisions with a confidence to bound the error at 1%; has 120 | — | — |
| 2% | a target of 1 wrong in every 50 automated decisions | none: needs 313 decisions with a confidence to bound the error at 2%; has 120 | — | — |
| 5% (primary) | a target of 1 wrong in every 20 automated decisions | none: needs 124 decisions with a confidence to bound the error at 5%; has 120 | — | — |
| 10% | a target of 1 wrong in every 10 automated decisions | none: no threshold passes: the first cut tested holds 107 decisions with 41 errors (95% upper bound on the error rate 46.7%, above the 10% target) | — | — |

_Valid only for: judge `llm:llama3.2:3b` · model `llama3.2:3b` · data `examples/task-routing/labels.jsonl` · sha256 `27250d78eda6…` · measured 2026-09-20T17:04:59+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_The threshold is the lowest cut whose exact one-sided 95% upper bound on the error rate stays within the target. The bound speaks only for traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The held-out check chooses the threshold on half of the labelled decisions (split by distinct text, seed 0, range over other seeds) and applies it to the other half, both ways; its bound pools the errors of both held-out halves, treating them as independent draws (an approximation: each half's threshold depends on the other half). It is a conservative check rather than a forecast, and its share is called validated only when that bound is within the target. The share on all labelled decisions is what the threshold to deploy covers. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 107 | 41 | 38.3% | 46.7% |
| ≥ 0.95 | 107 | 41 | 38.3% | 46.7% |
| ≥ 0.99 | 107 | 41 | 38.3% | 46.7% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Observed on all rows, no bound — not a basis for deployment

Zero observed errors through the most confident **0.0%** [0.0, 3.0]† (none: the most confident group of decisions already holds an error).
Retrospective on this dataset: what these rows show, not a forecast.

### Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 89.2% | 61.7% | 1.00 | 107 |
| 100.0% | 65.8% | 0.50 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 100.0% | 13 |
| 0.9-1.0 | 1.000 | 61.7% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
