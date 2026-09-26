"""The MCP server exposes the same engine; simulated results are always tagged."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("mcp")

from judge_audit import mcp_server  # noqa: E402
from judge_audit.judges.simulated import SIMULATED_TAG  # noqa: E402


def test_run_audit_simulated_is_tagged_and_carries_provenance(labels_path, tmp_path):
    out = mcp_server.run_audit(str(labels_path), judge="simulated",
                               judgments_path=str(tmp_path / "j.jsonl"))
    assert "error" not in out
    assert out["n"] == 12 and 0.0 <= out["ece"] <= 1.0
    assert out["confidence"] == {"known": 12, "total": 12}
    assert out["tag"] == SIMULATED_TAG
    assert out["run"]["judge"]["name"] == "simulated"
    assert out["run"]["dataset"]["rows"] == 12
    assert (tmp_path / "j.jsonl").read_text().count("\n") == 12
    assert out["judgments_path"] == str(tmp_path / "j.jsonl")


def test_run_audit_missing_file_is_a_structured_error(tmp_path):
    out = mcp_server.run_audit(str(tmp_path / "nope.jsonl"))
    assert set(out) == {"error"} and "not found" in out["error"]


def test_run_audit_jev_without_key_is_a_structured_error(labels_path, monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_API_KEY", raising=False)
    monkeypatch.delenv("JEV_BACKEND", raising=False)
    out = mcp_server.run_audit(str(labels_path), judge="jev")
    assert "error" in out and "AI_GATEWAY_API_KEY" in out["error"]


def test_run_audit_unknown_judge_is_a_structured_error(labels_path):
    out = mcp_server.run_audit(str(labels_path), judge="oracle")
    assert "error" in out and "unknown judge" in out["error"]


def test_check_drift_ok_against_own_baseline(labels_path, tmp_path):
    base = mcp_server.run_audit(str(labels_path))
    (tmp_path / "base.json").write_text(json.dumps(base))
    out = mcp_server.check_drift(str(labels_path), str(tmp_path / "base.json"))
    assert out["ok"] is True and out["failures"] == [] and out["tag"] == SIMULATED_TAG


def test_check_drift_detects_a_less_honest_judge(labels_path, tmp_path):
    (tmp_path / "strict.json").write_text(json.dumps({"ece": 0.0, "accuracy": 1.0}))
    out = mcp_server.check_drift(str(labels_path), str(tmp_path / "strict.json"))
    assert out["ok"] is False and any("ECE" in f for f in out["failures"])


def test_check_drift_incompatible_baseline_is_a_structured_error(labels_path, tmp_path):
    base = mcp_server.run_audit(str(labels_path))
    base["run"]["dataset"]["sha256_rows"] = "00" * 32
    base["run"]["dataset"]["sha256"] = "00" * 32
    (tmp_path / "other.json").write_text(json.dumps(base))
    out = mcp_server.check_drift(str(labels_path), str(tmp_path / "other.json"))
    assert out.get("incompatible_baseline") is True and "sha256" in out["error"]
    ok = mcp_server.check_drift(str(labels_path), str(tmp_path / "other.json"),
                                allow_incompatible=True)
    assert ok["ok"] is True


def test_check_drift_empty_baseline_is_a_structured_error(labels_path, tmp_path):
    (tmp_path / "empty.json").write_text("{}")
    out = mcp_server.check_drift(str(labels_path), str(tmp_path / "empty.json"))
    assert "error" in out and "baseline" in out["error"]


def test_list_judges_names_every_judge():
    out = mcp_server.list_judges()
    assert {j["name"] for j in out["judges"]} == {"jev", "llm", "nli", "finetuned", "logprob",
                                                  "simulated"}
    assert all("description" in j and "env" in j for j in out["judges"])
    assert out["simulated_tag"] == SIMULATED_TAG


def test_main_help_exits_zero_without_starting_the_server(capsys):
    with pytest.raises(SystemExit) as e:
        mcp_server.main(["--help"])
    assert e.value.code == 0 and "run_audit" in capsys.readouterr().out


@pytest.mark.anyio
async def test_tools_are_registered():
    tools = await mcp_server.server.list_tools()
    assert {t.name for t in tools} == {"run_audit", "check_drift", "list_judges"}


@pytest.mark.anyio
async def test_run_audit_returns_brier_and_equal_mass_ece(labels_path):
    out = mcp_server.run_audit(str(labels_path), judge="simulated")
    assert 0.0 <= out["brier"] <= 1.0 and 0.0 <= out["ece_equal_mass"] <= 1.0
    assert "brier_ci" in out and "ece_equal_mass_ci" in out
    tool = next(t for t in await mcp_server.server.list_tools() if t.name == "run_audit")
    assert "Brier" in tool.description and "equal-mass" in tool.description
