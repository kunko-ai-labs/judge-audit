"""scripts/protect_main.sh: what it asks GitHub for, and that re-running it is safe.

A stub `gh` on PATH records every call, so nothing here touches a live repository.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

SCRIPT = "scripts/protect_main.sh"

STUB = """#!/usr/bin/env bash
# records each call as one JSON line: argv and stdin (when --input - is given)
input=""
for a in "$@"; do [ "$a" = "-" ] && input="$(cat)"; done
python3 -c 'import json,sys; print(json.dumps({"argv": sys.argv[1:-1], "input": sys.argv[-1]}))' \
  "$@" "$input" >> "$GH_LOG"
case "$*" in
  *"/rulesets --jq"*) printf '%s' "${GH_RULESET_ID:-}" ;;
esac
"""


@pytest.fixture
def run_script(root, tmp_path):
    if shutil.which("bash") is None:
        pytest.skip("bash not available")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(STUB, encoding="utf-8")
    gh.chmod(0o755)

    def run(ruleset_id: str = "") -> list[dict]:
        log = tmp_path / f"gh-{ruleset_id or 'none'}.log"
        env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}",
                   GH_LOG=str(log), GH_RULESET_ID=ruleset_id)
        subprocess.run(["bash", str(root / SCRIPT), "owner/repo"], env=env, check=True,
                       capture_output=True, text=True)
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    return run


def protection(calls: list[dict]) -> dict:
    (put,) = [c for c in calls if c["argv"][:3] == ["api", "-X", "PUT"]
              and c["argv"][3].endswith("/branches/main/protection")]
    return json.loads(put["input"])


def test_main_requires_ci_and_codeql_but_no_approving_review(run_script, root):
    p = protection(run_script())
    contexts = p["required_status_checks"]["contexts"]
    assert set(contexts) == {"test (3.10)", "test (3.11)", "test (3.12)", "datasets", "analyze"}
    assert p["required_status_checks"]["strict"] is True
    # single maintainer: an author cannot approve their own PR (see CONTRIBUTING.md § Review)
    assert p["required_pull_request_reviews"]["required_approving_review_count"] == 0
    assert p["allow_force_pushes"] is False and p["allow_deletions"] is False
    assert p["required_linear_history"] is True
    # every required context is a real job name
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    codeql = (root / ".github/workflows/codeql.yml").read_text(encoding="utf-8")
    assert re.search(r"^  test:\n", ci, flags=re.M) and '"3.10", "3.11", "3.12"' in ci
    assert re.search(r"^  datasets:\n", ci, flags=re.M)
    assert re.search(r"^  analyze:\n", codeql, flags=re.M)


def test_release_tags_ruleset_is_created_when_missing(run_script):
    calls = run_script("")
    writes = [c["argv"] for c in calls if "rulesets" in " ".join(c["argv"]) and "-X" in c["argv"]]
    assert writes == [["api", "-X", "POST", "repos/owner/repo/rulesets", "--input", "-"]]


def test_release_tags_ruleset_is_updated_not_duplicated_when_present(run_script):
    calls = run_script("23699681")
    writes = [c for c in calls if "rulesets" in " ".join(c["argv"]) and "-X" in c["argv"]]
    assert [c["argv"] for c in writes] == [
        ["api", "-X", "PUT", "repos/owner/repo/rulesets/23699681", "--input", "-"]]
    body = json.loads(writes[0]["input"])
    assert body["name"] == "release-tags" and body["target"] == "tag"
    assert {r["type"] for r in body["rules"]} == {"deletion", "non_fast_forward"}
