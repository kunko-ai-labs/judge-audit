"""US-004-015: no expected decision leaves the denominator silently."""
from __future__ import annotations

import pytest

from judge_audit.judges.base import Judge, Judgment
from judge_audit.report import render_markdown
from judge_audit.runner import IncompleteAnswers, run_audit

Q = [{"name": "a", "type": "choice", "options": ["x", "y"]},
     {"name": "b", "type": "choice", "options": ["x", "y"]}]


def rows(n=4):
    return [{"state": f"s{i}", "questions": Q, "labels": {"a": "x", "b": "y"}} for i in range(n)]


class Scripted(Judge):
    name = "scripted"

    def __init__(self, answer):
        self.answer = answer

    def decide(self, state, questions):
        return self.answer(state)


def right(q, conf=0.9):
    return Judgment(question=q, decision={"a": "x", "b": "y"}[q], confidence=conf)


def test_a_complete_run_reports_every_decision_answered():
    r = run_audit(Scripted(lambda s: [right("a"), right("b")]), rows(), ci=False)
    assert r.n == 8 and r.accuracy == 1.0
    assert r.completeness == {"expected": 8, "answered": 8, "missing": 0, "unexpected": 0}
    assert r.to_dict()["completeness"]["answered"] == 8


def test_a_skipped_question_has_unknown_latency_so_silence_does_not_look_fast():
    slow = [Judgment(question="a", decision="x", confidence=0.9, latency_s=2.0)]
    r = run_audit(Scripted(lambda s: slow), rows(4), ci=False)
    assert r.p50_latency_s == 2.0 and r.p99_latency_s == 2.0
    assert all(x["latency_s"] is None for x in r.records if x["question"] == "b")


def test_a_skipped_question_costs_nothing_extra_unless_the_row_cost_is_unknown():
    priced = [Judgment(question="a", decision="x", confidence=0.9, cost_usd=0.002)]
    assert run_audit(Scripted(lambda s: priced), rows(2), ci=False).total_cost_usd == \
        pytest.approx(0.004)
    # nothing came back at a known cost: the skipped question's cost is unknown, not $0
    assert run_audit(Scripted(lambda s: []), rows(2), ci=False).total_cost_usd is None


@pytest.mark.parametrize("blank", ["", "  ", None])
def test_a_blank_or_null_label_is_a_dataset_error(blank):
    bad = rows(1)
    bad[0]["labels"]["b"] = blank
    with pytest.raises(IncompleteAnswers, match="blank or null"):
        run_audit(Scripted(lambda s: [right("a")]), bad, ci=False)


def test_a_skipped_question_stays_in_n_as_a_wrong_answer_with_unknown_confidence():
    # it answers only the question it is sure of: the old runner scored this 100 % on n=4
    r = run_audit(Scripted(lambda s: [right("a")]), rows(), ci=False)
    assert r.n == 8 and r.accuracy == 0.5
    assert r.completeness["missing"] == 4
    assert r.confidence == {"known": 4, "total": 8}
    skipped = [x for x in r.records if x["question"] == "b"]
    assert all(x["parse_status"] == "no_answer" and x["confidence"] is None
               and not x["correct"] for x in skipped)


def test_an_answer_to_a_question_not_asked_is_counted_and_dropped():
    extra = Judgment(question="zzz", decision="x", confidence=1.0)
    r = run_audit(Scripted(lambda s: [right("a"), right("b"), extra]), rows(), ci=False)
    assert r.n == 8 and r.completeness["unexpected"] == 4


def test_two_answers_to_one_question_break_the_contract():
    with pytest.raises(IncompleteAnswers, match="twice"):
        run_audit(Scripted(lambda s: [right("a"), right("a", 0.2), right("b")]), rows(),
                  ci=False)


def test_a_label_without_its_question_is_a_dataset_error():
    bad = rows(1)
    bad[0]["labels"]["c"] = "x"
    with pytest.raises(IncompleteAnswers, match="name no question"):
        run_audit(Scripted(lambda s: [right("a"), right("b")]), bad, ci=False)


def test_an_unlabelled_question_is_asked_but_not_scored():
    part = rows(2)
    for r in part:
        del r["labels"]["b"]
    r = run_audit(Scripted(lambda s: [right("a"), right("b")]), part, ci=False)
    assert r.n == 2 and r.completeness == {"expected": 2, "answered": 2, "missing": 0,
                                           "unexpected": 0}


def test_the_report_says_how_complete_the_run_was():
    r = run_audit(Scripted(lambda s: [right("a")]), rows(), ci=False)
    md = render_markdown(r)
    assert "answered **4/8** expected decisions · 4 skipped" in md


