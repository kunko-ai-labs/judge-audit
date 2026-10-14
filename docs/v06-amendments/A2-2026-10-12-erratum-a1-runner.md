# v0.6 plan, amendment A2 (2026-10-12): erratum to A1, and the order of hosted runs

**Governs:** every hosted study run from now on, and the Jev `en-US` rerun of A1. Committed, and its sha256 committed in public judge-audit `docs/v06-amendments.sha256`, before the first call it governs. Plan: sha256 `aef725edbaa078e0c3956757709e95ae1ce01364d72451df9c7d1e7bc35863b6` (tag `v06-plan-freeze`). A1: sha256 `09ceb3a4e8da5adec32ad47f266548ea5f2f4c3bcaf69592cf2bda4a7ca51bd1`. A1 is not edited; this amendment corrects it. Both were checked by an independent review before this commit.

## Corrections to A1

1. **A report was written from the incident checkpoint.** When the first copy finished `en-US` (19:24:41Z), `scripts/audit_resumable.py` wrote its usual report files (Markdown, JSON and a log line) from the double-written checkpoint, outside the repository. Nobody opened them. They were deleted unread at about 19:37Z, after recording their sha256: JSON `d817bace90a9e5b9c04767566ed61511dc6655999f066ff49cfe7c649fa8589c`, Markdown `782e1af0674bd7f32fde0970bbb3a0864bf5897956473b261f259ea72f62e712`, log `e14d88007e64ac090b599ef57d80410c2b12f1e89c956dee0ff7f450262ceb99`. A1's "no result has been computed" should read: no result has been read or used; the driver's automatic report was deleted unread.
2. **The second copy stopped at 19:23:40Z**, not "about 19:25Z".
3. **What the first copy did after `en-US`.** Its Jev `es-ES` and `ca-ES` runs exited at argument parsing without any call (the per-locale ceiling it passed had more than 6 decimal places, which `--max-usd` refuses). It then started `gpt-6-luna` `en-US` and was stopped at about 19:25:41Z with 135 rows written; that checkpoint is valid and is resumed, not restarted.
4. **A second run script** (started 19:27:17Z) ran Jev `es-ES` with `--max-usd 0.383708` ($0.50 minus the incident's recorded $0.116291). It was stopped at 19:36:58Z, with 1,975 rows written, because it could start a later locale, or the A1 rerun, after an incomplete one. That checkpoint is valid and is resumed under the ceiling in its header.

## Order of hosted runs (from now on)

- A judge's locales run in turn (Jev: `es-ES`, `ca-ES`, then the A1 `en-US` rerun; others: `en-US`, `es-ES`, `ca-ES`), and the next one starts only when the previous checkpoint holds all 2,974 rows. A locale that ends incomplete stops that judge until it is resumed. So each locale's ceiling (the judge's ceiling minus what its other checkpoints recorded when it started) never overlaps another's.
- The Jev `en-US` rerun starts only when Jev `es-ES` and `ca-ES` each hold 2,974 rows.
- One run script, with one lock: a second copy refuses to start.
