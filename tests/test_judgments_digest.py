"""The digest of the judgments a result was computed from (#144).

The fixture's canonical form is written out by hand below, so the pinned digest is the
sha256 of bytes a reader can check without the library."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

from judge_audit.runner import (
    canonical_judgments,
    judgments_digest,
    load_jsonl,
    run_audit,
    summarize,
    verify_judgments,
    write_judgments,
)

FIXTURE = [   # deliberately out of order, with a non-ASCII value and nested keys
    {"idx": 1, "question": "intent", "expected": "b", "decision": "b", "correct": True,
     "confidence": 0.75, "parse_status": "parsed", "latency_s": 0.1, "cost_usd": None,
     "meta": {"lang": "es"}, "raw": {"z": 1, "a": "décision"}},
    {"idx": 0, "question": "intent", "expected": "a", "decision": "b", "correct": False,
     "confidence": 1.0, "parse_status": "parsed", "latency_s": 0.2, "cost_usd": 0.001,
     "meta": {}, "raw": {}},
]
CANONICAL = (
    '{"confidence":1.0,"correct":false,"cost_usd":0.001,"decision":"b","expected":"a",'
    '"idx":0,"latency_s":0.2,"meta":{},"parse_status":"parsed","question":"intent",'
    '"raw":{}}\n'
    '{"confidence":0.75,"correct":true,"cost_usd":null,"decision":"b","expected":"b",'
    '"idx":1,"latency_s":0.1,"meta":{"lang":"es"},"parse_status":"parsed",'
    '"question":"intent","raw":{"a":"décision","z":1}}\n'
)
PINNED = "f5e752242699360497041494eaefdc3893ef74d829342510fe77a4366b89413d"  # shasum -a 256


def test_the_canonical_form_is_the_documented_one():
    assert canonical_judgments(FIXTURE) == CANONICAL.encode("utf-8")
    assert judgments_digest(FIXTURE) == hashlib.sha256(CANONICAL.encode("utf-8")).hexdigest()


def test_the_digest_is_pinned():
    assert judgments_digest(FIXTURE) == PINNED


def test_order_does_not_matter_and_a_0001_confidence_change_does():
    assert judgments_digest(list(reversed(FIXTURE))) == judgments_digest(FIXTURE)
    moved = [dict(FIXTURE[0], confidence=0.751), FIXTURE[1]]
    assert judgments_digest(moved) != judgments_digest(FIXTURE)
    # every count is unchanged: only the digest sees it
    a, b = summarize("x", FIXTURE, ci=False), summarize("x", moved, ci=False)
    assert (a.n, a.accuracy, a.confidence) == (b.n, b.accuracy, b.confidence)
    assert a.judgments_sha256 != b.judgments_sha256


def test_the_digest_is_the_same_on_every_supported_python():
    """A fresh interpreter computes it from the JSON a reader would load; CI runs
    this file on 3.10, 3.11 and 3.12 against the same pinned value."""
    code = ("import json,sys;from judge_audit.runner import judgments_digest;"
            "print(judgments_digest(json.loads(sys.stdin.read())))")
    out = subprocess.run([sys.executable, "-c", code], input=json.dumps(FIXTURE),
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == PINNED


def test_run_writes_the_digest_and_the_judgments_file_verifies(labels_path, tmp_path):
    from judge_audit.judges.simulated import SimulatedJudge
    rows = load_jsonl(str(labels_path))
    res = run_audit(SimulatedJudge(rows), rows, ci=False)
    d = res.to_dict()
    assert len(d["judgments_sha256"]) == 64
    path = tmp_path / "audit-judgments.jsonl"
    write_judgments(res, str(path))
    assert verify_judgments(json.loads(json.dumps(d)), str(path)) is None
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["confidence"] = round(first["confidence"] + 0.001, 6)
    path.write_text("\n".join([json.dumps(first), *lines[1:]]) + "\n", encoding="utf-8")
    assert "differs" in verify_judgments(d, str(path))


def test_a_result_without_the_digest_still_loads_and_cannot_be_verified(tmp_path):
    path = tmp_path / "j.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in FIXTURE), encoding="utf-8")
    old = {"judge": "x", "n": 2, "accuracy": 0.5}
    reason = verify_judgments(old, str(path))
    assert reason is not None and "no judgments_sha256" in reason


def test_audit_resumable_writes_the_digest_of_its_records(root, tmp_path):
    sys.path.insert(0, str(root / "scripts"))
    import audit_resumable

    from judge_audit.judges.simulated import SimulatedJudge
    from judge_audit.runner import load_dataset, questions_of
    rows, meta = load_dataset(str(root / "examples/email-routing/labels.jsonl"))
    rec = audit_resumable.checkpoint_row
    judge = SimulatedJudge(rows)
    done = {i: rec(i, r, list(judge.decide(r["state"], questions_of(r))))
            for i, r in enumerate(rows)}
    started = {"timestamp_utc": "2026-01-01T00:00:00+00:00"}
    res = audit_resumable.build_result("simulated", rows, meta, list(range(len(rows))), done,
                                       tmp_path / "c.ckpt.jsonl", started, None)
    assert res.to_dict()["judgments_sha256"] == judgments_digest(res.records)



def test_the_cli_result_names_the_judgments_file_it_wrote(labels_path, tmp_path):
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(labels_path),
                        "--judge", "simulated"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    res = json.loads((tmp_path / "audit-result.json").read_text(encoding="utf-8"))
    assert verify_judgments(res, str(tmp_path / "audit-judgments.jsonl")) is None
