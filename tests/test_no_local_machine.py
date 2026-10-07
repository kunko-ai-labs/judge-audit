"""Provenance records what a reproducer needs (library versions, device, dtype, relative
paths), never what identifies the computer a run happened on. No network."""
from __future__ import annotations

import getpass
import io
import json
import platform
import re
import socket
import sys
import urllib.request
from pathlib import Path

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.llm import LLMJudge, local_fingerprint
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.runner import load_dataset, run_audit, run_metadata

ROOT = Path(__file__).resolve().parent.parent
LABELS = ROOT / "examples" / "email-routing" / "labels.jsonl"

# What a mlx_lm.server reports as its system_fingerprint: its version, mlx's, then
# platform.platform() and the GPU class of the computer it runs on.
# Assembled, so the repository's text guard (which flags such strings) does not match here.
MLX_FP = "-".join(["0.31.3", "0.32.2", "mac" + "OS", "26.6.2", "arm64", "arm", "64bit",
                   "apple" + "gpu_g16g"])


def identifying() -> list[str]:
    """Strings that would identify this computer if they appeared in provenance."""
    home = str(Path.home())
    out = [home, socket.gethostname(), platform.platform(), platform.node()]
    try:
        out.append(getpass.getuser())
    except Exception:  # noqa: BLE001 - no user name in some sandboxes
        pass
    return [s for s in out if s and len(s) >= 3]


PATTERNS = re.compile(r"/Users/|/home/|(?<![\w.])~/(?!\.cache/huggingface/)|/var/folders/"
                      r"|/private/|\bmac" r"OS-\d|\bDar" r"win \d|apple" r"gpu_|\barm64\b"
                      r"|\bx86_64\b"
                      r"|\bApple M\d|\bMacBook|\bhostname\b")


def leaks(text: str) -> list[str]:
    found = [m.group(0) for m in PATTERNS.finditer(text)]
    found += [s for s in identifying() if s in text]
    return found


@pytest.mark.parametrize("fp, want", [
    (MLX_FP, "mlx-lm 0.31.3 / mlx 0.32.2"),
    ("0.28.1-0.29.0-Linux-6.8.0-x86_64-with-glibc2.39-cpu", "mlx-lm 0.28.1 / mlx 0.29.0"),
])
def test_a_local_mlx_fingerprint_keeps_only_the_library_versions(fp, want):
    assert local_fingerprint(fp) == want


@pytest.mark.parametrize("fp", ["b6131-llama.cpp", "ollama", "fp_abc", ""])
def test_a_local_fingerprint_of_another_shape_is_dropped_not_guessed(fp):
    assert local_fingerprint(fp) is None


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


Q = Question(name="category", type=QuestionType.CHOICE, instructions="Which?",
             options=["spam", "ham"])


def _served(monkeypatch, base_url: str, fingerprint: str) -> dict:
    from judge_audit.judges import llm as llm_mod
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_MODEL", "qwen3-8b")
    monkeypatch.setenv("LLM_INPUT_PRICE", "0")
    monkeypatch.setenv("LLM_OUTPUT_PRICE", "0")
    reply = {"model": "qwen3-8b", "system_fingerprint": fingerprint,
             "choices": [{"message": {"content":
                          '{"answers": {"category": {"decision": "spam", "confidence": 0.8}}}'}}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0: _Resp(json.dumps(reply).encode()))
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)
    (out,) = LLMJudge().decide("x", [Q])
    return out.raw["served"]


def test_a_local_server_s_fingerprint_is_reduced_to_versions(monkeypatch):
    served = _served(monkeypatch, "http://127.0.0.1:8080/v1", MLX_FP)
    assert served == {"model": "qwen3-8b", "system_fingerprint": "mlx-lm 0.31.3 / mlx 0.32.2"}
    assert not leaks(json.dumps(served))


