# Plan — from calibration audit to automation decision (October 2026)

**Status:** working plan, agreed with the maintainer on 2026-10-03. No release until phases A and B are merged and reviewed. Issue: [#122](https://github.com/kunko-ai-labs/judge-audit/issues/122) (phase A).

## Why

The v0.5 study ([results](v05-results.md), pre-registered in [v05-plan.md](v05-plan.md)) answers its questions honestly and mostly not in the direction the literature suggests: reading a model's own token probabilities is not reliably better than asking it (H1-lp not supported), and self-consistency makes confidence rank errors **worse** (T3, T4, T5 resolved in the opposite direction; T6 too under the re-reading). Its most useful finding for a deployer is not a hypothesis test at all: **accuracy does not order judges by what they let you automate.** On BANKING77 test (human-labelled), gemini-3.6-flash verbalized is more accurate than Jev (83.4 % vs 80.2 %), yet at a certified error of at most 10 % it automates 45.5 % of the texts against Jev's 72.3 % (seed spread 45.5–45.5 % and 72.0–73.4 %). That comparison is **exploratory** (computed in the report, not one of the eight pre-registered tests).

A team does not want an ECE; it wants a decision: *automate this share, at this threshold, with this guaranteed error, and send the rest to a human.* The library already computes that (`coverage_at_risk`, `coverage_at_risk_crossfit`, tested since #98 and used by the study); the product does not show it. Other tools audit calibration (ECE, Brier, reliability bins, CI gates); none we know of states a certified automatable share with the threshold to deploy.

## Phases

| phase | what | issue | gate |
|---|---|---|---|
| **A** | **Automation certificate** as the headline of every report, the CLI, the CI gate and the Action's PR comment | #122 | reviewer + QA |
| **B** | **Decision receipt** per judgment: "said 92 %; at this confidence the judge was right 78 % (n = 140, 95 % interval …), above / below the certified threshold → automated / escalated" | #11 | reviewer + QA |
| **C** | **Pre-register the next confirmatory study** on data no judge has been scored on (#106 held-out slice, or #94 real traffic): H3 "the judge with the higher accuracy is not the one that certifies the larger automatable share"; replication of the self-consistency result; the certificate's out-of-sample coverage | #94, #106 | frozen plan before any call |
| **D** | Public report cards per judge (versioned, every number linked to its checkpoint) and the 30-second "confidently wrong" demo, each with its caveats on the same screen | later | after A |
| **E** | Hosted weekly drift monitor | later | after customers |

Nothing merges to `main` until A and B are reviewed; PR #121 (the study) stays open and these branches build on it.

## Phase A — design

**What is certified.** For each question and each target risk *r* (default 1, 2, 5, 10 %; δ = 0.05):

1. **Units.** One unit per distinct text: its lowest confidence, right only if every row of that text is right (`aggregate_by_group`), so a repeated text is not counted as independent evidence. A text with any row lacking a confidence is never automated; it stays in the denominator.
2. **Deploy threshold** (`certify_threshold`): walk the units from the most confident down, one whole tie group at a time, and keep the lowest confidence whose top slice passes the exact one-sided binomial bound at *r*; stop at the first failure. The walk starts at the cut holding the units needed to certify *r* with 2 errors (D3 of the v0.5 plan: 628 / 313 / 124 / 61 at 1 / 2 / 5 / 10 %). Fixed-sequence testing (Learn then Test, Angelopoulos et al. 2025): **with probability at least 95 %, the error rate among decisions at or above the threshold is at most *r* — on traffic drawn like the labelled rows.**
3. **Out-of-sample check** (`coverage_at_risk_crossfit`, seed recorded): the threshold chosen on half the texts and applied to the other half, both ways; how much it automates and how many errors it makes there. This is the honest estimate of the share; the in-sample share of step 2 is what the deployed threshold covers on the labelled data.

**What the report must say next to the numbers.** The guarantee holds only if future traffic is drawn like the labelled rows (same mix, same judge version) and the labels are right (a label error counts as a judge error); each target is its own 95 % statement (reading the four together is not a 95 % statement about all four); with too few texts a target cannot be certified, and the report says how many it needs.

**Surfaces.** `audit-result.json` (`certificate`), the markdown and HTML reports ("Can I automate this?" first), the CLI summary line, `judge-audit check --min-coverage RISK:SHARE` (exit 1 when the certified share falls below), the Action (`min-coverage` input, the comment opens with the certificate), and every committed audit under `docs/` regenerated from its checkpoint.

**Not in phase A.** Any change to what is measured or to a published number other than adding the certificate; README rework (after B); a release.

## What we will not claim

- That the BANKING77 comparison above is confirmed: it is exploratory until phase C tests it on unseen data.
- That a certificate transfers to other traffic: it is a statement about traffic drawn like the labelled rows.
- "4 of 4" for self-consistency: under the pre-registered rule it is 3 of 4 in the opposite direction (T6 depends on the scoring rule).
