"""audit_resumable.py --max-usd: a run stops before the request that would start at or past
its cost ceiling, counting the cost of every earlier session of the same checkpoint (#172)."""
from __future__ import annotations

import json
import stat
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


AMEND = "v06-plan amendment 2026-10-20"


@pytest.mark.parametrize("flags", [(), ("--max-usd", "0.06"), ("--max-usd", "0.04")])
def test_another_ceiling_without_an_amendment_is_refused(tmp_path, labels, monkeypatch,
                                                         flags):
    """Without a dated amendment the header's ceiling governs the rest of the run: another
    ceiling, or none, would leave it recording one that no longer held."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.05") == 3
    before = (tmp_path / "c.ckpt.jsonl").read_text()
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, *flags)
    assert "records --max-usd 0.05" in str(code) and judge.calls == 0
    assert ("--ceiling-amendment" in str(code)) == bool(flags)
    assert (tmp_path / "c.ckpt.jsonl").read_text() == before  # nothing written


def test_an_amendment_does_not_lift_the_ceiling(tmp_path, labels, monkeypatch, capsys):
    """Resuming without --max-usd stays refused: an amendment changes a ceiling, never
    removes it, and --ceiling-amendment alone is a usage error."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.05") == 3
    before = (tmp_path / "c.ckpt.jsonl").read_text()
    judge = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--ceiling-amendment", AMEND) == 2
    assert "--ceiling-amendment needs --max-usd" in capsys.readouterr().err
    assert judge.calls == 0 and (tmp_path / "c.ckpt.jsonl").read_text() == before