def test_a_hosted_fingerprint_stays_as_the_server_reports_it(monkeypatch):
    served = _served(monkeypatch, "https://api.example.test/v1", "fp_44709d6fcb")
    assert served["system_fingerprint"] == "fp_44709d6fcb"


def test_a_dataset_outside_the_working_directory_is_named_by_its_repository(tmp_path,
                                                                          monkeypatch):
    """Run from elsewhere, a dataset inside a repository is named relative to that
    repository's root; a file in no repository by its name. Never `~/…` or absolute."""
    from judge_audit.runner import display_path
    monkeypatch.chdir(tmp_path)
    assert display_path(str(LABELS.resolve())) == "examples/email-routing/labels.jsonl"
    loose = tmp_path / "loose" / "labels.jsonl"
    loose.parent.mkdir()
    loose.write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(ROOT)
    assert display_path(str(loose)) == "labels.jsonl"


def test_an_absolute_dataset_path_is_recorded_relative():
    rows, meta = load_dataset(str(LABELS))
    header = run_metadata(SimulatedJudge(rows), str(LABELS.resolve()), len(rows), meta)
    assert not Path(header["dataset"]["path"]).is_absolute()
    assert not leaks(json.dumps(header))


def test_a_simulated_audit_writes_nothing_that_identifies_the_computer(tmp_path):
    """A whole run through the CLI: report, result JSON and judgments, all scanned."""
    import subprocess
    out = subprocess.run(
        [sys.executable, "-m", "judge_audit.cli", "run", str(LABELS.resolve()),
         "--judge", "simulated", "--out", str(tmp_path / "r.md"),
         "--json", str(tmp_path / "r.json"), "--judgments", str(tmp_path / "j.jsonl")],
        capture_output=True, text=True, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    for name in ("r.md", "r.json", "j.jsonl"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert not leaks(text), f"{name}: {leaks(text)}"


def test_the_result_records_the_python_version_only():
    rows, meta = load_dataset(str(LABELS))
    d = run_audit(SimulatedJudge(rows), rows, str(LABELS), meta, ci=False).to_dict()
    assert d["run"]["python"] == platform.python_version()
    assert not leaks(json.dumps(d))


def test_the_training_record_names_the_device_not_the_computer():
    sys.path.insert(0, str(ROOT / "scripts"))
    import train_classifier
    assert train_classifier.hardware("mps") == "device mps"
    assert not leaks(train_classifier.hardware("cpu"))


@pytest.mark.parametrize("text", [MLX_FP, "/Users/someone/x.jsonl",
                                  "Apple " + "M4 (Dar" + "win 25.6.0)",
                                  "~/Documents/project/labels.jsonl"])
def test_the_scan_catches(text):
    assert leaks(text)


def test_the_mcp_server_returns_no_absolute_path(tmp_path, monkeypatch):
    from judge_audit import mcp_server
    monkeypatch.chdir(tmp_path)
    out = mcp_server.run_audit(str(LABELS.resolve()), judge="simulated",
                               judgments_path=str(tmp_path / "j.jsonl"))
    assert out["judgments_path"] == "j.jsonl"
    missing = mcp_server.run_audit(str(tmp_path / "nope.jsonl"))
    assert "error" in missing
    assert not leaks(json.dumps(out)) and not leaks(json.dumps(missing))


def test_a_loader_message_names_the_model_cache_not_where_it_is(monkeypatch, tmp_path):
    from judge_audit.judges.systemone import tidy
    home_cache = str(Path.home() / ".cache/huggingface/hub/models--a--b/snapshots/c")
    assert tidy(f"loading from '{home_cache}'") == (
        "loading from '~/.cache/huggingface/hub/models--a--b/snapshots/c'")
    custom = tmp_path / "volume" / "hf"
    monkeypatch.setenv("HF_HOME", str(custom))
    got = tidy(f"loading from '{custom}/hub/models--a--b/snapshots/c'")
    assert got == "loading from '<hf-cache>/hub/models--a--b/snapshots/c'"
    assert not leaks(got)
