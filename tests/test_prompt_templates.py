"""Prompt templates (US-005-007, #92): a second wording for the `llm` and `logprob` judges.

`v1` is the prompt every published run used, byte for byte; `v2` rewords it to test prompt
sensitivity with the same task, options, output contract, decision rule and confidence.
Network and model mocked.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

from judge_audit.judges import llm as llm_mod
from judge_audit.judges import logprob as lp_mod
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.llm import LLMJudge
from judge_audit.judges.logprob import LogprobJudge

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "v05" / "prompt-templates.md"

# The digests every committed checkpoint of these adapters recorded (docs/runs/**). v1 must
# keep them for ever; changing either is changing a published run's question.
LLM_V1 = "fe16e59adeda960f12e22d035cf7f126a82c526117e73a379d8c301f1763d2c9"
LOGPROB_V1 = "e3f03049572329d2457a798202b9ce91a11998af94294036ac4b1390ff328e30"
# Fixed when v2 was written, before any run used it: the pre-registration cites them.
LLM_V2 = "ab4f08750ed37ec92f5e6716bec63b03f9bafce67beb440041dbf03fa8b1f502"
LOGPROB_V2 = "3b73900112a90c2e7f958b794dec4c3b5c8750776244dd40903e063c6d5d301a"

Q = Question(name="intent", type=QuestionType.CHOICE,
             instructions="Which intent does this message express? Choose exactly one.",
             options=["card_arrival", "top_up_failed", "top_up"],
             descriptions={"top_up": "money added to the account"})
NOUL = Question(name="urgent", type=QuestionType.NOUL, instructions="Is it urgent?")


def llm_judge(monkeypatch, template: str | None = None, reply: str | None = None,
              samples: str | None = None):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen3-8b")
    for var, value in (("LLM_PROMPT_TEMPLATE", template), ("LLM_SAMPLES", samples),
                       ("LLM_TEMPERATURE", "1" if samples else None)):
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)
    sent: list[dict] = []
    text = reply or json.dumps({"answers": {"intent": {"decision": "top_up_failed",
                                                       "confidence": 0.8}}})

    def fetch(req, deadline):
        sent.append(json.loads(req.data))
        return {"model": "qwen3-8b", "choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}

    monkeypatch.setattr(llm_mod, "_fetch_json", fetch)
    return LLMJudge(), sent


class FakeBackend:
    chat_kwargs = {"enable_thinking": False}
    end_ids = [1]
    cache_mode = "trim"

    def __init__(self):
        self.prompts: list[tuple[str, str]] = []

    def prompt_text(self, system, user):
        self.prompts.append((system, user))
        return f"{system}\n{user}"

    def option_logprobs(self, prompt, labels):
        lp = {"card_arrival": math.log(0.05), "top_up_failed": math.log(0.6),
              "top_up": math.log(0.15)}
        return {lab: lp[lab] for lab in labels}


def lp_judge(monkeypatch, template: str | None = None):
    if template is None:
        monkeypatch.delenv("LOGPROB_PROMPT_TEMPLATE", raising=False)
    else:
        monkeypatch.setenv("LOGPROB_PROMPT_TEMPLATE", template)
    backend = FakeBackend()
    return LogprobJudge(model="mlx-community/Qwen3-8B-4bit", backend=backend,
                        version="0.31.3"), backend


# --- v1 is the published prompt, byte for byte ------------------------------------------------


def test_v1_keeps_the_digest_every_published_run_recorded():
    assert llm_mod.prompt_sha256() == llm_mod.prompt_sha256("v1") == LLM_V1
    assert lp_mod.prompt_sha256() == lp_mod.prompt_sha256("v1") == LOGPROB_V1


def test_every_committed_checkpoint_of_these_judges_recorded_the_v1_digest():
    """A new template never re-labels an old run: every header that carries a digest for
    the llm or logprob adapter carries v1's."""
    expected = {"llm": LLM_V1, "logprob": LOGPROB_V1}
    seen = 0
    for path in sorted((ROOT / "docs" / "runs").rglob("*.ckpt.jsonl")):
        with open(path, encoding="utf-8") as f:
            first = json.loads(f.readline() or "{}")
        judge = (first.get("run") or {}).get("judge") or {}
        adapter = str(judge.get("name", "")).split(":")[0]
        if adapter in expected and "prompt_sha256" in judge:
            assert judge["prompt_sha256"] == expected[adapter], path
            seen += 1
    assert seen >= 2


