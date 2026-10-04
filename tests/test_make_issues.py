"""scripts/make_issues.py is public: no machine-specific path; the helper location is input."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_issues  # noqa: E402


def test_no_hard_coded_absolute_path():
    src = (ROOT / "scripts" / "make_issues.py").read_text(encoding="utf-8")
    assert "/opt/" not in src and "sys.path.insert(0, \"/" not in src


def test_helper_dir_comes_from_the_cli_or_the_environment(monkeypatch):
    monkeypatch.delenv("JUDGE_AUDIT_CREDENTIAL_HELPER_DIR", raising=False)
    assert make_issues.helper_dir(None) is None
    monkeypatch.setenv("JUDGE_AUDIT_CREDENTIAL_HELPER_DIR", "/from/env")
    assert make_issues.helper_dir(None) == "/from/env"
    assert make_issues.helper_dir("/from/cli") == "/from/cli"


def test_dry_run_stays_offline(capsys):
    make_issues.main(["--dry-run"])
    assert "(dry run)" in capsys.readouterr().out
