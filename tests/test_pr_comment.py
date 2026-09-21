"""The PR comment the Action posts: banner, numbers, verdict, one marker."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("pr_comment", ROOT / "scripts" / "pr_comment.py")
pr_comment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pr_comment)

RESULT = {
    "judge": "simulated", "n": 200, "accuracy": 0.855, "ece": 0.0359,
    "zero_error_coverage": {"coverage": 0.19, "n": 38, "threshold": 0.9594},
    "total_cost_usd": 0.016, "p50_latency_s": 0.407, "p99_latency_s": 0.556,
    "run": {"judge": {"name": "simulated", "seed": 7,
                      "tag": "SIMULATED — not a real vendor audit"},
            "dataset": {"path": "examples/email-routing/labels.jsonl", "rows": 200,
                        "sha256": "c5b4c111290aa657236ea520a8043b14ce23e9b26af01a6c5e7ec9b87082e1cf"
                        }},
}


def test_simulated_banner_and_marker_present_once():
    md = pr_comment.build(RESULT)
    assert md.startswith(pr_comment.MARKER + "\n")
    assert md.count(pr_comment.MARKER) == 1
    assert "SIMULATED — not a real vendor audit" in md


def test_numbers_are_formatted_for_humans():
    md = pr_comment.build(RESULT)
    row = ("| 200 | 85.5% | GT-0 unknown | 0.0359 | 19.0% (n=38, conf ≥ 0.9594) | $0.0160 | "
           "0.407 s | 0.556 s |")
    assert row in md
    assert "`examples/email-routing/labels.jsonl` (200 rows, sha256 `c5b4c111290a…`)" in md


def test_ground_truth_tier_sits_next_to_accuracy_and_is_never_silent():
    # No tier recorded: GT-0 plus the hint on how to declare one.
    md = pr_comment.build(RESULT)
    assert "| n | accuracy | ground truth | ECE |" in md
    assert ("_Ground truth: GT-0 unknown — declare it with a dataset header line "
            "(see docs/ground-truth.md)_") in md
    # A declared tier: label in the table cell, meaning and caveats in the line below.
    tiered = json.loads(json.dumps(RESULT))
    tiered["run"]["dataset"]["ground_truth"] = {
        "tier": "GT-1", "label": "constructed", "meaning": "true by construction",
        "validation": "not_validated", "purpose": ["stress test"],
        "caveats": ["synthetic mail", "no human checked it"]}
    md = pr_comment.build(tiered)
    assert "| 200 | 85.5% | GT-1 constructed | 0.0359 |" in md
    assert ("_Ground truth: GT-1 constructed — true by construction; synthetic mail; "
            "no human checked it_") in md


def test_drift_failure_is_rendered_with_its_reasons():
    ece_line = "ECE drifted +0.0359 (>0.02): the judge is less honest than baseline."
    drift = {"ok": False, "failures": [ece_line, "Accuracy dropped 14.50% (>1%)."],
             "baseline": "strict.json", "max_ece_drift": 0.02, "max_acc_drop": 0.01}
    md = pr_comment.build(RESULT, drift, artifact_url="https://example.test/run/1")
    assert "❌ **Drift detected** vs `strict.json`" in md
    assert "- ECE drifted +0.0359" in md and "- Accuracy dropped 14.50%" in md
    assert "[run artifacts](https://example.test/run/1)" in md
    ok = pr_comment.build(RESULT, {**drift, "ok": True, "failures": []})
    assert "✅ **No drift** vs `strict.json`" in ok and "❌" not in ok


def test_real_judge_has_no_banner_and_cli_roundtrip(tmp_path):
    real = json.loads(json.dumps(RESULT))
    real["run"]["judge"] = {"name": "jev", "model": "typesafe-ai/jev", "backend": "gateway"}
    (tmp_path / "r.json").write_text(json.dumps(real))
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "pr_comment.py"),
                          str(tmp_path / "r.json")], capture_output=True, text=True, check=True)
    assert "SIMULATED" not in out.stdout
    assert "Judge `jev` · model `typesafe-ai/jev` · backend `gateway`" in out.stdout
