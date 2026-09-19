# Integrations

## Install

```bash
pip install kunko-judge-audit            # CLI only, stdlib core
pip install "kunko-judge-audit[mcp]"     # + the MCP server
pip install "kunko-judge-audit[charts]"  # + HTML reports with charts (matplotlib)
```

## CLI

```bash
judge-audit run labels.jsonl --judge simulated            # audit-report.md, audit-result.json, audit-judgments.jsonl
judge-audit check labels.jsonl --judge jev --baseline audit-result.json --max-ece-drift 0.02
```

Exit codes: `0` ok · `1` drift detected · `2` usage or configuration error. Judges and their environment variables: [judges.md](judges.md). Real vendor runs: [real-audits.md](real-audits.md).

## Inside the agent's own session (MCP)

```bash
pip install "kunko-judge-audit[mcp]"
claude mcp add judge-audit -- judge-audit-mcp
```

Cursor (`.cursor/mcp.json`) or any stdio MCP client:

```json
{
  "mcpServers": {
    "judge-audit": { "command": "judge-audit-mcp" }
  }
}
```

Tools: `run_audit`, `check_drift`, `list_judges`. The agent can ask *"audit `examples/email-routing/labels.jsonl` with the simulated judge and tell me the zero-error coverage"* and gets back the same numbers the CLI writes — n, accuracy, ECE, reliability bins, accuracy-coverage curve, zero-error coverage, cost, p50/p99 — plus the run provenance (judge, model, backend, dataset sha256). Or *"has our judge drifted since `baseline.json`?"* → `check_drift` returns `ok`, the failures, and the new ECE/accuracy.

Paths resolve from the directory the server was started in. Results from the simulated judge always carry the `SIMULATED` tag; a judge that is not configured (no API key) comes back as a structured `error`, never as a crashed server. The server makes no network calls of its own — only the ones the judge you chose makes.

## In CI

```yaml
- run: pip install "kunko-judge-audit"
- run: judge-audit check labels.jsonl --judge jev --baseline baseline/audit-result.json
  env:
    AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }}
```

Exit `1` fails the job when the judge is less honest than the committed baseline. Regenerate the baseline deliberately (`judge-audit run … --json baseline/audit-result.json`) and review the diff like any other change.

## As a library

```python
from judge_audit import run_audit
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.runner import load_jsonl

rows = load_jsonl("labels.jsonl")
result = run_audit(SimulatedJudge(rows), rows, labels_path="labels.jsonl")
print(result.ece, result.zero_error, result.run["dataset"]["sha256"])
```

Implement your own judge by subclassing `judge_audit.Judge` — see [judges.md](judges.md#writing-an-adapter).
