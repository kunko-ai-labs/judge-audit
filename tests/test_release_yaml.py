"""The release workflow's contract: nothing leaves the runner without a green smoke test.

`release.yml` runs build -> smoke -> github-release -> publish. `smoke` installs the built
wheel in a clean runner and exercises the CLI, a simulated audit and the MCP entry point,
then generates and checks an SBOM of that install. Only after it passes are the wheel and
SBOM attested (in a job that installs nothing), attached to the GitHub release and
published to PyPI. These tests fail the build if
that ordering, the hash-pinned SBOM tool or the credential hygiene ever regresses.
"""
from __future__ import annotations

import re

import pytest

yaml = pytest.importorskip("yaml")

RELEASE = ".github/workflows/release.yml"
ATTEST = "actions/attest-build-provenance@"


@pytest.fixture(scope="module")
def workflow(root):
    return yaml.safe_load((root / RELEASE).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow):
    return workflow["jobs"]


def runs(job) -> str:
    return "\n".join(s.get("run", "") for s in job["steps"])


def needs(job) -> list[str]:
    n = job.get("needs", [])
    return [n] if isinstance(n, str) else list(n)


def test_jobs_run_build_smoke_release_publish_in_that_order(jobs):
    assert needs(jobs["smoke"]) == ["build"]
    assert set(needs(jobs["github-release"])) == {"build", "smoke"}
    assert set(needs(jobs["publish"])) == {"build", "smoke", "github-release"}


def test_only_the_release_job_uploads_to_the_github_release(jobs):
    for name, job in jobs.items():
        uploads = "gh release upload" in runs(job) or "gh release create" in runs(job)
        assert uploads == (name == "github-release"), f"{name} touches the GitHub release"
    assert "dist/*" in runs(jobs["github-release"])
    assert "sbom.cdx.json" in runs(jobs["github-release"])
    # write access to contents only where the release is written
    for name, job in jobs.items():
        wants_write = job.get("permissions", {}).get("contents") == "write"
        assert wants_write == (name == "github-release"), name


def test_smoke_installs_the_built_wheel_not_the_source_tree(jobs):
    steps = jobs["smoke"]["steps"]
    install = next(s for s in steps if "Install" in s.get("name", ""))
    assert "dist/*.whl" in install["run"]
    assert "-e ." not in install["run"], "must install the built artifact, not editable source"
    assert "--without-pip" in install["run"], "pip would end up in the SBOM"


def test_smoke_checks_version_run_and_mcp_help(jobs):
    run_blocks = runs(jobs["smoke"])
    assert "judge-audit --version" in run_blocks
    assert "GITHUB_REF_NAME" in run_blocks, "the printed version must be checked against the tag"
    assert re.search(r"judge-audit run examples/email-routing/labels\.jsonl --judge simulated",
                     run_blocks)
    assert "judge-audit-mcp --help" in run_blocks


def test_sbom_tool_is_hash_pinned_and_describes_the_package(root, jobs):
    run_blocks = runs(jobs["smoke"])
    assert "--require-hashes" in run_blocks and ".github/sbom-requirements.txt" in run_blocks
    pins = (root / ".github" / "sbom-requirements.txt").read_text(encoding="utf-8")
    assert re.search(r"^cyclonedx-bom==\d+\.\d+\.\d+ \\$", pins, flags=re.M)
    lines = [ln for ln in pins.splitlines() if not ln.startswith("#")]
    for i, line in enumerate(lines):
        if line and not line.startswith(" "):            # a requirement, not a hash/comment
            assert re.fullmatch(r"[A-Za-z0-9_.-]+==\S+ \\", line), f"not an exact pin: {line}"
            assert lines[i + 1].startswith("    --hash=sha256:"), f"{line} has no hash"
    assert "cyclonedx-py environment" in run_blocks
    assert "--pyproject pyproject.toml" in run_blocks, "root component must be kunko-judge-audit"
    assert "smoke-venv" in run_blocks.split("cyclonedx-py environment", 1)[1]
    assert '"kunko-judge-audit"' in run_blocks, "the SBOM root is checked, not assumed"


def test_wheel_and_sbom_are_attested_with_the_same_pinned_action_before_upload(jobs):
    for name, job in jobs.items():
        attests = [s for s in job["steps"] if s.get("uses", "").startswith(ATTEST)]
        if name != "github-release":
            assert not attests, f"{name} attests: only github-release may"
    steps = jobs["github-release"]["steps"]
    attests = [s for s in steps if s.get("uses", "").startswith(ATTEST)]
    assert len({s["uses"] for s in attests}) == 1
    assert [s["with"]["subject-path"] for s in attests] == ["dist/*", "sbom.cdx.json"]
    upload = next(i for i, s in enumerate(steps) if "gh release upload" in s.get("run", ""))
    assert all(steps.index(s) < upload for s in attests), "attest before attaching"
    perms = jobs["github-release"]["permissions"]
    assert perms.get("id-token") == "write" and perms.get("attestations") == "write"


INSTALLS = re.compile(r"pip (--python \S+ )?install|python -m build|npm (install|ci)|uv (pip|sync)")


def test_no_job_that_installs_packages_holds_an_oidc_token(jobs):
    """A dependency that is not hash-pinned could mint Sigstore or PyPI credentials."""
    for name, job in jobs.items():
        installs = any(INSTALLS.search(s.get("run", "")) for s in job["steps"])
        token = job.get("permissions", {}).get("id-token") == "write"
        assert not (installs and token), f"{name} installs packages and holds id-token: write"
    assert INSTALLS.search(runs(jobs["build"])) and INSTALLS.search(runs(jobs["smoke"]))


def test_checkouts_do_not_persist_credentials(jobs):
    for name, job in jobs.items():
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step.get("with", {}).get("persist-credentials") is False, name


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
