"""Paths a caller sees are named as provenance names them; inputs are read the way
`display_path` reads them; the carrier-grade NAT range is on premises. No network."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit import mcp_server
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.runner import load_dataset, normalise_path, run_audit, write_judgments

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"


def _deep(tmp_path: Path) -> Path:
    d = tmp_path / "clients" / "acme corp" / "q3"
    d.mkdir(parents=True)
    return d


def _baseline(at: Path) -> Path:
    rows, meta = load_dataset(str(LABELS))
    result = run_audit(SimulatedJudge(rows), rows, str(LABELS), meta, ci=False)
    at.write_text(json.dumps(result.to_dict()), encoding="utf-8")
    return at


def test_check_drift_names_its_baseline_as_provenance_does(tmp_path, monkeypatch):
    base = _baseline(_deep(tmp_path) / "baseline.json")
    monkeypatch.chdir(ROOT)
    out = mcp_server.check_drift(str(LABELS), str(base))
    assert "error" not in out, out
    assert out["baseline"] == "baseline.json"


@pytest.mark.parametrize("flag", ["--out", "--judgments", "--json"])
def test_a_run_that_cannot_write_an_output_says_so_without_the_path(tmp_path, flag):
    blocked = _deep(tmp_path) / "not-a-dir"
    blocked.write_text("a file where a directory is expected", encoding="utf-8")
    target = blocked / "out.file"
    args = {"--out": str(tmp_path / "r.md"), "--json": str(tmp_path / "r.json"),
            "--judgments": str(tmp_path / "j.jsonl")}
    args[flag] = str(target)
    out = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(LABELS),
                          "--judge", "simulated", *[x for kv in args.items() for x in kv]],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 2, out.stderr
    assert "Traceback" not in out.stderr and "cannot write" in out.stderr
    assert "acme corp" not in out.stderr and str(tmp_path) not in out.stderr, out.stderr


@pytest.mark.parametrize("flag", ["--out", "--json", "--drift"])
def test_a_check_that_cannot_write_an_output_says_so_without_the_path(tmp_path, flag):
    base = _baseline(tmp_path / "baseline.json")
    blocked = _deep(tmp_path) / "not-a-dir"
    blocked.write_text("x", encoding="utf-8")
    out = subprocess.run([sys.executable, "-m", "judge_audit.cli", "check", str(LABELS),
                          "--judge", "simulated", "--baseline", str(base),
                          flag, str(blocked / "out.file")],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 2, out.stderr
    assert "Traceback" not in out.stderr and "cannot write" in out.stderr
    assert "acme corp" not in out.stderr and str(tmp_path) not in out.stderr, out.stderr


def test_the_drift_file_names_its_baseline_as_provenance_does(tmp_path):
    base = _baseline(_deep(tmp_path) / "baseline.json")
    drift = tmp_path / "drift.json"
    subprocess.run([sys.executable, "-m", "judge_audit.cli", "check", str(LABELS),
                    "--judge", "simulated", "--baseline", str(base), "--drift", str(drift)],
                   capture_output=True, text=True, cwd=ROOT)
    assert json.loads(drift.read_text(encoding="utf-8"))["baseline"] == "baseline.json"


@pytest.mark.parametrize("form", ["tilde", "quoted", "double-quoted", "spaces"])
def test_the_mcp_reads_a_path_the_way_provenance_names_it(tmp_path, monkeypatch, form):
    data = _deep(tmp_path) / "labels.jsonl"
    data.write_bytes(LABELS.read_bytes())
    monkeypatch.setenv("HOME", str(tmp_path))
    given = {"tilde": "~/clients/acme corp/q3/labels.jsonl", "quoted": f"'{data}'",
             "double-quoted": f'"{data}"', "spaces": f"  {data}  "}[form]
    assert normalise_path(given) == str(data)
    out = mcp_server.run_audit(given, judge="simulated")
    assert "error" not in out, out
    assert out["run"]["dataset"]["path"] == "labels.jsonl"


def test_the_mcp_writes_judgments_to_a_tilde_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    out = mcp_server.run_audit(str(LABELS), judge="simulated", judgments_path="~/j.jsonl")
    assert "judgments_error" not in out, out
    assert (tmp_path / "j.jsonl").exists() and not (Path.cwd() / "~").exists()


@pytest.mark.parametrize("url", ["http://100.64.0.1:8080/v1", "http://100.100.10.20/v1",
                                 "http://100.127.255.254/v1"])
def test_carrier_grade_nat_addresses_are_on_premises(url):
    from judge_audit.judges.llm import _is_on_premises
    assert _is_on_premises(url), url


@pytest.mark.parametrize("url", ["http://100.63.255.255/v1", "http://100.128.0.1/v1"])
def test_the_addresses_around_that_range_stay_hosted(url):
    from judge_audit.judges.llm import _is_on_premises
    assert not _is_on_premises(url), url


def test_write_judgments_still_writes_where_it_is_told(tmp_path):
    rows, meta = load_dataset(str(LABELS))
    result = run_audit(SimulatedJudge(rows), rows, str(LABELS), meta, ci=False)
    write_judgments(result, str(tmp_path / "j.jsonl"))
    assert (tmp_path / "j.jsonl").read_text(encoding="utf-8").count("\n") == result.n
