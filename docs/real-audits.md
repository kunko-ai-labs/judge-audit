# Running a real audit against Jev

The published audits in this repo were produced against TypeSafe's Jev through the
Vercel AI Gateway. This page is everything you need to reproduce one, or run your own.

## What you need

| | |
|---|---|
| A Vercel AI Gateway API key | Vercel dashboard → AI Gateway → API Keys. Export it as `AI_GATEWAY_API_KEY`. |
| Node ≥ 20 | Jev is an *evaluation* model: it is not reachable through `/v1/chat/completions`. The only supported path is the AI SDK `experimental_evaluate` API, so a 50-line Node bridge (`src/judge_audit/judges/bridge/jev_bridge.mjs`) speaks that API and hands JSON back to Python. |
| Python ≥ 3.10 | `pip install -e ".[dev]"` |

```bash
npm install --prefix src/judge_audit/judges/bridge      # installs `ai` (AI SDK 7)
export AI_GATEWAY_API_KEY=...                           # never commit it
```

## One-shot audit (small datasets)

```bash
judge-audit run examples/email-routing/labels.jsonl --judge jev \
  --out docs/audit-my-run.md --json docs/audit-my-run.json --judgments docs/runs/my-run.jsonl
```

`--judgments` writes one JSON line per decision (decision, confidence, latency, cost,
the raw per-option probabilities the gateway returned). Commit it: it is the evidence
behind every number in the report.

## Long audits (rate limits)

The gateway's free tier is rate-limited per model. `scripts/audit_resumable.py` judges
one row at a time, appends each to a checkpoint and resumes where it stopped, so a
200-row audit can take a couple of hours and survive it:

```bash
python scripts/audit_resumable.py examples/email-routing-adversarial/labels.jsonl --judge jev \
  --checkpoint docs/runs/audit-jev-adversarial.ckpt.jsonl \
  --out docs/audit-jev-adversarial-base.md --json docs/audit-jev-adversarial-base.json
```

The first line of a checkpoint records how the run was produced (model, backend,
timestamp, dataset hash, judge-audit version); the report's provenance line comes from it.
Tune pacing with `JEV_MIN_INTERVAL_S` (default 3 s between calls).

Then the audit-specific analysis reads the checkpoint — no API call:

```bash
python scripts/analyze_adversarial.py            # the whole .md + .json, from the checkpoint
python scripts/analyze_adversarial.py --charts   # also redraws docs/assets/*-jev-adversarial.png

python scripts/audit_router.py examples/task-routing/labels.jsonl \
  --checkpoint docs/runs/audit-jev-router.ckpt.jsonl \
  --out docs/audit-jev-router.md --json docs/audit-jev-router.json
```

## What "confidence" means here

For a Choice question the gateway returns a probability per option. judge-audit takes
**P(chosen option)** as the confidence — that is the probabilistic claim a downstream
system would act on. TypeSafe's separate `confidence` statistic is kept in the raw
record for comparison. Cost is input tokens × TypeSafe's published price
($0.042 / MTok input, output free); latency is wall-clock through the bridge.

## The house rule

`python scripts/verify_published.py` recomputes every `docs/audit-*.json` from its
checkpoint and fails on any drift. CI runs it. A report without a checkpoint is not
an audit.

## Direct TypeSafe API

`JEV_BACKEND=typesafe` with `TYPESAFE_API_KEY` uses the SystemOne HTTP endpoint
directly (waitlist). Same interface, no Node.
