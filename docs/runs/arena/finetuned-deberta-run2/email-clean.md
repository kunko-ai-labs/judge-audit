# Audit report — finetuned

**n=100** · accuracy **100.0%** [96.4, 100.0]† · confidence known **100/100** · ECE **0.0169** [0.0160, 0.0177] · ECE (equal-mass) **0.0169** [0.0160, 0.0177] · Brier **0.0003** ‡ · NLL **0.0170** [0.0162, 0.0179]
· cost **$0.0000** · p50 **0.017s** · p99 **0.042s** · slowest **0.669s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:16:56+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `2b2ff2f88b3a…`_
_regenerated 2026-10-06T20:00:30+00:00 from `docs/runs/arena/finetuned-deberta-run2/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=100 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._
_**‡** degenerate: every clustered-bootstrap resample returned the same value, so no interval width is published for that number._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 100.

This labelled set repeats texts (100 decisions, 86 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 86).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 100 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 100 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 100 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (100 of 100 decisions; 0 wrong, error bound 3.0%) | 0.975421↑ | not checkable: a half holds at most 53 decisions with a confidence; the target needs 61 |

_Valid only for: judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-22T08:16:56+00:00. Review by 2026-12-21, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **100.0%** [96.4, 100.0]† (100 decisions, confidence ≥ 0.9754).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.99 | 5 |
| 10.0% | 100.0% | 0.99 | 10 |
| 15.0% | 100.0% | 0.99 | 15 |
| 20.0% | 100.0% | 0.99 | 20 |
| 25.0% | 100.0% | 0.99 | 25 |
| 30.0% | 100.0% | 0.98 | 30 |
| 40.0% | 100.0% | 0.98 | 40 |
| 45.0% | 100.0% | 0.98 | 45 |
| 50.0% | 100.0% | 0.98 | 50 |
| 55.0% | 100.0% | 0.98 | 55 |
| 60.0% | 100.0% | 0.98 | 60 |
| 65.0% | 100.0% | 0.98 | 65 |
| 70.0% | 100.0% | 0.98 | 70 |
| 75.0% | 100.0% | 0.98 | 75 |
| 80.0% | 100.0% | 0.98 | 80 |
| 86.0% | 100.0% | 0.98 | 86 |
| 90.0% | 100.0% | 0.98 | 90 |
| 95.0% | 100.0% | 0.98 | 95 |
| 100.0% | 100.0% | 0.98 | 100 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.9-1.0 | 0.983 | 100.0% | 100 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
