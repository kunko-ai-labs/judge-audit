"""Every way the code reaches the network is known and reviewed (#169).

Two guards. Statically, every module under src/, scripts/ and examples/ is parsed and each
network primitive it uses (an HTTP client, a socket, a model download, a child process) must
be in `REVIEWED` for that file, with the reason it is there; a primitive that is not, or an
entry that no longer matches the code, fails. A request that carries a key is sent only by
`OPENER` (no redirects), from a module that builds its URL with `checked_endpoint`.

At run time, `tests/conftest.py` installs `tests/offline/offline_guard.py` for the whole suite
and every Python process a test starts: a connection or lookup that leaves this computer
fails the test that made it. The last tests here prove that guard fires, and run the CLI's
offline paths under it.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import urllib.request
from pathlib import Path

import offline_guard
import pytest

from judge_audit import cli

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"
SCANNED = ("src/judge_audit", "scripts", "examples")

# Modules whose import is itself a way out: HTTP clients, sockets, SDKs that call a hosted
# model, the libraries that download weights, and child processes.
NETWORK_MODULES = {
    "socket", "http.client", "requests", "httpx", "aiohttp", "urllib3", "ftplib", "smtplib",
    "websocket", "websockets", "anthropic", "openai", "huggingface_hub", "transformers",
    "mlx_lm", "subprocess",
}
# Names that open a connection or download whatever module they come from.
NETWORK_CALLS = {
    "urlopen", "build_opener", "install_opener", "OpenerDirector", "HTTPConnection",
    "HTTPSConnection", "create_connection", "snapshot_download", "hf_hub_download",
    "from_pretrained", "Anthropic", "OpenAI",
}

KEYED = "the request carries a key: OPENER (no redirects) to a checked_endpoint URL"
WEIGHTS = ("downloads model weights from the Hugging Face Hub (HF_ENDPOINT, no key of ours "
           "unless HF_TOKEN is set); not under the endpoint rule, see #169")
EXCEPTIONS_ONLY = "imported for its exception types; the request goes through OPENER"
GIT = "runs git or a local script, no network"
SNAPSHOT = "loads the snapshot that snapshot_download fetched"

# file -> {primitive: why it is there}. A primitive is `import <module>`, a name from
# NETWORK_CALLS, or `OPENER.open`.
REVIEWED: dict[str, dict[str, str]] = {
    "src/judge_audit/judges/secrets.py": {
        "build_opener": "builds OPENER itself, the one opener that refuses redirects"},
    "src/judge_audit/judges/llm.py": {
        "OPENER.open": KEYED,
        "import http.client": EXCEPTIONS_ONLY,
        "import anthropic": "the anthropic SDK; the client gets the checked ANTHROPIC_BASE_URL "
                            "and an HTTP client that does not follow redirects",
        "Anthropic": "built only through _anthropic_client_args (checked URL, no redirects)",
    },
    "src/judge_audit/judges/hosted.py": {"OPENER.open": KEYED},
    "src/judge_audit/judges/jev.py": {
        "OPENER.open": KEYED,
        "import subprocess": "the gateway backend runs the Node bridge, whose AI SDK calls the "
                             "gateway; not under the endpoint rule, see #169",
    },
    "src/judge_audit/judges/decider.py": {"import huggingface_hub": WEIGHTS,
                                          "snapshot_download": WEIGHTS,
                                          "import transformers": SNAPSHOT},
    "src/judge_audit/judges/clef.py": {"import huggingface_hub": WEIGHTS,
                                       "snapshot_download": WEIGHTS,
                                       "import transformers": SNAPSHOT},
    "src/judge_audit/judges/strands.py": {"import huggingface_hub": WEIGHTS,
                                          "snapshot_download": WEIGHTS,
                                          "import transformers": SNAPSHOT},
    "src/judge_audit/judges/laya.py": {"import huggingface_hub": WEIGHTS,
                                       "snapshot_download": WEIGHTS},
    "src/judge_audit/judges/logprob.py": {
        "import huggingface_hub": "snapshot_download(local_files_only=True): reads the cache",
        "snapshot_download": "local_files_only=True: reads the cache, never downloads",
        "import mlx_lm": WEIGHTS},
    "src/judge_audit/judges/decision2.py": {"import transformers": WEIGHTS,
                                            "from_pretrained": WEIGHTS},
    "src/judge_audit/judges/nli.py": {"import transformers": WEIGHTS},
    "src/judge_audit/judges/finetuned.py": {
        "import transformers": "loads a local model directory",
        "from_pretrained": "a local model directory, the one train_classifier.py wrote"},
    "scripts/logprob_smoke.py": {"OPENER.open": KEYED},
    "scripts/fetch_real_datasets.py": {
        "import http.client": "exception types for the retry",
        "urlopen": "keyless download of pinned public dataset files, each checked against its "
                   "recorded sha256",
    },
    "scripts/train_classifier.py": {"import huggingface_hub": WEIGHTS,
                                    "snapshot_download": WEIGHTS,
                                    "import transformers": WEIGHTS,
                                    "from_pretrained": WEIGHTS},
    "scripts/jury_deliberate.py": {"import subprocess": GIT},
    "scripts/runs_report.py": {"import subprocess": GIT},
    "scripts/check_dist.py": {"import subprocess": "runs `python -m build`, which installs the "
                                                   "build backend from the package index"},
    "scripts/verify_readme.py": {"import subprocess": "runs the CLI on the simulated judge"},
}


def primitives(source: str) -> dict[str, list[int]]:
    """The network primitives `source` uses -> the lines they are on."""
    found: dict[str, list[int]] = {}

    def add(name: str, node: ast.AST) -> None:
        found.setdefault(name, []).append(node.lineno)

    def module(name: str) -> str | None:
        return next((m for m in NETWORK_MODULES if name == m or name.startswith(m + ".")), None)

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if m := module(alias.name):
                    add(f"import {m}", node)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if m := module(node.module):
                add(f"import {m}", node)
            elif node.module in ("http", "urllib") and any(
                    a.name in ("client",) for a in node.names):
                add("import http.client", node)
            for alias in node.names:
                if alias.name in NETWORK_CALLS:
                    add(alias.name, node)
        elif isinstance(node, ast.Attribute):
            if node.attr in NETWORK_CALLS:
                add(node.attr, node)
            elif (node.attr == "open" and isinstance(node.value, ast.Name)
                  and node.value.id == "OPENER"):
                add("OPENER.open", node)
        elif isinstance(node, ast.Name) and node.id in NETWORK_CALLS:
            add(node.id, node)
    return found


def scanned_files() -> list[Path]:
    return sorted(p for d in SCANNED for p in (ROOT / d).rglob("*.py")
                  if "node_modules" not in p.parts)


def test_every_network_primitive_in_the_code_is_reviewed():
    unreviewed = []
    for path in scanned_files():
        rel = path.relative_to(ROOT).as_posix()
        for name, lines in primitives(path.read_text(encoding="utf-8")).items():
            if name not in REVIEWED.get(rel, {}):
                unreviewed.append(f"{rel}:{lines[0]} uses {name}")
    assert not unreviewed, (
        "a way to the network that nobody reviewed; send a keyed request through OPENER to a "
        "checked_endpoint URL, or add it to REVIEWED with its reason:\n" + "\n".join(unreviewed))


def test_every_reviewed_entry_still_matches_the_code():
    stale = []
    for rel, allowed in REVIEWED.items():
        path = ROOT / rel
        found = primitives(path.read_text(encoding="utf-8")) if path.exists() else {}
        stale += [f"{rel}: {name}" for name in allowed if name not in found]
    assert not stale, "REVIEWED names what the code no longer does:\n" + "\n".join(stale)


def test_a_keyed_request_is_sent_from_a_module_that_checks_its_endpoint():
    for rel, allowed in REVIEWED.items():
        if "OPENER.open" in allowed:
            assert "checked_endpoint(" in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_a_stray_urlopen_is_caught(tmp_path):
    """The mutation the guard exists for: a plain urlopen added to a judge."""
    src = (ROOT / "src/judge_audit/judges/hosted.py").read_text(encoding="utf-8")
    assert "urlopen" not in primitives(src)
    for stray in ("\nimport urllib.request\nurllib.request.urlopen('https://x.test')\n",
                  "\nfrom urllib.request import urlopen\n",
                  "\nimport requests\n", "\nimport httpx\n", "\nimport socket\n"):
        found = primitives(src + stray)
        assert set(found) - set(REVIEWED["src/judge_audit/judges/hosted.py"]), stray


# --- the runtime guard ----------------------------------------------------------------------

def test_the_offline_guard_refuses_an_outside_host_and_records_it():
    import conftest
    conftest._new_attempts()
    with pytest.raises(OSError):
        urllib.request.urlopen("https://api.example.com/v1", timeout=1)
    attempts = conftest._new_attempts()                     # consumed: this test passes
    assert attempts and "api.example.com" in attempts[0]


def test_the_offline_guard_allows_this_computer():
    assert offline_guard.allowed(("127.0.0.1", 9)) and offline_guard.allowed(("::1", 9, 0, 0))
    assert offline_guard.allowed(("localhost", 9)) and offline_guard.allowed("/tmp/s.sock")
    assert not offline_guard.allowed(("10.0.0.1", 443))
    assert not offline_guard.allowed(("api.example.com", 443))


def test_a_child_python_process_inherits_the_guard():
    import conftest
    conftest._new_attempts()
    code = ("import socket\ntry:\n    socket.create_connection(('203.0.113.7', 443), 1)\n"
            "except OSError as e:\n    print(type(e).__name__)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=60).stdout
    attempts = conftest._new_attempts()
    assert "NetworkBlocked" in out and any("203.0.113.7" in a for a in attempts)


@pytest.mark.parametrize("argv", [
    ["run", str(LABELS), "--judge", "simulated", "--no-ci"],
    ["run", str(LABELS), "--judge", "simulated", "--no-ci", "--format", "html"],
], ids=["run-md", "run-html"])
def test_the_cli_offline_paths_make_no_connection(tmp_path, argv):
    """A simulated audit and its report: the paths that run with no key, under the guard
    (which fails this test on any connection, caught or not)."""
    out = tmp_path / "r"
    cli.main([*argv, "--out", str(out), "--json", str(tmp_path / "r.json")])
    cli.main(["check", str(LABELS), "--judge", "simulated", "--no-ci",
              "--baseline", str(tmp_path / "r.json"), "--out", str(tmp_path / "c.md")])
