#!/usr/bin/env bash
# Protect `main` the way agent-assurance does. Run once the repo is public
# (branch protection is a Pro/public feature on GitHub):
#   bash scripts/protect_main.sh
set -euo pipefail
repo="${1:-kunko-ai-labs/judge-audit}"
gh api -X PUT "repos/$repo/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {"strict": true,
    "contexts": ["test (3.10)", "test (3.11)", "test (3.12)", "datasets"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
gh api -X POST "repos/$repo/rulesets" --input - <<'JSON'
{
  "name": "release-tags", "target": "tag", "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
  "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]
}
JSON
gh api "repos/$repo/branches/main/protection" \
  --jq '{checks: .required_status_checks.contexts, force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, linear: .required_linear_history.enabled}'