def test_the_checkpoint_check_finds_a_skipped_and_a_doubled_answer(tmp_path, monkeypatch):
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import check_complete

    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(r) for r in rows(3)) + "\n")
    ans = [{"question": "a", "decision": "x"}, {"question": "b", "decision": "y"}]
    lines = [{"idx": -1, "run": {"dataset": {"path": str(labels)}}},
             {"idx": 0, "judgments": ans},
             {"idx": 1, "judgments": ans[:1]},                 # b skipped
             {"idx": 2, "judgments": ans + ans[:1]}]            # a answered twice
    ckpt = tmp_path / "x.ckpt.jsonl"
    ckpt.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    monkeypatch.setattr(check_complete, "ROOT", Path("/"))
    found = check_complete.gaps(ckpt)
    assert any("row 1 missing ['b']" in g for g in found)
    assert any("row 2 duplicate ['a']" in g for g in found)
    assert len(found) == 2


def test_every_committed_checkpoint_is_complete():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import check_complete

    ckpts = sorted((check_complete.ROOT / "docs" / "runs").rglob("*.ckpt.jsonl"))
    assert len(ckpts) >= 58
    assert [g for c in ckpts for g in check_complete.gaps(c)] == []


def _scripts():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def test_the_resumable_driver_writes_a_skipped_question_as_a_no_answer():
    _scripts()
    from audit_resumable import checkpoint_row

    rec = checkpoint_row(3, rows(1)[0], [right("a")])
    assert [j["question"] for j in rec["judgments"]] == ["a", "b"]
    b = rec["judgments"][1]
    assert (b["decision"], b["confidence"], b["latency_s"], b["parse_status"]) == \
        ("", None, None, "no_answer")


def test_the_resumable_driver_stops_on_a_doubled_answer():
    _scripts()
    from audit_resumable import checkpoint_row

    with pytest.raises(SystemExit, match="twice"):
        checkpoint_row(0, rows(1)[0], [right("a"), right("a"), right("b")])


def test_a_row_written_twice_in_a_checkpoint_is_a_gap(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    _scripts()
    import check_complete

    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(r) for r in rows(2)) + "\n")
    ans = [{"question": "a", "decision": "x"}, {"question": "b", "decision": "y"}]
    lines = [{"idx": -1, "run": {"dataset": {"path": str(labels)}}},
             {"idx": 0, "judgments": ans}, {"idx": 0, "judgments": ans},
             {"idx": 1, "judgments": ans}]
    ckpt = tmp_path / "x.ckpt.jsonl"
    ckpt.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    monkeypatch.setattr(check_complete, "ROOT", Path("/"))
    assert check_complete.gaps(ckpt) == [f"{ckpt}: row 0 written 2 times"]


def test_a_run_declared_stopped_may_miss_only_its_tail(tmp_path, monkeypatch):
    """A hosted run stopped on a quota error is kept to be resumed: when run-notes.json beside
    it says it stopped, rows missing after its last written one are not gaps. Anything else
    still is: an undeclared tail, a hole before the tail, a doubled row."""
    import json
    from pathlib import Path

    _scripts()
    import check_complete

    labels = tmp_path / "labels.jsonl"
    labels.write_text("\n".join(json.dumps(r) for r in rows(4)) + "\n")
    ans = [{"question": "a", "decision": "x"}, {"question": "b", "decision": "y"}]
    head = {"idx": -1, "run": {"dataset": {"path": str(labels)}}}
    ckpt = tmp_path / "slug.ckpt.jsonl"
    monkeypatch.setattr(check_complete, "ROOT", Path("/"))

    def write(idxs):
        ckpt.write_text("\n".join(json.dumps(x) for x in
                                  [head] + [{"idx": i, "judgments": ans} for i in idxs]) + "\n")

    write([0, 1])
    assert check_complete.gaps(ckpt) == [f"{ckpt}: row 2 missing", f"{ckpt}: row 3 missing"]
    notes = tmp_path / "run-notes.json"
    # a note without the rows it stopped at, or with another count, silences nothing: the
    # maintainer states where the run stopped and the checkpoint must agree
    notes.write_text(json.dumps({"runs": {"slug": {"stopped": "provider quota"}}}))
    assert check_complete.gaps(ckpt) == [f"{ckpt}: row 2 missing", f"{ckpt}: row 3 missing"]
    notes.write_text(json.dumps({"runs": {"slug": {"stopped": "provider quota", "rows": 3}}}))
    assert check_complete.gaps(ckpt) == [f"{ckpt}: row 2 missing", f"{ckpt}: row 3 missing"]
    notes.write_text(json.dumps({"runs": {"slug": {"stopped": "provider quota", "rows": 2}}}))
    assert check_complete.gaps(ckpt) == []
    write([0, 2])                                   # a hole before the tail is still a gap
    assert check_complete.gaps(ckpt) == [f"{ckpt}: row 1 missing"]


