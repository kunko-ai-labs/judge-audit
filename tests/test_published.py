"""The house rule: every published audit recomputes from its raw checkpoint."""
from __future__ import annotations

import subprocess
import sys


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
