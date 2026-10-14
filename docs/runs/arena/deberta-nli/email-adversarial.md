# Audit report — nli

**n=200** · accuracy **59.5%** [51.7, 66.7] · confidence known **200/200** · ECE **0.1247** [0.0876, 0.2007] · ECE (equal-mass) **0.1106** [0.0911, 0.2002] · Brier **0.2049** [0.1696, 0.2420] · NLL **0.6031** [0.5143, 0.6993]
· cost **$0.0000** · p50 **0.354s** · p99 **0.835s** · slowest **1.074s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:51:52+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `74741868f533…`_
_regenerated 2026-10-14T13:25:02+00:00 from `docs/runs/arena/deberta-nli/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.6.0rc2_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Validated on held-out decisions, at a 5% error target: none** — no threshold passes: the first cut tested holds 124 decisions with 36 errors (95% upper bound on the error rate 36.5%, above the 5% target).

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (no threshold passes: the first cut tested holds 124 texts with 33 errors (95% upper bound on the error rate 34.0%, above the 5% target)).

| error target | in plain words | validated on held-out decisions | deploy at confidence ≥ | on all labelled decisions |
|---|---|---|---|---|
| 1% | a target of 1 wrong in every 100 automated decisions | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | a target of 1 wrong in every 50 automated decisions | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | a target of 1 wrong in every 20 automated decisions | none: no threshold passes: the first cut tested holds 124 decisions with 36 errors (95% upper bound on the error rate 36.5%, above the 5% target) | — | — |
| 10% | a target of 1 wrong in every 10 automated decisions | none: no threshold passes: the first cut tested holds 61 decisions with 16 errors (95% upper bound on the error rate 37.1%, above the 10% target) | — | — |

_Valid only for: judge `nli:deberta-v3-base-zeroshot-v2.0` · model `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-20T18:51:52+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_The threshold is the lowest cut whose exact one-sided 95% upper bound on the error rate stays within the target. The bound speaks only for traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The held-out check chooses the threshold on half of the labelled decisions (split by distinct text, seed 0, range over other seeds) and applies it to the other half, both ways; its bound pools the errors of both held-out halves, treating them as independent draws (an approximation: each half's threshold depends on the other half). It is a conservative check rather than a forecast, and its share is called validated only when that bound is within the target. The share on all labelled decisions is what the threshold to deploy covers. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 28 | 4 | 14.3% | 29.8% |
| ≥ 0.95 | 13 | 0 | 0.0% | 20.6% |
| ≥ 0.99 | 0 | 0 | — | — |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Observed on all rows, no bound — not a basis for deployment

Zero observed errors through the most confident **8.0%** [3.9, 16.0] (16 decisions, confidence ≥ 0.9319).
Retrospective on this dataset: what these rows show, not a forecast.

### Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 6.5% | 100.0% | 0.96 | 13 |
| 10.0% | 95.0% | 0.93 | 20 |
| 15.0% | 83.3% | 0.90 | 30 |
| 20.0% | 77.5% | 0.86 | 40 |
| 25.0% | 74.0% | 0.84 | 50 |
| 30.0% | 73.3% | 0.80 | 60 |
| 35.0% | 75.7% | 0.78 | 70 |
| 40.0% | 77.5% | 0.75 | 80 |
| 45.0% | 77.8% | 0.72 | 90 |
| 50.0% | 75.0% | 0.67 | 100 |
| 55.0% | 73.6% | 0.64 | 110 |
| 60.0% | 71.7% | 0.61 | 120 |
| 65.0% | 70.8% | 0.59 | 130 |
| 70.0% | 70.7% | 0.56 | 140 |
| 75.0% | 70.0% | 0.51 | 150 |
| 80.0% | 68.8% | 0.48 | 160 |
| 85.0% | 67.7% | 0.42 | 170 |
| 90.0% | 64.4% | 0.34 | 180 |
| 95.0% | 61.6% | 0.30 | 190 |
| 100.0% | 59.5% | 0.20 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.1-0.2 | 0.199 | 0.0% | 1 |
| 0.2-0.3 | 0.252 | 22.2% | 9 |
| 0.3-0.4 | 0.345 | 11.1% | 18 |
| 0.4-0.5 | 0.463 | 45.0% | 20 |
| 0.5-0.6 | 0.562 | 64.5% | 31 |
| 0.6-0.7 | 0.650 | 48.3% | 29 |
| 0.7-0.8 | 0.756 | 86.7% | 30 |
| 0.8-0.9 | 0.848 | 64.7% | 34 |
| 0.9-1.0 | 0.945 | 85.7% | 28 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
