> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=200** · accuracy **97.0%** [94.4, 99.0] · confidence known **200/200** · ECE **0.0530** [0.0344, 0.0790] · ECE (equal-mass) **0.0530** [0.0310, 0.0796] · Brier **0.0349** [0.0233, 0.0488] · NLL **0.1220** [0.0882, 0.1622]
· cost **$0.0032** · p50 **0.261s** · p99 **0.377s** · slowest **0.575s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-26T07:45:35+00:00 · judge-audit 0.4.0_
_served as reported by the provider: `jev-1.13.0` × 200 decisions_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-10-07T07:06:26+00:00 from `docs/runs/repeats/jev/email-adversarial.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: 96.0%** of the labelled decisions (192 of 200; 4 wrong, error bound 4.7%), deploying at confidence ≥ 0.56. Checked out of sample, with the threshold chosen on half the data: not checkable: a half holds at most 100 decisions with a confidence; the target needs 124.

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): 92.1% of the texts (174 of 189; 3 counted wrong, error bound 4.4%), at confidence ≥ 0.64.

Worst segment above that threshold (true label): `spam`, 0 of 30 automated decisions wrong (0.0%; its own error bound 9.5%). The overall bound does not cover a segment. 9 segments with fewer than 30 automated decisions are not ranked. 4 of the 4 errors above the threshold sit in segments too small to rank.

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | 96.0% (192 of 200 decisions; 4 wrong, error bound 4.7%) | 0.56 | not checkable: a half holds at most 100 decisions with a confidence; the target needs 124 |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (200 of 200 decisions; 6 wrong, error bound 5.8%) | 0.5 | 100.0% automated, 3.0% wrong (seeds 0–9: 97.5%–100.0%) |

_Valid only for: judge `jev` · model `jev-latest` · served `jev-1.13.0` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-26T07:45:35+00:00. Review by 2026-12-25, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **70.5%** [64.5, 94.4] (141 decisions, confidence ≥ 0.92).
Retrospective on this dataset — not a production guarantee.

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 147 | 1 | 0.7% | 3.2% |
| ≥ 0.95 | 135 | 0 | 0.0% | 2.2% |
| ≥ 0.99 | 118 | 0 | 0.0% | 2.5% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 53.5% | 100.0% | 1.00 | 107 |
| 59.0% | 100.0% | 0.99 | 118 |
| 63.5% | 100.0% | 0.98 | 127 |
| 66.0% | 100.0% | 0.97 | 132 |
| 70.0% | 100.0% | 0.93 | 140 |
| 75.0% | 99.3% | 0.88 | 150 |
| 81.0% | 99.4% | 0.84 | 162 |
| 85.0% | 99.4% | 0.77 | 170 |
| 90.0% | 99.4% | 0.66 | 180 |
| 95.0% | 97.9% | 0.60 | 190 |
| 100.0% | 97.0% | 0.50 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.530 | 80.0% | 10 |
| 0.6-0.7 | 0.642 | 80.0% | 15 |
| 0.7-0.8 | 0.740 | 100.0% | 7 |
| 0.8-0.9 | 0.849 | 100.0% | 21 |
| 0.9-1.0 | 0.990 | 99.3% | 147 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
