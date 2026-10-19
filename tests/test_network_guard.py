"""Every way the code reaches the network, as written in the source, is listed and reviewed
(#169).

Two guards. Statically, every module under src/, scripts/ and examples/ is parsed and each
network primitive it uses (an HTTP client, a socket, a model download, a child process) must
be in `REVIEWED` for that file, with the reason it is there; a primitive that is not, or an
entry that no longer matches the code, fails. The scan finds network use written explicitly in
the source. It does not find code that hides the call: `eval`, `exec` or `compile`, `ctypes`,
`runpy`, a lookup in `vars()`, `__dict__` or `sys.modules`, or a function that returns the
opener. Review catches those; the runtime guard below still refuses what they would send.
A request that carries a key is sent only by `OPENER` (no redirects), from a module that
builds its URL with `checked_endpoint`.

At run time, `tests/conftest.py` installs `tests/offline/offline_guard.py` for the whole suite
and every Python process a test starts with its environment: a connection, datagram or lookup
that leaves this computer fails the test that made it. What that guard does not cover is
listed in its docstring. The last tests here prove that it fires, and run the CLI's offline
paths under it.
"""
from __future__ import annotations

import _socket
import ast
import socket
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

# Modules whose import is itself a way out: HTTP clients, sockets, mail and RPC clients, SDKs
# that call a hosted model, the libraries that download weights, child processes and terminals,
# the browser, and urllib.request (its Request is built for OPENER, but it holds urlopen too).
NETWORK_MODULES = {
    "socket", "http.client", "urllib.request", "requests", "httpx", "aiohttp", "urllib3",
    "ftplib", "smtplib", "imaplib", "poplib", "telnetlib", "xmlrpc", "asyncio",
    "multiprocessing.connection", "websocket", "websockets", "webbrowser", "anthropic",
    "_socket", "posix", "nt",
    "openai", "huggingface_hub", "transformers", "mlx_lm", "subprocess", "pty",
}
# Names that open a connection, download or start a process, whatever module they come from.
NETWORK_CALLS = {
    "urlopen", "urlretrieve", "build_opener", "install_opener", "OpenerDirector",
    "HTTPConnection", "HTTPSConnection", "create_connection", "open_connection", "ServerProxy",
    "snapshot_download", "hf_hub_download", "from_pretrained", "Anthropic", "OpenAI",
    "import_module", "__import__",
}
# Functions of `os` that run another program, which can reach the network on its own.
OS_CALLS = {"system", "popen", "startfile", "posix_spawn", "posix_spawnp"}
OS_PREFIXES = ("exec", "spawn")

KEYED = "the request carries a key: OPENER (no redirects) to a checked_endpoint URL"
WEIGHTS = ("downloads model weights from the Hugging Face Hub (HF_ENDPOINT, no key of ours "
           "unless HF_TOKEN is set); not under the endpoint rule, see #169")
EXCEPTIONS_ONLY = "imported for its exception types; the request goes through OPENER"
GIT = "runs git or a local script, no network"
SNAPSHOT = "loads the snapshot that snapshot_download fetched"
REQUEST = "builds the urllib Request that OPENER sends"

