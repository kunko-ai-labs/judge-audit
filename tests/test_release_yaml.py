"""The release workflow's contract: nothing leaves the runner without a green smoke test.

`release.yml` runs build -> smoke -> github-release -> publish. `smoke` installs the built
wheel in a clean runner and exercises the CLI, a simulated audit and the MCP entry point,
then generates and checks an SBOM of that install. Only after it passes are the wheel and
SBOM attested (in a job that installs nothing), attached to the GitHub release and
published to PyPI. These tests fail the build if
that ordering, the hash-pinned SBOM tool or the credential hygiene ever regresses.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

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


INSTALLS = re.compile(
    r"\bpip3? (--python \S+ )?install\b"       # pip install, pip3 install, pip --python X install
    r"|\bpipx\b"                               # pipx install / run
    r"|\bpython3? -m build\b"                  # isolated build env installs the backend
    r"|\bnpm (install|ci)\b"
    r"|\buv (pip|sync|tool)\b")


def holds_oidc(permissions) -> bool:
    """`id-token: write`, explicitly or through `write-all`. A string other than write-all
    (read-all) grants no token; a missing block is handled by the caller (inheritance)."""
    if isinstance(permissions, str):
        return permissions.strip() == "write-all"
    return isinstance(permissions, dict) and permissions.get("id-token") == "write"


def oidc_violations(workflow: dict) -> list[str]:
    """Every job that installs packages while holding an OIDC token, and a workflow-level
    grant of the token (which every job without its own block would inherit)."""
    top = workflow.get("permissions")
    out = [f"workflow-level permissions grant id-token: write ({top!r})"] if holds_oidc(top) else []
    for name, job in workflow["jobs"].items():
        perms = job["permissions"] if "permissions" in job else top
        installs = any(INSTALLS.search(s.get("run", "")) for s in job.get("steps", []))
        if installs and holds_oidc(perms):
            out.append(f"{name} installs packages and holds id-token: write ({perms!r})")
    return out


def test_no_job_that_installs_packages_holds_an_oidc_token(workflow, jobs):
    """A dependency that is not hash-pinned could mint Sigstore or PyPI credentials."""
    assert oidc_violations(workflow) == []
    assert not holds_oidc(workflow.get("permissions"))
    assert "id-token" not in (workflow.get("permissions") or {})
    # the detector is not vacuous: both installing jobs are recognised as installing
    assert INSTALLS.search(runs(jobs["build"])) and INSTALLS.search(runs(jobs["smoke"]))


@pytest.mark.parametrize("command", [
    "pip install build", "pip3 install -r req.txt", "python -m pip --python v/bin/python install x",
    "pipx run cyclonedx-py", "pipx install x", "python3 -m build", "npm ci", "npm install x",
    "uv pip install x", "uv sync", "uv tool install ruff"])
def test_install_detector_catches(command):
    assert INSTALLS.search(command), command


@pytest.mark.parametrize("command", [
    "gh release upload v1 dist/*", "smoke-venv/bin/judge-audit --version", "echo pipeline"])
def test_install_detector_ignores(command):
    assert not INSTALLS.search(command), command


def wf(top=None, **job_perms):
    jobs = {name: {"steps": [{"run": run}], **({"permissions": p} if p is not None else {})}
            for name, (run, p) in job_perms.items()}
    return {"jobs": jobs, **({"permissions": top} if top is not None else {})}


def test_oidc_check_flags_every_way_a_token_reaches_an_installing_job():
    token = {"id-token": "write"}
    assert oidc_violations(wf(a=("pip3 install x", token))) == [
        "a installs packages and holds id-token: write ({'id-token': 'write'})"]
    assert oidc_violations(wf(a=("pipx run x", token)))
    assert oidc_violations(wf(a=("uv tool install x", token)))
    # write-all is a string, not a dict: a clear failure, never an AttributeError
    assert oidc_violations(wf(a=("pip install x", "write-all"))) == [
        "a installs packages and holds id-token: write ('write-all')"]
    # a workflow-level grant is itself a violation and is inherited by jobs without a block
    got = oidc_violations(wf(top=token, a=("pip install x", None)))
    assert got[0].startswith("workflow-level") and got[1].startswith("a installs")
    assert oidc_violations(wf(top="write-all", a=("echo hi", None)))
    # no install, or no token: fine
    assert oidc_violations(wf(a=("gh release upload v1 x", token))) == []
    assert oidc_violations(wf(top="read-all", a=("pip install x", {"contents": "read"}))) == []


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


def release_step(jobs) -> str:
    return next(s["run"] for s in jobs["github-release"]["steps"]
                if "gh release create" in s.get("run", ""))


def shell_function(run: str, name: str) -> str:
    """The `name() { … }` block of a step's script, exactly as the workflow defines it."""
    m = re.search(rf"^( *){name}\(\) \{{\n.*?^\1\}}$", run, flags=re.M | re.S)
    assert m, f"{name}() is not defined in the step"
    return m.group(0)


