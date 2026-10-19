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
    ("docs/runs/v06/x-en-US.ckpt.jsonl", "a raw checkpoint"),
    ("tests/fixtures/run.ckpt.jsonl", "a raw checkpoint"),
    ("docs/audit-jev-real.json", "the published evidence (docs/)"),
    ("run.log", "a log"),
    (".env", "an environment file"),
    (".env.example", "an environment file"),
    ("CLAUDE.md", "editor or agent configuration"),
    (".claude/settings.json", "editor or agent configuration"),
    ("notes.local.md", "local review notes"),
    ("src/judge_audit/judges/bridge/node_modules/ai/index.js", "installed npm packages"),
    ("src/judge_audit/__pycache__/cli.cpython-312.pyc", "bytecode"),
    ("tests/test_cli.py", "outside the allow-list"),
    ("scripts/v06_study.py", "outside the allow-list"),
    ("examples/email-routing/labels.jsonl", "outside the allow-list"),
])
def test_a_path_that_must_not_ship_is_named(tmp_path, name, what):
    out = check_dist.findings(sdist(tmp_path, {**SDIST_OK, name: b"x"}), home="/nowhere/u")
    assert out == [f"{TOP}.tar.gz: {name} is {what}"]


@pytest.mark.parametrize("name, what", [
    ("docs/index.md", "the published evidence (docs/)"), ("judge_audit/x.log", "a log"),
    ("tests/test_cli.py", "outside the allow-list"),
    ("judge_audit/__pycache__/x.pyc", "bytecode")])
def test_the_wheel_is_held_to_the_same_rules(tmp_path, name, what):
    out = check_dist.findings(wheel(tmp_path, {**WHEEL_OK, name: b"x"}), home="/nowhere/u")
    assert out == [f"{TOP}-py3-none-any.whl: {name} is {what}"]


def test_a_file_or_an_archive_over_its_limit_is_named(tmp_path, monkeypatch):
    big = {**SDIST_OK, "CHANGELOG.md": b"x" * 2048}
    monkeypatch.setattr(check_dist, "MAX_FILE", 1024)
    out = check_dist.findings(sdist(tmp_path, big), home="/nowhere/u")
    assert out == [f"{TOP}.tar.gz: CHANGELOG.md is 2,048 bytes, over the 1,024 limit"]
    monkeypatch.setattr(check_dist, "MAX_ARCHIVE", 10)
    path = wheel(tmp_path, WHEEL_OK)
    assert check_dist.findings(path, home="/nowhere/u") == [
        f"{path.name}: {path.stat().st_size:,} bytes, over the 10 limit"]


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_a_link_in_the_sdist_is_named(tmp_path, kind):
    """A link is not read as a file, so it would pass the allow-list unseen."""
    path = sdist(tmp_path, SDIST_OK)
    with tarfile.open(path, "r:gz") as t:
        members = [(m, t.extractfile(m).read()) for m in t.getmembers()]
    with tarfile.open(path, "w:gz") as t:
        for m, data in members:
            t.addfile(m, io.BytesIO(data))
        link = tarfile.TarInfo(f"{TOP}/src/judge_audit/data")
        link.type, link.linkname = kind, "../../../.."
        t.addfile(link)
    assert check_dist.findings(path, home="/nowhere/u") == [
        f"{TOP}.tar.gz: src/judge_audit/data is a link or a special file"]


def test_a_symlink_in_the_wheel_is_named(tmp_path):
    path = wheel(tmp_path, WHEEL_OK)
    with zipfile.ZipFile(path, "a") as z:
        info = zipfile.ZipInfo("judge_audit/data")
        info.external_attr = (0o120777 << 16)
        z.writestr(info, "../..")
    assert check_dist.findings(path, home="/nowhere/u") == [
        f"{path.name}: judge_audit/data is a link or a special file"]


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
