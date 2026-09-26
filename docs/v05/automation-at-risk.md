# How much can you automate at error ≤ X %?

**Short version.** A team deploying a judge does not ask "what is its ECE?". It asks: *if I let it decide alone whenever it is confident enough, what share of my traffic does it handle, and how often will those automatic decisions be wrong?* v0.5 answers that directly: choose the confidence threshold on one half of the data, then **certify** on the other half, with an exact binomial bound, that the automated decisions err at most X % of the time. The answer has the shape a manager can act on: "Y % of tickets, error at most X %, with 95 % confidence".

## Why not ECE

The expected calibration error averages, over confidence bins, the gap between how sure the judge says it is and how often it is right. It is a useful diagnostic and stays in every report, but it cannot carry the question:

- **It says nothing about ranking.** A judge that says 0.98 on everything and is right 98 % of the time has ECE ≈ 0, and you cannot automate any subset more safely than the whole: its confidence carries no information about *which* answers are wrong. v0.4 shows exactly this. Under attack, Gemini 3 Flash had ten-bin ECE 0.015 against Jev's 0.039 (intervals overlapping), said 1.0 on 125 of 200 emails and was wrong on 5 of them; **0 %** of its decisions could be automated with no observed error, against **73 %** of Jev's, a gap the intervals do separate ([README § Arena](../../README.md), [arena-2026-09.md](../arena-2026-09.md); synthetic data, n = 200, one run).
- **Its value depends on the binning**, and equal-width bins, equal-mass bins and the Brier score can order judges differently: in v0.4, 28 judge pairs swap places, though none of those swaps is separated by the intervals ([arena-2026-09.md](../arena-2026-09.md)).
- **It has no unit a decision can use.** "0.04" does not say how much to automate.

## Why not v0.4's zero-error coverage alone

v0.4 reported the largest share of most-confident decisions with **no** observed error. It showed the effect, but it cannot carry a benchmark of a few thousand rows:

- The chance of seeing zero errors in a slice shrinks as n grows, so the same judge looks worse on a bigger dataset.
- A wrong **label** counts as an error, so label noise alone drives it to zero.
- Its threshold is chosen on the same rows it is scored on, which flatters it.

## What v0.5 computes instead (`judge_audit.metrics.selective`, #98)

1. **Split by distinct text** into a calibration half and a test half (seeded; a repeated text never sits on both sides; rows repeating one text count as one).
2. **Choose the threshold on the calibration half** by fixed-sequence testing (Learn then Test; Angelopoulos et al., 2025). Start at the most confident cut large enough to certify X % at all (299 rows at 1 %), then walk down one group of equal confidence at a time. At each cut, test whether a one-sided exact (Clopper–Pearson) 95 % bound on the error of the rows above it is at most X %, and stop at the first cut that fails; the threshold is the last cut that passed. Ties are whole groups: a confidence shared by 125 rows is one threshold, not 125 decisions to order.
3. **Check it on the test half**, where no row helped choose it, and report the coverage and the bound there. Then swap the halves and pool (cross-fitting), so every text is scored once.

The guarantee has a price in rows. With zero errors, certifying an error rate of at most 1 % needs 299 automated rows, 2 % needs 149 and 5 % needs 59; at 1 %, each further error costs roughly 129–174 more rows ([power analysis](../v05-power.md), part A). The procedure also has a price in power: it walks down from the most confident rows and stops at the first cut that fails, starting at the smallest cut that could pass. Simulated on continuous confidences, it certifies every time when the automatable rows are error-free, but only about half the time when their true error rate is a quarter of the target (part A2). Which targets are primary per dataset, and where the sequence starts, are decisions the pre-registration takes from that analysis.

## Around it

- **AUROC**: the probability that a right answer, drawn at random, carries a higher confidence than a wrong one (ties count one half). It measures ranking only: 1.0 = every error is less confident than every right answer, 0.5 = confidence says nothing.
- **AURC**: the area under the risk–coverage curve (Geifman, Uziel & El-Yaniv, ICLR 2019), computed as its expectation over tie orders, so a judge gains nothing by saying the same number often.
- **ECE (both binnings), Brier, NLL** stay in every report, next to each other, never combined into one score; MCE (the worst bin) is computed by the library and will join the reports with v0.5 ([#12](https://github.com/kunko-ai-labs/judge-audit/issues/12)).

## What a reader should take away

Report "coverage at error ≤ X %" with its bound, AUROC with its interval, and ECE as a diagnostic. When two judges differ, compare them on the same rows ([paired tests](judgment-models-vs-llms.md)). When a difference is smaller than the power analysis says the data can resolve, the report says "not resolved", never "no difference".

Sources: [reading list](reading-list.md) § Calibration and selective prediction.
