# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow SemVer.

## [Unreleased]

### Fixed
- `llm` judge: the reply parser scans every candidate JSON object (prose containing `{`, fenced JSON followed by a reasoning paragraph) and prefers one with an `answers` key; `parse_reply()` is pure so `scripts/reparse_checkpoints.py` recomputes decisions offline from the raw text kept in checkpoints. Re-parsed 14 Claude Sonnet 4.5 router replies the old parser had counted as blank (router, described options: 88.3 % → 95.0 %); the reparse is recorded in the checkpoint headers. `LLM_MAX_TOKENS` for the Anthropic path; `docs/judges.md` documents token budgets for reasoning models. DeepSeek R1 rerun on the four datasets with a 4,096-token budget (43 of its 480 replies had been empty at 1,024 tokens, counted as wrong at confidence 0): under attack 76.5 % → 80.5 %, but ECE 0.074 → 0.127 and confidence when wrong 0.51 → 0.90 — the earlier "drops when wrong" reading was an artefact of truncation; 2 of 240 router replies still exhaust 4,096 tokens and stay blank.

### Added
- **Fine-tuned classifier baseline on a pre-registered held-out split** (`--judge finetuned`, `src/judge_audit/judges/finetuned.py`, `docs/finetuned-baseline-2026-09.md`): the answer to "isn't a judgment model just a classifier?". `scripts/split_heldout.py` writes a seeded (2026), label-stratified 50/50 split of row indices (`examples/<dataset>/split-heldout.json`; the router stratum also fixes difficulty and attack flag) — committed, with the prediction, before any training run; CI regenerates it. `scripts/train_classifier.py --dataset <name>` fine-tunes `microsoft/deberta-v3-base` on the train half only (seed 2026, 10 epochs, lr 2e-5, batch 8, 256 tokens, fp32, laptop MPS) and records hyper-parameters, loss curve, wall time, hardware, backbone revision and the sha256 of the train rows in `docs/runs/finetuned/<dataset>.train.json`; the model lives under `~/.cache/judge-audit/finetuned/` and is never committed. The judge's confidence is the softmax probability of the chosen option; it reads only the state text (no instructions, no option descriptions — documented). `scripts/audit_resumable.py --rows <split.json>:heldout` judges only a pre-registered subset and records the split and its sha256 in the checkpoint header; `scripts/arena_run_heldout.sh` runs the four datasets that way (email-adversarial in full as a robustness test); `scripts/arena_report.py` sets held-out runs aside from the main table (their n differs) and points to the held-out report. `scripts/heldout_report.py` re-scores every Arena judge on the same held-out rows next to the fine-tuned model — accuracy, ECE, zero-error coverage, confidence right/wrong, no-answer count, cost — scores the four pre-registered predictions mechanically and carries the caveats (synthetic GT-1 data, train and test rows from the same generator); CI diffs it. The zero-shot NLI judge is now documented as the *control*, not a competitor. Results (held-out, same generator as training): run 1 (pre-registered, 10 epochs) 100 % on the clean half (n=100), 97.0 % under attack (n=200), 100 % on the router half (n=60), but under-confident (ECE 0.458) — 0 of 3 testable predictions hold. A disclosed post-hoc amendment adds run 2 (`--run 2`: 20 % of the train half becomes a seeded validation slice, early stopping on train loss, cap 40 epochs) and temperature scaling (Guo et al. 2017; `temperature` in the model's `judge-audit.json`, `FINETUNED_TEMPERATURE` override): run 2 converges in 19 / 15 epochs and calibrates (clean ECE 0.017; under attack 99.0 %, ECE 0.048), the temperature is not identified because both validation slices are classified perfectly, and scaling only sharpens (confidence when wrong under attack 0.61 → 0.92) — reported as such. The report also counts, next to every n, the held-out rows whose text equals or contains a training text (the generators repeat texts, #54: 20/100 clean emails, 40/60 router rows, 49/200 attacked emails) and reports accuracy on unseen-text rows for every judge. `scripts/arena_run_heldout.sh`; README hero chart regenerated with the fine-tuned rows.
- **Error correlation and jury composition** (`scripts/consensus_report.py` → `docs/consensus-2026-09.md/.json`, `error_correlation` and `jury_composition`): for every judge pair, over the rows where both answered (a blank is an abstention; n stated per pair): agreement, joint error rate, P(A wrong | B wrong), P(B wrong | A wrong), error-set Jaccard and the phi coefficient between the two error indicators (`null` when a judge has no error — or no correct answer — on the compared rows). Per dataset: a phi matrix, the full pair table and a one-line reading of the most and least correlated pairs. On the 40 hard routing tasks, every 3-judge jury from the frozen panel (`docs/runs/jury/panel.json`, 56 juries): majority accuracy (ties as no decision) and decided-rows accuracy, ties, vote-share ECE, mean pairwise phi on the hard rows and on all 120 rows, shared-wrong cases, cost per 120 rows and p50 latency from the Arena JSON, sorted by majority accuracy, no composite; plus the Spearman correlation between mean phi and majority accuracy across juries. README states the finding; tests with hand-computed fixtures for every statistic.
- Arena report: a `no answer` column per judge per dataset (blank, unparseable replies — counted as wrong elsewhere, visible on their own here) and a "Why these judges" section stating what each judge stands for, that the zero-shot NLI judge is a control, and what is deliberately missing.
- **Ground-truth provenance tiers** (`src/judge_audit/ground_truth.py`, `docs/ground-truth.md`): `GT-0 unknown` … `GT-6 production outcome`, a provenance class that says what an accuracy is evidence of. A labels JSONL declares its tier with a first-line dataset header `{"idx": -1, "dataset": {"ground_truth": {...}}}`; an unknown tier fails at load. `run_metadata` records `dataset.ground_truth` (and `sha256_rows`, the digest of the rows alone); every Markdown/HTML report header shows `Ground truth: GT-1 constructed — <meaning>; <caveats>` (or `GT-0 unknown` with a hint — never silent); the CLI summary prints `gt=GT-1`; the MCP `run_audit` result, `check_drift` and the Action's PR comment show the tier next to accuracy; Arena dataset headings carry it. The four published datasets declare GT-1 with their caveats (routing label by design, downstream task quality not measured, email categories synthetic and seeded). `runner.load_dataset(path) -> (rows, dataset)` is new; `load_jsonl` still returns rows only. `scripts/verify_published.py` now also checks every checkpoint's recorded dataset `sha256` against the labels file (whole file or rows only).
- `CLAUDE.md` (house rules for Claude Code) and `.claude/agents/`: `story-implementer`, `story-reviewer`, `release-qa`, `audit-runner` — the pipeline every user story goes through; documented in CONTRIBUTING.
- Arena: Gemini 3 Flash on the four datasets (97.0 % under attack, ECE 0.015, confidence 0.98 whether right or wrong); README table and hero chart regenerated.
- Logo (`docs/assets/logo.png`, `logo-dark.png`, SVG sources): the reliability diagram as the mark; README header picks the theme with `<picture>`.
- **Consensus audit** (`scripts/consensus_report.py` → `docs/consensus-2026-09.md`): the Arena judges read as a jury — pairwise agreement, unanimity, majority accuracy vs best single judge, vote share when right vs wrong, declared confidence of wrong majorities, vote share scored as a confidence (ECE, zero-error coverage) next to each judge's own, and the spread across every three-judge jury. Round 1 of #39, no new API call, diffed in CI.
- **Deliberation round** (`scripts/jury_deliberate.py`, `scripts/jury_report.py` → `docs/jury-consensus.md`): each judge re-votes after seeing the panel's anonymised round-1 votes; protocol and predictions pre-registered in `docs/jury-consensus-plan.md` before any call; inputs and raw answers under `docs/runs/jury/`. Run on seven judges × two router prompts under the amended protocol (blank answers are abstentions, ties are no decision, frozen 8-judge panel checked in CI); the report scores the four predictions mechanically (two held, one partly, one did not).
- README charts redesigned (`scripts/charts_readme.py`): shared light/dark themes, rounded bars, direct labels, subtitles and footnotes; every chart ships in both themes and the README picks one with `<picture>`. Categorical palette validated for colour-vision deficiency in both themes.
- README hero chart `docs/assets/hero-arena.png`: zero-error coverage per judge under attack, drawn from the Arena JSON by `scripts/charts_readme.py`; demo gif retaped to show the Arena table.
- **Judge Arena** (`docs/arena-2026-09.md`, `scripts/arena_report.py`, `scripts/arena_run.sh`): the four published datasets run through several judges with every raw response under `docs/runs/arena/`; per judge: accuracy, ECE, zero-error coverage, confidence when right vs wrong, distinct confidence values, prompt-injection confidence drop, routing behaviour. Regenerated and diffed in CI.
- **`nli` judge**: local zero-shot NLI encoder (default `MoritzLaurer/deberta-v3-base-zeroshot-v2.0`, MIT) as the small-model baseline — real softmax confidence, cannot follow instructions by construction, no cost. `pip install 'kunko-judge-audit[nli]'`.
- **`llm` judge**: `custom` provider (`LLM_PROVIDER_MODULE=/path/to/module.py` exposing `call(model, system, user)`) for hosted platforms without an OpenAI-compatible endpoint; `LLM_MODEL_LABEL` sets the name reports show; transient HTTP errors (429/502/503/504/529) are retried with backoff.
- `.env.example` documenting every credential the adapters read.

### Fixed
- Consensus and jury reports index panel votes by row id, so a resumed run whose redone rows were appended out of order no longer misaligns judges.
- `llm` judge: a reply that carries a complete JSON object followed by garbage (Gemini's JSON mode sometimes appends fragments) parses as the object instead of counting as an unparseable, zero-confidence answer.
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
