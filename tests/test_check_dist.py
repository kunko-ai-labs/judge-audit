"""scripts/check_dist.py: what may and may not be in the published sdist and wheel (#169),
on small archives built here. CI runs the script itself on the real build."""
from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_dist", ROOT / "scripts" / "check_dist.py")
check_dist = importlib.util.module_from_spec(spec)
sys.modules["check_dist"] = check_dist
spec.loader.exec_module(check_dist)

TOP = "kunko_judge_audit-9.9.9"
SDIST_OK = {"PKG-INFO": b"Name: kunko-judge-audit", "pyproject.toml": b"[project]",
            "README.md": b"# judge-audit", "LICENSE": b"Apache", "CHANGELOG.md": b"# Changelog",
            "SECURITY.md": b"# Security", "src/judge_audit/__init__.py": b"",
            "src/judge_audit/judges/bridge/package.json": b"{}"}
WHEEL_OK = {"judge_audit/__init__.py": b"", "judge_audit/judges/bridge/package.json": b"{}",
            f"{TOP}.dist-info/METADATA": b"Name: kunko-judge-audit",
            f"{TOP}.dist-info/RECORD": b""}


def sdist(tmp_path: Path, files: dict[str, bytes]) -> Path:
    path = tmp_path / f"{TOP}.tar.gz"
    with tarfile.open(path, "w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(f"{TOP}/{name}")
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return path


def wheel(tmp_path: Path, files: dict[str, bytes]) -> Path:
    path = tmp_path / f"{TOP}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def test_the_package_alone_has_no_finding(tmp_path):
    assert check_dist.findings(sdist(tmp_path, SDIST_OK), home="/nowhere/u") == []
    assert check_dist.findings(wheel(tmp_path, WHEEL_OK), home="/nowhere/u") == []


@pytest.mark.parametrize("name, what", [
    ("docs/runs/v06/x-en-US.ckpt.jsonl", "checkpoint"),
    ("tests/fixtures/run.ckpt.jsonl", "checkpoint"),
    ("docs/audit-jev-real.json", "evidence"),
    ("run.log", "log"),
    (".env", "environment"),
    (".env.example", "environment"),
    ("CLAUDE.md", "agent"),
    (".claude/settings.json", "agent"),
    ("notes.local.md", "local review"),
    ("src/judge_audit/judges/bridge/node_modules/ai/index.js", "npm"),
    ("src/judge_audit/__pycache__/cli.cpython-312.pyc", "bytecode"),
    ("tests/test_cli.py", "allow-list"),
    ("scripts/v06_study.py", "allow-list"),
    ("examples/email-routing/labels.jsonl", "allow-list"),
])
def test_a_path_that_must_not_ship_is_named(tmp_path, name, what):
    out = check_dist.findings(sdist(tmp_path, {**SDIST_OK, name: b"x"}), home="/nowhere/u")
    assert len(out) == 1 and name in out[0] and what in out[0], out


@pytest.mark.parametrize("name", ["docs/index.md", "judge_audit/x.log", "tests/test_cli.py",
                                  "judge_audit/__pycache__/x.pyc"])
def test_the_wheel_is_held_to_the_same_rules(tmp_path, name):
    out = check_dist.findings(wheel(tmp_path, {**WHEEL_OK, name: b"x"}), home="/nowhere/u")
    assert len(out) == 1 and name in out[0], out


def test_a_file_or_an_archive_over_its_limit_is_named(tmp_path, monkeypatch):
    big = {**SDIST_OK, "CHANGELOG.md": b"x" * 2048}
    monkeypatch.setattr(check_dist, "MAX_FILE", 1024)
    out = check_dist.findings(sdist(tmp_path, big), home="/nowhere/u")
    assert len(out) == 1 and "CHANGELOG.md" in out[0] and "limit" in out[0]
    monkeypatch.setattr(check_dist, "MAX_ARCHIVE", 10)
    assert any("over the 10 limit" in f for f in
               check_dist.findings(wheel(tmp_path, WHEEL_OK), home="/nowhere/u"))


def test_the_current_home_directory_in_a_file_is_named(tmp_path):
    files = {**SDIST_OK, "src/judge_audit/cli.py": b"DEFAULT = '/nowhere/u/data'"}
    out = check_dist.findings(sdist(tmp_path, files), home="/nowhere/u")
    assert out == [f"{TOP}.tar.gz: src/judge_audit/cli.py holds the current user's home "
                   "directory"]


def test_the_allow_list_is_the_one_pyproject_builds():
    tomllib = pytest.importorskip("tomllib")
    sdist_cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "tool"]["hatch"]["build"]["targets"]["sdist"]
    listed = set(sdist_cfg["only-include"])
    assert listed == (check_dist.SDIST_FILES - {"PKG-INFO", ".gitignore"}) | {
        d.rstrip("/") for d in check_dist.SDIST_DIRS}


def test_main_needs_a_wheel_and_an_sdist(tmp_path, capsys):
    assert check_dist.main([str(wheel(tmp_path, WHEEL_OK))]) == 2
