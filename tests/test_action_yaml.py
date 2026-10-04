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


def test_the_run_step_survives_a_drift_verdict(action):
    """The runner's shell adds -e; a drift verdict is exit 1, not a crash.

    Without `|| code=$?` the step aborts before recording JA_DRIFT, and
    `fail-on-drift: false` fails the job anyway (caught in CI 2026-09-22).
    """
    steps = action["runs"]["steps"]
    body = next(s["run"] for s in steps if "${cmd[@]}" in s.get("run", ""))
    assert '"${cmd[@]}" || code=$?' in body
    assert "JA_DRIFT=1" in body


def test_the_safe_rate_inputs_are_matched_against_patterns_and_passed_as_argv(action, steps):
    inputs = action["inputs"]
    assert inputs["min-safe-rate"]["default"] == ""
    assert inputs["target"]["default"] == "0.05" and inputs["segment-by"]["default"] == "label"
    dispatch = next(s for s in steps if "MODE" in s.get("env", {}))
    env = dispatch["env"]
    assert env["MIN_SAFE_RATE"] == "${{ inputs.min-safe-rate }}"
    assert env["TARGET"] == "${{ inputs.target }}"
    assert env["SEGMENT_BY"] == "${{ inputs.segment-by }}"
    run = dispatch["run"]
    assert '=~ ^0?\\.[0-9]+:' in run and 'cmd+=(--min-safe-rate "$m")' in run
    assert '"$TARGET" =~ ^0?\\.[0-9]+$' in run
    assert '"$SEGMENT_BY" =~ ^(label|none|meta\\.[A-Za-z0-9_]+)$' in run
    assert 'cmd+=(--target "$TARGET" --segment-by "$SEGMENT_BY")' in run
    read = next(s for s in steps if s.get("id") == "read")["run"]
    assert "safe_automation_rate=" in read and "safe_automation_rates=" in read


BASHES = sorted({b for b in ("bash", "/bin/bash") if __import__("shutil").which(b)})


def _dispatch(steps, tmp_path, bash, **env):
    """Run the Action's dispatch step for real, with a stub `judge-audit` that records its
    argv: what the CLI would receive, and the step's exit code."""
    import os
    import stat
    import subprocess

    script = next(s for s in steps if "MODE" in s.get("env", {}))["run"]
    stub = tmp_path / "bin" / "judge-audit"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text('#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done > argv.txt\n'
                    'echo report > judge-audit-report.md\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    full = {"PATH": f"{stub.parent}{os.pathsep}{os.environ['PATH']}", "MODE": "check",
            "LABELS": "l.jsonl", "JUDGE": "simulated", "BASELINE": "b.json",
            "MAX_ECE_DRIFT": "0.02", "MAX_ACC_DROP": "0.01", "ALLOW_INCOMPATIBLE": "false",
            "MIN_SAFE_RATE": "", "TARGET": "0.05", "SEGMENT_BY": "label",
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
            "GITHUB_ENV": str(tmp_path / "genv"), **env}
    r = subprocess.run([bash, "-c", script], cwd=tmp_path, env=full, capture_output=True,
                       text=True)
    argv = (tmp_path / "argv.txt").read_text().splitlines() if (
        tmp_path / "argv.txt").exists() else None
    return r.returncode, argv, r.stdout + r.stderr


@pytest.mark.parametrize("bash", BASHES)
def test_the_dispatch_step_passes_every_minimum_and_refuses_hostile_values(
        steps, tmp_path, bash):
    code, argv, out = _dispatch(steps, tmp_path, bash)               # empty: no minimum
    assert code == 0, out
    assert "--min-safe-rate" not in argv and argv[-4:] == ["--target", "0.05",
                                                           "--segment-by", "label"]
    code, argv, out = _dispatch(steps, tmp_path, bash,
                                MIN_SAFE_RATE="0.05:0.40\n0.10:0.7\r\n", SEGMENT_BY="meta.lang")
    assert code == 0, out
    assert [argv[i + 1] for i, a in enumerate(argv) if a == "--min-safe-rate"] == [
        "0.05:0.40", "0.10:0.7"]
    assert argv[-1] == "meta.lang"
    for env in ({"MIN_SAFE_RATE": "0.05:0.4;touch pwned"}, {"MIN_SAFE_RATE": "1:0.5"},
                {"MIN_SAFE_RATE": ".05:2"}, {"TARGET": "0.05;id"}, {"TARGET": "5"},
                {"SEGMENT_BY": "meta.$(id)"}, {"SEGMENT_BY": "lang"}):
        (tmp_path / "argv.txt").unlink(missing_ok=True)
        code, argv, out = _dispatch(steps, tmp_path, bash, **env)
        assert code == 2 and argv is None, (env, out)
        assert not (tmp_path / "pwned").exists()
