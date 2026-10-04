# Audit report — finetuned

**n=100** · accuracy **100.0%** [96.4, 100.0]† · confidence known **100/100** · ECE **0.4581** [0.4241, 0.4951] · ECE (equal-mass) **0.4581** [0.4241, 0.4951] · Brier **0.2337** [0.1991, 0.2716] · NLL **0.6668** [0.5919, 0.7510]
· cost **$0.0000** · p50 **0.016s** · p99 **0.327s** · slowest **0.978s**

_judge `finetuned:deberta-v3-base-ft-email-routing` · model `deberta-v3-base-ft-email-routing` · seed 2026 · run 2026-09-22T03:13:37+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_
_regenerated 2026-10-04T09:30:59+00:00 from `docs/runs/arena/finetuned-deberta/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=100 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 100.

This labelled set repeats texts (100 decisions, 86 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 86).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 100 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 100 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 100 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (100 of 100 decisions; 0 wrong, error bound 3.0%) | 0.188508↑ | not checkable: a half holds at most 53 decisions with a confidence; the target needs 61 |

_Valid only for: judge `finetuned:deberta-v3-base-ft-email-routing` · model `deberta-v3-base-ft-email-routing` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-22T03:13:37+00:00. Review by 2026-12-21, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run; every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **100.0%** [96.4, 100.0]† (100 decisions, confidence ≥ 0.1885).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.75 | 5 |
| 10.0% | 100.0% | 0.75 | 10 |
| 15.0% | 100.0% | 0.72 | 15 |
| 20.0% | 100.0% | 0.70 | 20 |
| 25.0% | 100.0% | 0.66 | 25 |
| 32.0% | 100.0% | 0.65 | 32 |
| 35.0% | 100.0% | 0.60 | 35 |
| 40.0% | 100.0% | 0.59 | 40 |
| 45.0% | 100.0% | 0.57 | 45 |
| 50.0% | 100.0% | 0.55 | 50 |
| 55.0% | 100.0% | 0.54 | 55 |
| 60.0% | 100.0% | 0.54 | 60 |
| 65.0% | 100.0% | 0.51 | 65 |
| 70.0% | 100.0% | 0.50 | 70 |
| 75.0% | 100.0% | 0.44 | 75 |
| 80.0% | 100.0% | 0.44 | 80 |
| 88.0% | 100.0% | 0.40 | 88 |
| 90.0% | 100.0% | 0.30 | 90 |
| 95.0% | 100.0% | 0.21 | 95 |
| 100.0% | 100.0% | 0.19 | 100 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.193 | 100.0% | 3 |
| 0.2-0.3 | 0.227 | 100.0% | 8 |
| 0.3-0.4 | 0.384 | 100.0% | 5 |
| 0.4-0.5 | 0.459 | 100.0% | 16 |
| 0.5-0.6 | 0.547 | 100.0% | 32 |
| 0.6-0.7 | 0.643 | 100.0% | 16 |
| 0.7-0.8 | 0.737 | 100.0% | 20 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
