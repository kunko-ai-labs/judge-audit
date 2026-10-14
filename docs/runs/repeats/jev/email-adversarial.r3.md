> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=200** · accuracy **96.0%** [93.0, 98.5] · confidence known **200/200** · ECE **0.0426** [0.0354, 0.0702] · ECE (equal-mass) **0.0428** [0.0282, 0.0699] · Brier **0.0340** [0.0224, 0.0486] · NLL **0.1207** [0.0863, 0.1628]
· cost **$0.0032** · p50 **0.259s** · p99 **0.399s** · slowest **0.442s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-26T07:46:29+00:00 · judge-audit 0.4.0_
_served as reported by the provider: `jev-1.13.0` × 200 decisions_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-10-14T13:25:02+00:00 from `docs/runs/repeats/jev/email-adversarial.r3.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.6.0rc2_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Validated on held-out decisions, at a 5% error target: too few decisions to check** with 200 decisions. The check splits the decisions into two halves and needs 124 scored decisions in a half (about 248 in all); the larger half has 100. Not validated: to deploy, confidence ≥ 0.570001↑; on all labelled decisions it automates 94.5% (189 of 200 decisions; 3 wrong, 95% upper bound on the error rate: 4.1%).

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): 94.2% of the texts (178 of 189; 3 counted wrong, 95% upper bound on the error rate: 4.3%), at confidence ≥ 0.570001↑.

Worst segment above that threshold (true label): `spam`, 0 of 30 automated decisions wrong (0.0%; its own 95% upper bound on the error rate: 9.6%). The overall bound does not cover a segment. 9 segments with fewer than 30 automated decisions are not ranked. 3 of the 3 errors above the threshold sit in segments too small to rank.

| error target | in plain words | validated on held-out decisions | deploy at confidence ≥ | on all labelled decisions |
|---|---|---|---|---|
| 1% | a target of 1 wrong in every 100 automated decisions | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | a target of 1 wrong in every 50 automated decisions | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | a target of 1 wrong in every 20 automated decisions | too few decisions to check on held-out data (each half needs 124, the larger has 100) | 0.570001↑ | 94.5% (189 of 200 decisions; 3 wrong, 95% upper bound on the error rate: 4.1%) |
| 10% | a target of 1 wrong in every 10 automated decisions | 99.0% (198 of 200 decisions; 7 wrong: 3.5%; 95% upper bound on the error rate: 6.6%; seeds 0–9: 96.0%–100.0%) | 0.51 | 100.0% (200 of 200 decisions; 8 wrong, 95% upper bound on the error rate: 7.2%) |

_Valid only for: judge `jev` · model `jev-latest` · served `jev-1.13.0` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-26T07:46:29+00:00. Review by 2026-12-25, and measure again as soon as any of these changes._

_The threshold is the lowest cut whose exact one-sided 95% upper bound on the error rate stays within the target. The bound speaks only for traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The held-out check chooses the threshold on half of the labelled decisions (split by distinct text, seed 0, range over other seeds) and applies it to the other half, both ways; its bound pools the errors of both held-out halves, treating them as independent draws (an approximation: each half's threshold depends on the other half). It is a conservative check rather than a forecast, and its share is called validated only when that bound is within the target. The share on all labelled decisions is what the threshold to deploy covers. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

## When it says ≥ 90 / 95 / 99 %, how often is it wrong?

| confidence | decisions | wrong | error rate | upper bound (95%) |
|---|---|---|---|---|
| ≥ 0.90 | 147 | 1 | 0.7% | 3.2% |
| ≥ 0.95 | 134 | 0 | 0.0% | 2.3% |
| ≥ 0.99 | 119 | 0 | 0.0% | 2.5% |

_0 decisions without a known confidence are left out of every row and counted here._

_A reading of the accuracy-vs-coverage curve at three fixed confidences, not a new score and not combined with any other number: the decisions declaring at least that confidence, how many were wrong, and an exact one-sided upper bound on their error rate (Clopper–Pearson, 95%). Rows are taken as independent: on a dataset that repeats texts, each copy counts, which can make the bound too tight. The cut is fixed in advance, not chosen on these rows, unlike the threshold an automation decision searches for._

## Observed on all rows, no bound — not a basis for deployment

Zero observed errors through the most confident **68.5%** [62.2, 95.5] (137 decisions, confidence ≥ 0.94).
Retrospective on this dataset: what these rows show, not a forecast.

### Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 54.0% | 100.0% | 1.00 | 108 |
| 59.5% | 100.0% | 0.99 | 119 |
| 62.5% | 100.0% | 0.98 | 125 |
| 65.0% | 100.0% | 0.97 | 130 |
| 71.0% | 99.3% | 0.93 | 142 |
| 75.0% | 99.3% | 0.88 | 150 |
| 80.5% | 99.4% | 0.85 | 161 |
| 85.0% | 99.4% | 0.80 | 170 |
| 90.5% | 99.5% | 0.66 | 181 |
| 95.5% | 97.4% | 0.56 | 191 |
| 100.0% | 96.0% | 0.51 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.552 | 56.2% | 16 |
| 0.6-0.7 | 0.665 | 100.0% | 10 |
| 0.7-0.8 | 0.748 | 100.0% | 4 |
| 0.8-0.9 | 0.849 | 100.0% | 23 |
| 0.9-1.0 | 0.990 | 99.3% | 147 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
