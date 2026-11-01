"""Repeatable `--target` (#201): up to three error targets declared before a run, each row
flagged `primary`, the first one headlining (`primary_target`). δ is not split: every row
is the same statement it was with one target. One `--target` leaves every output unchanged."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit import __version__, cli
from judge_audit.certificate import MAX_DECLARED, automation_certificate
from judge_audit.judges.base import Judge, Judgment
from judge_audit.report import certificate_html, certificate_note

ROOT = Path(__file__).resolve().parent.parent
SMALL = ROOT / "examples" / "task-routing" / "labels.jsonl"
GOLDEN = Path(__file__).parent / "fixtures" / "single_target_golden.json"


def desc(n: int) -> list[float]:
    """n distinct confidences, highest first."""
    return [1.0 - i / (2 * n) for i in range(n)]


def _records(n: int = 200, wrong: int = 50) -> list[dict]:
    """n decisions, highest confidence first, the `wrong` least confident wrong."""
    return [{"question": "q", "confidence": c, "correct": i < n - wrong}
            for i, c in enumerate(desc(n))]


def _cli(*args, cwd):
    return subprocess.run([sys.executable, "-m", "judge_audit.cli", *args],
                          cwd=cwd, capture_output=True, text=True)


# --- the certificate: declared rows flagged, nothing else moves ---------------------------


def test_each_declared_target_is_flagged_and_its_row_is_unchanged():
    """200 decisions, the 50 least confident wrong. At 10 % the walk stops at 159 decisions
    with 9 errors (9.67 %; 10 in 160 is 10.37 %), declared or not: δ is not split."""
    recs = _records()
    one = automation_certificate(recs, primary=0.05)
    three = automation_certificate(recs, primary=0.10, declared=(0.10, 0.02, 0.05))
    assert three["primary_target"] == 0.10
    assert three["declared_targets"] == [0.10, 0.02, 0.05]   # in the order given
    assert three["targets"] == one["targets"] == [0.01, 0.02, 0.05, 0.10]
    flags = {t["target_risk"]: t["primary"] for t in three["questions"][0]["targets"]}
    assert flags == {0.01: False, 0.02: True, 0.05: True, 0.10: True}
    for a, b in zip(one["questions"][0]["targets"], three["questions"][0]["targets"],
                    strict=True):
        assert {**a, "primary": None} == {**b, "primary": None}
    ten = three["questions"][0]["targets"][-1]
    assert (ten["automated"], ten["errors"]) == (159, 9)


def test_one_declared_target_is_the_certificate_it_always_was():
    recs = _records()
    one = automation_certificate(recs, primary=0.10, declared=(0.10,))
    assert one == automation_certificate(recs, primary=0.10)
    assert "declared_targets" not in one   # the single-target bytes do not move


@pytest.mark.parametrize("primary, declared, why", [
    (0.01, (0.01, 0.02, 0.05, 0.10), "at most 3"),
    (0.05, (0.05, 0.05), "twice"),
    (0.05, (0.02, 0.05), "first declared"),
    (0.05, (0.05, 0.03), "not among the targets"),
    (0.05, (), "first declared"),
])
def test_a_declaration_the_statement_cannot_carry_is_refused(primary, declared, why):
    with pytest.raises(ValueError, match=why):
        automation_certificate(_records(), primary=primary, declared=declared)


def test_the_limit_is_three():
    assert MAX_DECLARED == 3


# --- the note: each on its own, together at 1 − k·δ --------------------------------------


def _note(declared: tuple[float, ...]) -> str:
    targets = sorted({0.01, 0.02, 0.05, 0.10, *declared})
    return certificate_note(automation_certificate(_records(), targets=targets,
                                                   primary=declared[0], declared=declared))


def test_the_note_says_what_several_declared_targets_hold_together():
    note = _note((0.08, 0.03, 0.05))
    assert ("The declared targets are the ones passed with `--target` before the run (here "
            "8%, 3% and 5%; 8% headlines this section): each holds at 95% on its own, and "
            "the 3 together with probability at least 85% (approximately, for the held-out "
            "check).") in note
    assert "the 6 rows hold together with probability at least 70%" in note
    assert "The primary target is the one passed" not in note


def test_the_note_with_one_declared_target_is_the_one_it_always_was():
    note = _note((0.05,))
    assert ("The primary target is the one passed with `--target` (here 5%), to be chosen "
            "before the run; every row is its own 95% statement") in note
    assert "declared targets" not in note


# --- the CLI ------------------------------------------------------------------------------


def test_three_targets_are_declared_and_the_first_headlines(tmp_path):
    r = _cli("run", str(SMALL), "--judge", "simulated", "--no-ci", "--judgments", "",
             "--target", "0.2", "--target", "0.15", "--target", "0.03",
             "--json", "r.json", "--out", "r.md", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    c = json.loads((tmp_path / "r.json").read_text())["certificate"]
    assert c["primary_target"] == 0.2
    assert c["declared_targets"] == [0.2, 0.15, 0.03]
    assert c["targets"] == [0.01, 0.02, 0.03, 0.05, 0.1, 0.15, 0.2]
    rows = c["questions"][0]["targets"]
    assert [t["target_risk"] for t in rows if t["primary"]] == [0.03, 0.15, 0.2]
    assert "safe_automation@20%=" in r.stdout and "@3%" not in r.stdout
    md = (tmp_path / "r.md").read_text()
    assert "at a 20% error target" in md and "at a 3% error target" not in md
    # the headlining row is the primary one; the others were declared with it
    assert md.count(" (primary) |") == 1 and "| 20% (primary) |" in md
    assert md.count(" (declared) |") == 2
    assert "| 15% (declared) |" in md and "| 3% (declared) |" in md
    assert "(here 20%, 15% and 3%; 20% headlines this section)" in md
    assert "the 3 together with probability at least 85%" in md


def test_a_fourth_target_is_refused_with_exit_2(labels_path, tmp_path):
    four = [a for t in ("0.01", "0.02", "0.03", "0.04") for a in ("--target", t)]
    for cmd in (["run", str(labels_path)],
                ["check", str(labels_path), "--baseline", "none.json"]):
        r = _cli(*cmd, "--judge", "simulated", *four, cwd=tmp_path)
        assert r.returncode == 2, r.stderr
        assert "--target is given at most 3 times, got 4" in r.stderr
    assert not (tmp_path / "audit-result.json").exists()


@pytest.mark.parametrize("args, says", [
    (("--target", "0.05", "--target", "0.05"), "--target 0.05 is given twice"),
    # the same target to the certificate, which compares with math.isclose
    (("--target", "0.05", "--target", "0.05000000001"), "--target 0.05 is given twice"),
    (("--target", "0.05", "--target", "1.5"), "--target must be between 0 and 1, got 1.5"),
])
def test_a_repeated_or_invalid_target_is_refused_with_exit_2(labels_path, tmp_path, args,
                                                               says):
    r = _cli("run", str(labels_path), "--judge", "simulated", *args, cwd=tmp_path)
    assert r.returncode == 2 and says in r.stderr


def test_the_pr_comment_headlines_the_first_declared_target(tmp_path):
    recs = _records()
    cert = automation_certificate(recs, primary=0.10, declared=(0.10, 0.05))
    spec = importlib.util.spec_from_file_location("pr_comment_201",
                                                  ROOT / "scripts" / "pr_comment.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    lines = mod._certificate({"certificate": cert})
    assert any("at a 10% error target" in x for x in lines)
    assert not any("at a 5% error target" in x for x in lines)
    assert any(x.startswith("| 10% (primary) |") for x in lines)
    assert any(x.startswith("| 5% (declared) |") for x in lines)
    assert not any(x.startswith("| 5% (primary) |") for x in lines)


def test_the_html_table_marks_the_primary_and_the_declared_rows():
    recs = _records()
    cert = automation_certificate(recs, primary=0.10, declared=(0.10, 0.05))
    page = certificate_html({"certificate": cert})
    assert "<td>10% (primary)</td>" in page and "<td>5% (declared)</td>" in page
    one = certificate_html({"certificate": automation_certificate(recs, primary=0.10)})
    assert "<td>10% (primary)</td>" in one and "(declared)" not in one


# --- one --target: byte for byte what it was before #201 ----------------------------------

class Replay(Judge):
    """The judgments a committed checkpoint recorded, answered in row order: the same
    decisions and confidences on every platform. The simulated judge draws its confidences
    through libm (`random.gauss`, `betavariate`), whose last bits differ between platforms."""

    name = "replay"

    def __init__(self, checkpoint: Path):
        rows = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
        self.answers = iter([r["judgments"] for r in sorted(
            (r for r in rows if r["idx"] >= 0), key=lambda r: r["idx"])])

    def decide(self, state, questions):
        return [Judgment(question=j["question"], decision=j.get("decision", ""),
                         confidence=j.get("confidence"), latency_s=j.get("latency_s", 0.0),
                         cost_usd=j.get("cost_usd", 0.0),
                         parse_status=j.get("parse_status", "parsed"))
                for j in next(self.answers)]


ARENA = ROOT / "docs" / "runs" / "arena"
NLI = (ARENA / "deberta-nli" / "email-clean.ckpt.jsonl",
       ROOT / "examples" / "email-routing" / "labels.jsonl")
SONNET = (ARENA / "claude-sonnet-4.5" / "email-adversarial.ckpt.jsonl",
          ROOT / "examples" / "email-routing-adversarial" / "labels.jsonl")
# case -> (checkpoint, labels, CLI arguments)
CASES = {
    "default": (*NLI, ("run", "--json", "r.json", "--out", "r.md")),
    "met": (*SONNET, ("run", "--target", "0.08", "--json", "r.json", "--out", "r.md")),
    "html": (*NLI, ("run", "--target", "0.08", "--format", "html", "--json", "r.json",
                    "--out", "r.html")),
}


def _normalized(text: str) -> str:
    """What may differ between two runs of the same code: the run's time and the review date
    it sets, the package and Python versions, and the PNG charts (bytes depend on the
    matplotlib build). Everything else must not move."""
    text = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "data:image/png;base64,PNG", text)
    time = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00"
    text = re.sub(rf'(\brun |measured |"timestamp_utc": "|"measured_utc": "){time}',
                  r"\1TIME", text)
    text = re.sub(r'([Rr]eview by |"review_by": ")\d{4}-\d{2}-\d{2}', r"\1DATE", text)
    text = re.sub(r'"python": "[^"]*"', '"python": "PY"', text)
    return re.sub(rf'(judge-audit |"judge_audit_version": "){re.escape(__version__)}',
                  r"\1VERSION", text)


def _digests(case: str, tmp_path: Path, monkeypatch, capsys) -> dict[str, str]:
    """sha256 of every normalized output of `case`: the CLI line, the report, the result
    JSON and the PR comment built from it."""
    checkpoint, labels, (cmd, *rest) = CASES[case]
    work = tmp_path / case
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(cli, "_judge", lambda name, rows=None: (Replay(checkpoint), ""))
    cli.main([cmd, str(labels), "--judge", "simulated", "--no-ci", "--judgments", "", *rest])
    out = {"line": capsys.readouterr().out}
    for name in ("r.json", "r.md", "r.html"):
        if (work / name).exists():
            out[name] = (work / name).read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("pr_comment_golden",
                                                  ROOT / "scripts" / "pr_comment.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    out["pr_comment"] = mod.build(json.loads(out["r.json"]))
    return {k: hashlib.sha256(_normalized(v).encode()).hexdigest() for k, v in out.items()}


@pytest.mark.parametrize("case", sorted(CASES))
def test_one_target_is_byte_identical_to_before(case, tmp_path, monkeypatch, capsys):
    """The judgments the committed checkpoints recorded, replayed through the CLI (`Replay`):
    no `--target` and `--target 0.08` as HTML (deberta-nli on email-routing: the held-out
    check not met), and `--target 0.08` (claude-sonnet-4.5 on email-routing-adversarial:
    met). #201 was checked against digests taken on the code before it (f889b87), on macOS
    and Linux (#205). The #199 wording then changed these outputs on purpose, so the fixture
    now holds the digests of #199's code on top of e3f7089; its PR (#207) shows that its
    raw outputs differ from e3f7089's in that wording only. A later change of wording
    updates them the same way, with the same proof; a change that should not alter the
    output must leave them as they are."""
    golden = json.loads(GOLDEN.read_text())["cases"][case]
    assert _digests(case, tmp_path, monkeypatch, capsys) == golden


def test_the_unchanged_outputs_are_the_ones_a_reader_sees():
    """The fixture covers every surface: the CLI line, the report, the JSON, the PR
    comment."""
    cases = json.loads(GOLDEN.read_text())["cases"]
    assert set(cases) == set(CASES)
    assert set(cases["default"]) == {"line", "r.json", "r.md", "pr_comment"}
    assert set(cases["html"]) == {"line", "r.json", "r.html", "pr_comment"}
