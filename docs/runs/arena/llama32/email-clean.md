# Audit report — llm

**n=200** · accuracy **90.0%** [77.8, 100.0] · confidence known **200/200** · ECE **0.0340** [0.0245, 0.1431] · ECE (equal-mass) **0.0340** [0.0245, 0.1431] · Brier **0.0892** [0.0182, 0.1743] · NLL **0.3205** [0.1377, 0.5408]
· cost **$0.0000** · p50 **0.703s** · p99 **0.931s** · slowest **0.975s**

_judge `llm:llama3.2:3b` · model `llama3.2:3b` · run 2026-09-20T17:00:06+00:00 · judge-audit 0.3.0_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-10-07T07:06:26+00:00 from `docs/runs/arena/llama32/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — no threshold passes: the first cut tested holds 132 decisions with 9 errors (bound 11.6% > 5%).

This labelled set repeats texts (200 decisions, 161 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): 100.0% of the texts (161 of 161; 2 counted wrong, error bound 3.9%), at confidence ≥ 0.8.

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: no threshold passes: the first cut tested holds 132 decisions with 9 errors (bound 11.6% > 5%) | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 132 decisions with 9 errors (bound 11.6% > 10%) | — | — |

_Valid only for: judge `llm:llama3.2:3b` · model `llama3.2:3b` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-20T17:00:06+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 100.0] (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 132 | 9 | 6.8% | 11.6% |
| ≥ 0.95 | 0 | 0 | — | — |
| ≥ 0.99 | 0 | 0 | — | — |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 66.0% | 93.2% | 0.90 | 132 |
| 100.0% | 90.0% | 0.80 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.8-0.9 | 0.800 | 83.8% | 68 |
| 0.9-1.0 | 0.900 | 93.2% | 132 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