# file -> {primitive: why it is there}. A primitive is `import <module>`, a name from
# NETWORK_CALLS, `os.<name>` for a call that runs a program, `getattr <module>` for a name
# looked up at run time on a network module, `import * from <module>` for a star import of
# a network module or `os`, `OPENER.open` (`.open` on a name or attribute called OPENER) or
# `OPENER binding` (OPENER assigned, imported or looked up under another name, or held in a
# value such as a tuple).
# Out of reach by design: the `custom` provider of the `llm` judge loads a user's own module
# (LLM_PROVIDER_MODULE, llm.py) that this scan cannot read; the runtime guard still applies.
REVIEWED: dict[str, dict[str, str]] = {
    "src/judge_audit/judges/secrets.py": {
        "build_opener": "builds OPENER itself, the one opener that refuses redirects",
        "import urllib.request": "the redirect handler OPENER is built with",
        "OPENER binding": "the one place OPENER is defined"},
    "src/judge_audit/judges/llm.py": {
        "OPENER.open": KEYED,
        "import http.client": EXCEPTIONS_ONLY,
        "import anthropic": "the anthropic SDK; the client gets the checked ANTHROPIC_BASE_URL "
                            "and an HTTP client that does not follow redirects",
        "Anthropic": "built only through _anthropic_client_args (checked URL, no redirects)",
        "getattr anthropic": "looks up DefaultHttpxClient, to build a client that does not "
                             "follow redirects",
        "import urllib.request": REQUEST,
    },
    "src/judge_audit/judges/hosted.py": {"OPENER.open": KEYED, "import urllib.request": REQUEST},
    "src/judge_audit/judges/jev.py": {
        "OPENER.open": KEYED,
        "import urllib.request": REQUEST,
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
    "scripts/logprob_smoke.py": {"OPENER.open": KEYED, "import urllib.request": REQUEST},
    "scripts/fetch_real_datasets.py": {
        "import http.client": "exception types for the retry",
        "import urllib.request": "the urlopen below",
        "urlopen": "keyless download of pinned public dataset files, each checked against its "
                   "recorded sha256",
    },
    "scripts/train_classifier.py": {"import huggingface_hub": WEIGHTS,
                                    "snapshot_download": WEIGHTS,
                                    "import transformers": WEIGHTS,
                                    "from_pretrained": WEIGHTS,
                                    "__import__": "reads transformers.__version__ for the "
                                                  "provenance"},
    "scripts/jury_deliberate.py": {"import subprocess": GIT},
    "scripts/runs_report.py": {"import subprocess": GIT},
    "scripts/check_dist.py": {"import subprocess": "runs `python -m build`, which installs the "
                                                   "build backend from the package index"},
    "scripts/verify_readme.py": {"import subprocess": "runs the CLI on the simulated judge"},
}


def _network_module(name: str) -> str | None:
    return next((m for m in NETWORK_MODULES if name == m or name.startswith(m + ".")), None)


def _ends_in_opener(node: ast.AST) -> bool:
    return ((isinstance(node, ast.Name) and node.id == "OPENER")
            or (isinstance(node, ast.Attribute) and node.attr == "OPENER"))


def _holds_opener(value: ast.AST) -> bool:
    """Whether `value` holds OPENER itself (`OPENER`, `(OPENER, 1)`, `[x.OPENER]`), not only
    something read from it (`OPENER.open(req)`)."""
    read_from = {id(n.value) for n in ast.walk(value) if isinstance(n, ast.Attribute)}
    return any(_ends_in_opener(n) and id(n) not in read_from for n in ast.walk(value))


def primitives(source: str) -> dict[str, list[int]]:
    """The network primitives `source` uses -> the lines they are on."""
    tree = ast.parse(source)
    found: dict[str, list[int]] = {}
    bound: dict[str, str] = {}               # a name -> the module it was imported as

    def add(name: str, node: ast.AST) -> None:
        found.setdefault(name, []).append(node.lineno)

    def dotted(node: ast.AST) -> str | None:
        """`a.b.c` as the module path it names, through the names imports bound."""
        if isinstance(node, ast.Name):
            return bound.get(node.id, node.id)
        if isinstance(node, ast.Attribute) and (base := dotted(node.value)):
            return f"{base}.{node.attr}"
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                bound[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if m := _network_module(alias.name):
                    add(f"import {m}", node)
        elif isinstance(node, ast.ImportFrom):
            # OPENER under another name, whatever the import's level: the judges import it
            # relatively (`from .secrets import OPENER`).
            if any(a.name == "OPENER" and a.asname not in (None, "OPENER") for a in node.names):
                add("OPENER binding", node)
            if not node.module or node.level != 0:
                continue
            if m := _network_module(node.module):
                add(f"import {m}", node)
            if any(a.name == "*" for a in node.names) and (
                    node.module == "os" or _network_module(node.module)):
                add(f"import * from {node.module}", node)
            for alias in node.names:
                if m := _network_module(f"{node.module}.{alias.name}"):
                    add(f"import {m}", node)
                if alias.name in NETWORK_CALLS:
                    add(alias.name, node)
                if node.module == "os" and (alias.name in OS_CALLS
                                            or alias.name.startswith(OS_PREFIXES)):
                    add(f"os.{alias.name}", node)
        elif isinstance(node, ast.Attribute):
            if node.attr in NETWORK_CALLS:
                add(node.attr, node)
            elif node.attr == "open" and _ends_in_opener(node.value):
                add("OPENER.open", node)
            elif (dotted(node.value) == "os"
                  and (node.attr in OS_CALLS or node.attr.startswith(OS_PREFIXES))):
                add(f"os.{node.attr}", node)
        elif isinstance(node, ast.Name) and node.id in NETWORK_CALLS:
            add(node.id, node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and (
                node.func.id == "getattr" and node.args):
            name = node.args[1] if len(node.args) > 1 else None
            if isinstance(name, ast.Constant) and name.value == "OPENER":
                add("OPENER binding", node)
            target = dotted(node.args[0]) or ""
            if m := _network_module(target) or next(
                    (n for n in (*NETWORK_MODULES, "os") if n == target
                     or n.startswith(target + ".")), None):
                add(f"getattr {m}", node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_ends_in_opener(x) for x in targets) or (
                    node.value is not None and _holds_opener(node.value)):
                add("OPENER binding", node)
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


# Each way out, planted alone in an otherwise clean module, and the primitive it must yield.
PLANTED = [
    ("import urllib.request\nurllib.request.urlretrieve(u, 'f')", "urlretrieve"),
    ("from urllib.request import urlretrieve", "urlretrieve"),
    ("import os\nos.system('curl ' + u)", "os.system"),
    ("import os\nos.popen('curl ' + u)", "os.popen"),
    ("import os\nos.execvp('curl', ['curl', u])", "os.execvp"),
    ("import os\nos.spawnlp(os.P_WAIT, 'curl', 'curl', u)", "os.spawnlp"),
    ("import os as o\no.system('curl ' + u)", "os.system"),
    ("from os import system\nsystem('curl ' + u)", "os.system"),
    ("import os\nos.posix_spawn('/usr/bin/curl', ['curl', u], {})", "os.posix_spawn"),
    ("import pty\npty.spawn(['curl', u])", "import pty"),
    ("import asyncio\nasyncio.open_connection('h', 443)", "import asyncio"),
    ("import asyncio\nasyncio.open_connection('h', 443)", "open_connection"),
    ("import xmlrpc.client\nxmlrpc.client.ServerProxy(u)", "import xmlrpc"),
    ("from xmlrpc.client import ServerProxy", "ServerProxy"),
    ("import imaplib", "import imaplib"),
    ("import smtplib", "import smtplib"),
    ("import ftplib", "import ftplib"),
    ("import poplib", "import poplib"),
    ("from multiprocessing.connection import Client", "import multiprocessing.connection"),
    ("from multiprocessing import connection", "import multiprocessing.connection"),
    ("import webbrowser\nwebbrowser.open(u)", "import webbrowser"),
    ("import importlib\nimportlib.import_module('requests')", "import_module"),
    ("from importlib import import_module", "import_module"),
    ("__import__('requests')", "__import__"),
    ("import urllib\ngetattr(urllib, 'request')", "getattr urllib.request"),
    ("import urllib.request as r\ngetattr(r, 'url' + 'open')(u)", "getattr urllib.request"),
    ("import os\ngetattr(os, 'sys' + 'tem')('curl')", "getattr os"),
    ("from judge_audit.judges import secrets\nsecrets.OPENER.open(req)", "OPENER.open"),
    ("from judge_audit.judges.secrets import OPENER\no = OPENER\no.open(req)",
     "OPENER binding"),
    ("from judge_audit.judges.secrets import OPENER as O\nO.open(req)", "OPENER binding"),
    ("from judge_audit.judges import secrets\nsecrets.OPENER = None", "OPENER binding"),
    ("from .secrets import OPENER as O\nO.open(req)", "OPENER binding"),
    ("from ..judges.secrets import OPENER as O\nO.open(req)", "OPENER binding"),
    ("from judge_audit.judges import secrets\ngetattr(secrets, 'OPENER').open(req)",
     "OPENER binding"),
    ("from .secrets import OPENER\na, b = OPENER, 1", "OPENER binding"),
    ("from os import *\nsystem('curl ' + u)", "import * from os"),
    ("from urllib.request import *\nurlopen(u)", "import * from urllib.request"),
    ("from socket import *", "import * from socket"),
    ("import _socket", "import _socket"),
    ("import posix\nposix.system('curl')", "import posix"),
    ("import nt", "import nt"),
]


@pytest.mark.parametrize("source, primitive", PLANTED,
                         ids=[f"{p}-{i}" for i, (_, p) in enumerate(PLANTED)])
def test_each_way_out_is_found_when_planted(source, primitive):
    assert primitive in primitives(source), primitives(source)


def test_ordinary_code_is_not_a_way_out():
    clean = ("import os\nimport platform\nos.path.join('a', 'b')\nplatform.system()\n"
             "getattr(obj, 'system')\nmodel.system_one(x)\nopen('f').read()\n"
             "from .base import Judge\nfrom pathlib import *\n")
    assert primitives(clean) == {}
    sent = "from .secrets import OPENER\nresp = OPENER.open(req)\n"      # a send, not a binding
    assert set(primitives(sent)) == {"OPENER.open"}


# --- the runtime guard ----------------------------------------------------------------------

def _attempts_of(action) -> list[str]:
    """What `action` recorded in the guard's log; consumed, so the calling test passes."""
    import conftest
    conftest._new_attempts()
    with pytest.raises(OSError):
        action()
    return conftest._new_attempts()


def test_the_offline_guard_refuses_an_outside_host_and_records_it():
    assert _attempts_of(lambda: urllib.request.urlopen("https://api.example.com/v1",
                                                       timeout=1)) == [
        "lookup 'api.example.com'"]


@pytest.mark.parametrize("action, line", [
    (lambda: socket.gethostbyname("api.example.com"), "lookup 'api.example.com'"),
    (lambda: socket.gethostbyname_ex("api.example.com"), "lookup 'api.example.com'"),
    (lambda: socket.gethostbyaddr("203.0.113.7"), "lookup '203.0.113.7'"),
    (lambda: socket.getnameinfo(("203.0.113.7", 443), 0), "lookup ('203.0.113.7', 443)"),
    (lambda: _socket.gethostbyname("api.example.com"), "lookup 'api.example.com'"),
    (lambda: _udp().sendto(b"x", ("203.0.113.7", 53)), "send ('203.0.113.7', 53)"),
    (lambda: _udp().sendto(b"x", 0, ("api.example.com", 53)), "send ('api.example.com', 53)"),
    (lambda: _udp().sendmsg([b"x"], [], 0, ("203.0.113.7", 53)), "send ('203.0.113.7', 53)"),
], ids=["gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo",
        "_socket.gethostbyname", "sendto", "sendto-flags-name", "sendmsg"])
def test_every_guarded_call_refuses_and_records(action, line):
    assert _attempts_of(action) == [line]


def _udp() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _open.append(s)
    return s


_open: list[socket.socket] = []


@pytest.fixture(autouse=True)
def _close_sockets():
    yield
    while _open:
        _open.pop().close()


def test_the_offline_guard_allows_this_computer():
    for here in (("127.0.0.1", 9), ("::1", 9, 0, 0), ("localhost", 9), ("0.0.0.0", 9),
                 ("::", 9, 0, 0), ("::ffff:127.0.0.1", 9, 0, 0), "/tmp/s.sock"):
        assert offline_guard.allowed(here), here
    for away in (("10.0.0.1", 443), ("api.example.com", 443), ("::ffff:10.0.0.1", 443, 0, 0)):
        assert not offline_guard.allowed(away), away


def test_a_lookup_on_this_computer_still_answers():
    """Through `socket` and through `_socket`: neither wrapper calls itself."""
    assert socket.getaddrinfo("127.0.0.1", 80)
    assert _socket.getaddrinfo("127.0.0.1", 80)
    assert socket.gethostbyname("127.0.0.1") == "127.0.0.1"
    assert _socket.gethostbyname("127.0.0.1") == "127.0.0.1"
    assert socket.getnameinfo(("127.0.0.1", 80), socket.NI_NUMERICHOST | socket.NI_NUMERICSERV)


def test_a_child_python_process_inherits_the_guard():
    import conftest
    conftest._new_attempts()
    code = ("import socket\ntry:\n    socket.create_connection(('203.0.113.7', 443), 1)\n"
            "except OSError as e:\n    print(type(e).__name__)\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         timeout=60).stdout
    assert out.strip() == "NetworkBlocked"
    assert conftest._new_attempts() == ["lookup '203.0.113.7'"]


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
