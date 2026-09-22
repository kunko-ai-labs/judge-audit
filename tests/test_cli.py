"""Exit-code contract: 0 ok · 1 drift · 2 usage/config error."""
from __future__ import annotations

import json
import subprocess
import sys


def run(*args, cwd):
    return subprocess.run([sys.executable, "-m", "judge_audit.cli", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_run_simulated_writes_report_json_and_judgments(labels_path, tmp_path):
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "SIMULATED" in (tmp_path / "audit-report.md").read_text()
    res = json.loads((tmp_path / "audit-result.json").read_text())
    assert res["n"] == 12 and res["run"]["judge"]["name"] == "simulated"
    assert (tmp_path / "audit-judgments.jsonl").read_text().count("\n") == 12


def test_check_no_drift_against_own_baseline(labels_path, tmp_path):
    run("run", str(labels_path), "--judge", "simulated", "--json", "base.json", cwd=tmp_path)
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "base.json",
            cwd=tmp_path)
    assert r.returncode == 0 and "OK: no drift" in r.stdout


def test_check_detects_drift(labels_path, tmp_path):
    (tmp_path / "strict.json").write_text(json.dumps({"ece": 0.0, "accuracy": 1.0}))
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "strict.json",
            cwd=tmp_path)
    assert r.returncode == 1 and "DRIFT DETECTED" in r.stderr


def test_missing_labels_file_is_exit_2(tmp_path):
    r = run("run", "nope.jsonl", "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 2 and "cannot read" in r.stderr


def test_jev_without_key_is_exit_2_with_guidance(labels_path, tmp_path, monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    r = run("run", str(labels_path), "--judge", "jev", cwd=tmp_path)
    assert r.returncode == 2
    assert "AI_GATEWAY_API_KEY" in r.stderr and "--judge simulated" in r.stderr


def test_version(tmp_path):
    r = run("--version", cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("judge-audit ")


def test_empty_baseline_is_exit_2(labels_path, tmp_path):
    (tmp_path / "empty.json").write_text("{}")
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "empty.json",
            cwd=tmp_path)
    assert r.returncode == 2 and "baseline" in r.stderr


def test_check_against_another_dataset_is_exit_2(labels_path, tmp_path):
    # A baseline measured on other rows is not a baseline: refuse rather than compare.
    run("run", str(labels_path), "--judge", "simulated", "--json", "base.json", cwd=tmp_path)
    base = json.loads((tmp_path / "base.json").read_text())
    base["run"]["dataset"]["sha256_rows"] = "00" * 32
    base["run"]["dataset"]["sha256"] = "00" * 32
    (tmp_path / "base.json").write_text(json.dumps(base))
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "base.json",
            cwd=tmp_path)
    assert r.returncode == 2 and "not the same measurement" in r.stderr
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "base.json",
            "--allow-incompatible", cwd=tmp_path)
    assert r.returncode == 0 and "OK: no drift" in r.stdout


def test_check_against_another_n_is_exit_2(labels_path, tmp_path):
    run("run", str(labels_path), "--judge", "simulated", "--json", "base.json", cwd=tmp_path)
    base = json.loads((tmp_path / "base.json").read_text())
    base["n"] = base["n"] + 1
    (tmp_path / "base.json").write_text(json.dumps(base))
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "base.json",
            cwd=tmp_path)
    assert r.returncode == 2 and "n:" in r.stderr


def test_bad_jev_backend_is_exit_2(labels_path, tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_BACKEND", "foo")
    r = run("run", str(labels_path), "--judge", "jev", cwd=tmp_path)
    assert r.returncode == 2 and "unknown backend" in r.stderr


def test_run_prints_and_writes_intervals_unless_no_ci(labels_path, tmp_path):
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "audit-result.json").read_text())
    lo, hi = res["accuracy_ci"]
    assert lo <= res["accuracy"] <= hi
    assert len(res["ece_ci"]) == 2 and len(res["zero_error_coverage_ci"]) == 2
    report = (tmp_path / "audit-report.md").read_text()
    assert f"accuracy **{res['accuracy']:.1%}** [{lo * 100:.1f}, {hi * 100:.1f}]" in report
    assert "percentile-bootstrap" in report
    assert f"accuracy={res['accuracy']:.1%} [{lo * 100:.1f}, {hi * 100:.1f}]" in r.stdout

    r = run("run", str(labels_path), "--judge", "simulated", "--no-ci", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "audit-result.json").read_text())
    assert "accuracy_ci" not in res and "bootstrap" not in res
    assert "[" not in r.stdout
    assert "percentile-bootstrap" not in (tmp_path / "audit-report.md").read_text()


def test_bootstrap_env_var_skips_intervals(labels_path, tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_AUDIT_BOOTSTRAP", "0")
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "accuracy_ci" not in json.loads((tmp_path / "audit-result.json").read_text())
