# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [0.2.0] — 2026-09-19

First public release.

### Added
- **Jev adapter** through the Vercel AI Gateway evaluate API (Node bridge) and the direct TypeSafe endpoint; per-option descriptions are passed as SDK criteria.
- **Three independent audits of Jev**, each with its dataset generator, raw checkpoint under `docs/runs/`, report and JSON: clean business emails (n=200), adversarial emails (n=200: prompt injection, homoglyphs, ambiguity, PII, social engineering), task routing (n=120) with the option-description ablation.
- **Provenance** in every report and JSON: model, backend, timestamp, dataset SHA-256, judge-audit version. The resumable driver records it as the first line of each checkpoint.
- `--judgments`: per-decision evidence written as JSONL by `judge-audit run`.
- `scripts/verify_published.py`: recomputes every published audit from its checkpoint; runs in CI.
- Router analysis reports the constant-classifier baseline, the number of distinct task texts, the confidence range on wrong decisions and whether the judge ever chose the strong model — before any headline.
- `judge-audit --version`; exit-code contract `0 / 1 (drift) / 2 (usage or configuration)`.
- Tests (metrics on hand-checked inputs, runner, CLI contract, published-audit reproducibility, dataset regeneration), CI matrix 3.10–3.12, ruff.
- LICENSE (Apache-2.0), CONTRIBUTING, SECURITY, CODEOWNERS, Dependabot, roadmap, this changelog.

### Changed
- License from MIT (declared, no file) to Apache-2.0 (file included), aligned with the rest of Kunko AI Labs.
- Build backend to hatchling; `charts` extra (matplotlib) is now declared — `--format html` used to fail with a hint to install an extra that did not exist.
- Configuration errors (no API key, missing file) now exit 2 with the fix in the message instead of a traceback.

## [0.1.0] — 2026-09-18

Scaffold: judge interface, simulated judge, calibration metrics, Markdown/HTML report, `check` gate, seeded email-routing dataset.
