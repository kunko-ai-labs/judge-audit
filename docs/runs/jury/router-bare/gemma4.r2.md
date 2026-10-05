# Audit report — llm

**n=120** · accuracy **61.7%** [48.4, 74.3] · confidence known **120/120** · ECE **0.3098** [0.1924, 0.4460] · ECE (equal-mass) **0.3152** [0.1977, 0.4414] · Brier **0.3299** [0.2222, 0.4410] · NLL **∞** (2 answers declared certain and wrong)
· cost **$0.0000** · p50 **17.021s** · p99 **28.198s** · slowest **50.48s**

_judge `llm:gemma4:e4b` · model `gemma4:e4b` · run 2026-09-21T18:52:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/gemma4.r2.input.jsonl` · 120 rows · sha256 `6f5b14b5cbc2…`_
_regenerated 2026-10-04T19:08:48+00:00 from `docs/runs/jury/router-bare/gemma4.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.5.0_

**Ground truth: GT-1 constructed — labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy; the route label is the generator's difficulty class by design (easy -> route_easy, hard -> route_strong), not an observed outcome; downstream task quality is not measured: whether the cheap model solves the easy tasks and fails the hard ones is unverified; 40 adversarial rows keep the honest label route_easy; _meta.target is what the attacker wanted**

_Brackets are 95% percentile-bootstrap intervals over the dataset's distinct texts (2,000 resamples, seed 0): how far the number would move on another sample of n=120 drawn the same way._

## Can I automate this?

**Safe automation rate at ≤ 5% error: none** — needs 124 decisions with a confidence to bound the error at 5%; has 120.

This labelled set repeats texts (120 decisions, 61 distinct texts). The bound above treats the decisions as a random sample of your traffic, repeats included as they occur there. If the repeats were copied in instead, count each text once (at its highest confidence, wrong if any copy is: not always the more cautious reading when the copies of a text carry different confidences): at this target, none (needs 124 texts with a confidence to bound the error at 5%; has 61).

| at most this error | in plain words | safe automation rate | deploy at confidence ≥ | checked out of sample |
|---|---|---|---|---|
| 1% | at most 1 in 100 automated decisions wrong | none: needs 628 decisions with a confidence to bound the error at 1%; has 120 | — | — |
| 2% | at most 1 in 50 automated decisions wrong | none: needs 313 decisions with a confidence to bound the error at 2%; has 120 | — | — |
| 5% (primary) | at most 1 in 20 automated decisions wrong | none: needs 124 decisions with a confidence to bound the error at 5%; has 120 | — | — |
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 70 decisions with 23 errors (bound 43.2% > 10%) | — | — |

_Valid only for: judge `llm:gemma4:e4b` · model `gemma4:e4b` · data `docs/runs/jury/router-bare/gemma4.r2.input.jsonl` · sha256 `1ef6d6d785ff…` · measured 2026-09-21T18:52:47+00:00. Review by 2026-12-20, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 13.3] (none: the most confident group of decisions already holds an error).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 17.5% | 85.7% | 0.98 | 21 |
| 58.3% | 67.1% | 0.95 | 70 |
| 89.2% | 62.6% | 0.90 | 107 |
| 90.0% | 62.0% | 0.88 | 108 |
| 96.7% | 61.2% | 0.85 | 116 |
| 100.0% | 61.7% | 0.70 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.7-0.8 | 0.733 | 66.7% | 3 |
| 0.8-0.9 | 0.848 | 50.0% | 10 |
| 0.9-1.0 | 0.939 | 62.6% | 107 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
