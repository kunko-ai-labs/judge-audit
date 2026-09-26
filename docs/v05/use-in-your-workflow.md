# Use it in your own workflow

judge-audit is a Python package (`kunko-judge-audit` on PyPI), a CLI, a GitHub Action and an MCP server. A team can audit its own judge on its own labelled rows, not only read our benchmark. The v0.5 pieces (new metrics, judges and extras) are on `main` and install from source (`pip install -e .` in a clone) until v0.5 is released on PyPI; the CLI, Action and MCP server do not print the new metrics yet.

## 1. On your own data, once (CLI)

```bash
pip install kunko-judge-audit            # v0.4 on PyPI; extras [anthropic], [nli], [mcp]
# from a clone of main, v0.5 extras too: pip install -e ".[laya]" or ".[mlx]"
judge-audit run my-labels.jsonl --judge llm --json result.json
```

A labels file is one JSON object per row: the state, the questions with their options, and the right answer (format: [README](../../README.md), [ground-truth tiers](../ground-truth.md)). The report gives:

- accuracy;
- ECE (both binnings) and Brier;
- zero-error coverage;
- cost and latency percentiles;
- intervals;
- the provenance of the run.

The v0.5 metrics (`judge_audit.metrics.selective`) are library functions today; the v0.5 reports will print them.

## 2. On every pull request (GitHub Action)

The Action in this repository audits a judge on a labelled file in CI. It comments the table on the pull request and fails when calibration or accuracy drift past a baseline:

```yaml
- uses: kunko-ai-labs/judge-audit@<pinned sha>
  with:
    labels: evals/labels.jsonl
    judge: llm
    extras: anthropic                 # the SDK the llm judge needs for Claude
    mode: check
    baseline: evals/baseline.json
  env:
    LLM_PROVIDER: anthropic
    LLM_MODEL: <model id>
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Keys come from repository secrets, never from the file. Full inputs, and what to check before running third-party code in your CI: [integrations.md](../integrations.md). This is how a team catches a prompt edit or a model update that makes its judge less honest before it ships, provided the change moves ECE or accuracy past the thresholds it set.

**Scheduled audits.** The same Action on a `schedule:` trigger re-audits a hosted judge every week against a frozen labelled set and a frozen baseline. That catches silent model updates: the served model version is recorded per decision.

## 3. Inside an agent's session (MCP)

```bash
pip install "kunko-judge-audit[mcp]"
claude mcp add judge-audit -- judge-audit-mcp
```

The server exposes three tools: `run_audit`, `check_drift` and `list_judges`. An agent can audit a judge before relying on it and check drift after a change. What it gets back today is the v0.4 report: accuracy, ECE, and the retrospective zero-error coverage. It does not yet choose a certified threshold for the agent; exposing the v0.5 "coverage at error ≤ X %" through the server is future work. The server makes no network calls of its own, only the ones the chosen judge makes.

## 4. As a library in your own pipeline

```python
from judge_audit.metrics.selective import coverage_at_risk_crossfit, failure_auroc

cov = coverage_at_risk_crossfit(confidences, correct, target_risk=0.02, groups=texts)
auc = failure_auroc(confidences, correct)
```

With any judge's confidences and your labels, you get:
- how much you can automate at your error budget, with its certified bound;
- how well the confidence ranks errors.

Nothing is sent anywhere.

## What could be automated next (not done)

- **A scheduled benchmark job.** It would run the hosted judges on the frozen v0.5 sets with keys from repository secrets, commit the checkpoints and open a pull request with the regenerated reports. This is possible, but each run costs money and must respect the pre-registered cost ceiling, so it is a maintainer decision, not a default.
- **Local judges in CI.** Laya and small MLX models run on CPU runners slowly. That is fine for a smoke test on a few rows; published runs stay on the maintainer's machine.
