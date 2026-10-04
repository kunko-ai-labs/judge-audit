# judge-audit — vision

## The thesis in one sentence

Every vendor publishes its own benchmarks; a team that lets a judge decide on its own needs an independent, reproducible measurement of whether that judge's confidence can be trusted — on its own decisions.

## What this repository is

- **An open measurement harness.** Run any judge in shadow mode against decisions your humans already made; get calibration, discrimination, what can be automated at a bounded error, cost and latency, each with its interval and its caveats. No LLM in the measurement.
- **Open, pre-registered studies.** Protocols, power analyses and predictions are committed before the first call; raw checkpoints are committed after it; CI recomputes every published number. Results are published whether or not the predictions hold.
- **A CI gate, a GitHub Action and an MCP server**, so the measurement lives where the judge is used.

## What it is not

It does not build or sell a judge, and it does not certify anything: a result describes the judge on the labelled data it was measured on, under the conditions stated next to it.

## Why open

A measurement that cannot be recomputed is an opinion. Everything here — data, raw responses, scripts, analysis — is public so anyone can check it, and anyone can audit the judge they actually run.

## Sibling project

[Agent Assurance](https://github.com/kunko-ai-labs/agent-assurance) checks what an AI agent is allowed to do (declared vs observed, deterministic). judge-audit measures whether the judge deciding for it can be trusted (probabilistic). Deterministic where it can be proven, measured where it has to be.

## Professional use

For audits on private data or support, open an issue or contact the maintainers through the organisation profile.
