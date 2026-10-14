# Audit report — finetuned

**n=100** · accuracy **100.0%** [96.4, 100.0]† · confidence known **100/100** · ECE **0.0000** ‡ · ECE (equal-mass) **0.0000** ‡ · Brier **0.0000** ‡ · NLL **0.0000** ‡
· cost **$0.0000** · p50 **0.017s** · p99 **0.057s** · slowest **0.173s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:17:21+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_
_regenerated 2026-10-14T13:25:02+00:00 from `docs/runs/arena/finetuned-deberta-run2-ts/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.6.0rc2_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=100 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number._

## Can I automate this?

**Validated on held-out decisions, at a 5% error target: none** — needs 124 decisions with a confidence to bound the error at 5%; has 100.

This labelled set repeats texts (100 decisions, 86 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 86).

| error target | in plain words | validated on held-out decisions | deploy at confidence ≥ | on all labelled decisions |
|---|---|---|---|---|
| 1% | a target of 1 wrong in every 100 automated decisions | none: needs 628 decisions with a confidence to bound the error at 1%; has 100 | — | — |
| 2% | a target of 1 wrong in every 50 automated decisions | none: needs 313 decisions with a confidence to bound the error at 2%; has 100 | — | — |
| 5% (primary) | a target of 1 wrong in every 20 automated decisions | none: needs 124 decisions with a confidence to bound the error at 5%; has 100 | — | — |
| 10% | a target of 1 wrong in every 10 automated decisions | too few decisions to check on held-out data (each half needs 61, the larger has 53) | 1↑ | 100.0% (100 of 100 decisions; 0 wrong, 95% upper bound on the error rate: 3.0%) |

_Valid only for: judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-22T08:17:21+00:00. Review by 2026-12-21, and measure again as soon as any of these changes._

_The threshold is the lowest cut whose exact one-sided 95% upper bound on the error rate stays within the target. The bound speaks only for traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The held-out check chooses the threshold on half of the labelled decisions (split by distinct text, seed 0, range over other seeds) and applies it to the other half, both ways; its bound pools the errors of both held-out halves, treating them as independent draws (an approximation: each half's threshold depends on the other half). It is a conservative check rather than a forecast, and its share is called validated only when that bound is within the target. The share on all labelled decisions is what the threshold to deploy covers. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 100 | 0 | 0.0% | 3.0% |
| ≥ 0.95 | 100 | 0 | 0.0% | 3.0% |
| ≥ 0.99 | 100 | 0 | 0.0% | 3.0% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Observed on all rows, no bound — not a basis for deployment

Zero observed errors through the most confident **100.0%** [96.4, 100.0]† (100 decisions, confidence ≥ 1.0).
Retrospective on this dataset: what these rows show, not a forecast.

### Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 1.00 | 5 |
| 10.0% | 100.0% | 1.00 | 10 |
| 15.0% | 100.0% | 1.00 | 15 |
| 20.0% | 100.0% | 1.00 | 20 |
| 25.0% | 100.0% | 1.00 | 25 |
| 32.0% | 100.0% | 1.00 | 32 |
| 35.0% | 100.0% | 1.00 | 35 |
| 40.0% | 100.0% | 1.00 | 40 |
| 45.0% | 100.0% | 1.00 | 45 |
| 50.0% | 100.0% | 1.00 | 50 |
| 55.0% | 100.0% | 1.00 | 55 |
| 60.0% | 100.0% | 1.00 | 60 |
| 65.0% | 100.0% | 1.00 | 65 |
| 70.0% | 100.0% | 1.00 | 70 |
| 77.0% | 100.0% | 1.00 | 77 |
| 80.0% | 100.0% | 1.00 | 80 |
| 85.0% | 100.0% | 1.00 | 85 |
| 90.0% | 100.0% | 1.00 | 90 |
| 95.0% | 100.0% | 1.00 | 95 |
| 100.0% | 100.0% | 1.00 | 100 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 1.000 | 100.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
