"""After every module of the package is imported, OPENER still refuses redirects (#210).

The static scan in `test_network_guard.py` flags every named use of `OPENER` and
`_RefuseRedirects`, but not the forms it lists as hidden (`vars()`, `__dict__`,
`sys.modules`, `operator.attrgetter`, a `getattr` with a computed name, a change to
`urllib.request.HTTPRedirectHandler`). Those would be caught only if some redirect test
happened to run after the module that hides them. Here a fresh Python process imports every
module of the package, in a fixed order, and only then checks the opener: what it is, what it
is built from, and what it does with a redirect from a local server. The planted modules prove
that each hidden form fails the check.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Run in a fresh process: `python -c CHECK [planted module ...]`. Prints {"modules",
# "failures"} as JSON and exits 1 when a check fails.
CHECK = r'''
import http.server, importlib, json, sys, threading, urllib.error, urllib.request
from pathlib import Path

import judge_audit
from judge_audit.judges import secrets

opener, refusal = secrets.OPENER, secrets._RefuseRedirects
before = {
    "handlers": [type(h) for h in opener.handlers],
    "addheaders": list(opener.addheaders),
    "refusal": dict(vars(refusal)),
    "base": {k: v for k, v in vars(urllib.request.HTTPRedirectHandler).items()
             if k.startswith(("http_error_", "redirect_request"))},
}

root = Path(judge_audit.__file__).parent
modules = sorted("judge_audit." + ".".join(p.relative_to(root).with_suffix("").parts)
                 for p in root.rglob("*.py")
                 if p.name != "__init__.py" and "node_modules" not in p.parts)
for name in modules + sys.argv[1:]:
    importlib.import_module(name)

failures = []
if secrets.OPENER is not opener:
    failures.append("secrets.OPENER is not the opener it was built as")
if secrets._RefuseRedirects is not refusal:
    failures.append("secrets._RefuseRedirects is not the class OPENER was built with")
for name, module in sorted(sys.modules.items()):
    held = getattr(module, "OPENER", opener) if name.startswith("judge_audit") else opener
    if held is not opener:
        failures.append(f"{name}.OPENER is not secrets' opener")
if [type(h) for h in opener.handlers] != before["handlers"]:
    failures.append("OPENER's handlers changed")
if list(opener.addheaders) != before["addheaders"]:
    failures.append("OPENER's headers changed")
if dict(vars(refusal)) != before["refusal"]:
    failures.append("_RefuseRedirects changed")
base = {k: v for k, v in vars(urllib.request.HTTPRedirectHandler).items()
        if k.startswith(("http_error_", "redirect_request"))}
if base != before["base"]:
    failures.append("urllib.request.HTTPRedirectHandler changed")

followed = []

class Redirects(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/redirect/"):
            self.send_response(int(self.path.rsplit("/", 1)[1]))
            self.send_header("Location", f"http://127.0.0.1:{port}/target")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            followed.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Redirects)
port = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()
for code in (301, 302, 303, 307, 308):
    # a code this Python's redirect handler does not follow (308 before 3.11) is an
    # HTTPError, never followed; the target count below still checks it
    follows = hasattr(urllib.request.HTTPRedirectHandler, f"http_error_{code}")
    try:
        secrets.OPENER.open(f"http://127.0.0.1:{port}/redirect/{code}", timeout=10).close()
        failures.append(f"a {code} was followed")
    except secrets.RedirectRefused:
        pass
    except urllib.error.HTTPError as e:
        if follows or e.code != code:
            failures.append(f"a {code} raised HTTPError {e.code}, not RedirectRefused")
    except Exception as e:
        failures.append(f"a {code} raised {type(e).__name__}, not RedirectRefused")
server.shutdown()
if followed:
    failures.append(f"the redirect target was requested {len(followed)} time(s)")

print(json.dumps({"modules": modules, "failures": failures}))
sys.exit(1 if failures else 0)
'''


def _check(tmp_path: Path, *planted: str) -> tuple[int, dict]:
    """Run CHECK in a fresh process, each planted source as a module imported last."""
    names = []
    for i, source in enumerate(planted):
        (tmp_path / f"planted_{i}.py").write_text(source, encoding="utf-8")
        names.append(f"planted_{i}")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        p for p in (str(tmp_path), os.environ.get("PYTHONPATH", "")) if p)}
    r = subprocess.run([sys.executable, "-c", CHECK, *names], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.stdout.strip(), r.stderr
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def test_every_module_imported_and_the_opener_still_refuses_redirects(tmp_path):
    code, out = _check(tmp_path)
    assert out["failures"] == [] and code == 0
    # every module of the package was imported, the namespace packages' too
    assert "judge_audit.judges.secrets" in out["modules"]
    assert "judge_audit.judges.llm" in out["modules"]
    assert "judge_audit.metrics.selective" in out["modules"]
    assert "judge_audit.mcp_server" in out["modules"]
    src = Path(__file__).resolve().parent.parent / "src" / "judge_audit"
    files = [p for p in src.rglob("*.py") if p.name != "__init__.py"
             and "node_modules" not in p.parts]
    assert len(out["modules"]) == len(files)


# Hidden forms the static scan does not see, each planted in a module imported after the
# package: each one must fail the check.
HIDDEN = {
    "vars": ("from judge_audit.judges import secrets\n"
             "import urllib.request\n"
             "vars(secrets)['_Refuse' + 'Redirects'].redirect_request = "
             "urllib.request.HTTPRedirectHandler.redirect_request\n",
             "_RefuseRedirects changed"),
    "sys.modules": ("import sys, urllib.request\n"
                    "sys.modules['judge_audit.judges.secrets'].__dict__['OPE' + 'NER'] = "
                    "getattr(urllib.request, 'build_' + 'opener')()\n",
                    "secrets.OPENER is not the opener it was built as"),
    "attrgetter": ("import operator\nfrom judge_audit.judges import secrets\n"
                   "operator.attrgetter('OPE' + 'NER.addheaders')(secrets).append("
                   "('X-Planted', '1'))\n",
                   "OPENER's headers changed"),
    "getattr": ("import urllib.request\nfrom judge_audit.judges import secrets\n"
                "getattr(secrets, 'OPE' + 'NER').add_handler("
                "getattr(urllib.request, 'HTTPRedirect' + 'Handler')())\n",
                "OPENER's handlers changed"),
    "base class": ("import urllib.request\n"
                   "base = getattr(urllib.request, 'HTTPRedirect' + 'Handler')\n"
                   "def follow(self, req, fp, code, msg, headers):\n"
                   "    return self.parent.open(headers['Location'])\n"
                   "for code in (301, 302, 303, 307, 308):\n"
                   "    setattr(base, f'http_error_{code}', follow)\n",
                   "urllib.request.HTTPRedirectHandler changed"),
}


@pytest.mark.parametrize("form", sorted(HIDDEN))
def test_a_hidden_change_to_the_opener_fails_the_check(tmp_path, form):
    source, says = HIDDEN[form]
    code, out = _check(tmp_path, source)
    assert code == 1 and says in out["failures"], out["failures"]


def test_a_followed_redirect_fails_the_check_even_when_nothing_else_moved(tmp_path):
    """The behaviour is checked on its own: a patch to the handler *instance* inside the
    opener leaves every class and list as it was, and only the local redirect shows it."""
    source = ("from judge_audit.judges import secrets\n"
              "import urllib.request\n"
              "h = next(h for h in getattr(secrets, 'OPE' + 'NER').handlers\n"
              "         if isinstance(h, urllib.request.HTTPRedirectHandler))\n"
              "h.redirect_request = lambda *a: urllib.request.HTTPRedirectHandler"
              ".redirect_request(h, *a)\n")
    code, out = _check(tmp_path, source)
    assert code == 1
    assert "a 302 was followed" in out["failures"]
    assert not any("changed" in f or " is not " in f for f in out["failures"])
