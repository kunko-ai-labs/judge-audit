# Running a real audit against Jev

The published audits in this repo were produced against TypeSafe's Jev through the
AI Gateway evaluate API. This page is everything you need to reproduce one, or run your own.

## What you need

| | |
|---|---|
| An AI Gateway API key | From the gateway that serves `typesafe-ai/jev` (its dashboard → API Keys). Export it as `AI_GATEWAY_API_KEY`. |
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

## Pin the model version

With the direct API (below) the engine asks for the alias `jev-latest` unless you say otherwise. An alias moves: `jev-latest` pointed to Jev 1.13.0 when the v0.6 study ran and has pointed to `jev-1.14.0` since 2026-10-22 ([model list](https://docs.typesafe.ai/models.md)). A run under the alias therefore measures whichever model the alias names that day, and two runs weeks apart can be two different models.

Pin the model version with `JEV_MODEL`; the engine sends it as given:

```bash
JEV_BACKEND=typesafe JEV_MODEL=jev-1.14.0 \
  judge-audit run examples/email-routing/labels.jsonl --judge jev --json audits/jev-1.14.0.json
```

Results are comparable only within one model version, so a calibration, a threshold or a share automated measured with Jev 1.13.0 says nothing about Jev 1.14.0: audit the version you will run. The model you asked for goes into the report's provenance (`model`); on the direct API each checkpoint row also records the id the reply says it served (`raw.served`), so you can check that no alias moved in the middle of a run. The gateway does not report a served version, so there it stays recorded as unknown; use a gateway model id that names a version if the gateway offers one, and keep the date of the run.

The v0.6 study figures are labelled "Jev 1.13.0" for this reason: every one of its 2,974 rows per language was served by `jev-1.13.0` ([section 8 of the results](v06/README.md#8-served-model)).

## The house rule

`python scripts/verify_published.py` recomputes every `docs/audit-*.json` from its
checkpoint and fails on any drift. CI runs it. A report without a checkpoint is not
an audit.

## Direct TypeSafe API

`JEV_BACKEND=typesafe` with `TYPESAFE_API_KEY` uses the SystemOne HTTP endpoint
directly (waitlist). Same interface, no Node.
