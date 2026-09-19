from __future__ import annotations

import json

import pytest

from judge_audit.judges.base import Judge, Judgment, Question
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.runner import load_jsonl, run_audit, summarize, write_judgments


class ConstantJudge(Judge):
    name = "constant"

    def __init__(self, decision: str, confidence: float):
        self.decision, self.confidence = decision, confidence

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        return [Judgment(q.name, self.decision, self.confidence, latency_s=0.1, cost_usd=0.001)
                for q in questions]

    def describe(self) -> dict:
        return {"name": self.name, "model": "unit-test"}


def test_run_audit_records_everything_and_summarises(labels_path):
    rows = load_jsonl(str(labels_path))
    res = run_audit(ConstantJudge("quote_request", 0.9), rows, labels_path=str(labels_path))
    assert res.n == 12 and res.accuracy == 1.0
    assert res.ece == 0.1  # says 0.9, is right 100% of the time: under-confident by 0.1
    assert res.total_cost_usd == pytest.approx(0.012)
    assert len(res.records) == 12
    assert res.run["judge"] == {"name": "constant", "model": "unit-test"}
    assert res.run["dataset"]["rows"] == 12 and len(res.run["dataset"]["sha256"]) == 64


def test_always_wrong_and_confident_is_the_worst_ece(labels_path):
    rows = load_jsonl(str(labels_path))
    res = run_audit(ConstantJudge("spam", 1.0), rows)
    assert res.accuracy == 0.0 and res.ece == 1.0
    assert res.zero_error == {"coverage": 0.0, "n": 0, "threshold": None}


def test_simulated_judge_is_deterministic(labels_path):
    rows = load_jsonl(str(labels_path))
    a = run_audit(SimulatedJudge(rows), rows).to_dict()
    b = run_audit(SimulatedJudge(rows), rows).to_dict()
    a.pop("run"), b.pop("run")
    assert a == b


def test_write_judgments_roundtrip(labels_path, tmp_path):
    rows = load_jsonl(str(labels_path))
    res = run_audit(ConstantJudge("quote_request", 0.8), rows)
    out = tmp_path / "j.jsonl"
    write_judgments(res, str(out))
    back = [json.loads(line) for line in out.read_text().splitlines()]
    assert len(back) == 12 and back[0]["correct"] is True and back[0]["confidence"] == 0.8
    again = summarize("x", back)
    assert again.accuracy == res.accuracy and again.ece == res.ece


def test_rows_without_a_label_for_the_question_are_skipped(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps({"state": "s", "questions": [{"name": "q", "options": ["a", "b"]}],
                             "labels": {}}) + "\n")
    res = run_audit(ConstantJudge("a", 0.5), load_jsonl(str(p)))
    assert res.n == 0 and res.accuracy == 0.0 and res.ece == 0.0
