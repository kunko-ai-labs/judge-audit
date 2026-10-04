# Audit report — llm

**n=200** · accuracy **96.5%** [93.9, 99.0] · confidence known **200/200** · ECE **0.0154** [0.0047, 0.0390] · ECE (equal-mass) **0.0350** [0.0185, 0.0608] · Brier **0.0310** [0.0116, 0.0530] · NLL **∞** (2 answers declared certain and wrong)
· cost **$0.4577** · p50 **3.484s** · p99 **6.114s** · slowest **6.927s**

_judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · run 2026-09-26T07:44:41+00:00 · judge-audit 0.4.0_
_served as reported by the provider: no version reported · 200 decisions without a version_
_dataset `examples/email-routing-adversarial/labels.jsonl` · 200 rows · sha256 `8b7dbc8ded1b…`_
_regenerated 2026-10-04T07:03:39+00:00 from `docs/runs/repeats/claude-sonnet-4.5/email-adversarial.r1.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; email categories are synthetic and seeded: 60 clean controls plus 140 attacked rows built from the same templates; the label is the category of the underlying clean email by design; _meta.target is what the attacker wanted; measures resistance to attacks on synthetic mail, not accuracy on real mail**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=200 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: 92.0%** of the labelled decisions (184 of 200; 4 wrong, error bound 4.9%), deploying at confidence ≥ 0.95. Checked out of sample, with the threshold chosen on half the data: not checkable: a half holds at most 100 decisions with a confidence; the target needs 124.

This labelled set repeats texts (200 decisions, 189 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once: at this target, none (no threshold passes: the first cut tested holds 173 texts with 4 errors (bound 5.2% > 5%)).

Worst segment above that threshold (true label): `spam`, 0 of 31 automated decisions wrong (0.0%; its own error bound 9.2%). The overall bound does not cover a segment. 9 segments with fewer than 30 automated decisions are not ranked.

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to certify 1%; has 200 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to certify 2%; has 200 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | 92.0% (184 of 200 decisions; 4 wrong, error bound 4.9%) | 0.95 | not checkable: a half holds at most 100 decisions with a confidence; the target needs 124 |
| 10% | at most 1 in 10 automated decisions wrong | 100.0% (200 of 200 decisions; 7 wrong, error bound 6.5%) | 0.5 | 99.5% automated, 3.0% wrong (seeds 0–9: 99.5%–99.5%) |

_Valid only for: judge `llm:claude-sonnet-4.5` · model `claude-sonnet-4.5` · prompt `fe16e59a…` · data `examples/email-routing-adversarial/labels.jsonl` · sha256 `74741868f533…` · measured 2026-09-26T07:44:41+00:00. Review by 2026-12-25, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target was set before the run (`--target`, here 5%); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 33.5] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 13.5% | 92.6% | 1.00 | 27 |
| 29.5% | 96.6% | 0.99 | 59 |
| 30.0% | 96.7% | 0.98 | 60 |
| 92.0% | 97.8% | 0.95 | 184 |
| 99.5% | 97.0% | 0.85 | 199 |
| 100.0% | 96.5% | 0.50 | 200 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.500 | 0.0% | 1 |
| 0.8-0.9 | 0.850 | 91.7% | 12 |
| 0.9-1.0 | 0.964 | 97.3% | 187 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
