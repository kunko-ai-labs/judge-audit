from __future__ import annotations

import json

import pytest

from judge_audit.judges.base import Judge, Judgment, Question
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.metrics.calibration import accuracy_ci, brier_ci, clopper_pearson, ece_ci
from judge_audit.runner import (
    checkpoint_confidence,
    checkpoint_cost,
    checkpoint_parse_status,
    clamp_confidence,
    groups_of,
    load_jsonl,
    record_of,
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
    assert res.n == 0 and res.accuracy == 0.0 and res.ece is None


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


def test_unknown_confidence_is_excluded_from_calibration_not_accuracy(labels_path):
    records = [
        {"confidence": 0.9, "correct": True, "latency_s": 0.1, "cost_usd": 0.01},
        {"confidence": None, "correct": False, "latency_s": 0.2, "cost_usd": None},
    ]
    res = summarize("mixed", records, ci=False, groups=["known", "unknown"])
    assert res.n == 2 and res.accuracy == 0.5
    assert res.confidence == {"known": 1, "total": 2}
    assert res.ece == 0.1 and res.ece_equal_mass == 0.1 and res.brier == 0.01
    assert sum(b["n"] for b in res.reliability) == 1 and res.curve
    assert res.zero_error == {"coverage": 1.0, "n": 1, "threshold": 0.9}
    assert res.total_cost_usd is None
    assert res.to_dict()["confidence"] == {"known": 1, "total": 2}
    assert res.to_dict()["total_cost_usd"] is None


def test_no_known_confidence_publishes_null_calibration_metrics():
    records = [{"confidence": None, "correct": False, "cost_usd": 0.0}]
    res = summarize("unknown", records, ci=True, groups=["one"])
    assert res.n == 1 and res.accuracy == 0.0
    assert res.confidence == {"known": 0, "total": 1}
    assert res.ece is None and res.ece_equal_mass is None and res.brier is None
    assert res.reliability == [] and res.curve == []
    assert res.zero_error == {"coverage": None, "n": 0, "threshold": None}
    assert res.ece_ci is None and res.zero_error_coverage_ci is None


def test_legacy_checkpoint_confidence_is_unknown_without_a_decision():
    # the old parser stored 0.0 for these; only a chat row's explicit parse says so
    missing = {"decision": "", "confidence": 0.0, "raw": {"parsed": None}}
    blank = {"decision": "", "confidence": 0.0, "raw": {"parsed": {"decision": ""}}}
    empty = {"decision": "", "confidence": 0.0, "raw": {"parsed": {}}}
    no_decision_declared = {"decision": "", "confidence": 0.0,
                            "raw": {"parsed": {"confidence": 0.0}}}
    for j in (missing, blank, empty, no_decision_declared):
        assert checkpoint_confidence(j) is None
        assert checkpoint_parse_status(j) == "no_answer"
    no_number = {"decision": "spam", "confidence": 0.0, "raw": {"parsed": {"decision": "spam"}}}
    assert checkpoint_confidence(no_number) is None
    assert checkpoint_parse_status(no_number) == "no_confidence"
    outside = {"decision": "invoice", "confidence": 0.8,
               "raw": {"parsed": {"decision": "invoice", "confidence": 0.8}}}
    assert checkpoint_confidence(outside) == 0.8 and checkpoint_parse_status(outside) == "parsed"
    non_llm = {"decision": "spam", "confidence": 0.7, "raw": {}}
    assert checkpoint_confidence(non_llm) == 0.7 and checkpoint_parse_status(non_llm) == "parsed"


def test_legacy_checkpoint_cost_distinguishes_local_free_from_unknown_hosted():
    judgment = {"cost_usd": 0.0, "raw": {"priced": False}}
    local = {"judge": {"provider": "openai-compatible", "base_url": "http://localhost:11434/v1"}}
    hosted = {"judge": {"provider": "openai-compatible", "base_url": "https://example.test/v1"}}
    assert checkpoint_cost(judgment, local) == 0.0
    assert checkpoint_cost(judgment, hosted) is None


def test_record_preserves_parse_status_and_unknown_confidence():
    row = {"_meta": {"split": "test"}}
    judgment = Judgment("category", "", None, parse_status="no_answer", cost_usd=None)
    record = record_of(0, row, judgment, "spam")
    assert record["confidence"] is None and record["parse_status"] == "no_answer"
    assert record["correct"] is False and record["cost_usd"] is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), "NaN", "x", -0.1, 1.2])
def test_invalid_confidence_is_unknown_not_clamped(bad):
    assert clamp_confidence(bad) is None
    assert clamp_confidence("0.5") == 0.5


