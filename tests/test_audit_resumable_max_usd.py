"""audit_resumable.py --max-usd: a run stops before the request that would start at or past
its cost ceiling, counting the cost of every earlier session of the same checkpoint (#172)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit.judges.base import Judge, Judgment

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import audit_resumable  # noqa: E402

Q = [{"name": "a", "type": "choice", "options": ["x", "y"]}]


class Priced(Judge):
    """A fake judge: one answer per question, each costing `costs[call]` (None = unknown)."""

    name = "fake"

    def __init__(self, costs, fail_at=None):
        self.costs, self.fail_at, self.calls = list(costs), fail_at, 0

    def decide(self, state, questions):
        if self.calls == self.fail_at:
            raise RuntimeError("HTTP 500")
        cost = self.costs[self.calls]
        self.calls += 1
        return [Judgment(question=q.name, decision="x", confidence=0.9, latency_s=0.1,
                         cost_usd=cost) for q in questions]


@pytest.fixture
def labels(tmp_path):
    p = tmp_path / "labels.jsonl"
    p.write_text("".join(json.dumps({"state": f"synthetic row {i}", "questions": Q,
                                     "labels": {"a": "x"}}) + "\n" for i in range(10)))
    return p


def drive(monkeypatch, tmp_path, labels, judge, *flags):
    """One driver session in-process with `judge`; its exit code (0 when it returned)."""
    monkeypatch.setattr(audit_resumable, "_judge", lambda name, rows: (judge, ""))
    monkeypatch.setattr(audit_resumable.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", [
        "audit_resumable.py", str(labels), "--judge", "fake",
        "--checkpoint", str(tmp_path / "c.ckpt.jsonl"),
        "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"), *flags])
    try:
        audit_resumable.main()
    except SystemExit as e:
        return e.code
    return 0


def lines(tmp_path):
    return [json.loads(x) for x in (tmp_path / "c.ckpt.jsonl").read_text().splitlines()]


def test_a_run_stops_before_the_request_that_would_start_at_the_ceiling(
        tmp_path, labels, monkeypatch, capsys):
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.05")
    err = capsys.readouterr().err
    assert code == 3 and judge.calls == 5
    assert "cost ceiling reached: $0.05 recorded of $0.05" in err
    rows = lines(tmp_path)  # every line still parses: the checkpoint stays valid
    assert rows[0]["idx"] == -1 and [r["idx"] for r in rows[1:]] == [0, 1, 2, 3, 4]
    assert not (tmp_path / "r.md").exists()  # an incomplete run writes no report


def test_the_sum_is_exact_on_the_recorded_values(tmp_path, labels, monkeypatch, capsys):
    """0.7 + 0.1 is 0.7999999999999999 in floats: the ceiling of 0.8 is still reached."""
    judge = Priced([0.7, 0.1, 0.1])
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.8") == 3
    assert judge.calls == 2 and "$0.8 recorded of $0.8" in capsys.readouterr().err


def test_a_run_below_the_ceiling_sends_the_next_request(tmp_path, labels, monkeypatch):
    """The ceiling is checked before each request, so the last row can pass it."""
    judge = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.051") == 3
    assert judge.calls == 6


def test_a_resumed_run_counts_the_cost_of_earlier_sessions(tmp_path, labels, monkeypatch,
                                                            capsys):
    first = Priced([0.01] * 10, fail_at=3)  # session 1 keeps 3 rows ($0.03), then fails
    assert drive(monkeypatch, tmp_path, labels, first, "--max-usd", "0.05") == 2
    second = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, second, "--max-usd", "0.05") == 3
    assert second.calls == 2 and len(lines(tmp_path)) == 1 + 5
    third = Priced([0.01] * 10)  # nothing left under the ceiling: no request at all
    assert drive(monkeypatch, tmp_path, labels, third, "--max-usd", "0.05") == 3
    assert third.calls == 0 and len(lines(tmp_path)) == 1 + 5
    assert "cost ceiling reached: $0.05 recorded of $0.05" in capsys.readouterr().err


def test_an_unknown_cost_stops_the_run(tmp_path, labels, monkeypatch, capsys):
    judge = Priced([0.01, 0.01, None] + [0.01] * 7)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "5") == 3
    err = capsys.readouterr().err
    assert judge.calls == 3 and len(lines(tmp_path)) == 1 + 3  # the unpriced row is kept
    assert "cost ceiling cannot be enforced" in err and "1 judgment" in err


def test_a_local_judge_at_zero_cost_runs_to_the_end(tmp_path, labels, monkeypatch):
    judge = Priced([0.0] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.01") == 0
    assert judge.calls == 10 and (tmp_path / "r.md").exists()


def test_the_header_records_the_ceiling(tmp_path, labels, monkeypatch):
    assert drive(monkeypatch, tmp_path, labels, Priced([0.0] * 10), "--max-usd", "2.5") == 0
    assert lines(tmp_path)[0]["run"]["max_usd"] == 2.5
    assert json.loads((tmp_path / "r.json").read_text())["run"]["max_usd"] == 2.5


@pytest.mark.parametrize("flags", [(), ("--max-usd", "0.06")])
def test_a_checkpoint_resumes_only_under_the_ceiling_it_was_started_with(
        tmp_path, labels, monkeypatch, capsys, flags):
    """The header is written once: another ceiling, or none, would leave it recording a
    ceiling that did not govern the rest of the run."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.05") == 3
    before = (tmp_path / "c.ckpt.jsonl").read_text()
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, *flags)
    assert code and "was started with --max-usd 0.05" in str(code) and judge.calls == 0
    assert (tmp_path / "c.ckpt.jsonl").read_text() == before  # nothing appended


def test_a_ceiling_is_not_added_to_a_checkpoint_started_without_one(tmp_path, labels,
                                                                     monkeypatch):
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10, fail_at=2)) == 2
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "1")
    assert "was started without --max-usd" in str(code) and judge.calls == 0


def test_without_the_flag_nothing_changes(tmp_path, labels, monkeypatch):
    """No ceiling: an unknown cost does not stop the run and the header has no max_usd."""
    judge = Priced([0.01, None] + [5.0] * 8)
    assert drive(monkeypatch, tmp_path, labels, judge) == 0
    assert judge.calls == 10 and "max_usd" not in lines(tmp_path)[0]["run"]
    assert (tmp_path / "r.md").exists()


def test_a_complete_checkpoint_recomputes_whatever_the_flag_says(tmp_path, labels,
                                                                  monkeypatch):
    """A recompute makes no request, so no ceiling applies to it."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10)) == 0
    judge = Priced([])
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.01") == 0
    assert judge.calls == 0


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "five"])
def test_the_ceiling_must_be_a_positive_amount(tmp_path, labels, value):
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_resumable.py"),
                        str(labels), "--judge", "simulated",
                        "--checkpoint", str(tmp_path / "c.ckpt.jsonl"),
                        "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                        "--max-usd", value], capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 2 and "--max-usd" in p.stderr
    assert not (tmp_path / "c.ckpt.jsonl").exists()


def test_the_driver_stops_a_real_process_with_exit_3(tmp_path, labels):
    """End to end through an interpreter: the simulated judge records $0.00008 per answer."""
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_resumable.py"),
                        str(labels), "--judge", "simulated",
                        "--checkpoint", str(tmp_path / "c.ckpt.jsonl"),
                        "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                        "--max-usd", "0.00024"], capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 3, p.stderr
    assert "cost ceiling reached" in p.stderr and "Traceback" not in p.stderr
    assert len((tmp_path / "c.ckpt.jsonl").read_text().splitlines()) == 1 + 3
