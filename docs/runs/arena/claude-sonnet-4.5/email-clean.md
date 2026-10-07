# Audit report — llm

**n=200** · accuracy **100.0%** [98.2, 100.0]† · confidence known **200/200** · ECE **0.0290** [0.0243, 0.0333] · ECE (equal-mass) **0.0290** [0.0243, 0.0333] · Brier **0.0015** [0.0012, 0.0018] · NLL **0.0297** [0.0249, 0.0341]
· cost **$0.3798** · p50 **2.913s** · p99 **4.587s** · slowest **4.964s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-20T18:17:43+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-10-07T07:06:26+00:00 from `docs/runs/arena/claude-sonnet-4.5/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Safe automation rate at ≤ 5% error: 100.0%** of the labelled decisions (200 of 200; 0 wrong, error bound 1.5%), deploying at confidence ≥ 0.85. Checked out of sample, with the threshold chosen on half the data: not checkable: a half holds at most 110 decisions with a confidence; the target needs 124.

This labelled set repeats texts (200 decisions, 161 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): 100.0% of the texts (161 of 161; 0 counted wrong, error bound 1.8%), at confidence ≥ 0.85.

Segments (true label): none has 30 automated decisions, so none is ranked. 10 segments with fewer than 30 automated decisions are not ranked.

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | 100.0% (200 of 200 decisions; 0 wrong, error bound 1.5%) | 0.85 | not checkable: a half holds at most 110 decisions with a confidence; the target needs 124 |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (200 of 200 decisions; 0 wrong, error bound 1.5%) | 0.85 | 99.5% automated, 0.0% wrong (seeds 0–9: 99.5%–99.5%) |

_Valid only for: judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-20T18:17:43+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **100.0%** [98.2, 100.0]† (200 decisions, confidence ≥ 0.85).
Retrospective on this dataset — not a production guarantee.

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 199 | 0 | 0.0% | 1.5% |
| ≥ 0.95 | 199 | 0 | 0.0% | 1.5% |
| ≥ 0.99 | 91 | 0 | 0.0% | 3.2% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 33.5% | 100.0% | 1.00 | 67 |
| 45.5% | 100.0% | 0.99 | 91 |
| 99.5% | 100.0% | 0.95 | 199 |
| 100.0% | 100.0% | 0.85 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.850 | 100.0% | 1 |
| 0.9-1.0 | 0.972 | 100.0% | 199 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