def test_record_of_marks_an_invalid_confidence_from_any_adapter_as_no_confidence():
    judgment = Judgment("category", "spam", 1.0000001)  # a non-chat adapter, parse_status default
    record = record_of(0, {}, judgment, "spam")
    assert record["confidence"] is None and record["parse_status"] == "no_confidence"
    blank = Judgment("category", "", 0.0, parse_status="no_answer")
    assert record_of(0, {}, blank, "spam")["confidence"] is None


def test_served_versions_count_decisions_per_reported_version_and_skip_old_records():
    from judge_audit.runner import served_versions

    recs = [{"raw": {"served": {"model": "m-1", "system_fingerprint": None}}}] * 3 + \
           [{"raw": {"served": {"model": "m-2", "system_fingerprint": "fp"}}}] + \
           [{"raw": {"served": {"model": None, "system_fingerprint": None}}}] * 2
    s = served_versions(recs)
    assert s == {"versions": [{"model": "m-1", "system_fingerprint": None, "decisions": 3},
                              {"model": "m-2", "system_fingerprint": "fp", "decisions": 1}],
                 "decisions_without_version": 2}
    assert served_versions([{"raw": {"text": "old checkpoint"}}]) is None


def _served_judge(version, fingerprint=None):
    from judge_audit.judges.base import Judge, Judgment

    class J(Judge):
        name = "versioned"

        def decide(self, state, questions):
            return [Judgment(question=q.name, decision=q.options[0], confidence=0.9,
                             raw={"served": {"model": version,
                                             "system_fingerprint": fingerprint}})
                    for q in questions]
    return J()


def _rows(n=3):
    return [{"state": f"s{i}", "questions": [{"name": "c", "options": ["x", "y"]}],
             "labels": {"c": "x"}} for i in range(n)]


def test_run_audit_publishes_the_served_versions_in_the_run():
    from judge_audit.runner import run_audit

    r = run_audit(_served_judge("m-1"), _rows(), ci=False)
    assert r.run["served"] == {"versions": [{"model": "m-1", "system_fingerprint": None,
                                             "decisions": 3}],
                               "decisions_without_version": 0}


def test_rows_without_the_key_count_as_without_version_once_a_run_records_versions():
    from judge_audit.runner import served_versions

    recs = [{"raw": {"served": {"model": "m-1", "system_fingerprint": None}}},
            {"raw": {"text": "resumed row from before the upgrade"}}]
    assert served_versions(recs)["decisions_without_version"] == 1


def test_the_report_names_each_served_version_with_its_decisions():
    from judge_audit.report import provenance_lines

    lines = provenance_lines({"judge": {"name": "x"}, "served": {
        "versions": [{"model": "m-1", "system_fingerprint": "fp_a", "decisions": 200}],
        "decisions_without_version": 3}})
    assert any("`m-1` (fingerprint `fp_a`) × 200 decisions" in ln
               and "3 decisions without a version" in ln for ln in lines)


@pytest.mark.parametrize("base,now,warns", [
    ("m-1", "m-2", True),     # the provider changed what it served
    ("m-1", "m-1", False),
    (None, "m-1", False),     # a side without versions cannot be compared
    ("m-1", None, False),
    (("m-1", "fp_a"), ("m-1", "fp_b"), True),   # same model, another backend fingerprint
])
def test_the_drift_gate_warns_when_the_served_version_changed(base, now, warns, tmp_path):
    import json
    import warnings

    from judge_audit.report import check_drift
    from judge_audit.runner import run_audit

    path = tmp_path / "baseline.json"
    def judge(v):
        return _served_judge(*v) if isinstance(v, tuple) else _served_judge(v)

    path.write_text(json.dumps(run_audit(judge(base), _rows(), ci=False).to_dict()))
    current = run_audit(judge(now), _rows(), ci=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_drift(current, str(path))
    assert any("model version or backend fingerprint" in str(w.message)
               for w in caught) is warns


def test_a_checkpoint_rebuild_publishes_served_versions_only_when_rows_carry_them(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from audit_resumable import build_result

    rows = _rows(2)
    started = {"judge": {"name": "x"}, "timestamp_utc": "2026-09-24T00:00:00+00:00"}

    def done(raw):
        return {i: {"idx": i, "judgments": [{"question": "c", "decision": "x",
                                             "confidence": 0.9, "latency_s": 1.0,
                                             "cost_usd": 0.0, "raw": raw}]} for i in range(2)}

    new = build_result("x", rows, {}, [0, 1], done({"served": {"model": "m-1"}}),
                       tmp_path / "a.ckpt.jsonl", dict(started), None)
    assert new.run["served"]["versions"][0]["model"] == "m-1"
    old = build_result("x", rows, {}, [0, 1], done({"text": "before the upgrade"}),
                       tmp_path / "b.ckpt.jsonl", dict(started), None)
    assert "served" not in old.run  # older checkpoints: their reports do not change