def _orphan_dataset(tmp_path):
    import json

    row = {"state": "hello", "questions": [{"name": "category", "type": "choice",
                                            "options": ["order", "spam"]}],
           "labels": {"category": "order", "urgency": "high"}}
    path = tmp_path / "orphan.jsonl"
    path.write_text(json.dumps(row) + "\n")
    return path


def test_the_cli_exits_2_when_the_audit_would_not_be_complete(tmp_path):
    import subprocess
    import sys

    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run",
                        str(_orphan_dataset(tmp_path)), "--judge", "simulated"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 2 and "would not be complete" in r.stderr


def test_the_mcp_tool_returns_an_error_instead_of_crashing(tmp_path):
    pytest.importorskip("mcp")
    from judge_audit import mcp_server

    out = mcp_server.run_audit(str(_orphan_dataset(tmp_path)), judge="simulated")
    assert "IncompleteAnswers" in out["error"] and "name no question" in out["error"]


def test_a_dataset_error_is_found_before_the_first_call():
    calls = []

    def answer(state):
        calls.append(state)
        return [right("a"), right("b")]

    bad = rows(3)
    bad[2]["labels"]["b"] = ""
    with pytest.raises(IncompleteAnswers, match="blank or null"):
        run_audit(Scripted(answer), bad, ci=False)
    assert calls == []


def withheld(q):
    return Judgment(question=q, decision="", confidence=None, latency_s=0.0, cost_usd=0.0,
                    parse_status="no_answer",
                    raw={"error": "max_length_exceeded", "max_len": 512, "head_max_len": 192,
                         "problems": ["the 77 options need 553 of head_max_len=192 tokens"]})


def test_an_over_length_question_warns_once_and_is_counted_apart_from_answered():
    from judge_audit.runner import NotSentWarning
    with pytest.warns(NotSentWarning) as caught:
        r = run_audit(Scripted(lambda s: [withheld("a"), right("b")]), rows(), ci=False)
    assert len([w for w in caught if w.category is NotSentWarning]) == 1
    message = str(caught[0].message)
    assert "row 0, question 'a' was not sent" in message
    assert "max_len=512, head_max_len=192" in message and "LAYA_" not in message
    # still an answered record (the adapter returned it), but counted on its own
    assert r.completeness["answered"] == 8 and r.not_sent == 4
    assert r.to_dict()["not_sent"] == 4
    md = render_markdown(r)
    assert "**4/8 questions not sent**" in md
    assert "Check the input length against the judge's window" in md


def test_a_run_with_nothing_withheld_says_nothing_about_it(recwarn):
    from judge_audit.report import render_html
    from judge_audit.runner import NotSentWarning
    r = run_audit(Scripted(lambda s: [right("a"), right("b")]), rows(), ci=False)
    assert not [w for w in recwarn if w.category is NotSentWarning]
    assert r.not_sent == 0 and "not_sent" not in r.to_dict()
    assert "not sent" not in render_markdown(r) and "not sent" not in render_html(r)


def test_the_cli_summary_line_counts_what_was_not_sent(tmp_path, monkeypatch, capsys):
    import json

    from judge_audit import cli
    labels = tmp_path / "labels.jsonl"
    labels.write_text("".join(json.dumps(r) + "\n" for r in rows(3)))
    monkeypatch.setattr(cli, "_judge", lambda name, rows: (
        Scripted(lambda s: [withheld("a"), withheld("b")]), ""))
    with pytest.warns(Warning, match="was not sent"):
        cli.main(["run", str(labels), "--judge", "simulated", "--no-ci",
                  "--out", str(tmp_path / "r.html"), "--format", "html",
                  "--json", str(tmp_path / "r.json")])
    out = capsys.readouterr().out
    assert "answered=6/6 not_sent=6 confidence_known=0/6" in out
    assert "6/6 questions not sent" in (tmp_path / "r.html").read_text()
    assert json.loads((tmp_path / "r.json").read_text())["not_sent"] == 6


def test_a_judge_without_its_own_advice_gets_the_generic_one(over_length_warning):
    class Plain(Judge):
        name = "plain"

        def decide(self, state, questions):
            return [Judgment(question=q.name, decision="", confidence=None,
                             parse_status="no_answer", raw={"error": "max_length_exceeded"})
                    for q in questions]

    message, variables = over_length_warning(Plain())
    assert "(over length)" in message and variables == set()
    assert "shorten the state or the options, or ask fewer questions per row" in message


def test_a_scratch_dataset_is_read_from_its_committed_copy_with_the_same_digest():
    import hashlib
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import check_complete
    for name, path in check_complete.SCRATCH.items():
        ckpt = next((check_complete.ROOT / "docs" / "runs").rglob(name))
        header = json.loads(ckpt.read_text(encoding="utf-8").splitlines()[0])["run"]["dataset"]
        data = (check_complete.ROOT / path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == header["sha256"], name   # the same file, renamed
        assert check_complete.gaps(ckpt) == []