@pytest.mark.parametrize(("tag", "pre"), [
    ("v0.6.0", False), ("v0.6.0rc1", True), ("v0.6.0a2", True), ("v0.6.0b1", True),
    ("v0.6.0.post1", False), ("v1.10.12rc10", True), ("v0.6", False), ("v0.6.0rc", False),
    ("v0.6.0-rc1", False), ("v0.6.0rc1x", False)])
def test_prerelease_detection_runs_the_workflow_function(jobs, tag, pre):
    """The function is run by bash as release.yml defines it, not re-implemented here."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    fn = shell_function(release_step(jobs), "is_prerelease")
    got = subprocess.run([bash, "-c", f'{fn}\nis_prerelease "$1"', "_", tag]).returncode == 0
    assert got is pre, tag


def test_prerelease_is_never_latest_and_finals_keep_the_defaults(jobs):
    run = release_step(jobs)
    create = next(ln for ln in run.splitlines() if "gh release create" in ln)
    assert '"${flags[@]}"' in create, "the flags reach gh release create"
    assert "flags=(--prerelease --latest=false)" in run
    assert re.search(r"^ *flags=\(\)$", run, flags=re.M), "a final tag gets no extra flags"
    # a release created by hand before the tag is corrected too
    assert re.search(r'is_prerelease "\$\{GITHUB_REF_NAME\}"; then\n *gh release edit '
                     r'"\$\{GITHUB_REF_NAME\}" --prerelease --latest=false', run)
    assert "--latest=true" not in run and "--latest " not in run


@pytest.mark.parametrize("tag", ["v0.6.0", "v0.6.0rc1"])
def test_build_and_trigger_accept_a_prerelease_tag(root, jobs, workflow, tag, tmp_path):
    """The trigger glob matches the tag, and the build job's tag-vs-version check, run as
    written, passes when pyproject carries the same version (and fails when it differs)."""
    from fnmatch import fnmatchcase
    assert any(fnmatchcase(tag, g) for g in workflow[True]["push"]["tags"])
    check = next(s["run"] for s in jobs["build"]["steps"]
                 if s.get("name") == "Tag must match the package version")
    bash = shutil.which("bash")
    if bash is None or sys.version_info < (3, 11):
        pytest.skip("needs bash and tomllib (the build job runs Python 3.12)")
    py = tmp_path / "bin"
    py.mkdir()
    (py / "python").symlink_to(sys.executable)
    for version, ok in ((tag[1:], True), ("0.6.0", tag == "v0.6.0")):
        (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
        env = {**os.environ, "GITHUB_REF_NAME": tag,
               "PATH": f"{py}{os.pathsep}{os.environ['PATH']}"}
        r = subprocess.run([bash, "-e", "-c", check], cwd=tmp_path, env=env,
                           capture_output=True, text=True)
        assert (r.returncode == 0) is ok, (tag, version, r.stdout)
