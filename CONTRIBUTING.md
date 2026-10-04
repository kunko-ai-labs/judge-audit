# Contributing

judge-audit checks whether an AI judge's confidence can be trusted, on decisions people already labelled. Contributions that make that measurement more correct, more reproducible or easier to run are welcome.

## What helps most

| Contribution | What to send |
|---|---|
| **A bug in a metric or a report** | An issue with the smallest input that reproduces it, the number you got and the number you expected, and why. A failing test is the best bug report. |
| **A new judge adapter** | A PR adding `src/judge_audit/judges/<name>.py` (see [Adding a judge](#adding-a-judge)), with tests that mock the network. |
| **A new labelled dataset** | A PR with a seeded `generate.py` or a pinned public source, its licence, and its ground-truth tier (see [Adding a dataset](#adding-a-dataset)). |
| **An audit you ran** | The checkpoint (`docs/runs/…`), the command that produced it, and the report regenerated from it. Numbers without their checkpoint are not merged. |
| **Docs** | Corrections, clearer explanations, a missing caveat. |

Out of scope: building or selling a judge, ranking vendors without published evidence, features unrelated to measuring a judge. If you are unsure, open an issue first and ask.

## The house rule: no number without its evidence

A published audit is three files that agree with each other: the dataset (`examples/*/labels.jsonl`), the raw checkpoint (`docs/runs/*.ckpt.jsonl`) and the report (`docs/audit-*.md` + `.json`). `scripts/verify_published.py` recomputes every report from its checkpoint and CI fails if they drift; `scripts/verify_readme.py` does the same for every figure in the README. A PR that changes a report without its checkpoint, or the other way round, is wrong by construction.

- Simulated output is always labelled **SIMULATED**; never present it as a vendor audit.
- No LLM inside a measurement; metrics are deterministic.
- A judge adapter never invents a confidence; an unknown confidence is reported as unknown.
- API keys never appear in code, logs, checkpoints or reports.
- Hosted models are named by model, not by the platform that served them.

## Development

```bash
git clone https://github.com/kunko-ai-labs/judge-audit && cd judge-audit
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check src tests scripts examples && mypy && pytest -q
python scripts/verify_published.py && python scripts/verify_readme.py
```

Python 3.10–3.12. Tests come first: a new metric is tested on inputs whose answer you can compute by hand.

## Adding a judge

Implement `Judge.decide(state, questions) -> [Judgment]` in `src/judge_audit/judges/` (see `base.py`), return the *probability of the chosen option* as `confidence` — that is the claim we audit — and implement `describe()` so reports can say what model and backend produced them. Register it in `cli.py`. Add a test that runs it against `examples/email-routing/labels.jsonl` with the network mocked.

## Adding a dataset

A seeded `generate.py` that writes `labels.jsonl`, or a fetch script pinned to an upstream file and its hash. Rows are `{state, questions, labels, _meta}`. The first line of the file is a dataset header with the [ground-truth tier](docs/ground-truth.md) and its caveats, which every report prints next to the accuracy. CI regenerates every dataset and fails if the committed file differs.

## Issues

Use the templates: 🐛 bug report, or 💡 proposal for a judge, a dataset or an audit. Security problems (a key in a log, a fabricated confidence presented as measured) go to the [private advisory](https://github.com/kunko-ai-labs/judge-audit/security/advisories/new), never a public issue.

## Pull requests

- Title `type(scope): description` (`feat`, `fix`, `docs`, `test`, `chore`, `audit`); squash-merged, so the title becomes the commit.
- Small and focused; link the issue it closes.
- CI green: tests on 3.10–3.12, dataset regeneration, report regeneration, CodeQL.
- Say in the PR what you verified and how; a reviewer will recompute any number you add.

## Review

This is a single-maintainer repository, and branch protection does **not** require a GitHub approving review: GitHub does not let an author approve their own pull request, so with one maintainer a required approval could only be satisfied by an admin bypass on every merge, which on classic branch protection also skips failing CI. Instead, every pull request that changes code, data or reports gets an independent, adversarial review that recomputes the statistics and checks each claim against the diff, a clean-room install with the tests on every supported Python and a smoke test of the CLI, the MCP server and the Action, and the maintainer's own read, before a squash-merge on green CI. Dependency bumps get CI and the maintainer's read. That is not a second person's approval, and we do not claim it is; when an external reviewer joins, `required_approving_review_count` in `scripts/protect_main.sh` goes to 1.

## Branches

- `main` — releasable at all times; tags `vX.Y.Z`. Protected as `scripts/protect_main.sh` configures it: pull request required, linear history, no force-push, no deletion, and the `test (3.10/3.11/3.12)`, `datasets` and CodeQL checks green before merge.
- `release/vX.Y.Z` — one per release; see [docs/RELEASING.md](docs/RELEASING.md).
- `feat/*`, `fix/*`, `docs/*`, `audit/*` — short-lived, PR into `main`.
