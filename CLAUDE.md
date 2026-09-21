# judge-audit — project rules for Claude Code

Calibration audits for AI judges: "when it says 90 %, is it right 90 % of the time?" Everything here serves one promise: **no published number without its evidence**.

## House rules (they override convenience)

- **Evidence first.** Every number in README, `docs/` or a release note recomputes from a committed raw checkpoint (`docs/runs/**.ckpt.jsonl`). `scripts/verify_published.py`, `scripts/arena_report.py`, `scripts/consensus_report.py` and `scripts/jury_report.py` regenerate the reports and CI diffs them. If you cannot recompute it, you cannot publish it.
- **Deterministic metrics.** No LLM anywhere in the measurement. Confidence is what the judge declares (Jev: P(chosen option); chat models: the verbalized number). Unknown confidence is reported, never imputed.
- **Pre-register before you run.** An experiment's protocol, jury, metrics and predictions are committed before the first API call (see `docs/jury-consensus-plan.md`). Results are published whether or not the predictions hold.
- **Models, not platforms.** Hosted models are named by model (`claude-sonnet-4.5`, `llama-3.3-70b`, `deepseek-r1`) with provider `hosted-api`. The cloud platform behind them is never mentioned — not in code, docs, commits, PRs, issues, provenance or logs.
- **Credentials never enter the repo.** `.env` is git-ignored; private provider modules live in `~/.config/judge-audit/`. Never print a key, never paste one into a file.
- **Caveats travel with the numbers.** Synthetic datasets, ground truth by construction, small n: say it in the same table or paragraph, not in a footnote nobody reads.
- **No composite scores.** Accuracy, ECE, zero-error coverage, confidence when wrong, cost, latency stay separate. The reader decides.
- **English everywhere in the repo.** Commits imperative with `feat|fix|docs|ci|test|chore|audit(scope): [US-XXX-YYY] …` when a story applies.

## How to work

- Environment: `.venv` with `pip install -e ".[dev,charts,mcp]"`. Before pushing: `ruff check src tests scripts examples && pytest -q && python scripts/verify_published.py`.
- Branches: `main` (protected) + `release/vX.Y.Z`; short-lived `feat/*`, `fix/*`, `docs/*`, `audit/*`, `chore/*`. There is no `develop`. Deleting a branch that is the base of an open PR closes the PR.
- PRs are squash-merged; the title becomes the commit. `gh pr edit` can fail on this repo (projects API) — use `gh api -X PATCH repos/kunko-ai-labs/judge-audit/pulls/N`.
- Releases: `docs/RELEASING.md`. Marketplace listing is manual after the tag.
- Long model runs go through `scripts/audit_resumable.py` / `scripts/arena_run.sh` (checkpointed, resumable). Run them in the background and poll the checkpoint row count; never stash or checkout a checkpoint that a running driver is appending to.

## Agents (`.claude/agents/`)

A user story moves through three agents, each in its own worktree, none of them merging its own work:

| Agent | Does | Never |
|---|---|---|
| `story-implementer` | reads the issue, writes tests first, implements, regenerates reports, opens the PR | merges, edits `.env`, mentions a platform |
| `story-reviewer` | independent review: recomputes statistics by hand, checks every acceptance criterion against the diff, wording, house rules | edits code |
| `release-qa` | clean install from the branch, CLI / MCP / Action smoke, report regeneration diff, tests on all supported Pythons | approves with a failing step |
| `audit-runner` | runs a judge over the datasets with credentials from the environment, checkpoints committed, provenance clean | prints or commits a key |

Nothing merges without implementer + reviewer + QA green and a final human-level critique.
