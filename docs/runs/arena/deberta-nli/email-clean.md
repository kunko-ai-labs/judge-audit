# Audit report — nli

**n=200** · accuracy **86.5%** [80.8, 91.6] · confidence known **200/200** · ECE **0.1765** [0.1244, 0.2416] · ECE (equal-mass) **0.1630** [0.1174, 0.2348] · Brier **0.1288** [0.0970, 0.1696] · NLL **0.4021** [0.3247, 0.4969]
· cost **$0.0000** · p50 **0.321s** · p99 **0.744s** · slowest **1.208s**

_judge `nli:deberta-v3-base-zeroshot-v2.0` · model `deberta-v3-base-zeroshot-v2.0` · run 2026-09-20T18:50:38+00:00 · judge-audit 0.3.1_
_dataset `examples/email-routing/labels.jsonl` · 200 rows · sha256 `c5b4c111290a…`_
_regenerated 2026-10-14T13:25:02+00:00 from `docs/runs/arena/deberta-nli/email-clean.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.6.0rc2_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic: seeded templates with item and number fills, not real mail; the label is the template's category by design; no human checked it; 100 % here is the floor a judge must clear, not evidence of production routing accuracy**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Validated on held-out decisions, at a 5% error target: none** — no threshold passes: the first cut tested holds 125 decisions with 5 errors (95% upper bound on the error rate 8.3%, above the 5% target).

This labelled set repeats texts (200 decisions, 161 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (no threshold passes: the first cut tested holds 124 texts with 8 errors (95% upper bound on the error rate 11.4%, above the 5% target)).

| error target | in plain words | validated on held-out decisions | deploy at confidence ≥ | on all labelled decisions |
|---|---|---|---|---|
| 1% | a target of 1 wrong in every 100 automated decisions | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | a target of 1 wrong in every 50 automated decisions | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | a target of 1 wrong in every 20 automated decisions | none: no threshold passes: the first cut tested holds 125 decisions with 5 errors (95% upper bound on the error rate 8.3%, above the 5% target) | — | — |
| 10% | a target of 1 wrong in every 10 automated decisions | not met at the 10% target (95% upper bound 17.6%): 39.5% held out (79 of 200 decisions; 8 wrong: 10.1%; seeds 0–9: 20.5%–66.0%) | 0.612689↑ | 69.5% (139 of 200 decisions; 7 wrong, 95% upper bound on the error rate: 9.3%) |

_Valid only for: judge `nli:deberta-v3-base-zeroshot-v2.0` · model `MoritzLaurer/deberta-v3-base-zeroshot-v2.0` · data `examples/email-routing/labels.jsonl` · sha256 `c5b4c111290a…` · measured 2026-09-20T18:50:38+00:00. Review by 2026-12-19, and measure again as soon as any of these changes._

_The threshold is the lowest cut whose exact one-sided 95% upper bound on the error rate stays within the target. The bound speaks only for traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The held-out check chooses the threshold on half of the labelled decisions (split by distinct text, seed 0, range over other seeds) and applies it to the other half, both ways; its bound pools the errors of both held-out halves, treating them as independent draws (an approximation: each half's threshold depends on the other half). It is a conservative check rather than a forecast, and its share is called validated only when that bound is within the target. The share on all labelled decisions is what the threshold to deploy covers. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 49 | 0 | 0.0% | 6.0% |
| ≥ 0.95 | 32 | 0 | 0.0% | 9.0% |
| ≥ 0.99 | 0 | 0 | — | — |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Observed on all rows, no bound — not a basis for deployment

Zero observed errors through the most confident **51.5%** [41.4, 64.1] (103 decisions, confidence ≥ 0.7368).
Retrospective on this dataset: what these rows show, not a forecast.

### Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.98 | 10 |
| 10.0% | 100.0% | 0.97 | 20 |
| 16.0% | 100.0% | 0.96 | 32 |
| 20.0% | 100.0% | 0.92 | 40 |
| 25.0% | 100.0% | 0.90 | 50 |
| 30.5% | 100.0% | 0.85 | 61 |
| 35.0% | 100.0% | 0.81 | 70 |
| 40.0% | 100.0% | 0.79 | 80 |
| 45.0% | 100.0% | 0.75 | 90 |
| 51.0% | 100.0% | 0.74 | 102 |
| 55.0% | 98.2% | 0.70 | 110 |
| 60.0% | 96.7% | 0.67 | 120 |
| 65.0% | 95.4% | 0.64 | 130 |
| 70.0% | 94.3% | 0.61 | 140 |
| 75.0% | 94.7% | 0.56 | 150 |
| 80.0% | 93.8% | 0.54 | 160 |
| 85.0% | 91.8% | 0.48 | 170 |
| 90.0% | 88.3% | 0.42 | 180 |
| 95.0% | 86.8% | 0.35 | 190 |
| 100.0% | 86.5% | 0.23 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.236 | 88.9% | 9 |
| 0.3-0.4 | 0.369 | 54.5% | 11 |
| 0.4-0.5 | 0.462 | 33.3% | 15 |
| 0.5-0.6 | 0.555 | 87.5% | 24 |
| 0.6-0.7 | 0.650 | 80.0% | 30 |
| 0.7-0.8 | 0.748 | 94.3% | 35 |
| 0.8-0.9 | 0.841 | 100.0% | 27 |
| 0.9-1.0 | 0.954 | 100.0% | 49 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
