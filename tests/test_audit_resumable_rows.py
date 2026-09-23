"""audit_resumable.py --rows: judge only a pre-registered subset, record it in the header."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "audit_resumable.py"
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"
SPLIT = ROOT / "examples" / "email-routing" / "split-heldout.json"


def run(args, cwd):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                          capture_output=True, text=True)


def test_rows_subset_parses_and_validates(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_resumable
    idx, meta = audit_resumable.rows_subset(None, 5)
    assert idx == [0, 1, 2, 3, 4] and meta is None
    s = tmp_path / "s.json"
    s.write_text(json.dumps({"heldout": [3, 1], "train": [0, 2]}))
    idx, meta = audit_resumable.rows_subset(f"{s}:heldout", 4)
    assert idx == [1, 3] and meta["part"] == "heldout" and meta["n"] == 2
    assert meta["split"] == str(s) and len(meta["sha256"]) == 64
    with pytest.raises(SystemExit, match="outside"):
        audit_resumable.rows_subset(f"{s}:heldout", 3)
    with pytest.raises(SystemExit, match="no row list"):
        audit_resumable.rows_subset(f"{s}:nope", 4)
    with pytest.raises(SystemExit, match="expects"):
        audit_resumable.rows_subset(str(s), 4)


def test_a_rerun_of_a_complete_checkpoint_writes_the_same_report(tmp_path):
    """The fresh run's report reads its run time from the header it just wrote, so a
    recompute from the finished checkpoint (what runs_report.py does) is byte-identical —
    before #61 the fresh report said 'original run time not recorded' next to a header
    that recorded it."""
    ckpt = tmp_path / "c.ckpt.jsonl"
    args = [str(LABELS), "--judge", "simulated", "--checkpoint", str(ckpt),
            "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")]
    assert run(args, tmp_path).returncode == 0
    first = [(tmp_path / f).read_text() for f in ("r.md", "r.json")]
    header = json.loads(ckpt.read_text().splitlines()[0])["run"]
    result = json.loads(first[1])
    assert result["run"]["timestamp_utc"] == header["timestamp_utc"]
    assert "note" not in result["run"] and "recomputed_utc" not in result["run"]
    assert result["accuracy_ci"] is not None and first[0].startswith("> ⚠️ **SIMULATED")
    p = run(args, tmp_path)
    assert p.returncode == 0 and "already done" in p.stdout
    assert [(tmp_path / f).read_text() for f in ("r.md", "r.json")] == first


def test_heldout_run_judges_only_the_subset_and_resumes(tmp_path):
    ckpt = tmp_path / "email-clean.ckpt.jsonl"
    args = [str(LABELS), "--judge", "simulated", "--checkpoint", str(ckpt),
            "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
            "--rows", f"{SPLIT}:heldout"]
    p = run(args, tmp_path)
    assert p.returncode == 0, p.stderr
    lines = [json.loads(x) for x in ckpt.read_text().splitlines() if x.strip()]
    header, body = lines[0], lines[1:]
    heldout = json.load(SPLIT.open())["heldout"]
    assert header["idx"] == -1 and [r["idx"] for r in body] == heldout
    sub = header["run"]["rows_subset"]
    assert sub["part"] == "heldout" and sub["n"] == 100 and sub["split"] == str(SPLIT)
    assert len(sub["sha256"]) == 64
    result = json.loads((tmp_path / "r.json").read_text())
    assert result["n"] == 100 and result["run"]["rows_subset"] == sub
    # A second invocation has nothing left to judge and recomputes from the checkpoint.
    p = run(args, tmp_path)
    assert p.returncode == 0 and "100/100 rows already done" in p.stdout
    assert len(ckpt.read_text().splitlines()) == 101
    # The same checkpoint cannot be continued on a different subset.
    p = run(args[:-1] + [f"{SPLIT}:train"], tmp_path)
    assert p.returncode != 0 and "different --rows subset" in p.stderr
