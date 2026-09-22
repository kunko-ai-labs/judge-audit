"""The house rule: every published audit recomputes from its raw checkpoint."""
from __future__ import annotations

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
