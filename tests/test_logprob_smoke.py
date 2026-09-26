"""scripts/logprob_smoke.py — network mocked; the key never reaches the output."""
from __future__ import annotations

import importlib.util
import io
import json
import math
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("logprob_smoke",
                                              ROOT / "scripts" / "logprob_smoke.py")
smoke = importlib.util.module_from_spec(spec)
sys.modules["logprob_smoke"] = smoke
spec.loader.exec_module(smoke)

KEY = "sk-test-SECRET-1234567"


def _content(tokens):
    return {"choices": [{"message": {"content": "".join(t for t, _ in tokens)},
                         "logprobs": {"content": [
                             {"token": t, "logprob": lp,
                              "top_logprobs": [{"token": t, "logprob": lp},
                                               {"token": "transfer", "logprob": math.log(0.07)}]}
                             for t, lp in tokens]}}], "model": "some-model"}


WITH = _content([("card", math.log(0.9))])
WITHOUT = {"model": "some-model", "choices": [{"message": {"content": "card"}}]}


def test_a_numeric_logprob_for_the_answer_is_a_yes():
    status, f = smoke.summarize(WITH, 5)
    assert status == smoke.YES and f["logprobs_returned"] and f["answer_is_expected"]
    assert f["answer_token"] == "card" and f["answer_token_probability"] == 0.9
    assert f["top_logprobs_returned"] == 2 and f["alternatives"]["transfer"] == 0.07


def test_the_answer_token_skips_markup_and_reasoning_tags():
    status, f = smoke.summarize(_content([("<think>", -0.001), ("c", -0.3),
                                          ("ould be", -0.2), ("</think>", -0.01),
                                          ("\n", -0.01), ("**", -0.01),
                                          ("card", math.log(0.6)), ("**", -0.01)]), 5)
    assert status == smoke.YES and f["answer_token"] == "card"
    assert f["answer_token_probability"] == pytest.approx(0.6)


def test_an_unexpected_answer_reports_no_answer_token():
    status, f = smoke.summarize(_content([("transfer", -0.2)]), 5)
    assert status == smoke.YES and f["answer_token"] is None and not f["answer_is_expected"]


@pytest.mark.parametrize("resp, status", [
    (WITHOUT, 1),                                                    # ignored or unsupported
    ({"choices": [{"message": {"content": "card"},
                   "logprobs": {"content": [{"token": "card", "logprob": None}]}}]}, 1),
    ({"choices": [{"message": {"content": "card"},
                   "logprobs": {"tokens": ["card"], "token_logprobs": [-0.1]}}]}, 3),
    ({"error": {"message": "bad model"}}, 2),
    (["not", "a", "completion"], 2),
])
def test_exit_status_for_each_kind_of_reply(resp, status):
    assert smoke.summarize(resp, 5)[0] == status


def test_the_routing_object_cannot_override_the_request_and_is_checked():
    body = smoke.build_request("m", {"provider": {"order": ["x"]}}, 5)
    assert body["logprobs"] is True and body["model"] == "m"
    assert body["provider"] == {"order": ["x"]}
    assert smoke.main(["--model", "m", "--base-url", "http://x.test",
                       "--extra-body", '{"logprobs": false}']) == smoke.FAILED


def _run(monkeypatch, capsys, tmp_path, resp=None, error=None):
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("LLM_BASE_URL", "https://gateway.test/api/v1/")
    monkeypatch.delenv("LLM_EXTRA_BODY", raising=False)

    def fake_post(base_url, api_key, body, timeout=60.0):
        assert api_key == KEY
        if error:
            raise error
        return resp

    monkeypatch.setattr(smoke, "post", fake_post)
    out = tmp_path / "finding.json"
    code = smoke.main(["--model", "m", "--json", str(out)])
    captured = capsys.readouterr()
    written = out.read_text() if out.exists() else ""
    assert KEY not in captured.out + captured.err + written
    return code, captured, written


def test_exit_status_and_json(monkeypatch, capsys, tmp_path):
    code, _, written = _run(monkeypatch, capsys, tmp_path, resp=WITH)
    assert code == 0 and json.loads(written)["base_url"] == "https://gateway.test/api/v1"
    assert _run(monkeypatch, capsys, tmp_path, resp=WITHOUT)[0] == 1


def test_an_error_body_that_echoes_the_key_is_redacted(monkeypatch, capsys, tmp_path):
    body = io.BytesIO(f"Unauthorized. Received headers: Authorization: Bearer {KEY}".encode())
    err = urllib.error.HTTPError("https://gateway.test", 401, "Unauthorized", {}, body)
    code, captured, _ = _run(monkeypatch, capsys, tmp_path, error=err)
    assert code == 2 and "[redacted]" in captured.err


def test_a_reply_field_that_echoes_the_key_is_redacted(monkeypatch, capsys, tmp_path):
    echoed = dict(WITH, model=f"Bearer {KEY}")
    code, captured, written = _run(monkeypatch, capsys, tmp_path, resp=echoed)
    assert code == 0 and "[redacted]" in written


def test_a_failed_call_exits_2(monkeypatch, capsys, tmp_path):
    code, captured, _ = _run(monkeypatch, capsys, tmp_path,
                             error=urllib.error.URLError("unreachable"))
    assert code == 2 and "request failed" in captured.err