def test_the_default_llm_judge_is_unchanged(monkeypatch):
    j, sent = llm_judge(monkeypatch)
    j.decide("my top up did not go through", [Q])
    assert sent[0]["messages"] == [
        {"role": "system", "content": llm_mod.SYSTEM},
        {"role": "user", "content": llm_mod._render("my top up did not go through", [Q])}]
    d = j.describe()
    assert j.name == "llm:qwen3-8b" and d["prompt_sha256"] == LLM_V1
    assert d["prompt_template"] == "v1"
    j1, _ = llm_judge(monkeypatch, template="v1")
    assert j1.name == j.name and j1.describe() == d


def test_the_default_logprob_judge_is_unchanged(monkeypatch):
    j, backend = lp_judge(monkeypatch)
    j.decide("my top up did not go through", [Q])
    assert backend.prompts == [(lp_mod.SYSTEM, lp_mod.render("my top up did not go through", Q))]
    d = j.describe()
    assert j.name == "logprob:Qwen3-8B-4bit" and d["prompt_sha256"] == LOGPROB_V1
    assert d["prompt_template"] == "v1"


# --- v2: another wording, the same measurement ---------------------------------------------


def test_v2_digests_are_fixed_and_differ_from_v1():
    assert llm_mod.prompt_sha256("v2") == LLM_V2 != LLM_V1
    assert lp_mod.prompt_sha256("v2") == LOGPROB_V2 != LOGPROB_V1


def test_the_digest_is_system_plus_the_rendered_sample():
    """What docs/v05/prompt-templates.md prints lets a reader recompute each digest."""
    for mod in (llm_mod, lp_mod):
        for t in mod.PROMPT_TEMPLATES:
            system, sample = mod.prompt_sample(t)
            assert mod.prompt_sha256(t) == hashlib.sha256(
                f"{system}\n---\n{sample}".encode()).hexdigest()


def test_the_llm_v2_request_uses_v2_and_is_recorded(monkeypatch):
    j, sent = llm_judge(monkeypatch, template="v2")
    (out,) = j.decide("my top up did not go through", [Q])
    assert sent[0]["messages"] == [
        {"role": "system", "content": llm_mod.SYSTEM_V2},
        {"role": "user", "content": llm_mod._render_v2("my top up did not go through", [Q])}]
    d = j.describe()
    assert d["prompt_template"] == "v2" and d["prompt_sha256"] == LLM_V2
    assert j.name == "llm:qwen3-8b:prompt-v2"
    # Same output contract, same parser, same decision and confidence.
    assert (out.decision, out.confidence, out.parse_status) == ("top_up_failed", 0.8, "parsed")


def test_the_llm_v2_self_consistency_name_keeps_both_suffixes(monkeypatch):
    j, _ = llm_judge(monkeypatch, template="v2", samples="5")
    assert j.name == "llm:qwen3-8b:sc5:prompt-v2"
    assert j.describe()["prompt_sha256"] == LLM_V2


def test_the_llm_v2_system_prompt_reaches_a_custom_provider(monkeypatch, tmp_path):
    mod = tmp_path / "prov.py"
    mod.write_text("SEEN = []\n"
                   "def call(model, system, user):\n"
                   "    SEEN.append(system)\n"
                   "    return '{\"answers\": {}}', 1, 1\n")
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_PROMPT_TEMPLATE", "v2")
    j = LLMJudge()
    j.decide("x", [Q])
    assert j._custom.SEEN == [llm_mod.SYSTEM_V2]
    assert j.describe()["prompt_template"] == "v2"


