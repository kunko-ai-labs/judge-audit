#!/usr/bin/env bash
# Run a judge that trained on the published datasets over the rows it did NOT train on.
# Same layout as arena_run.sh (docs/runs/arena/<slug>/<dataset>.ckpt.jsonl) but:
#   - email-clean, router-bare, router-described: only the `heldout` rows of the
#     pre-registered split (examples/<dataset>/split-heldout.json), recorded in the header;
#   - email-adversarial: every row — none of them was a training row (robustness test).
# The fine-tuned judge needs one model per dataset; FINETUNED_MODEL_ROOT holds
# <root>/email-routing and <root>/task-routing (scripts/train_classifier.py's default).
# Usage: scripts/arena_run_heldout.sh <slug> <judge> [env assignments...]
#   scripts/arena_run_heldout.sh finetuned-deberta finetuned FINETUNED_MODEL_ROOT=~/.cache/judge-audit/finetuned
set -euo pipefail
slug=$1; judge=$2; shift 2; ENVS=("$@")
root=${FINETUNED_MODEL_ROOT:-$HOME/.cache/judge-audit/finetuned}
for pair in "${ENVS[@]}"; do case $pair in FINETUNED_MODEL_ROOT=*) root=${pair#*=};; esac; done
out=docs/runs/arena/$slug; mkdir -p "$out"
for spec in \
  "email-clean examples/email-routing/labels.jsonl email-routing examples/email-routing/split-heldout.json:heldout" \
  "email-adversarial examples/email-routing-adversarial/labels.jsonl email-routing -" \
  "router-bare examples/task-routing/labels.jsonl task-routing examples/task-routing/split-heldout.json:heldout" \
  "router-described examples/task-routing/labels-described.jsonl task-routing examples/task-routing/split-heldout.json:heldout"; do
  set -- $spec; name=$1; labels=$2; model=$3; rows=$4
  extra=(); [ "$rows" != "-" ] && extra=(--rows "$rows")
  echo "== $slug / $name (${rows/-/all rows})"
  env "${ENVS[@]}" FINETUNED_MODEL_DIR="$root/$model" .venv/bin/python scripts/audit_resumable.py "$labels" \
    --judge "$judge" --checkpoint "$out/$name.ckpt.jsonl" --out "$out/$name.md" --json "$out/$name.json" \
    "${extra[@]}" | tail -1
done
