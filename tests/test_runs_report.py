"""scripts/runs_report.py: every checkpoint under docs/runs/ is a regenerated report."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import runs_report  # noqa: E402

RESUMABLE = ROOT / "scripts" / "audit_resumable.py"
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"


def test_every_checkpoint_under_docs_runs_yields_a_job():
    """Discovery starts from the evidence: no arena or jury checkpoint goes unregenerated."""
    jobs = {t["ckpt"] for t in runs_report.targets()}
    ckpts = {p.relative_to(ROOT).as_posix()
             for p in (ROOT / "docs" / "runs").glob("*/*/*.ckpt.jsonl")}
    assert len(ckpts) == 54 and ckpts <= jobs, sorted(ckpts - jobs)


def test_a_checkpoint_without_its_report_fails_instead_of_being_skipped(tmp_path):
    ck = tmp_path / "email-clean.ckpt.jsonl"
    ck.write_text("{}\n")
    js = tmp_path / "email-clean.json"
    js.write_text("{}")                                  # the .md is missing
    with pytest.raises(SystemExit, match="missing"):
        runs_report._siblings(js, "email-clean")


def test_a_fresh_run_reports_the_new_calibration_numbers(tmp_path):
    ckpt = tmp_path / "c.ckpt.jsonl"
    p = subprocess.run([sys.executable, str(RESUMABLE), str(LABELS), "--judge", "simulated",
                        "--checkpoint", str(ckpt), "--out", str(tmp_path / "r.md"),
                        "--json", str(tmp_path / "r.json")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    res = json.loads((tmp_path / "r.json").read_text())
    assert f"ece_equal_mass={res['ece_equal_mass']:.4f}" in p.stdout
    assert f"brier={res['brier']:.4f}" in p.stdout
    assert res["brier_ci_method"] and res["ece_equal_mass_ci_method"]
    assert "ECE (equal-mass)" in (tmp_path / "r.md").read_text()


def test_a_non_finite_confidence_in_a_checkpoint_stays_unknown(tmp_path):
    ckpt = tmp_path / "c.ckpt.jsonl"
    rows = sum(1 for line in LABELS.read_text().splitlines()
               if line.strip() and json.loads(line).get("idx") != -1)
    lines = [{"idx": -1, "run": {"judge": {"name": "llm:x"}}}]
    lines += [{"idx": i, "judgments": [{"question": "category", "decision": "spam",
                                        "confidence": float("nan") if i == 3 else 0.9}]}
              for i in range(rows)]
    ckpt.write_text("".join(json.dumps(x) + "\n" for x in lines))   # json writes NaN
    p = subprocess.run([sys.executable, str(RESUMABLE), str(LABELS), "--judge", "llm",
                        "--checkpoint", str(ckpt), "--out", str(tmp_path / "r.md"),
                        "--json", str(tmp_path / "r.json")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    result = json.loads((tmp_path / "r.json").read_text())
    assert result["n"] == rows
    assert result["confidence"] == {"known": rows - 1, "total": rows}
    judgments = [json.loads(line) for line in ckpt.read_text().splitlines()[1:]]
    assert any(str(j["judgments"][0]["confidence"]) == "nan" for j in judgments)