def test_the_anthropic_path_sends_the_template_s_system_prompt(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("LLM_PROMPT_TEMPLATE", "v2")
    j = LLMJudge(provider="anthropic", model="claude-opus-5")
    sent: dict = {}

    class Msg:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": '{"answers": {}}'})()]
        usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()

    def create(**kwargs):
        sent.update(kwargs)
        return Msg()

    monkeypatch.setattr(j._client.messages, "create", create)
    j._call_anthropic("hello")
    assert sent["system"] == llm_mod.SYSTEM_V2


def test_the_llm_v2_keeps_the_output_contract():
    """The JSON shape the parser reads is the same line in both system prompts, and v2 shows
    the question's name, instructions and every option with its description."""
    shape = '{"answers": {"<question name>": {"decision": "<option>", "confidence": <0..1>}}}'
    assert llm_mod.SYSTEM.endswith(shape) and llm_mod.SYSTEM_V2.endswith(shape)
    text = llm_mod._render_v2("hello", [Q, NOUL])
    assert '"intent"' in text and Q.instructions in text and "hello" in text
    assert "card_arrival | top_up_failed | top_up (money added to the account)" in text
    assert '"urgent"' in text and "true | false" in text
    for word in ("0", "1", "probability", "correct", "JSON"):
        assert word in llm_mod.SYSTEM_V2
    # v1's anchors reworded, not tightened: "1.0 = certain" is not "1 only if certain".
    assert "0.5 if it is a coin flip, 1 if you are certain" in llm_mod.SYSTEM_V2
    assert "only if" not in llm_mod.SYSTEM_V2
    # The prompt does not end on the raw input text, as logprob v2 does not.
    assert text.endswith("INPUT:\nhello\n\nReply with the JSON only.")


def test_the_logprob_v2_prompt_is_used_and_the_decision_rule_is_not_touched(monkeypatch):
    v1, _ = lp_judge(monkeypatch)
    (a,) = v1.decide("x", [Q])
    j, backend = lp_judge(monkeypatch, template="v2")
    (b,) = j.decide("x", [Q])
    assert backend.prompts == [(lp_mod.SYSTEM_V2, lp_mod.render_v2("x", Q))]
    assert (a.decision, a.confidence, a.raw) == (b.decision, b.confidence, b.raw)
    assert b.decision == "top_up_failed" and b.confidence == pytest.approx(0.6 / 0.8)
    d = j.describe()
    assert d["prompt_template"] == "v2" and d["prompt_sha256"] == LOGPROB_V2
    assert j.name == "logprob:Qwen3-8B-4bit:prompt-v2"
    assert (j.system, j.render) == (lp_mod.SYSTEM_V2, lp_mod.render_v2)


def test_the_logprob_v2_asks_for_the_option_name_only():
    text = lp_mod.render_v2("hello", Q)
    assert Q.instructions in text and "hello" in text
    assert "card_arrival | top_up_failed | top_up (money added to the account)" in text
    assert "only" in lp_mod.SYSTEM_V2 and "exactly as written" in lp_mod.SYSTEM_V2


@pytest.mark.parametrize("raw", ["v3", "V2 ", "2", "default", "none"])
def test_an_unknown_template_is_refused(monkeypatch, raw):
    with pytest.raises(ValueError, match="v1"):
        llm_mod.prompt_template_of(raw)
    with pytest.raises(ValueError, match="v1"):
        lp_mod.prompt_template_of(raw)


@pytest.mark.parametrize("raw,value", [("", "v1"), ("  ", "v1"), ("v1", "v1"), ("v2", "v2")])
def test_template_values(raw, value):
    assert llm_mod.prompt_template_of(raw) == value == lp_mod.prompt_template_of(raw)


def test_an_unknown_template_stops_the_judge_before_any_call(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_PROMPT_TEMPLATE", "v9")
    with pytest.raises(ValueError, match="LLM_PROMPT_TEMPLATE"):
        LLMJudge()
    monkeypatch.setenv("LOGPROB_PROMPT_TEMPLATE", "v9")
    with pytest.raises(ValueError, match="LOGPROB_PROMPT_TEMPLATE"):
        LogprobJudge(model="m", backend=FakeBackend())


# --- a checkpoint is never resumed across templates ------------------------------------------


def _resumable():
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_resumable
    return audit_resumable


def test_a_v1_checkpoint_is_not_resumed_with_v2(monkeypatch, tmp_path):
    ar = _resumable()
    old, _ = llm_judge(monkeypatch)
    new, _ = llm_judge(monkeypatch, template="v2")
    with pytest.raises(SystemExit, match="use a new checkpoint"):
        ar.same_method(tmp_path / "c", old.describe(), new.describe())
    lp_old, _ = lp_judge(monkeypatch)
    lp_new, _ = lp_judge(monkeypatch, template="v2")
    with pytest.raises(SystemExit, match="use a new checkpoint"):
        ar.same_method(tmp_path / "c", lp_old.describe(), lp_new.describe())


def test_the_prompt_digest_alone_stops_a_resume(monkeypatch, tmp_path):
    """Even under one name, a different prompt_sha256 is a different measurement."""
    ar = _resumable()
    j, _ = llm_judge(monkeypatch)
    now = j.describe()
    with pytest.raises(SystemExit, match="prompt_sha256"):
        ar.same_method(tmp_path / "c", {**now, "prompt_sha256": LLM_V2}, now)


PILOT = ROOT / "docs" / "runs" / "v05-pilot"


@pytest.mark.parametrize("ckpt", ["llm-gemini-3.6-flash.ckpt.jsonl", "llm-qwen3-8b.ckpt.jsonl",
                                  "logprob-qwen3-8b.ckpt.jsonl"])
def test_a_header_written_before_templates_existed_still_resumes_with_v1(
        monkeypatch, tmp_path, ckpt):
    """Headers written before this change have no `prompt_template`. A default (v1) run of
    the same judge passes the resume check against them, and a v2 run does not. Checked on
    the committed v0.5 pilot headers of the three judges v2 applies to."""
    ar = _resumable()
    with open(PILOT / ckpt, encoding="utf-8") as f:
        header = json.loads(f.readline())["run"]["judge"]
    assert "prompt_template" not in header
    adapter = header["name"].split(":")[0]
    judges = {}
    for template in (None, "v2"):
        if adapter == "llm":
            monkeypatch.setenv("LLM_MODEL_LABEL", header["model"])
            judges[template], _ = llm_judge(monkeypatch, template=template)
            judges[template].base_url = header["base_url"]   # the endpoint it recorded
        else:
            monkeypatch.setenv("LOGPROB_LABEL", header["model"])
            judges[template], _ = lp_judge(monkeypatch, template=template)
    ar.same_method(tmp_path / "c", header, judges[None].describe())
    with pytest.raises(SystemExit, match="use a new checkpoint"):
        ar.same_method(tmp_path / "c", header, judges["v2"].describe())


def test_audit_resumable_refuses_a_v2_session_on_a_v1_checkpoint(tmp_path, monkeypatch):
    import subprocess

    ckpt = tmp_path / "c.ckpt.jsonl"
    judge = {"name": "llm:m", "provider": "openai-compatible", "model": "m",
             "confidence_method": "verbalized (model-reported probability)",
             "temperature": 0, "prompt_sha256": LLM_V1}
    ckpt.write_text(json.dumps({"idx": -1, "run": {"judge": judge}}) + "\n")
    env = {"LLM_PROVIDER": "openai-compatible", "LLM_BASE_URL": "http://127.0.0.1:9",
           "LLM_MODEL": "m", "LLM_PROMPT_TEMPLATE": "v2",
           "PYTHONPATH": str(ROOT / "src")}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    p = subprocess.run([sys.executable, str(ROOT / "scripts" / "audit_resumable.py"),
                        str(ROOT / "examples" / "email-routing" / "labels.jsonl"),
                        "--judge", "llm", "--checkpoint", str(ckpt),
                        "--out", str(tmp_path / "r.md"), "--json", str(tmp_path / "r.json")],
                       cwd=tmp_path, capture_output=True, text=True)
    assert p.returncode != 0 and "llm:m:prompt-v2" in p.stderr
    assert len(ckpt.read_text().splitlines()) == 1        # nothing appended


# --- where the templates are listed ----------------------------------------------------------


def test_mcp_lists_the_templates_with_their_digests():
    pytest.importorskip("mcp")
    from judge_audit import mcp_server

    by_name = {j["name"]: j for j in mcp_server.list_judges()["judges"]}
    assert by_name["llm"]["prompt_templates"] == [
        {"id": "v1", "prompt_sha256": LLM_V1, "default": True},
        {"id": "v2", "prompt_sha256": LLM_V2, "default": False}]
    assert by_name["logprob"]["prompt_templates"] == [
        {"id": "v1", "prompt_sha256": LOGPROB_V1, "default": True},
        {"id": "v2", "prompt_sha256": LOGPROB_V2, "default": False}]
    assert "prompt_templates" not in by_name["jev"]
    assert any("LLM_PROMPT_TEMPLATE" in e for e in by_name["llm"]["env"])
    assert any("LOGPROB_PROMPT_TEMPLATE" in e for e in by_name["logprob"]["env"])


def _doc_sections() -> dict[str, str]:
    """{`### ` heading: the text under it, up to the next heading of any level}."""
    import re

    doc = DOC.read_text(encoding="utf-8")
    parts = re.split(r"^(#{1,6} .*)$", doc, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)
            if parts[i].startswith("### ")}


def test_the_doc_prints_each_template_verbatim_under_its_own_heading():
    """Each `### `<judge>`, `<template>`` section holds exactly that template's digest, its
    system prompt and its user message, in that order: a swap between sections fails."""
    import re

    sections = _doc_sections()
    seen = set()
    for judge, mod in (("llm", llm_mod), ("logprob", lp_mod)):
        for t in mod.PROMPT_TEMPLATES:
            (heading,) = [h for h in sections if h.startswith(f"### `{judge}`, `{t}`")]
            seen.add(heading)
            body = sections[heading]
            system, sample = mod.prompt_sample(t)
            assert re.findall(r"`prompt_sha256` = `([0-9a-f]{64})`", body) == [
                mod.prompt_sha256(t)], heading
            assert re.findall(r"```text\n(.*?)\n```", body, flags=re.S) == [system, sample], \
                heading
    assert len(seen) == 4
