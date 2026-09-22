"""The release workflow's contract: nothing reaches PyPI without a green smoke test.

`release.yml`'s `smoke` job installs the built wheel in a clean runner and exercises
the CLI, a simulated audit and the MCP entry point before `publish` is allowed to run;
it also generates and attaches an SBOM. These tests fail the build if that ordering,
or the pinned SBOM tool, ever regresses.
"""
from __future__ import annotations

import re

import pytest

yaml = pytest.importorskip("yaml")

RELEASE = ".github/workflows/release.yml"


@pytest.fixture(scope="module")
def workflow(root):
    return yaml.safe_load((root / RELEASE).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow):
    return workflow["jobs"]


def test_smoke_job_runs_between_build_and_publish(jobs):
    assert "smoke" in jobs, "no smoke-test job"
    assert jobs["smoke"]["needs"] == "build"
    publish_needs = jobs["publish"]["needs"]
    assert "smoke" in publish_needs, "publish does not depend on the smoke test"
    assert "build" in publish_needs


def test_smoke_installs_the_built_wheel_not_the_source_tree(jobs):
    steps = jobs["smoke"]["steps"]
    install = next(s for s in steps if "Install" in s.get("name", ""))
    assert "dist/*.whl" in install["run"]
    assert "-e ." not in install["run"], "must install the built artifact, not editable source"


def test_smoke_checks_version_run_and_mcp_help(jobs):
    steps = jobs["smoke"]["steps"]
    run_blocks = "\n".join(s.get("run", "") for s in steps)
    assert "judge-audit --version" in run_blocks
    assert "GITHUB_REF_NAME" in run_blocks, "the printed version must be checked against the tag"
    assert re.search(r"judge-audit run examples/email-routing/labels\.jsonl --judge simulated",
                      run_blocks)
    assert "judge-audit-mcp --help" in run_blocks


def test_smoke_generates_a_pinned_sbom_and_uploads_it(jobs):
    steps = jobs["smoke"]["steps"]
    run_blocks = "\n".join(s.get("run", "") for s in steps)
    assert re.search(r"cyclonedx-bom==\d+\.\d+\.\d+", run_blocks), "SBOM tool must be pinned"
    assert "cyclonedx-py" in run_blocks
    assert "sbom.cdx.json" in run_blocks
    assert "gh release upload" in run_blocks


def test_no_eval_in_release_workflow(jobs):
    for job in jobs.values():
        for step in job.get("steps", []):
            assert not re.search(r"(^|[;&|\s])eval\s", step.get("run", "")), (
                f"eval in release.yml step {step.get('name')!r}")


def test_all_actions_are_pinned_by_full_commit_sha(jobs):
    for job in jobs.values():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if uses:
                assert re.search(r"@[0-9a-f]{40}\b", uses), f"unpinned action: {uses}"
