"""Exit-code contract: 0 ok · 1 drift · 2 usage/config error."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest


def run(*args, cwd):
    return subprocess.run([sys.executable, "-m", "judge_audit.cli", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_run_simulated_writes_report_json_and_judgments(labels_path, tmp_path):
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "SIMULATED" in (tmp_path / "audit-report.md").read_text()
    res = json.loads((tmp_path / "audit-result.json").read_text())
    assert res["n"] == 12 and res["run"]["judge"]["name"] == "simulated"
    assert res["confidence"] == {"known": 12, "total": 12}
    assert "confidence_known=12/12" in r.stdout
    # the summary line is what gets copied: a simulated result must say so on it
    assert r.stdout.startswith("SIMULATED — not a real vendor audit · judge=simulated")
    assert (tmp_path / "audit-judgments.jsonl").read_text().count("\n") == 12


def test_check_no_drift_against_own_baseline(labels_path, tmp_path):
    run("run", str(labels_path), "--judge", "simulated", "--json", "base.json", cwd=tmp_path)
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "base.json",
            cwd=tmp_path)
    assert r.returncode == 0
    assert r.stdout.startswith("SIMULATED — not a real vendor audit · OK: no drift")


def test_check_detects_drift(labels_path, tmp_path):
    (tmp_path / "strict.json").write_text(json.dumps({"ece": 0.0, "accuracy": 1.0}))
    r = run("check", str(labels_path), "--judge", "simulated", "--baseline", "strict.json",
            cwd=tmp_path)
    assert r.returncode == 1
    assert r.stderr.startswith("SIMULATED — not a real vendor audit · DRIFT DETECTED")


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


def test_outputs_are_written_atomically_and_leave_no_temp_files(labels_path, tmp_path):
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert not list(tmp_path.glob(".judge-audit-*.tmp"))
    # A failed run must not replace a good report with a half-written one.
    good = (tmp_path / "audit-report.md").read_text()
    r = run("run", "nope.jsonl", "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 2
    assert (tmp_path / "audit-report.md").read_text() == good
    assert not list(tmp_path.glob(".judge-audit-*.tmp"))


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


def test_run_prints_and_writes_brier_and_equal_mass_ece(labels_path, tmp_path):
    r = run("run", str(labels_path), "--judge", "simulated", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "audit-result.json").read_text())
    for key in ("ece_equal_mass", "brier"):
        assert 0.0 <= res[key] <= 1.0
        assert res[f"{key}_ci_method"] in ("bootstrap", "degenerate-bootstrap")
    assert f"ece_equal_mass={res['ece_equal_mass']:.4f}" in r.stdout
    assert f"brier={res['brier']:.4f}" in r.stdout
    report = (tmp_path / "audit-report.md").read_text()
    assert f"ECE (equal-mass) **{res['ece_equal_mass']:.4f}**" in report
    assert f"Brier **{res['brier']:.4f}**" in report


def test_html_report_carries_brier_and_equal_mass_ece(labels_path, tmp_path):
    pytest.importorskip("matplotlib")
    r = run("run", str(labels_path), "--judge", "simulated", "--format", "html", "--out",
            "r.html", "--json", "r.json", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "r.json").read_text())
    page = (tmp_path / "r.html").read_text()
    assert f"ECE (equal-mass) <b>{res['ece_equal_mass']:.4f}</b>" in page
    assert f"Brier <b>{res['brier']:.4f}</b>" in page
