# v0.6 plan, amendment A3 (2026-10-13): gemini-3.6-flash ceiling from its measured rate; judges in parallel

**Governs:** the `gemini-3.6-flash` study runs from `ca-ES` on, and the hosted runs of Clef-flash, Microsoft-Decision-1 and deepseek-r1. Committed, and its sha256 committed in public judge-audit `docs/v06-amendments.sha256`, before the first call it governs. Plan: sha256 `aef725edbaa078e0c3956757709e95ae1ce01364d72451df9c7d1e7bc35863b6` (tag `v06-plan-freeze`); amendments A1 and A2 apply.

## 1. gemini-3.6-flash ceiling

The plan's §10 set gemini-3.6-flash's ceiling at $5 from an estimate ($3.2 for 8,922 rows), because it had no v0.6 pilot. Its first study locale, `en-US`, recorded $1.8961 for 2,974 rows (checkpoint `cost_usd`), so the three locales come to about $5.69: the $5 ceiling would stop `ca-ES` partway.

The ceiling is set again by the same §10 rule, on this measured rate instead of the estimate: $1.8961 / 2,974 × 8,922 × 1.5 = $8.53, rounded up to **$9**. The per-judge ceilings then add up to $85 (Jev $0.50, gpt-6-luna $1, claude-sonnet-4.5 $39, gemini-3.6-flash $9, Clef-flash $1, Microsoft-Decision-1 $0.50, deepseek-r1 $34), under the $115 budget (D10). Recorded cost of the study at this amendment: $30.31, every checkpoint included.

- `es-ES`, already started, continues under the ceiling in its header ($3.103947).
- `ca-ES` starts with $9 minus what `en-US` and `es-ES` recorded.
- The rate comes from the study's own `en-US` rows. No accuracy, calibration or other result was read to set it.

## 2. Judges in parallel

The run script of A2 runs one judge after another. From now on two copies may run at once, on different judges, with one lock per judge, so a judge is never run by two copies. Within a judge, A2's rule holds: its locales run in turn, and the next starts only when the previous holds all 2,974 rows. The running single-lock script is stopped between two requests, which the resumable driver allows. Then one copy runs gemini-3.6-flash, and another runs Clef-flash, Microsoft-Decision-1 and deepseek-r1, in that order. The judges, settings and ceilings are those of the plan and of §1 above. Only the order in time changes.
