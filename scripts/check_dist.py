"""The published archives carry the package and nothing else (#169).

The sdist and the wheel are what PyPI keeps for good: a file in them cannot be taken back. This
check reads both and fails when either holds a path outside its allow-list (the package, its
licence, README, CHANGELOG, SECURITY and build metadata), a path that must never ship (raw
checkpoints, logs, an `.env`, `docs/`, editor or agent configuration, node_modules, bytecode),
a link or special file, a file or archive over its size limit, or the current user's home
directory in any file. The
evidence (docs/: reports and their raw checkpoints) stays in the repository at the release tag.

  python scripts/check_dist.py                  # build both into a temporary directory, check
  python scripts/check_dist.py dist/*           # check archives already built (release.yml)

Building needs the `build` package (`pip install build`). Exit 1 lists every finding.
"""
from __future__ import annotations

import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What the sdist ships, under its `<name>-<version>/` directory: pyproject's `only-include`,
# plus the PKG-INFO and .gitignore hatchling adds. tests/test_check_dist.py keeps the two equal.
SDIST_FILES = {"README.md", "LICENSE", "CHANGELOG.md", "SECURITY.md", "pyproject.toml",
               "PKG-INFO", ".gitignore"}
SDIST_DIRS = ("src/judge_audit/",)
WHEEL_DIRS = ("judge_audit/",)
WHEEL_DIST_INFO = re.compile(r"^kunko_judge_audit-[^/]+\.dist-info/")

# Never in either archive, wherever it sits.
FORBIDDEN = (
    (re.compile(r"\.ckpt\.jsonl$"), "a raw checkpoint"),
    (re.compile(r"\.log$"), "a log"),
    (re.compile(r"(^|/)\.env($|\.)"), "an environment file"),
    (re.compile(r"(^|/)docs/"), "the published evidence (docs/)"),
    (re.compile(r"(^|/)(CLAUDE|AGENTS)\.md$|(^|/)\.claude/"), "editor or agent configuration"),
    (re.compile(r"\.local\.md$|(^|/)auditoria[^/]*\.md$"), "local review notes"),
    (re.compile(r"(^|/)node_modules/"), "installed npm packages"),
    (re.compile(r"(^|/)__pycache__/|\.py[co]$"), "bytecode"),
    (re.compile(r"(^|/)\.DS_Store$"), "desktop metadata"),
)
MAX_FILE = 512 * 1024             # bytes, any one file uncompressed (CHANGELOG.md is the largest)
MAX_ARCHIVE = 1024 * 1024         # bytes, each archive as published


def members(path: Path) -> Iterator[tuple[str, int, bytes]]:
    """(path inside the archive, size, content) of every file; the sdist's top directory
    is dropped."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                if not i.is_dir():
                    yield i.filename, i.file_size, z.read(i)
        return
    with tarfile.open(path) as t:
        for m in t.getmembers():
            if m.isfile():
                f = t.extractfile(m)
                yield m.name.split("/", 1)[1], m.size, f.read() if f else b""


def specials(path: Path) -> list[str]:
    """Members that are neither a regular file nor a directory (a symlink, a hard link, a
    device): `members` does not read them, so they would pass every other check."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as z:
            return [i.filename for i in z.infolist()
                    if not i.is_dir() and stat.S_IFMT(i.external_attr >> 16) not in (
                        0, stat.S_IFREG)]
    with tarfile.open(path) as t:
        return [m.name.split("/", 1)[-1] for m in t.getmembers()
                if not (m.isfile() or m.isdir())]


def allowed(name: str, wheel: bool) -> bool:
    if wheel:
        return name.startswith(WHEEL_DIRS) or bool(WHEEL_DIST_INFO.match(name))
    return name in SDIST_FILES or name.startswith(SDIST_DIRS)


def findings(path: Path, home: str | None = None) -> list[str]:
    """Every reason `path` (a wheel or an sdist) must not be published."""
    wheel = path.suffix == ".whl"
    home = str(Path.home()) if home is None else home
    out = []
    if path.stat().st_size > MAX_ARCHIVE:
        out.append(f"{path.name}: {path.stat().st_size:,} bytes, over the {MAX_ARCHIVE:,} limit")
    out += [f"{path.name}: {name} is a link or a special file" for name in specials(path)]
    for name, size, data in members(path):
        for pattern, what in FORBIDDEN:
            if pattern.search(name):
                out.append(f"{path.name}: {name} is {what}")
                break
        else:
            if not allowed(name, wheel):
                out.append(f"{path.name}: {name} is outside the allow-list")
        if size > MAX_FILE:
            out.append(f"{path.name}: {name} is {size:,} bytes, over the {MAX_FILE:,} limit")
        if len(home) > 1 and home.encode() in data:
            out.append(f"{path.name}: {name} holds the current user's home directory")
    return out


def build(into: Path) -> list[Path]:
    subprocess.run([sys.executable, "-m", "build", "--outdir", str(into), str(ROOT)],
                   check=True, stdout=subprocess.DEVNULL)
    return sorted(into.iterdir())


def main(argv: list[str]) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        paths = [Path(a) for a in argv] or build(Path(tmp))
        kinds = {p.suffix == ".whl" for p in paths}
        if kinds != {True, False}:
            print("check_dist: need one wheel and one sdist", file=sys.stderr)
            return 2
        problems = [f for p in paths for f in findings(p)]
        for p in paths:
            print(f"{p.name}: {p.stat().st_size:,} bytes, "
                  f"{sum(1 for _ in members(p))} files")
    for f in problems:
        print(f, file=sys.stderr)
    print(f"{len(problems)} finding(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
