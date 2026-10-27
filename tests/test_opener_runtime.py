"""After every module of the package is imported, OPENER still refuses redirects (#210).

The static scan in `test_network_guard.py` flags every named use of `OPENER` and
`_RefuseRedirects`, but not the forms it lists as hidden (`vars()`, `__dict__`,
`sys.modules`, `operator.attrgetter`, a `getattr` with a computed name, a change to
`urllib.request.HTTPRedirectHandler`). Those would be caught only if some redirect test
happened to run after the module that hides them. Here a fresh Python process first records
the reference: the redirect methods of `urllib.request.HTTPRedirectHandler`, and the opener
that `secrets.py` builds when it is loaded on its own, by path, before anything of the
package is imported. Then it imports every module of the package and the scripts that send a
keyed request (`scripts/logprob_smoke.py`), and compares the package's opener with that
reference: what it is, what it is built from, and what it does with a redirect from a local
server. A change made by any module, including the ones `judge_audit/__init__` imports first,
differs from the reference. The planted changes prove that each hidden form fails the check,
late (a module imported after the package) and early (appended to `certificate.py`, which
the package's `__init__` loads).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [ROOT / "scripts" / "logprob_smoke.py"]   # outside the package, keyed requests

# Run in a fresh process: `python -c CHECK [planted module ...]`, with the scripts to load in
# JUDGE_AUDIT_CHECK_SCRIPTS. Prints {"modules", "scripts", "failures"} as JSON and exits 1
# when a check fails.
CHECK = r'''
import http.server, importlib, importlib.util, json, os, sys, threading
import urllib.error, urllib.request
from pathlib import Path

# 1. The reference, before anything of the package is imported.
def redirect_methods():
    return {k: v for k, v in vars(urllib.request.HTTPRedirectHandler).items()
            if k.startswith(("http_error_", "redirect_request"))}

base = redirect_methods()
package = Path(importlib.util.find_spec("judge_audit").origin).parent
spec = importlib.util.spec_from_file_location("pristine_secrets",
                                              package / "judges" / "secrets.py")
pristine = importlib.util.module_from_spec(spec)
sys.modules["pristine_secrets"] = pristine          # dataclasses look the module up
spec.loader.exec_module(pristine)

def handlers(opener, module):
    return [(module if type(h).__module__ in ("pristine_secrets", "judge_audit.judges.secrets")
             else type(h).__module__, type(h).__qualname__) for h in opener.handlers]

def shape(cls):
    """A class's own attributes, each function by its code: equal for two loads of one file."""
    out = {}
    for k, v in vars(cls).items():
        if k in ("__module__", "__dict__", "__weakref__"):
            continue
        code = getattr(v, "__code__", None)
        out[k] = (code.co_code, code.co_consts, code.co_names) if code else repr(v)
    return out

# 2. Every module of the package, the scripts that send a keyed request, the planted ones.
import judge_audit
from judge_audit.judges import secrets

modules = sorted("judge_audit." + ".".join(p.relative_to(package).with_suffix("").parts)
                 for p in package.rglob("*.py")
                 if p.name != "__init__.py" and "node_modules" not in p.parts)
for name in modules:
    importlib.import_module(name)
scripts = [p for p in os.environ.get("JUDGE_AUDIT_CHECK_SCRIPTS", "").split(os.pathsep) if p]
for path in scripts:
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[Path(path).stem] = module
    spec.loader.exec_module(module)
for name in sys.argv[1:]:
    importlib.import_module(name)

# 3. The package's opener against the reference.
failures = []
opener = secrets.OPENER
held = [name for name, module in sorted(sys.modules.items())
        if (name.startswith("judge_audit") or name in {Path(p).stem for p in scripts})
        and getattr(module, "OPENER", opener) is not opener]
failures += [f"{name}.OPENER is not secrets' opener" for name in held]
if handlers(opener, "secrets") != handlers(pristine.OPENER, "secrets"):
    failures.append("OPENER's handlers differ from what secrets.py builds")
if list(opener.addheaders) != list(pristine.OPENER.addheaders):
    failures.append("OPENER's headers differ from what secrets.py builds")
if shape(secrets._RefuseRedirects) != shape(pristine._RefuseRedirects):
    failures.append("_RefuseRedirects differs from secrets.py's own")
def instance(opener, cls):
    """The redirect handler's own attributes but its `parent` (the opener it belongs to)."""
    h = next((h for h in opener.handlers if type(h) is cls), None)
    return None if h is None else {k: repr(v) for k, v in vars(h).items() if k != "parent"}

if instance(opener, secrets._RefuseRedirects) != instance(pristine.OPENER,
                                                          pristine._RefuseRedirects):
    failures.append("the redirect handler inside OPENER was changed")
if redirect_methods() != base:
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

print(json.dumps({"package": str(package), "modules": modules, "scripts": scripts,
                  "failures": failures}))
