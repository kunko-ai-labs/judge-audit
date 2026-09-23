from __future__ import annotations

import json

import pytest

from judge_audit.judges.base import Judge, Judgment, Question
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.metrics.calibration import accuracy_ci, brier_ci, clopper_pearson, ece_ci
from judge_audit.runner import (
    clamp_confidence,
    groups_of,
    load_jsonl,
    run_audit,
    summarize,
    write_judgments,
)


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


def test_summary_carries_bootstrap_intervals_around_the_point_estimates(labels_path):
    rows = load_jsonl(str(labels_path))
    res = run_audit(ConstantJudge("quote_request", 0.9), rows, ci=True)
    # All correct: the bootstrap cannot move, so accuracy and zero-error coverage are
    # published as exact binomial intervals and ECE keeps its (degenerate) bootstrap.
    assert res.accuracy_ci == clopper_pearson(res.n, res.n)
    assert res.accuracy_ci.method == "clopper-pearson"
    assert res.ece_ci == (0.1, 0.1) and res.ece_ci.degenerate
    assert res.zero_error_coverage_ci == clopper_pearson(res.n, res.n)
    d = res.to_dict()
    assert d["accuracy_ci"] == list(clopper_pearson(res.n, res.n))
    assert d["accuracy_ci_method"] == "clopper-pearson"
    assert d["ece_ci"] is None and d["ece_ci_method"] == "degenerate-bootstrap"
    assert d["bootstrap"]["n_boot"] == 2000
    assert d["bootstrap"]["seed"] == 0 and d["bootstrap"]["level"] == 0.95


def test_intervals_bracket_a_mixed_result_and_can_be_skipped(labels_path, monkeypatch):
    rows = load_jsonl(str(labels_path))
    judge = SimulatedJudge(rows)
    res = run_audit(judge, rows, ci=True)
    lo, hi = res.accuracy_ci
    assert lo <= res.accuracy <= hi and lo < hi
    lo, hi = res.ece_ci
    assert lo <= res.ece <= hi
    assert run_audit(judge, rows, ci=False).accuracy_ci is None
    assert "accuracy_ci" not in run_audit(judge, rows, ci=False).to_dict()
    monkeypatch.setenv("JUDGE_AUDIT_BOOTSTRAP", "0")
    assert run_audit(judge, rows).accuracy_ci is None
    monkeypatch.setenv("JUDGE_AUDIT_BOOTSTRAP", "1")
    assert run_audit(judge, rows).accuracy_ci == res.accuracy_ci


def test_groups_of_falls_back_to_one_cluster_per_record():
    rows = [{"state": "a"}, {"state": "b"}]
    assert groups_of([{"idx": 0}, {"idx": 1}, {"idx": 0}], rows) == ["a", "b", "a"]
    assert groups_of([{"idx": 7}, {}], rows) == ["#0", "#1"]


def test_intervals_resample_distinct_texts_not_rows():
    # Four distinct states, each judged twice: eight rows, four independent texts.
    rows = []
    for i in range(4):
        rows += [{"state": f"state {i}",
                  "questions": [{"name": "category", "type": "choice",
                                 "options": ["quote_request", "spam"]}],
                  "labels": {"category": "quote_request" if i else "spam"}}] * 2
    res = run_audit(ConstantJudge("quote_request", 0.9), rows, ci=True)
    assert res.accuracy == 0.75
    correct = [r["correct"] for r in res.records]
    assert res.accuracy_ci == accuracy_ci(correct, groups=[r["state"] for r in rows])
    # Treating the eight rows as independent would claim a narrower interval.
    naive = accuracy_ci(correct)
    assert res.accuracy_ci[1] - res.accuracy_ci[0] > naive[1] - naive[0]


def test_summary_carries_brier_and_equal_mass_ece_with_their_intervals(labels_path):
    rows = load_jsonl(str(labels_path))
    res = run_audit(ConstantJudge("quote_request", 0.9), rows, ci=True)
    # 12 rows all right at 0.9: one bin whatever the binning, Brier (1 - 0.9)^2
    assert res.ece == 0.1 and res.ece_equal_mass == 0.1 and res.brier == 0.01
    assert res.ece_equal_mass_ci.degenerate and res.brier_ci.degenerate
    d = res.to_dict()
    assert d["ece_equal_mass"] == 0.1 and d["brier"] == 0.01
    assert d["ece_equal_mass_ci"] is None
    assert d["ece_equal_mass_ci_method"] == "degenerate-bootstrap"
    assert d["brier_ci"] is None and d["brier_ci_method"] == "degenerate-bootstrap"
    # the new keys sit next to the ECE they qualify
    keys = list(d)
    assert keys.index("ece") + 1 == keys.index("ece_equal_mass")
    assert keys.index("ece_equal_mass") + 1 == keys.index("brier")


def test_intervals_of_the_new_numbers_resample_distinct_texts(labels_path):
    rows = []
    for i in range(4):
        rows += [{"state": f"state {i}",
                  "questions": [{"name": "category", "type": "choice",
                                 "options": ["quote_request", "spam"]}],
                  "labels": {"category": "quote_request" if i else "spam"}}] * 2
    res = run_audit(ConstantJudge("quote_request", 0.9), rows, ci=True)
    conf = [r["confidence"] for r in res.records]
    ok = [r["correct"] for r in res.records]
    texts = [r["state"] for r in rows]
    assert res.brier_ci == brier_ci(conf, ok, groups=texts)
    assert res.ece_equal_mass_ci == ece_ci(conf, ok, groups=texts, binning="equal_mass")


def test_brier_and_equal_mass_ece_of_no_rows_are_unknown_not_zero(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text(json.dumps({"state": "s", "questions": [{"name": "q", "options": ["a", "b"]}],
                             "labels": {}}) + "\n")
    res = run_audit(ConstantJudge("a", 0.5), load_jsonl(str(p)))
    assert res.brier is None and res.ece_equal_mass is None
    assert res.to_dict()["brier"] is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_confidence_stops_the_audit_instead_of_being_clamped(labels_path, bad):
    # max(0, min(1, nan)) is 1.0: clamping would impute full confidence to an unknown one
    rows = load_jsonl(str(labels_path))
    with pytest.raises(ValueError, match="not finite"):
        run_audit(ConstantJudge("quote_request", bad), rows, ci=False)
    assert clamp_confidence(1.2) == 1.0 and clamp_confidence(-0.1) == 0.0
    assert clamp_confidence("0.5") == 0.5
