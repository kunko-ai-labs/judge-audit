# The safe automation rate — design notes (October 2026)

Issue: [#122](https://github.com/kunko-ai-labs/judge-audit/issues/122). The method itself is documented in [judges.md § The safe automation rate](judges.md#the-safe-automation-rate); this note records why it exists and what it must not be read as.

## Why

The v0.5 study ([results](v05-results.md), pre-registered in [v05-plan.md](v05-plan.md)) mostly did not go the way the literature suggests: reading a model's own token probabilities is not reliably better than asking it (H1-lp not supported), and self-consistency makes confidence rank errors **worse** (T3, T4, T5 resolved in the opposite direction; T6 too under the re-reading). Its most useful finding for a team deciding what to automate is not one of the hypothesis tests: **accuracy does not order judges by what they let you automate.** On BANKING77 test (human-labelled), gemini-3.6-flash verbalized is more accurate than Jev (83.4 % vs 80.2 %), yet at an error of at most 10 % it lets you automate 45.5 % of the texts against Jev's 72.3 % (seed spread 45.5–45.5 % and 72.0–73.4 %). That comparison is **exploratory**: computed in the report, not one of the eight pre-registered tests.

A team does not want an ECE; it wants to know how much of its traffic the judge can decide alone, at what error, at which threshold. The library already computed it (`coverage_at_risk`, `coverage_at_risk_crossfit`, tested since #98 and used by the study); the reports did not show it. Now every report opens with it.

## Design

What is computed, per question and target error (1, 2, 5 and 10 %; the primary one chosen before the run), and the conditions it holds under, are in [judges.md](judges.md#the-safe-automation-rate). In short: decisions as units; a fixed-sequence exact binomial walk from the most confident down, starting at the cut that bounds the error with 2 errors; an out-of-sample check split by distinct text with its spread over seeds; a per-text line when texts repeat; the worst segment above the threshold; the scope the rate is valid for and a review date.

## What we will not claim

- That the BANKING77 comparison above is confirmed: it is exploratory until a pre-registered study tests it on data no judge has been scored on.
- That a rate transfers to other traffic: it is a statement about traffic drawn like the labelled decisions, judged by the same judge, model and prompt.
- That it is a certification or a conformity assessment of any kind.
- "4 of 4" for self-consistency: under the pre-registered rule it is 3 of 4 in the opposite direction (T6 depends on the scoring rule).
