# Roadmap

What shipped, what is next, and why. Issues on GitHub are the live backlog; this file is the narrative.

| Version | What | Why |
|---|---|---|
| v0.1 (done) | Harness: pluggable `Judge`, shadow-mode runner, ECE + reliability bins + accuracy-coverage + zero-error coverage, cost and p50/p99, Markdown/HTML reports, `check` CI gate, simulated judge | The questions a buyer asks before automating, answerable without trusting the vendor |
| v0.2 (done) | **First independent audits of a vendor judge** (Jev via Vercel AI Gateway): clean emails, adversarial emails, task routing + the option-description ablation; raw checkpoints committed; provenance in every report; `verify_published.py` in CI; **`llm` adapter** (Claude via SDK, any OpenAI-compatible endpoint) and **Jev-compatible endpoints** (OpenJev) through `JEV_ENDPOINT`; Apache-2.0, tests, CI | A number without its evidence is an opinion. The repo goes public with every claim reproducible, and with the adapters people need to audit what they actually run |
| v0.3 (done) | **MCP server** (`judge-audit-mcp`: `run_audit`, `check_drift`, `list_judges`) so agents and IDEs audit a judge in place; **GitHub Action** (`mode: run \| check`, sticky PR comment with the audit table, self-demo workflow) for the Marketplace; launch video | Distribution: the audit has to live where the judge is used — the agent session and the pull request |
| v0.3.x | **First side-by-side** (#21): Jev vs local open models (Ollama) vs Gemini / Claude on the four datasets, checkpoints committed, `docs/arena-2026-09.md` | The comparison is the story nobody has published |
| v0.3.x | **Consensus audit** (#39): the Arena judges as a jury — is vote share a confidence score? — plus a pre-registered deliberation round (Shao 2026, Huang et al. 2026) | Agent juries treat agreement as evidence; a calibration audit is where that assumption gets tested |
| v0.4 | **Score questions** and **MCE** (#12): worst-case calibration, the number a regulator asks for; decision receipts per judgment (#11) | AI Act art. 12/15 evidence starts with "show me the worst bin", not the average |
| v0.5 | **Judge Arena** (#14, #15): public, continuously updated calibration leaderboard; submission spec so anyone can add a judge with its checkpoint | Leaderboards are distribution; calibration is the axis nobody ranks on |
| v0.6 | **Evidence dossier** export (#10, #13): Markdown bundle mapped to AI Act logging / oversight / accuracy articles — *adapted*, never "certified" | What a European buyer's compliance team needs to say yes |
| later | Production drift monitor; Spanish-language audit packs for regulated sectors; conformal-prediction coverage guarantees (research) | Recurring revenue and the ES/EU wedge |

Out of scope: building a judge. judge-audit checks judges; it does not compete with them.
