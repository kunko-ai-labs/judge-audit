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

A seeded `generate.py` that writes `labels.jsonl`. Rows are `{state, questions, labels, _meta}`; `_meta` carries whatever the analysis needs (attack type, difficulty, target). State in the docstring how ground truth was obtained and what the dataset cannot show. CI regenerates every dataset and fails if the committed file differs.

## Issues

Templates under `.github/ISSUE_TEMPLATE/`: 🎯 Epic `[EP-XXX]`, 📖 User Story `[US-XXX-YYY]`, 🐛 Bug `[BUG]`. Labels: `type:*`, `priority:*`, `status:*`, `area:*` (metrics, runner, judge, report, docs, integration).

## Pull requests

Title `type(scope): [ID] Description`. Squash-merged; the title becomes the commit. Before you push: `ruff check src tests scripts examples && pytest -q && python scripts/verify_published.py`.

## Branches

- `main` — releasable at all times; tags `vX.Y.Z`. Protected: linear history, CI required, no force-push.
- `release/vX.Y.Z` — one per release, off `main`; version bump + changelog; PR into `main`, then tag. See [docs/RELEASING.md](docs/RELEASING.md).
- `feat/*`, `fix/*`, `docs/*`, `audit/*` — short-lived, PR into `main`.