sys.exit(1 if failures else 0)
'''


def _check(tmp_path: Path, *planted: str, package: Path | None = None) -> tuple[int, dict]:
    """Run CHECK in a fresh process, each planted source as a module imported last; with
    `package`, the directory holding a copy of `judge_audit` to import instead."""
    names = []
    for i, source in enumerate(planted):
        (tmp_path / f"planted_{i}.py").write_text(source, encoding="utf-8")
        names.append(f"planted_{i}")
    first = [str(package)] if package else []
    env = {**os.environ,
           "PYTHONPATH": os.pathsep.join(
               p for p in (*first, str(tmp_path), os.environ.get("PYTHONPATH", "")) if p),
           "JUDGE_AUDIT_CHECK_SCRIPTS": os.pathsep.join(str(p) for p in SCRIPTS)}
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
    src = ROOT / "src" / "judge_audit"
    files = [p for p in src.rglob("*.py") if p.name != "__init__.py"
             and "node_modules" not in p.parts]
    assert len(out["modules"]) == len(files)
    # and the script outside the package that sends a keyed request
    assert [Path(p).name for p in out["scripts"]] == ["logprob_smoke.py"]


# Hidden forms the static scan does not see, each planted in a module imported after the
# package: each one must fail the check.
HIDDEN = {
    "vars": ("from judge_audit.judges import secrets\n"
             "import urllib.request\n"
             "vars(secrets)['_Refuse' + 'Redirects'].redirect_request = "
             "urllib.request.HTTPRedirectHandler.redirect_request\n",
             "_RefuseRedirects differs from secrets.py's own"),
    "sys.modules": ("import sys, urllib.request\n"
                    "sys.modules['judge_audit.judges.secrets'].__dict__['OPE' + 'NER'] = "
                    "getattr(urllib.request, 'build_' + 'opener')()\n",
                    "OPENER's handlers differ from what secrets.py builds"),
    "attrgetter": ("import operator\nfrom judge_audit.judges import secrets\n"
                   "operator.attrgetter('OPE' + 'NER.addheaders')(secrets).append("
                   "('X-Planted', '1'))\n",
                   "OPENER's headers differ from what secrets.py builds"),
    "getattr": ("import urllib.request\nfrom judge_audit.judges import secrets\n"
                "getattr(secrets, 'OPE' + 'NER').add_handler("
                "getattr(urllib.request, 'HTTPRedirect' + 'Handler')())\n",
                "OPENER's handlers differ from what secrets.py builds"),
    "base class": ("import urllib.request\n"
                   "base = getattr(urllib.request, 'HTTPRedirect' + 'Handler')\n"
                   "def follow(self, req, fp, code, msg, headers):\n"
                   "    return self.parent.open(headers['Location'])\n"
                   "for code in (301, 302, 303, 307, 308):\n"
                   "    setattr(base, f'http_error_{code}', follow)\n",
                   "urllib.request.HTTPRedirectHandler changed"),
    "handler instance": ("from judge_audit.judges import secrets\n"
                         "import urllib.request\n"
                         "h = next(h for h in getattr(secrets, 'OPE' + 'NER').handlers\n"
                         "         if isinstance(h, urllib.request.HTTPRedirectHandler))\n"
                         "h.redirect_request = lambda *a: urllib.request.HTTPRedirectHandler"
                         ".redirect_request(h, *a)\n",
                         "the redirect handler inside OPENER was changed"),
}


@pytest.mark.parametrize("form", sorted(HIDDEN))
def test_a_hidden_change_to_the_opener_fails_the_check(tmp_path, form):
    source, says = HIDDEN[form]
    code, out = _check(tmp_path, source)
    assert code == 1 and says in out["failures"], out["failures"]


def test_a_followed_redirect_fails_the_check_on_its_own(tmp_path):
    """The behaviour is checked too, not only the identities: the patched handler instance
    follows the local redirect, and the probe says so."""
    code, out = _check(tmp_path, HIDDEN["handler instance"][0])
    assert code == 1 and "a 302 was followed" in out["failures"], out["failures"]


# The same hidden forms, made by a module that `judge_audit/__init__` imports before the rest
# (`certificate.py`, through `runner`): a reference taken after `import judge_audit` would
# already include them (#211 review).
EARLY = {
    "headers": ("getattr(vars(_s)['OPE' + 'NER'], 'add' + 'headers').append(('X-Planted', '1'))",
                "OPENER's headers differ from what secrets.py builds"),
    "proxy": ("getattr(vars(_s)['OPE' + 'NER'], 'add_' + 'handler')("
              "getattr(_u, 'Proxy' + 'Handler')({'https': 'http://127.0.0.1:9'}))",
              "OPENER's handlers differ from what secrets.py builds"),
    "refusal removed": ("delattr(vars(_s)['_Refuse' + 'Redirects'], 'redirect_request')",
                        "_RefuseRedirects differs from secrets.py's own"),
}


@pytest.mark.parametrize("form", sorted(EARLY))
def test_a_hidden_change_made_while_the_package_loads_fails_the_check(tmp_path, form):
    line, says = EARLY[form]
    copy = tmp_path / "pkg"
    shutil.copytree(ROOT / "src" / "judge_audit", copy / "judge_audit",
                    ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    with (copy / "judge_audit" / "certificate.py").open("a", encoding="utf-8") as f:
        f.write("\nimport importlib as _i, urllib.request as _u\n"
                "_s = _i.import_module('judge_audit.judges.' + 'secrets')\n" + line + "\n")
    code, out = _check(tmp_path, package=copy)
    assert Path(out["package"]) == copy / "judge_audit"    # the planted copy was imported
    assert code == 1 and says in out["failures"], out["failures"]
