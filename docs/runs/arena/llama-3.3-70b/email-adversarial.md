# Audit report — llm

**n=200** · accuracy **90.5%** [86.1, 94.5] · confidence known **200/200** · ECE **0.0155** [0.0052, 0.0598] · ECE (equal-mass) **0.1325** [0.1028, 0.1741] · Brier **0.0850** [0.0510, 0.1213] · NLL **∞** (12 answers declared certain and wrong)
· cost **$0.0411** · p50 **0.811s** · p99 **1.589s** · slowest **8.097s**

_judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · run 2026-09-20T19:04:55+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-10-07T07:06:26+00:00 from `docs/runs/arena/llama-3.3-70b/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._
_**†** exact 95 % Clopper–Pearson (binomial) interval, published where the estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes independent rows, so where the dataset repeats texts it is a *lower bound* on the width the clustered interval would have had._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — no threshold passes: the first cut tested holds 183 decisions with 14 errors (bound 11.7% > 5%).

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (no threshold passes: the first cut tested holds 173 texts with 14 errors (bound 12.4% > 5%)).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: no threshold passes: the first cut tested holds 183 decisions with 14 errors (bound 11.7% > 5%) | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 183 decisions with 14 errors (bound 11.7% > 10%) | — | — |

_Valid only for: judge `llm:llama-3.3-70b` · model `llama-3.3-70b` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-20T19:04:55+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 1.8]† (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 183 | 14 | 7.6% | 11.7% |
| ≥ 0.95 | 23 | 12 | 52.2% | 70.4% |
| ≥ 0.99 | 23 | 12 | 52.2% | 70.4% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 6.0% | 0.0% | 1.00 | 12 |
| 11.5% | 47.8% | 0.99 | 23 |
| 91.5% | 92.3% | 0.90 | 183 |
| 98.5% | 91.9% | 0.80 | 197 |
| 100.0% | 90.5% | 0.00 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.0-0.1 | 0.000 | 0.0% | 2 |
| 0.2-0.3 | 0.200 | 0.0% | 1 |
| 0.8-0.9 | 0.800 | 85.7% | 14 |
| 0.9-1.0 | 0.912 | 92.3% | 183 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
