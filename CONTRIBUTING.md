# Contributing

## What lives where

| Path | Audience | What |
|---|---|---|
| `src/judge_audit/` | developers | the harness: judge interface, adapters, calibration metrics, runner, reports, CLI |
| `examples/` | users, tests | seeded synthetic datasets, each with the `generate.py` that produced it |
| `docs/audit-*.md` / `.json` | users, buyers, auditors | published audits — every number re-derivable from `docs/runs/` |
| `docs/runs/` | auditors | raw per-row judge responses (checkpoints) behind each published audit |
| `docs/assets/` | readers | charts referenced by the reports and the README |
| `scripts/` | maintainers | resumable audit driver, per-audit analysis, issue tooling |
| `tests/` | developers | contract tests: metrics on known inputs, exit codes, report shape, reproducibility |

## The house rule: no number without its evidence

A published audit is three files that agree with each other: the dataset (`examples/*/labels.jsonl`), the raw checkpoint (`docs/runs/*.ckpt.jsonl`) and the report (`docs/audit-*.md` + `.json`). `scripts/verify_published.py` recomputes every report from its checkpoint and CI fails if they drift. A PR that changes a report without changing its checkpoint, or the other way round, is wrong by construction.

Simulated output is always labelled **SIMULATED**. Never present it as a vendor audit.

## Adding a judge

Implement `Judge.decide(state, questions) -> [Judgment]` in `src/judge_audit/judges/` (see `base.py`), return the *probability of the chosen option* as `confidence` — that is the claim we audit — and implement `describe()` so reports can say what model and backend produced them. Register it in `cli.py`. Add a test that runs it against `examples/email-routing/labels.jsonl` with the network mocked.

## Adding a dataset

A seeded `generate.py` that writes `labels.jsonl`. Rows are `{state, questions, labels, _meta}`; `_meta` carries whatever the analysis needs (attack type, difficulty, target). State in the docstring how ground truth was obtained and what the dataset cannot show, and declare it machine-readably: the first line of the file is a dataset header with the [ground-truth tier](docs/ground-truth.md) and its caveats, which every report prints next to the accuracy. CI regenerates every dataset and fails if the committed file differs.

## Issues

Templates under `.github/ISSUE_TEMPLATE/`: 🎯 Epic `[EP-XXX]`, 📖 User Story `[US-XXX-YYY]`, 🐛 Bug `[BUG]`. Labels: `type:*`, `priority:*`, `status:*`, `area:*` (metrics, runner, judge, report, docs, integration).

## Pull requests

Title `type(scope): [ID] Description`. Squash-merged; the title becomes the commit. Before you push: `ruff check src tests scripts examples && pytest -q && python scripts/verify_published.py`.

## Review

This is a single-maintainer repository, and branch protection does **not** require a GitHub approving review. GitHub does not let an author approve their own pull request, so with one maintainer a required approval could only be satisfied by an admin bypass on every merge — and on classic branch protection that bypass skips failing CI as well, which is weaker than requiring the checks alone.

The independent review happens outside GitHub's approval button, and is recorded on the PR:

1. the `story-reviewer` agent — an adversarial, read-only review that recomputes the statistics by hand and checks every acceptance criterion against the diff;
2. the `release-qa` agent — a clean-room install from the branch, CLI / MCP / Action smoke, report-regeneration diff, tests on every supported Python;
3. a human read of the PR by the maintainer before the squash-merge.

That is not the same as a second person's approval, and we do not claim it is. An external reviewer is sought; when one joins, `required_approving_review_count` in `scripts/protect_main.sh` goes to 1.

## Working with Claude Code

`CLAUDE.md` holds the house rules; `.claude/agents/` defines the four agents a story goes through — `story-implementer` (opens the PR), `story-reviewer` (adversarial, read-only), `release-qa` (clean-room install and smoke), `audit-runner` (paid model runs with clean provenance). None of them merges. A story is done when all three verdicts are green and a human has read the PR.

## Branches

- `main` — releasable at all times; tags `vX.Y.Z`. Protected as `scripts/protect_main.sh` configures it: a pull request is required (the single admin can still bypass; `enforce_admins` is off), linear history, no force-push, no deletion, and the `test (3.10/3.11/3.12)`, `datasets` and CodeQL (`analyze`) checks green before merge. No GitHub approving review is required — see [Review](#review) for why and for what replaces it.
- `release/vX.Y.Z` — one per release, off `main`; version bump + changelog; PR into `main`, then tag. See [docs/RELEASING.md](docs/RELEASING.md).
- `feat/*`, `fix/*`, `docs/*`, `audit/*` — short-lived, PR into `main`.
