# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Added
- README charts redesigned (`scripts/charts_readme.py`): shared light/dark themes, rounded bars, direct labels, subtitles and footnotes; every chart ships in both themes and the README picks one with `<picture>`. Categorical palette validated for colour-vision deficiency in both themes.
- README hero chart `docs/assets/hero-arena.png`: zero-error coverage per judge under attack, drawn from the Arena JSON by `scripts/charts_readme.py`; demo gif retaped to show the Arena table.
- **Judge Arena** (`docs/arena-2026-09.md`, `scripts/arena_report.py`, `scripts/arena_run.sh`): the four published datasets run through several judges with every raw response under `docs/runs/arena/`; per judge: accuracy, ECE, zero-error coverage, confidence when right vs wrong, distinct confidence values, prompt-injection confidence drop, routing behaviour. Regenerated and diffed in CI.
- **`nli` judge**: local zero-shot NLI encoder (default `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`, MIT) as the small-model baseline — real softmax confidence, cannot follow instructions by construction, no cost. `pip install 'kunko-judge-audit[nli]'`.
- **`llm` judge**: `custom` provider (`LLM_PROVIDER_MODULE=/path/to/module.py` exposing `call(model, system, user)`) for hosted platforms without an OpenAI-compatible endpoint; `LLM_MODEL_LABEL` sets the name reports show; transient HTTP errors (429/502/503/504/529) are retried with backoff.
- `.env.example` documenting every credential the adapters read.

### Fixed
- `llm` judge: an OpenAI-compatible endpoint that does not finish in JSON mode within `LLM_TIMEOUT_S` (default 120 s, wall clock — a server trickling keep-alive bytes never trips the socket timeout) is asked again without `response_format` (observed with Gemini on one prompt).

## [0.3.2] — 2026-09-20

### Fixed
- `action.yml` description shortened to meet the Marketplace limit (125 chars); `.DS_Store` files untracked and ignored.

## [0.3.1] — 2026-09-20

### Added
- **GitHub Action** (`action.yml`, Marketplace): `mode: run | check`, inputs `labels`, `judge`, `baseline`, `max-ece-drift`, `max-acc-drop`, `comment`, `fail-on-drift`; outputs `accuracy`, `ece`, `zero-error-coverage`, `n`, `drift`. Report in the job summary, one sticky PR comment updated on every push (`scripts/pr_comment.py`), report + result + drift verdict + per-decision evidence uploaded as an artifact. Judge credentials come from the job `env`; the Action reads no secret. `.github/workflows/judge-audit.yml` dogfoods it: must pass on the committed baseline, must detect drift against an unreachable one.
- `judge-audit check --out/--json/--drift`: the gate can now also write the report, the metrics and a machine-readable verdict (`{ok, failures, ece, accuracy, baseline, thresholds}`).
- `examples/email-routing/baseline-simulated.json` and `baseline-strict.json`: committed baselines for the self-demo.

## [0.3.0] — 2026-09-19

### Added
- Launch video (`docs/launch/`): 24 s, landscape and vertical cuts, built with the brag recipe on Hyperframes from the real router numbers; reproducible compositions and the procedural music bed committed. Attached to the release.
- **MCP server** `judge-audit-mcp` (`[mcp]` extra): tools `run_audit`, `check_drift`, `list_judges` over stdio, so Claude Code, Cursor or any MCP client can audit a judge in place. Same engine as the CLI; simulated results carry the SIMULATED tag; unconfigured judges and missing files come back as structured errors. `docs/integrations.md`. (#20)

## [0.2.1] — 2026-09-19

### Changed
- Package renamed on PyPI to `kunko-judge-audit` (`judge-audit` was already taken). The CLI (`judge-audit`) and the module (`judge_audit`) are unchanged. First release actually published to PyPI.

## [0.2.0] — 2026-09-19

First public release.

### Added
- **Jev adapter** through the Vercel AI Gateway evaluate API (Node bridge) and the direct TypeSafe HTTP API; per-option descriptions are passed as `criteria`. `JEV_ENDPOINT` points the direct client at any Jev-compatible server (OpenJev), key optional.
- **`llm` adapter**: any chat model as a judge with verbalized confidence — Claude through the official SDK (`[anthropic]` extra), or any OpenAI-compatible endpoint (OpenAI, Ollama, vLLM). Prices for known models; unknown models report cost 0 and say so.
- **Three independent audits of Jev**, each with its dataset generator, raw checkpoint under `docs/runs/`, report and JSON: clean business emails (n=200), adversarial emails (n=200: prompt injection, homoglyphs, ambiguity, PII, social engineering), task routing (n=120, bare option labels: 66.7 %, ECE 0.318, never chose the strong model) and the same 120 rows with one-line option descriptions (97.5 %, ECE 0.053) — see `docs/audit-jev-router-ablation.md`.
- **Provenance** in every report and JSON: model, backend, timestamp, dataset SHA-256, judge-audit version. The resumable driver records it as the first line of each checkpoint.
- `--judgments`: per-decision evidence written as JSONL by `judge-audit run`.
- `scripts/verify_published.py`: recomputes every published audit from its checkpoint; runs in CI.
- Router analysis reports the constant-classifier baseline, the number of distinct task texts, the confidence range on wrong decisions and whether the judge ever chose the strong model — before any headline.
- `judge-audit --version`; exit-code contract `0 / 1 (drift) / 2 (usage or configuration)`.
- Tests (metrics on hand-checked inputs, runner, CLI contract, published-audit reproducibility, dataset regeneration), CI matrix 3.10–3.12, ruff.
- LICENSE (Apache-2.0), CONTRIBUTING, SECURITY, CODEOWNERS, Dependabot, roadmap, this changelog.

### Fixed
- The direct TypeSafe backend sent `options` and read answers at the top level; the documented API takes `criteria` and returns them under `answers`. It had never been exercised.

### Changed
- License from MIT (declared, no file) to Apache-2.0 (file included), aligned with the rest of Kunko AI Labs.
- Build backend to hatchling; `charts` extra (matplotlib) is now declared — `--format html` used to fail with a hint to install an extra that did not exist.
- Configuration errors (no API key, missing file) now exit 2 with the fix in the message instead of a traceback.

## [0.1.0] — 2026-09-18

Scaffold: judge interface, simulated judge, calibration metrics, Markdown/HTML report, `check` gate, seeded email-routing dataset.
