"""The house rule: every published audit recomputes from its raw checkpoint."""
from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path


def test_published_audits_match_their_checkpoints(root):
    r = subprocess.run([sys.executable, "scripts/verify_published.py"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FAIL" not in r.stdout


def test_datasets_regenerate_identically(root, tmp_path):
    import filecmp
    import shutil

    for d in ("email-routing", "email-routing-adversarial", "task-routing"):
        src = root / "examples" / d
        work = tmp_path / d
        shutil.copytree(src, work)
        # the adversarial generator imports its sibling by relative path
        if d == "email-routing-adversarial":
            shutil.copytree(root / "examples" / "email-routing", tmp_path / "email-routing",
                            dirs_exist_ok=True)
        subprocess.run([sys.executable, "generate.py"], cwd=work, check=True,
                       capture_output=True)
        for f in src.glob("*.jsonl"):
            assert filecmp.cmp(f, work / f.name, shallow=False), f"{d}/{f.name} not reproducible"


def test_no_published_interval_has_zero_width(root):
    """A [x, x] interval claims certainty from a finite sample. It is never published:
    a proportion at the boundary gets the exact binomial interval (†), a degenerate
    bootstrap gets the ‡ mark and no brackets."""
    bad = []
    for md in sorted((root / "docs").rglob("*.md")):
        for line in md.read_text(encoding="utf-8").splitlines():
            # a `[x, x]` inside a code span is prose quoting the shape, not a number
            prose = re.sub(r"`[^`]*`", "", line)
            for lo, hi in re.findall(r"\[(\d+\.\d+), (\d+\.\d+)\]", prose):
                if lo == hi:
                    bad.append(f"{md.relative_to(root)}: {line.strip()[:90]}")
    assert not bad, "zero-width intervals published:\n" + "\n".join(bad[:10])


def test_every_interval_mark_carries_its_legend(root):
    """A † or a ‡ in a report means nothing without the line that defines it."""
    for md in [root / "README.md", *sorted((root / "docs").rglob("*.md"))]:
        text = md.read_text(encoding="utf-8")
        if "†" in text:
            assert "Clopper–Pearson" in text, f"{md.name} uses † without its legend"
        if "‡" in text:
            assert "degenerate" in text, f"{md.name} uses ‡ without its legend"


def test_no_absolute_home_path_in_docs(root):
    """Nothing under docs/ leaks the machine it was generated on (#58)."""
    needles = ["/Users/", "/home/", str(Path.home())]
    bad = []
    for f in sorted((root / "docs").rglob("*")):
        if not f.is_file() or f.suffix in (".png", ".gif", ".svg"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(n in line for n in needles):
                bad.append(f"{f.relative_to(root)}:{i}: {line.strip()[:80]}")
    assert not bad, "absolute home paths published:\n" + "\n".join(bad[:10])


def test_verify_published_compares_the_curve_and_zero_error_coverage(root):
    """The Jev clean-email audit publishes a curve and a zero-error coverage: both are
    compared point by point, not only n / accuracy / ECE / cost (#61)."""
    sys.path.insert(0, str(root / "scripts"))
    import verify_published as vp
    keys = next(k for _, _, pub, _, k in vp.PUBLISHED if pub == "docs/audit-jev-real.json")
    assert {"accuracy_coverage", "zero_error_coverage"} <= set(keys)
    got = {"n": 3, "accuracy_coverage": [
               {"coverage": 0.6667, "accuracy": 1.0, "n": 2, "min_confidence": 0.9},
               {"coverage": 1.0, "accuracy": 0.6667, "n": 3, "min_confidence": 0.5}],
           "zero_error_coverage": {"coverage": 0.6667, "n": 2, "threshold": 0.9}}
    compared = ("n", "accuracy_coverage", "zero_error_coverage")
    assert vp.metric_diffs(copy.deepcopy(got), got, compared) == []
    stale = copy.deepcopy(got)
    stale["accuracy_coverage"][0]["n"] = 1  # a cut inside a tie, as published before #61
    stale["zero_error_coverage"]["threshold"] = 0.5
    diffs = vp.metric_diffs(stale, got, compared)
    assert [d.split(":")[0] for d in diffs] == ["accuracy_coverage", "zero_error_coverage"]


def test_per_run_reports_regenerate_from_their_checkpoints(root):
    """Every audit_resumable.py report under docs/runs/ (and docs/audit-jev-real.json) is
    what scripts/runs_report.py writes from the committed checkpoint today."""
    r = subprocess.run([sys.executable, "scripts/runs_report.py", "--check"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_runs_report_covers_every_per_run_report(root):
    """A per-run report the regeneration does not know about could drift unseen."""
    sys.path.insert(0, str(root / "scripts"))
    import runs_report
    covered = {t["json"] for t in runs_report.targets()}
    # docs/runs/finetuned/ holds training logs and jury/panel.json the frozen panel:
    # neither is an audit report.
    on_disk = {str(p.relative_to(root)) for p in (root / "docs" / "runs").rglob("*.json")
               if p.name != "panel.json" and p.parent.name != "finetuned"}
    assert len(on_disk) == 54 and on_disk <= covered, sorted(on_disk - covered)
    assert "docs/audit-jev-real.json" in covered


def test_only_the_simulated_judge_carries_the_simulated_banner(root):
    """Only the simulated judge carries the SIMULATED banner; a recompute from a complete
    checkpoint used to stamp it on every non-Jev run (#61)."""
    sys.path.insert(0, str(root / "scripts"))
    import audit_resumable
    assert audit_resumable.tag_of("llm") == audit_resumable.tag_of("nli") == ""
    assert audit_resumable.tag_of("simulated").startswith("SIMULATED")
    md = (root / "docs/runs/arena/gemma4/email-clean.md").read_text(encoding="utf-8")
    assert md.startswith("# Audit report — llm") and "SIMULATED" not in md
