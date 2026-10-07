"""A judge that cannot be reached, or refuses the request, ends `run` and `check` with
exit 2 and one clear line: never a traceback, never exit 1 (drift), never a path. The
checkpointed driver keeps its rows so a rerun resumes. Network: a local HTTP server or a
port that refuses; no outside host is called."""
from __future__ import annotations

import http.server
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from judge_audit import cli

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"
SECRET = "sk-test-not-a-real-key-0123456789"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server():
    """A local server that answers every POST with `status` (a JSON error body)."""
    state = {"status": 500, "hits": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            state["hits"] += 1
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.dumps({"error": {"message": f"status {state['status']}"}}).encode()
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_address[1]}"
    yield state
    httpd.shutdown()


# Each family, pointed at `base` (a URL with no path); endpoint overrides are env-only.
FAMILIES = {
    "jev": lambda base: {"JEV_BACKEND": "typesafe", "TYPESAFE_API_KEY": SECRET,
                         "JEV_ENDPOINT": f"{base}/v1/systemone", "JEV_MIN_INTERVAL_S": "0"},
    "llm": lambda base: {"LLM_PROVIDER": "openai-compatible", "LLM_BASE_URL": f"{base}/v1",
                         "LLM_MODEL": "gpt-5-mini", "LLM_API_KEY": SECRET},
    "openai-decisions": lambda base: {"OPENAI_API_KEY": SECRET,
                                      "DECISIONS_ENDPOINT": f"{base}/v1/decisions"},
    "clef-hosted": lambda base: {"CLOUDFLARE_API_TOKEN": SECRET,
                                 "CLOUDFLARE_ACCOUNT_ID": "acct0123456789abcdef",
                                 "CLEF_HOSTED_ENDPOINT": f"{base}/ai/run/{{model_id}}"},
}


def _clean(text: str) -> list[str]:
    """What must never be in what a failed run prints."""
    bad = []
    if "Traceback" in text or 'File "' in text:
        bad.append("traceback")
    for s in (str(Path.home()), str(ROOT), sys.prefix, SECRET, "acct0123456789abcdef"):
        if s and s in text:
            bad.append(s)
    return bad


def _run_in_process(monkeypatch, capsys, judge: str, env: dict, cmd: str = "run",
                    tmp_path: Path | None = None) -> tuple[int, str]:
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import time as _time
    monkeypatch.setattr(_time, "sleep", lambda s: None)        # retries run instantly
    out = tmp_path or Path(".")
    argv = [cmd, str(LABELS), "--judge", judge, "--no-ci",
            "--json", str(out / "r.json")]
    if cmd == "run":
        argv += ["--out", str(out / "r.md"), "--judgments", str(out / "j.jsonl")]
    else:
        argv += ["--baseline", str(ROOT / "docs" / "audit-jev-real.json")]
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    return int(e.value.code or 0), capsys.readouterr().err


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("status", [401, 403, 500])
@pytest.mark.parametrize("cmd", ["run", "check"])
def test_an_http_error_is_exit_2_with_one_clean_line(server, monkeypatch, capsys, tmp_path,
                                                     family, status, cmd):
    server["status"] = status
    code, err = _run_in_process(monkeypatch, capsys, family, FAMILIES[family](server["url"]),
                                cmd, tmp_path)
    assert code == 2, err
    assert "judge request failed:" in err, err
    assert str(status) in err, err
    assert not _clean(err), _clean(err)


@pytest.mark.parametrize("family", sorted(FAMILIES))
@pytest.mark.parametrize("where", ["refused", "dns"])
def test_an_unreachable_server_is_exit_2_with_one_clean_line(monkeypatch, capsys, tmp_path,
                                                            family, where):
    base = (f"http://127.0.0.1:{_free_port()}" if where == "refused"
            else "http://judge-audit-test.invalid")
    code, err = _run_in_process(monkeypatch, capsys, family, FAMILIES[family](base),
                                "run", tmp_path)
    assert code == 2 and "judge request failed:" in err, err
    assert not _clean(err), _clean(err)


