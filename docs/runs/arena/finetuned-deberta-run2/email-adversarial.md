# Audit report — finetuned

**n=200** · accuracy **99.0%** [97.5, 100.0] · confidence known **200/200** · ECE **0.0480** [0.0360, 0.0659] · ECE (equal-mass) **0.0403** [0.0242, 0.0571] · Brier **0.0163** [0.0074, 0.0268] · NLL **0.0665** [0.0438, 0.0927]
· cost **$0.0000** · p50 **0.018s** · p99 **0.034s** · slowest **0.236s**

_judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · seed 2026 · run 2026-09-22T08:17:03+00:00 · judge-audit 0.3.2_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-10-06T20:00:30+00:00 from `docs/runs/arena/finetuned-deberta-run2/email-adversarial.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.1_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: 100.0%** of the labelled decisions (200 of 200; 2 wrong, error bound 3.1%), deploying at confidence ≥ 0.275445↑. Checked out of sample, with the threshold chosen on half the data: not checkable: a half holds at most 100 decisions with a confidence; the target needs 124.

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): 100.0% of the texts (189 of 189; 2 counted wrong, error bound 3.3%), at confidence ≥ 0.275445↑.

Worst segment above that threshold (true label): `spam`, 0 of 31 automated decisions wrong (0.0%; its own error bound 9.2%). The overall bound does not cover a segment. 9 segments with fewer than 30 automated decisions are not ranked. 2 of the 2 errors above the threshold sit in segments too small to rank.

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | 100.0% (200 of 200 decisions; 2 wrong, error bound 3.1%) | 0.275445↑ | not checkable: a half holds at most 100 decisions with a confidence; the target needs 124 |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (200 of 200 decisions; 2 wrong, error bound 3.1%) | 0.275445↑ | 99.5% automated, 1.0% wrong (seeds 0–9: 97.0%–99.5%) |

_Valid only for: judge `finetuned:deberta-v3-base-ft-email-routing-run2` · model `deberta-v3-base-ft-email-routing-run2` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-22T08:17:03+00:00. Review by 2026-12-21, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **96.0%** [93.1, 100.0] (192 decisions, confidence ≥ 0.7097).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 5.0% | 100.0% | 0.99 | 10 |
| 11.0% | 100.0% | 0.99 | 22 |
| 15.0% | 100.0% | 0.98 | 30 |
| 20.0% | 100.0% | 0.98 | 40 |
| 25.5% | 100.0% | 0.98 | 51 |
| 30.0% | 100.0% | 0.98 | 60 |
| 35.0% | 100.0% | 0.98 | 70 |
| 40.0% | 100.0% | 0.98 | 80 |
| 45.0% | 100.0% | 0.98 | 90 |
| 50.0% | 100.0% | 0.98 | 100 |
| 55.0% | 100.0% | 0.98 | 110 |
| 60.0% | 100.0% | 0.98 | 120 |
| 65.0% | 100.0% | 0.97 | 130 |
| 70.0% | 100.0% | 0.97 | 140 |
| 75.0% | 100.0% | 0.97 | 150 |
| 80.0% | 100.0% | 0.97 | 160 |
| 85.0% | 100.0% | 0.96 | 170 |
| 90.0% | 100.0% | 0.94 | 180 |
| 95.0% | 100.0% | 0.77 | 190 |
| 100.0% | 99.0% | 0.28 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.2-0.3 | 0.275 | 100.0% | 1 |
| 0.3-0.4 | 0.399 | 100.0% | 2 |
| 0.4-0.5 | 0.444 | 100.0% | 2 |
| 0.5-0.6 | 0.569 | 50.0% | 2 |
| 0.6-0.7 | 0.630 | 0.0% | 1 |
| 0.7-0.8 | 0.734 | 100.0% | 3 |
| 0.8-0.9 | 0.851 | 100.0% | 3 |
| 0.9-1.0 | 0.976 | 100.0% | 186 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
