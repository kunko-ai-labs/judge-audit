# v0.6 plan, amendment A4 (2026-10-13): two exploratory views of refused requests

**Governs:** the analysis of the v0.6 study (`scripts/v06_study.py`). Committed, and its sha256 committed in public judge-audit `docs/v06-amendments.sha256`, before the analysis is run on the study's checkpoints. Plan: sha256 `aef725edbaa078e0c3956757709e95ae1ce01364d72451df9c7d1e7bc35863b6` (tag `v06-plan-freeze`); amendments A1–A3 apply. These views were chosen without looking at any result. For the record: on 2026-10-13 at about 15:00Z the analysis script was dry-run on a snapshot of the checkpoints then complete, to check that it runs end to end; only the section headings of its output were looked at, and the output was deleted unread at about 17:35Z. One driver log line showing Laya multilingual's `en-US` accuracy was seen while fixing that run's settings. The refusal counts used in the reason below come from the run record, not from any result.

## Why

A hosted decision API may refuse a request. The plan counts a refusal as an answer without a usable confidence, against the judge, and that rule is unchanged. A buyer also needs two facts the plan's tables do not show: how a judge does on the requests it accepts, and which requests it refuses.

## What is added (exploratory, not pre-registered)

For every judge whose checkpoints record refusals (`raw.refusal`), per locale:

1. **Accepted requests only.** The secondary metrics of the plan (accuracy with its Wilson interval, AUROC, ECE and MCE, Brier, validated coverage at 1 / 2 / 5 / 10 %) recomputed on the rows the judge did not refuse, printed next to the plan's figures.
2. **What it refuses.** The count of refused requests by MASSIVE scenario (the intent's domain, e.g. `alarm`, `email`) and by gold intent, with the share of that scenario's rows.

Both are labelled "exploratory, not pre-registered (amendment A4)" on every row. Neither enters any test, Holm, prediction or headline. The plan's figures for every judge stay as the plan defines them.
