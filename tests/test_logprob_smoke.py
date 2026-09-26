"""scripts/logprob_smoke.py — network mocked; the key never reaches the output."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("logprob_smoke",
                                              ROOT / "scripts" / "logprob_smoke.py")
smoke = importlib.util.module_from_spec(spec)
sys.modules["logprob_smoke"] = smoke
spec.loader.exec_module(smoke)

WITH = {"model": "gpt-4.1-mini-2025-04-14", "provider": "OpenAI",
        "choices": [{"message": {"content": "card"},
                     "logprobs": {"content": [
                         {"token": "card", "logprob": math.log(0.9),
                          "top_logprobs": [{"token": "card", "logprob": math.log(0.9)},
                                           {"token": "transfer", "logprob": math.log(0.07)}]}]}}]}
WITHOUT = {"model": "some-model", "choices": [{"message": {"content": "card"}}]}


def test_summary_reads_the_first_answer_token():
    f = smoke.summarize(WITH, 5)
    assert f["logprobs_returned"] and f["answer_is_expected"]
    assert f["upstream_provider"] == "OpenAI" and f["served_model"] == "gpt-4.1-mini-2025-04-14"
    assert f["first_token"] == "card" and f["first_token_probability"] == 0.9
    assert f["top_logprobs_returned"] == 2 and f["alternatives"]["transfer"] == 0.07


def test_summary_of_an_endpoint_that_ignores_the_request():
    f = smoke.summarize(WITHOUT, 5)
    assert not f["logprobs_returned"] and "first_token" not in f


def test_request_merges_the_extra_body_and_asks_for_logprobs():
    body = smoke.build_request("m", {"provider": {"order": ["openai"]}}, 5)
    assert body["logprobs"] is True and body["top_logprobs"] == 5 and body["temperature"] == 0
    assert body["max_tokens"] >= 16 and body["provider"] == {"order": ["openai"]}


def _run(monkeypatch, capsys, tmp_path, resp=None, error=None):
    monkeypatch.setenv("LLM_API_KEY", "sk-test-SECRET-123")
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.test/api/v1/")

    def fake_post(base_url, api_key, body, timeout=60.0):
        assert api_key == "sk-test-SECRET-123" and base_url.endswith("/api/v1/")
        if error:
            raise error
        return resp

    monkeypatch.setattr(smoke, "post", fake_post)
    out = tmp_path / "finding.json"
    code = smoke.main(["--model", "m", "--json", str(out)])
    captured = capsys.readouterr()
    written = out.read_text() if out.exists() else ""
    assert "SECRET" not in captured.out + captured.err + written
    return code, captured, written


def test_exit_status_says_whether_logprobs_came_back(monkeypatch, capsys, tmp_path):
    code, _, written = _run(monkeypatch, capsys, tmp_path, resp=WITH)
    assert code == 0 and json.loads(written)["base_url"] == "https://gateway.test/api/v1"
    code, _, _ = _run(monkeypatch, capsys, tmp_path, resp=WITHOUT)
    assert code == 1


def test_a_failed_call_exits_2(monkeypatch, capsys, tmp_path):
    err = urllib.error.URLError("unreachable")
    code, captured, _ = _run(monkeypatch, capsys, tmp_path, error=err)
    assert code == 2 and "request failed" in captured.err
