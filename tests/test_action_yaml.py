"""The Action's contract: inputs are data, never shell.

A composite action interpolates `${{ inputs.* }}` into the script *before* bash sees
it, so an input containing `; rm -rf /` executes. Every input therefore travels through
`env:` and is quoted at use; these tests fail the build if that ever regresses.
"""
from __future__ import annotations

import re

import pytest

yaml = pytest.importorskip("yaml")

ACTION = "action.yml"


@pytest.fixture(scope="module")
def action(root):
    return yaml.safe_load((root / ACTION).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def steps(action):
    return action["runs"]["steps"]


def test_no_input_interpolation_inside_a_run_block(steps):
    offenders = [(s.get("name", "?"), m)
                 for s in steps
                 for m in re.findall(r"\$\{\{[^}]*\binputs\.[^}]*\}\}", s.get("run", ""))]
    assert offenders == [], f"inputs interpolated into a shell script: {offenders}"


def test_no_github_event_interpolation_inside_a_run_block(steps):
    # Attacker-controlled too: PR titles, branch names, comment bodies.
    offenders = [(s.get("name", "?"), m)
                 for s in steps
                 for m in re.findall(r"\$\{\{[^}]*\bgithub\.event\b[^}]*\}\}", s.get("run", ""))]
    assert offenders == [], f"github.event interpolated into a shell script: {offenders}"


def test_no_eval_in_any_run_block(steps):
    offenders = [s.get("name", "?") for s in steps
                 if re.search(r"(^|[;&|\s])eval\s", s.get("run", ""))]
    assert offenders == [], f"eval in a composite step: {offenders}"


def test_every_input_used_by_a_script_is_passed_through_env(steps):
    for s in steps:
        run = s.get("run", "")
        if not run:
            continue
        env = s.get("env", {})
        for var in set(re.findall(r'"\$\{?([A-Z][A-Z0-9_]*)\}?"', run)):
            if var.startswith(("GITHUB_", "RUNNER_")) or var in {"PATH", "HOME"}:
                continue
            assert var in env or var in {"JA_CMD", "JA_CODE"}, (
                f"step {s.get('name')!r} uses ${var} without declaring it in env:")


def test_mode_is_validated_against_an_allowlist(steps):
    dispatch = next(s for s in steps if "MODE" in s.get("env", {}))
    run = dispatch["run"]
    assert 'case "$MODE" in' in run, "mode must be dispatched, not pasted into a command"
    assert "run)" in run and "check)" in run, "the allowlist is run | check"
    assert re.search(r"\*\)\s*\n\s*echo [^\n]*unknown mode", run) and "exit 2" in run, (
        "an unknown mode must be a usage error, not a fall-through")


def test_new_inputs_are_declared_with_safe_defaults(action):
    inputs = action["inputs"]
    assert inputs["extras"]["default"] == ""
    # Raw judgments are the decisions themselves: never uploaded unless asked.
    assert inputs["upload-evidence"]["default"] == "false"


def test_evidence_is_uploaded_only_when_asked(steps):
    upload = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert upload, "the Action still uploads the report and result"
    judgments = [s for s in upload if "judgments" in str(s.get("with", {}).get("path", ""))]
    assert judgments, "no step uploads the per-decision evidence"
    for s in judgments:
        assert "upload-evidence" in s.get("if", ""), (
            "per-decision judgments are uploaded without checking upload-evidence")


def test_extras_reaches_pip_as_a_quoted_variable(steps):
    install = next(s for s in steps if "Install" in s.get("name", ""))
    assert "EXTRAS" in install.get("env", {})
    assert "${{" not in install["run"], "the install step interpolates an expression"
