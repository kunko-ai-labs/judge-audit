"""LLMJudge custom provider: a module on disk supplies the transport."""
from __future__ import annotations

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.llm import LLMJudge

MODULE = '''
CALLS = []
def call(model, system, user):
    CALLS.append((model, system[:20], user[:20]))
    return '{"answers": {"category": {"decision": "spam", "confidence": 0.7}}}', 40, 10
def describe(model):
    return {"provider": "hosted-api"}
def price(model):
    return (1.0, 2.0)
'''


def test_custom_provider_is_loaded_from_a_file(monkeypatch, tmp_path):
    mod = tmp_path / "prov.py"
    mod.write_text(MODULE)
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "vendor-internal-id-123")
    monkeypatch.setenv("LLM_MODEL_LABEL", "big-model")
    j = LLMJudge()
    q = Question(name="category", type=QuestionType.CHOICE, instructions="x",
                 options=["spam", "ham"])
    (out,) = j.decide("hello", [q])
    assert out.decision == "spam" and out.confidence == 0.7
    assert out.cost_usd == pytest.approx((40 * 1.0 + 10 * 2.0) / 1e6)
    d = j.describe()
    assert d["model"] == "big-model" and d["provider"] == "hosted-api" and j.name == "llm:big-model"
    assert "vendor-internal-id-123" not in str(d)


def test_custom_provider_without_module_is_a_config_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.delenv("LLM_PROVIDER_MODULE", raising=False)
    with pytest.raises(RuntimeError, match="LLM_PROVIDER_MODULE"):
        LLMJudge()
