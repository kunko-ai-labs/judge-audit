# v0.6 plan, amendment A1 (2026-10-12): Jev en-US checkpoint written by two processes; rerun

**Governs:** the study run `jev` on `en-US` (plan §11). Committed, and its sha256 committed in public judge-audit `docs/v06-amendments.sha256`, before the rerun's first call. Plan: sha256 `aef725edbaa078e0c3956757709e95ae1ce01364d72451df9c7d1e7bc35863b6` (tag `v06-plan-freeze`).

## What happened

The hosted-run script was started twice by mistake, at 19:09:34Z and at 19:21:03Z on 2026-10-12, at the freeze commit `43e7e1e`. Both copies ran `scripts/audit_resumable.py` on `examples/massive/labels-test-en-US.jsonl` with `--judge jev` into the same checkpoint, `docs/runs/v06/jev-en-US.ckpt.jsonl`. The second copy resumed at row 2266, while the first was still writing, so from row 2266 on the two processes judged the same rows and both appended them. The second copy was stopped at about 19:25Z. Rows judged twice: 542 when it was stopped. The first copy was left running and completes the file. No other checkpoint was written by the second copy (it was stopped before its first run ended).

No accuracy, calibration or other result has been computed or read from this checkpoint.

## What is done

1. The checkpoint is kept byte for byte, renamed `docs/runs/v06/jev-en-US.ckpt.duplicate-writes.jsonl`, committed with the study's evidence and reported in the study record as this incident. **No figure is computed from it.** It is not deduplicated: published evidence is never rewritten, and choosing one of two answers per row after the fact is a choice the plan did not fix.
2. Jev on `en-US` is rerun from row 0 into a new `docs/runs/v06/jev-en-US.ckpt.jsonl`, with the same code (the freeze commit `43e7e1e`), data and settings as the other Jev runs, after Jev's `es-ES` and `ca-ES` runs. Its `--max-usd` is Jev's ceiling ($0.50, plan §10) minus the recorded cost of every other Jev checkpoint of the study, the incident file included, so the incident's calls count against the ceiling.
3. Every Jev figure of the study comes from the rerun (`en-US`) and the two other locales. The study record gives the incident file's sha256, its row and duplicate counts, and its recorded cost.
4. The run script now refuses to start while another copy holds its lock.
