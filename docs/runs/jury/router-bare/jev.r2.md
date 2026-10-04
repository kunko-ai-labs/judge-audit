> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). Raw per-row responses: see the checkpoint file named in the provenance line.

# Audit report — jev

**n=120** · accuracy **72.5%** [58.8, 84.5] · confidence known **120/120** · ECE **0.2083** [0.1110, 0.3396] · ECE (equal-mass) **0.2083** [0.1057, 0.3393] · Brier **0.2149** [0.1186, 0.3279] · NLL **∞** (3 answers declared certain and wrong)
· cost **$0.0025** · p50 **0.609s** · p99 **2.884s** · slowest **3.117s**

_judge `jev` · model `jev-latest` · backend `typesafe` · run 2026-09-21T18:52:47+00:00 · judge-audit 0.3.2_
_dataset `docs/runs/jury/router-bare/jev.r2.input.jsonl` · 120 rows · sha256 `b2887a8c3706…`_
_regenerated 2026-10-04T09:59:40+00:00 from `docs/runs/jury/router-bare/jev.r2.ckpt.jsonl` by `scripts/runs_report.py` · judge-audit 0.4.0_

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
| 10% | at most 1 in 10 automated decisions wrong | none: no threshold passes: the first cut tested holds 73 decisions with 7 errors (bound 17.3% > 10%) | — | — |

_Valid only for: judge `jev` · model `jev-latest` · data `docs/runs/jury/router-bare/jev.r2.input.jsonl` · sha256 `bee5de2ada47…` · measured 2026-09-21T18:52:47+00:00. Review by 2026-12-20, and measure again as soon as any of these changes._

_With 95% confidence, the error rate among decisions at or above the threshold is at most the target — on traffic drawn like these labelled decisions (a random sample of it, each decision an independent draw), judged by the judge and prompt above, with the labels taken as right. Label errors cut both ways: a wrong label the judge disagrees with counts as a judge error, one it agrees with hides an error. The primary target is the one passed with `--target` (here 5%), to be chosen before the run (this report was regenerated from an archived checkpoint with the default target: the target was not fixed in advance); every row is its own 95% statement; the 4 rows hold together with probability at least 80%; keeping the best-looking row after reading them is neither. The rate is the share of the labelled decisions the threshold covers; the out-of-sample check chooses the threshold on half of them (split by distinct text, seed 0, spread over other seeds in brackets) and applies it to the other half, a conservative check rather than a forecast. A decision without a confidence is never automated. Exact one-sided binomial bound, fixed-sequence walk from the most confident down, starting at the cut that bounds the error with 2 errors (docs/judges.md § The safe automation rate). Statistical evidence on the labelled decisions, not a conformity assessment or a certification by a notified body._

Zero observed errors through the most confident **0.0%** [0.0, 64.2] (0 decisions, confidence ≥ None).
Retrospective on this dataset — not a production guarantee.

## Accuracy vs coverage

| coverage | accuracy | min confidence | n |
|---|---|---|---|
| 50.0% | 95.0% | 1.00 | 60 |
| 60.8% | 90.4% | 0.99 | 73 |
| 65.0% | 89.7% | 0.98 | 78 |
| 72.5% | 85.1% | 0.94 | 87 |
| 75.0% | 82.2% | 0.92 | 90 |
| 80.0% | 78.1% | 0.86 | 96 |
| 85.0% | 78.4% | 0.82 | 102 |
| 90.0% | 75.9% | 0.76 | 108 |
| 95.0% | 73.7% | 0.67 | 114 |
| 100.0% | 72.5% | 0.56 | 120 |

## Calibration (reliability bins)

| confidence bin | avg confidence | accuracy | n |
|---|---|---|---|
| 0.5-0.6 | 0.577 | 33.3% | 3 |
| 0.6-0.7 | 0.642 | 40.0% | 5 |
| 0.7-0.8 | 0.757 | 37.5% | 8 |
| 0.8-0.9 | 0.846 | 53.8% | 13 |
| 0.9-1.0 | 0.989 | 81.3% | 91 |

_A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin._

_ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of about equal size (tied confidences never split), so it does not hinge on one crowded bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence would impute one._
