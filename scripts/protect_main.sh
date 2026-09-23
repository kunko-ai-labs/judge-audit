#!/usr/bin/env bash
# Protect `main` and the release tags. Idempotent: re-running updates, never duplicates.
# Run by the maintainer (branch protection is a Pro/public feature on GitHub):
#   bash scripts/protect_main.sh [owner/repo]
#
# `main`: linear history, no force-push, no deletion, conversations resolved, and the CI
# checks below green and up to date before merge — the three `test` jobs and `datasets`
# (ci.yml) and CodeQL's `analyze` (codeql.yml). Changes go through a pull request.
#
# No approving review is required, on purpose. This is a single-maintainer repository
# and GitHub does not let an author approve their own pull request, so a required
# approval would force an admin bypass on every merge — and on classic protection that
# bypass skips red CI too, which is weaker than requiring the checks alone. The
# independent review is the story-reviewer and release-qa agents plus the maintainer's
# own read (CONTRIBUTING.md § Review). When an external reviewer joins, set
# required_approving_review_count to 1.
set -euo pipefail
repo="${1:-kunko-ai-labs/judge-audit}"

gh api -X PUT "repos/$repo/branches/main/protection" --input - >/dev/null <<'JSON'
{
  "required_status_checks": {"strict": true,
    "contexts": ["test (3.10)", "test (3.11)", "test (3.12)", "datasets", "analyze"]},
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

ruleset='{
  "name": "release-tags", "target": "tag", "enforcement": "active",
  "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
  "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}]
}'
id="$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "release-tags") | .id')"
if [ -n "$id" ]; then
  gh api -X PUT "repos/$repo/rulesets/$id" --input - >/dev/null <<<"$ruleset"
  echo "ruleset release-tags: updated ($id)"
else
  gh api -X POST "repos/$repo/rulesets" --input - >/dev/null <<<"$ruleset"
  echo "ruleset release-tags: created"
fi

gh api "repos/$repo/branches/main/protection" \
  --jq '{checks: .required_status_checks.contexts, reviews: .required_pull_request_reviews.required_approving_review_count, force_push: .allow_force_pushes.enabled, deletions: .allow_deletions.enabled, linear: .required_linear_history.enabled}'
