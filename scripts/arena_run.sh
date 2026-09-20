#!/usr/bin/env bash
# Run one judge over the four published datasets, checkpointed under docs/runs/arena/<slug>/.
# Usage: scripts/arena_run.sh <slug> <judge> [env assignments...]
#   scripts/arena_run.sh llama32 llm LLM_PROVIDER=openai-compatible LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2:3b
set -euo pipefail
slug=$1; judge=$2; shift 2; ENVS=("$@")
out=docs/runs/arena/$slug; mkdir -p "$out"
for pair in \
  "email-clean examples/email-routing/labels.jsonl" \
  "email-adversarial examples/email-routing-adversarial/labels.jsonl" \
  "router-bare examples/task-routing/labels.jsonl" \
  "router-described examples/task-routing/labels-described.jsonl"; do
  set -- $pair; name=$1; labels=$2
  echo "== $slug / $name"
  env "${ENVS[@]}" JEV_MIN_INTERVAL_S="${JEV_MIN_INTERVAL_S:-0}" .venv/bin/python scripts/audit_resumable.py "$labels" --judge "$judge" \
    --checkpoint "$out/$name.ckpt.jsonl" --out "$out/$name.md" --json "$out/$name.json" | tail -1
done
