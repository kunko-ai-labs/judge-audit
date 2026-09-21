"""Arena report: per-judge summary and the rendered selection rationale."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from arena_report import render, summarize  # noqa: E402


def rec(decision, confidence, expected="b"):
    return {"decision": decision, "confidence": confidence, "correct": decision == expected,
            "latency_s": 1.0, "cost_usd": 0.0, "meta": {}}


def test_summarize_counts_blank_answers_separately():
    s = summarize([rec("b", .9), rec("", 0.0), rec(" ", 0.0), rec("a", .8)], "email-clean")
    assert s["n"] == 4 and s["no_answer"] == 2 and s["accuracy"] == 0.25
    assert summarize([rec("b", .9)], "email-clean")["no_answer"] == 0


def test_render_states_why_these_judges_and_the_blank_column():
    judges = {"jev": {"label": "Jev", "method": "option probability",
                      "datasets": {"email-clean": summarize([rec("b", .9), rec("", 0.0)],
                                                            "email-clean")}}}
    md = render(judges)
    assert "## Why these judges" in md
    for name in ("Jev", "Claude Sonnet 4.5", "Gemini 3 Flash", "Llama 3.3 70B", "DeepSeek R1",
                 "gemma4", "llama3.2", "DeBERTa", "control", "#51"):
        assert name in md
    for missing in ("OpenJev", "GPT", "Mistral"):
        assert missing in md
    assert "| no answer |" in md
    assert "| Jev | option probability | 50.0% |" in md and "| 1 |" in md