def test_a_raised_ceiling_with_an_amendment_resumes_and_is_recorded(tmp_path, labels,
                                                                    monkeypatch):
    """The run continues on the same checkpoint, without paying again for its rows, and
    stops at the new ceiling. Only the header line changes: it records the new ceiling and
    appends the old one, the rows judged under it and the amendment to `max_usd_history`."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.05") == 3
    body = (tmp_path / "c.ckpt.jsonl").read_text().splitlines(keepends=True)[1:]
    judge = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.08",
                 "--ceiling-amendment", AMEND) == 3
    assert judge.calls == 3
    after = (tmp_path / "c.ckpt.jsonl").read_text().splitlines(keepends=True)
    assert after[1:1 + len(body)] == body and len(after) == 1 + 8  # earlier rows untouched
    run = json.loads(after[0])["run"]
    assert run["max_usd"] == 0.08
    (entry,) = run["max_usd_history"]
    assert {k: entry[k] for k in ("max_usd", "until_rows", "unknown_cost_judgments",
                                  "amendment")} == {
        "max_usd": 0.05, "until_rows": 5, "unknown_cost_judgments": 0, "amendment": AMEND}
    assert entry["changed_utc"].endswith("+00:00")
    # The same ceiling again needs no amendment, and an amendment that would change nothing
    # is refused rather than recorded; a second change appends a second entry.
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.08") == 3
    before = (tmp_path / "c.ckpt.jsonl").read_bytes()
    for ref in (AMEND, "another amendment"):
        judge = Priced([0.01] * 10)
        code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.08",
                     "--ceiling-amendment", ref)
        assert "changes nothing" in str(code) and judge.calls == 0
    assert (tmp_path / "c.ckpt.jsonl").read_bytes() == before
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "1",
                 "--ceiling-amendment", "second amendment") == 0
    run = lines(tmp_path)[0]["run"]
    assert run["max_usd"] == 1.0 and [(e["max_usd"], e["until_rows"], e["amendment"])
                                      for e in run["max_usd_history"]] == [
        (0.05, 5, AMEND), (0.08, 8, "second amendment")]
    report = json.loads((tmp_path / "r.json").read_text())["run"]
    assert report["max_usd"] == 1.0 and len(report["max_usd_history"]) == 2


def test_a_ceiling_is_added_to_a_checkpoint_started_without_one_only_by_amendment(
        tmp_path, labels, monkeypatch):
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10, fail_at=2)) == 2
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.03")
    assert "records no --max-usd" in str(code) and judge.calls == 0
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.03",
                 "--ceiling-amendment", AMEND) == 3
    assert judge.calls == 1
    (entry,) = lines(tmp_path)[0]["run"]["max_usd_history"]
    assert entry["max_usd"] is None and entry["until_rows"] == 2


def test_an_amendment_acknowledges_unknown_costs_and_a_new_one_stops_again(
        tmp_path, labels, monkeypatch, capsys):
    """A stop on an unknown cost is continued by a dated amendment under the same ceiling,
    which acknowledges the unknown costs recorded so far; one more unknown stops the run
    again, and acknowledging it needs another amendment."""
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01, None] + [0.01] * 8),
                 "--max-usd", "1") == 3
    judge = Priced([0.01] * 10)  # the same ceiling without an amendment: stopped again
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "1") == 3
    assert judge.calls == 0 and "cost ceiling cannot be enforced" in capsys.readouterr().err
    judge = Priced([0.01, 0.01, None] + [0.01] * 7)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "1",
                 "--ceiling-amendment", AMEND) == 3
    assert judge.calls == 3 and len(lines(tmp_path)) == 1 + 5
    assert "1 judgment(s) recorded with unknown cost beyond the 1 acknowledged" in \
        capsys.readouterr().err
    run = lines(tmp_path)[0]["run"]
    (entry,) = run["max_usd_history"]
    assert run["max_usd"] == 1.0 and {k: entry[k] for k in (
        "max_usd", "until_rows", "unknown_cost_judgments", "amendment")} == {
        "max_usd": 1.0, "until_rows": 2, "unknown_cost_judgments": 1, "amendment": AMEND}
    # An amendment already recorded cannot acknowledge the new unknown cost.
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "1",
                 "--ceiling-amendment", AMEND)
    assert "already recorded" in str(code) and judge.calls == 0
    judge = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "1",
                 "--ceiling-amendment", "second amendment") == 0
    assert judge.calls == 5
    second = lines(tmp_path)[0]["run"]["max_usd_history"][1]
    assert (second["until_rows"], second["unknown_cost_judgments"]) == (5, 2)


def test_an_amendment_rewrites_only_the_header_line(tmp_path, labels, monkeypatch):
    """Row lines keep their bytes, CRLF and non-canonical JSON included; the header keeps
    its line ending, the file keeps its mode, and the new file is synced before it replaces
    the old one."""
    def row(i):
        return (f'{{"idx":{i},  "judgments":[{{"question":"a","decision":"x",'
                f'"confidence":0.90,"latency_s":0.1,"cost_usd":0.010,'
                f'"raw":{{"note":"\\u00e9"}}}}]}}\r\n').encode()
    ckpt = tmp_path / "c.ckpt.jsonl"
    header = b'{"idx": -1, "run": {"judge": {"name": "fake"}, "max_usd": 0.05}}\r\n'
    body = b"".join(row(i) for i in range(5))
    ckpt.write_bytes(header + body)
    ckpt.chmod(0o640)
    synced = []
    real_fsync = audit_resumable.os.fsync
    monkeypatch.setattr(audit_resumable.os, "fsync",
                        lambda fd: (synced.append(fd), real_fsync(fd)))
    judge = Priced([0.01] * 10)
    assert drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.08",
                 "--ceiling-amendment", AMEND) == 3
    assert judge.calls == 3 and synced
    data = ckpt.read_bytes()
    first, rest = data.split(b"\r\n", 1)
    assert rest.startswith(body) and json.loads(first)["run"]["max_usd"] == 0.08
    assert stat.S_IMODE(ckpt.stat().st_mode) == 0o640
    assert not (tmp_path / "c.ckpt.jsonl.tmp").exists()


def test_a_failed_header_rewrite_leaves_the_checkpoint_as_it_was(tmp_path, labels,
                                                                 monkeypatch):
    assert drive(monkeypatch, tmp_path, labels, Priced([0.01] * 10), "--max-usd", "0.05") == 3
    ckpt = tmp_path / "c.ckpt.jsonl"
    before = ckpt.read_bytes()

    def fail(src, dst):
        raise OSError("disk full")
    monkeypatch.setattr(audit_resumable.os, "replace", fail)
    judge = Priced([0.01] * 10)
    code = drive(monkeypatch, tmp_path, labels, judge, "--max-usd", "0.08",
                 "--ceiling-amendment", AMEND)
    assert "could not rewrite the header" in str(code) and judge.calls == 0
    assert ckpt.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("c.ckpt")] == [
        "c.ckpt.jsonl"]


@pytest.mark.parametrize("ref", ["", "   ", "two\nlines", "x" * 201, "a\u2028b", "a\x85b",
                                 "tab\there", "nul\x00", "trailing\u2028"])
def test_an_amendment_reference_is_one_short_line(tmp_path, labels, monkeypatch, capsys, ref):
    code = drive(monkeypatch, tmp_path, labels, Priced([]), "--max-usd", "1",
                 "--ceiling-amendment", ref)
    assert code == 2 and "--ceiling-amendment" in capsys.readouterr().err


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


@pytest.mark.parametrize("value", ["0", "-0", "-1", "nan", "sNaN", "inf", "five", "1e999999",
                                   "1000000.000001", "1e7", "0.0000001", "0.1234567"])
def test_the_ceiling_must_be_a_sane_amount(tmp_path, labels, value):
    """Above $0, up to $1,000,000, to 6 decimal places: refused with a usage error, no
    traceback and no checkpoint."""
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_resumable.py"),
                        str(labels), "--judge", "simulated",
                        "--checkpoint", str(tmp_path / "c.ckpt.jsonl"),
                        "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                        "--max-usd", value], capture_output=True, text=True, cwd=tmp_path)
    assert p.returncode == 2 and "--max-usd" in p.stderr and "Traceback" not in p.stderr
    assert not (tmp_path / "c.ckpt.jsonl").exists()


@pytest.mark.parametrize("value", ["0.000003", "0.1", "2.5", "123456.789012",
                                   "999999.999999", "1e6"])
def test_the_header_records_the_ceiling_that_is_enforced(tmp_path, labels, monkeypatch,
                                                         value):
    """The header's number reads back as exactly the decimal typed, and the run stops on it."""
    from decimal import Decimal
    step = Decimal(value) / 3
    judge = Priced([float(step)] * 10)
    drive(monkeypatch, tmp_path, labels, judge, "--max-usd", value)
    recorded = lines(tmp_path)[0]["run"]["max_usd"]
    assert Decimal(repr(recorded)) == Decimal(value)
    spent = sum(Decimal(repr(float(step))) for _ in range(judge.calls - 1))
    assert spent < Decimal(value)  # every request but the last started below the ceiling


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
