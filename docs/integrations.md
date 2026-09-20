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

## GitHub Action

```yaml
# .github/workflows/judge-audit.yml
permissions:
  contents: read
  pull-requests: write     # only for the sticky PR comment

steps:
  - uses: actions/checkout@v4
  - uses: kunko-ai-labs/judge-audit@v0.3   # or pin the release's commit SHA (see below)
    with:
      labels: audits/labels.jsonl              # the decisions your humans already made
      judge: jev                               # simulated | jev | llm
      mode: check                              # gate on drift vs the baseline; 'run' only reports
      baseline: audits/baseline.json           # audit-result.json of the run you signed off
      max-ece-drift: "0.02"
      max-acc-drop: "0.01"
      fail-on-drift: "true"                    # 'false' = report, expose the `drift` output, do not fail
    env:
      AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }}   # jev; llm uses ANTHROPIC_API_KEY or LLM_*
```

The markdown report lands in the job summary; on pull requests one comment is created and then updated on every push (marker `<!-- judge-audit:<labels> -->`), with the SIMULATED banner whenever the judge is the simulator. Outputs: `accuracy`, `ece`, `zero-error-coverage`, `n`, `drift`, `report-path`, `result-path`. The report, the result JSON, the drift verdict and the per-decision evidence are uploaded as a run artifact.

Regenerate the baseline deliberately (`judge-audit run … --json audits/baseline.json`) and review the diff like any other change. This repo's own [`judge-audit.yml`](../.github/workflows/judge-audit.yml) asserts that the Action passes what it should and detects the drift it should — a green run means the gate still works.

### Running third-party code in your CI — what you should check

- **Pin by commit SHA**, not by tag. Tags can move; a SHA cannot. Get the SHA of any release with `gh api repos/kunko-ai-labs/judge-audit/git/ref/tags/v0.3.1 --jq .object.sha` and write `uses: kunko-ai-labs/judge-audit@<that sha>  # v0.3.1`; Dependabot keeps the SHA and the version comment in step. Our own workflows pin every action the same way.
- **What the Action does:** `pip install` of this repository at that SHA, then runs the CLI on your labels file. The only outbound traffic is `pip` and the judge endpoint you configure through the job's `env`; the Action itself reads no secret and executes nothing from your repository.
- **Least privilege:** `contents: read` is enough; add `pull-requests: write` only for the PR comment.
- **Verify what you get:** every release ships Sigstore build provenance (`gh attestation verify` on the artifacts) and the [OpenSSF Scorecard](https://scorecard.dev/viewer/?uri=github.com/kunko-ai-labs/judge-audit) of this repo is public.

## Plain CI step

```yaml
- run: pip install "kunko-judge-audit"
- run: judge-audit check labels.jsonl --judge jev --baseline baseline/audit-result.json --drift drift.json
  env:
    AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }}
```

Exit `1` fails the job when the judge is less honest than the committed baseline; `--drift` writes the verdict (`{ok, failures, ece, accuracy}`) for anything downstream.

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
