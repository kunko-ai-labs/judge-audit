# Judgment models against chat models, compared on the same rows

**Short version.** Some judges are built to judge: given a state and a set of options, they return a probability for each option in one forward pass (Jev; Laya). Most judges in production are chat models asked to classify and say how sure they are. v0.5 compares the two kinds on the same rows, with paired tests, because that is the choice a team actually faces: buy or run a dedicated judgment model, or prompt the chat model it already pays for.

## Why the comparison matters

- **The v0.4 lead needs an explanation.** Jev let you automate 73 % of the emails under attack with no observed error (retrospective: threshold and score on the same rows); Gemini 3 Flash 0 %, a gap the intervals separate. Claude Sonnet 4.5 also scored 0 %, but its interval reaches 90.9 %, so that comparison is not resolved (synthetic, n = 200, one run; [arena-2026-09.md](../arena-2026-09.md)). Is that because Jev is a judgment model, or because its confidence is read as a probability while the chat models' is a written number? v0.5 tests part of it: each chat model is also read by self-consistency, and open-weight models run locally with MLX by token probability too ([three methods](confidence-methods.md)). For hosted chat models the probability read-out cannot be measured, so a gap that self-consistency does not close is not thereby shown to be the model. The judgment models are compared with each chat model's *best* method (H2).
- **One judgment model is an anecdote.** A claim about "judgment models" needs more than one. Laya (Convai Innovations, Apache-2.0) has public weights and runs on a laptop, so anyone can reproduce its row at no cost.

## Why paired, on the same rows

Two judges answering the same questions make correlated mistakes: the hard rows are hard for both. Comparing two numbers that each carry a 95 % interval, and declaring a difference only when the intervals do not overlap, throws that correlation away and is conservative: it misses real differences (Schenker & Gentleman, 2001). v0.5 therefore:

- scores both judges on each **bootstrap resample of the same rows** and reports the interval of the difference (`paired_difference_ci`, clustered by distinct text);
- tests accuracy with an **exact McNemar test** on the rows where exactly one of them is right (`mcnemar_exact`);
- reports AUROC and coverage-at-risk differences the same way.

The pattern v0.4 suggests, similar accuracy but very different ranking of errors, is exactly what paired tests can confirm or refute on real data; v0.4 itself published no paired test, so that is a hypothesis, not a result.

## Caveats that travel with these rows

- **Laya is not Jev's zero-shot peer.** Its own README says its base checkpoints are near chance on typed decisions zero-shot, "a fast base to specialise, not a zero-shot decision engine", and reports 0.425 accuracy on BANKING77's 77 intents at default budgets. A zero-shot Laya row measures that, and says so.
- **Laya's token budget.** At its default budget BANKING77's 77 options do not fit; Laya 0.3.20 would truncate them silently (some become identical). The adapter refuses instead, and the pre-registration must choose: a larger budget (outside what Laya was trained with) or a shortlist of options first.
- **Laya's temperatures.** For questions with 11 or more options its checkpoint ships a temperature the library clamps; Laya warns that confidence from a clamped entry is uncalibrated. The run records which entries were clamped.
- **Jev** is a hosted, closed model. Its direct API reports the version it served and that is recorded; through the gateway the version is recorded as unknown, because the gateway reports none.
- **Everything is zero-shot.** Your own fine-tuned classifier is a different kind of row (it needs labels) and is reported in its own group with the labels it took.

Sources: [reading list](reading-list.md) § Judges and paired comparisons.
