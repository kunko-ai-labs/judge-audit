"""What `describe()` has to record for a number to be reproducible.

Two runs of the same judge on the same rows can differ because the sampling
temperature changed or because the prompt changed. Both are in the provenance, so a
reader can tell "the judge got worse" from "we asked a different question".
"""
from __future__ import annotations

import pytest

from judge_audit.judges.jev import CRITERIA_VERSION, JevJudge
from judge_audit.judges.llm import LLMJudge, prompt_sha256
from judge_audit.judges.simulated import SimulatedJudge


def llm(monkeypatch, provider="openai-compatible", **env):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_MODEL", "gpt-5-mini")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return LLMJudge()


def test_every_judge_declares_a_temperature_or_says_it_has_none(monkeypatch):
    # A judge with no temperature parameter says 'n/a'; it is never silently absent.
    assert llm(monkeypatch).describe()["temperature"] == 0
    assert SimulatedJudge([]).describe()["temperature"] == "n/a"
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    assert JevJudge().describe()["temperature"] == "n/a"


def test_the_anthropic_path_declares_the_same_temperature_as_the_openai_path(monkeypatch):
    sdk = pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    j = LLMJudge(provider="anthropic", model="claude-opus-5")
    assert j.describe()["temperature"] == 0 == llm(monkeypatch).describe()["temperature"]
    assert sdk is not None


def test_the_anthropic_call_sends_temperature_zero(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    j = LLMJudge(provider="anthropic", model="claude-opus-5")
    sent = {}

    class Msg:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": '{"answers": {}}'})()]
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()

    def create(**kwargs):
        sent.update(kwargs)
        return Msg()

    monkeypatch.setattr(j._client.messages, "create", create)
    j._call_anthropic("hello")
    assert sent["temperature"] == 0


def test_describe_carries_the_prompt_hash_of_system_plus_template(monkeypatch):
    d = llm(monkeypatch).describe()
    assert d["prompt_sha256"] == prompt_sha256()
    assert len(d["prompt_sha256"]) == 64


def test_the_prompt_hash_changes_when_the_prompt_changes(monkeypatch):
    import judge_audit.judges.llm as mod
    before = prompt_sha256()
    monkeypatch.setattr(mod, "SYSTEM", mod.SYSTEM + " and be brief")
    assert prompt_sha256() != before


def test_jev_records_the_version_of_its_criteria_rendering(monkeypatch):
    monkeypatch.setenv("JEV_BACKEND", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", "x")
    d = JevJudge().describe()
    # Jev has no text prompt; what it is shown is the criteria map this version renders.
    assert d["criteria_version"] == CRITERIA_VERSION
    assert "prompt_sha256" not in d
