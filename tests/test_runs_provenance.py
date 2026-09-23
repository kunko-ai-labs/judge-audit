"""Every committed checkpoint carries its provenance header, or is a documented exception.

docs/runs/README.md tells a reader that a checkpoint's first line records how the run was
produced. That is only true if every checkpoint has the `{"idx": -1, "run": {...}}`
header, except the legacy files the README lists by name. This test keeps the two in step.
"""
from __future__ import annotations

import json
import re

# Written before audit_resumable.py recorded a header; documented in docs/runs/README.md.
NO_HEADER = {
    "audit-jev-real.ckpt.jsonl",
    "audit-jev-adversarial.ckpt.jsonl",
    "audit-jev-router.ckpt.jsonl",
}


def first_line(path):
    with path.open(encoding="utf-8") as f:
        return json.loads(f.readline())


def test_every_checkpoint_has_a_header_or_is_a_documented_exception(root):
    runs = root / "docs" / "runs"
    checkpoints = sorted(runs.rglob("*.ckpt.jsonl"))
    assert checkpoints, "no checkpoint found"
    headerless = set()
    for ck in checkpoints:
        head = first_line(ck)
        if head.get("idx") != -1:
            headerless.add(str(ck.relative_to(runs)))
            continue
        run = head.get("run")
        assert isinstance(run, dict), f"{ck}: header without a run block"
        for key in ("timestamp_utc", "judge_audit_version", "dataset", "judge"):
            assert key in run, f"{ck}: header lacks run.{key}"
        assert {"path", "sha256", "rows"} <= set(run["dataset"]), f"{ck}: dataset incomplete"
        judge = run["judge"]
        assert "model" in judge and ("provider" in judge or "backend" in judge), ck
    assert headerless == NO_HEADER


def test_readme_lists_exactly_the_headerless_checkpoints(root):
    text = (root / "docs" / "runs" / "README.md").read_text(encoding="utf-8")
    section = text.split("**Checkpoints without a header.**", 1)[1]
    listed = set(re.findall(r"^- `([^`]+\.ckpt\.jsonl)`$", section, flags=re.M))
    assert listed == NO_HEADER
    # the sentence that used to be false: not every checkpoint has a header
    assert "every `*.ckpt.jsonl` here starts with" not in text