def test_a_local_decision_model_that_fails_is_exit_2(monkeypatch, capsys, tmp_path):
    """The local decision models (systemone) share the same exit."""
    from judge_audit.judges import systemone

    def boom(self, state, questions):
        raise RuntimeError(f"CUDA out of memory in {Path.home()}/.cache/model")
    monkeypatch.setattr(systemone.LocalSystemOneJudge, "decide", boom)
    monkeypatch.setattr(cli, "_judge", lambda name, rows: (
        systemone.LocalSystemOneJudge.__new__(systemone.LocalSystemOneJudge), ""))
    with pytest.raises(SystemExit) as e:
        cli.main(["run", str(LABELS), "--judge", "decision2", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                  "--judgments", str(tmp_path / "j.jsonl")])
    err = capsys.readouterr().err
    assert e.value.code == 2 and "judge request failed:" in err and "out of memory" in err
    assert not _clean(err), _clean(err)


def test_a_real_process_shows_no_traceback(server, tmp_path):
    """The same through a real interpreter, where an uncaught error would print one."""
    import os
    server["status"] = 401
    env = {**os.environ, **FAMILIES["openai-decisions"](server["url"])}
    out = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(LABELS),
                          "--judge", "openai-decisions", "--no-ci",
                          "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                          "--judgments", str(tmp_path / "j.jsonl")],
                         capture_output=True, text=True, env=env, cwd=tmp_path)
    assert out.returncode == 2, out.stderr
    assert "judge request failed:" in out.stderr and not _clean(out.stderr), out.stderr


def test_the_checkpointed_driver_keeps_its_rows_and_resumes(server, tmp_path):
    """Rows done before the failure stay in the checkpoint; the rerun starts after them."""
    import os
    ckpt = tmp_path / "x.ckpt.jsonl"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"),
           **FAMILIES["openai-decisions"](server["url"])}
    script = [sys.executable, str(ROOT / "scripts" / "audit_resumable.py"), str(LABELS),
              "--judge", "openai-decisions", "--checkpoint", str(ckpt),
              "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")]
    # A server that answers the first 3 rows, then refuses.
    good = {"answers": [{"type": "choice", "name": "category", "choice": "spam",
                         "confidence": 0.9, "probabilities": [
                             {"value": "spam", "probability": 0.9},
                             {"value": "other", "probability": 0.1}]}]}
    state = {"n": 0}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state["n"] += 1
            ok = state["n"] <= 3
            body = json.dumps(good if ok else {"error": "no"}).encode()
            self.send_response(200 if ok else 401)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    env.update(FAMILIES["openai-decisions"](f"http://127.0.0.1:{httpd.server_address[1]}"))
    try:
        first = subprocess.run(script, capture_output=True, text=True, env=env, cwd=tmp_path)
        assert first.returncode == 2, first.stderr
        assert "judge request failed:" in first.stderr and not _clean(first.stderr)
        kept = [json.loads(line) for line in ckpt.read_text(encoding="utf-8").splitlines()]
        assert [r["idx"] for r in kept if r["idx"] >= 0] == [0, 1, 2]
        assert "3 rows" in first.stderr and "resume" in first.stderr
        state["n"] = -10_000                    # the server answers again
        second = subprocess.run(script, capture_output=True, text=True, env=env,
                                cwd=tmp_path)
        assert "3/" in second.stdout                     # "checkpoint: 3/200 rows already done"
    finally:
        httpd.shutdown()


def test_judge_audit_debug_shows_the_traceback_for_a_maintainer(server, monkeypatch, capsys,
                                                                tmp_path):
    server["status"] = 401
    monkeypatch.setenv("JUDGE_AUDIT_DEBUG", "1")
    for k, v in FAMILIES["openai-decisions"](server["url"]).items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError):
        cli.main(["run", str(LABELS), "--judge", "openai-decisions", "--no-ci",
                  "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json"),
                  "--judgments", str(tmp_path / "j.jsonl")])
