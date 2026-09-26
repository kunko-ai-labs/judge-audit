"""LLM_SAMPLES / LLM_TEMPERATURE: self-consistency voting — network mocked."""
from __future__ import annotations

import json

import pytest

from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.llm import LLMJudge, samples_of, temperature_of, vote, vote_replies

Q = Question(name="category", type=QuestionType.CHOICE, instructions="classify",
             options=["spam", "order", "support"])


def reply(decision: str | None, confidence=0.9) -> str:
    if decision is None:
        return "I cannot help with that."
    return json.dumps({"answers": {"category": {"decision": decision,
                                                "confidence": confidence}}})


def judge(monkeypatch, replies: list[str], samples="5", temperature="1", fetch=None):
    import judge_audit.judges.llm as llm_mod

    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("LLM_MODEL", "local-model")
    for var, value in (("LLM_SAMPLES", samples), ("LLM_TEMPERATURE", temperature)):
        if value is None:
            monkeypatch.delenv(var, raising=False)
        else:
            monkeypatch.setenv(var, value)
    sent: list[dict] = []
    queue = list(replies)

    def fake_fetch(req, deadline):
        sent.append(json.loads(req.data))
        return {"model": "local-model-v2", "choices": [{"message": {"content": queue.pop(0)}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10}}

    monkeypatch.setattr(llm_mod, "_fetch_json", fetch or fake_fetch)
    return LLMJudge(), sent


# --- the vote, by hand -------------------------------------------------------------------


def _parsed(*decisions):
    return [{"category": ("" if d is None else d, 0.9 if d else None, None,
                          "no_answer" if d is None else "parsed")} for d in decisions]


def test_majority_share_counts_every_sample_including_the_unanswered():
    (decision, confidence, status, votes), = vote(
        _parsed("order", "spam", "order", None, "order"), [Q]).values()
    assert (decision, confidence, status) == ("order", 3 / 5, "parsed")
    assert votes == {"order": 3, "spam": 1}


def test_a_tie_goes_to_the_decision_drawn_first_not_the_first_option():
    ((decision, confidence, _, _),) = vote(_parsed("support", "spam", "spam", "support"),
                                           [Q]).values()
    assert decision == "support" and confidence == 0.5


def test_no_answer_in_any_sample_is_no_decision():
    ((decision, confidence, status, votes),) = vote(_parsed(None, None), [Q]).values()
    assert (decision, confidence, status, votes) == ("", None, "no_answer", {})


def test_a_decision_outside_the_options_votes_and_can_win():
    ((decision, confidence, _, _),) = vote(_parsed("refund", "refund", "spam"), [Q]).values()
    assert decision == "refund" and confidence == pytest.approx(2 / 3)


def test_vote_replies_reparses_raw_texts():
    texts = [reply("SPAM"), reply("order", 0.2), reply("spam", "high")]
    ((decision, confidence, _, votes),) = vote_replies(texts, [Q]).values()
    assert decision == "spam" and confidence == pytest.approx(2 / 3)
    assert votes == {"spam": 2, "order": 1}                        # case normalised


# --- configuration -----------------------------------------------------------------------


@pytest.mark.parametrize("raw, value", [("", 0), ("0", 0.0), ("0.7", 0.7), ("default", None),
                                        (" Default ", None), ("2", 2.0)])
def test_temperature_values(raw, value):
    assert temperature_of(raw) == value


@pytest.mark.parametrize("raw", ["-0.1", "2.5", "hot", "nan"])
def test_temperature_refuses_nonsense(raw):
    with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
        temperature_of(raw)


@pytest.mark.parametrize("raw", ["0", "-1", "1.5", "51", "five"])
def test_samples_refuses_nonsense(raw):
    with pytest.raises(ValueError, match="LLM_SAMPLES"):
        samples_of(raw)


def test_several_samples_at_temperature_zero_are_refused(monkeypatch):
    with pytest.raises(ValueError, match="needs sampling"):
        judge(monkeypatch, [], samples="5", temperature=None)
    with pytest.raises(ValueError, match="needs sampling"):
        judge(monkeypatch, [], samples="5", temperature="0")


def test_defaults_change_nothing(monkeypatch):
    j, sent = judge(monkeypatch, [reply("spam", 0.8)], samples=None, temperature=None)
    (out,) = j.decide("buy now", [Q])
    assert sent[0]["temperature"] == 0 and len(sent) == 1
    assert out.confidence == 0.8 and "text" in out.raw and "samples" not in out.raw
    d = j.describe()
    assert d["temperature"] == 0 and "samples" not in d
    assert d["confidence_method"].startswith("verbalized")


def test_temperature_default_sends_no_temperature(monkeypatch):
    j, sent = judge(monkeypatch, [reply("spam")], samples=None, temperature="default")
    j.decide("buy now", [Q])
    assert "temperature" not in sent[0]
    assert j.describe()["temperature"] == "provider default"


# --- the judge ---------------------------------------------------------------------------


def test_k_calls_one_majority_decision_and_every_sample_kept(monkeypatch):
    replies = [reply("order", 0.95), reply("spam", 0.6), reply("order", 0.9), reply(None),
               reply("order", 0.99)]
    j, sent = judge(monkeypatch, replies)
    (out,) = j.decide("where is my parcel", [Q])
    assert len(sent) == 5 and all(b["temperature"] == 1.0 for b in sent)
    assert len({json.dumps(b, sort_keys=True) for b in sent}) == 1   # the same request
    assert out.decision == "order" and out.confidence == pytest.approx(0.6)
    assert out.parse_status == "parsed"
    assert [s["text"] for s in out.raw["samples"]] == replies
    assert out.raw["votes"] == {"order": 3, "spam": 1}
    assert out.raw["verbalized"] == [0.95, 0.6, 0.9, None, 0.99]
    assert out.raw["usage"] == {"input_tokens": 250, "output_tokens": 50}
    assert out.raw["served"] == {"model": "local-model-v2", "system_fingerprint": None}
    assert out.cost_usd == 0.0 and out.raw["priced"] is True         # local endpoint
    d = j.describe()
    assert d["samples"] == 5 and d["temperature"] == 1.0
    assert d["confidence_method"].startswith("self-consistency")


def test_the_checkpointed_samples_revote_to_the_same_decision(monkeypatch):
    replies = [reply("support"), reply("spam"), reply("spam")]
    j, _ = judge(monkeypatch, replies, samples="3")
    (out,) = j.decide("help", [Q])
    ((decision, confidence, status, _),) = vote_replies(
        [s["text"] for s in out.raw["samples"]], [Q]).values()
    assert (decision, confidence, status) == (out.decision, out.confidence, out.parse_status)


def test_a_failed_sample_fails_the_decision(monkeypatch):
    calls = []

    def flaky(req, deadline):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("rate-limited by the endpoint")
        return {"choices": [{"message": {"content": reply("spam")}}], "usage": {}}

    j, _ = judge(monkeypatch, [], samples="3", fetch=flaky)
    with pytest.raises(RuntimeError, match="rate-limited"):
        j.decide("x", [Q])


# --- custom provider ---------------------------------------------------------------------


def _custom(monkeypatch, tmp_path, source: str, temperature: str | None, samples="3"):
    mod = tmp_path / "prov.py"
    mod.write_text(source)
    monkeypatch.setenv("LLM_PROVIDER", "custom")
    monkeypatch.setenv("LLM_PROVIDER_MODULE", str(mod))
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_SAMPLES", samples)
    if temperature is None:
        monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    else:
        monkeypatch.setenv("LLM_TEMPERATURE", temperature)
    return LLMJudge()


def test_a_custom_provider_without_a_temperature_keyword_is_refused(monkeypatch, tmp_path):
    src = "def call(model, system, user):\n    return '{}', 1, 1\n"
    with pytest.raises(RuntimeError, match="takes no temperature"):
        _custom(monkeypatch, tmp_path, src, "1")
    assert _custom(monkeypatch, tmp_path, src, None, samples="1").decide  # default: unchanged


def test_a_custom_provider_gets_the_temperature(monkeypatch, tmp_path):
    src = ("SEEN = []\n"
           "def call(model, system, user, temperature=0):\n"
           "    SEEN.append(temperature)\n"
           "    return '{\"answers\": {\"category\": {\"decision\": \"spam\", "
           "\"confidence\": 0.5}}}', 1, 1\n")
    j = _custom(monkeypatch, tmp_path, src, "default")
    (out,) = j.decide("x", [Q])
    assert j._custom.SEEN == [None, None, None] and out.confidence == 1.0


@pytest.mark.parametrize("temperature, sent", [(None, {"temperature": 0}),
                                               ("0.5", {"temperature": 0.5}),
                                               ("default", {})])
def test_the_anthropic_path_sends_the_temperature_or_none(monkeypatch, temperature, sent):
    from types import SimpleNamespace

    j, _ = judge(monkeypatch, [], samples=None, temperature=temperature)
    j.provider = "anthropic"
    calls: list[dict] = []
    resp = SimpleNamespace(stop_reason="end_turn", model="m", usage=SimpleNamespace(
        input_tokens=1, output_tokens=1), content=[SimpleNamespace(type="text",
                                                                   text=reply("spam"))])

    def create(**kw):
        calls.append(kw)
        return resp

    j._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    j._anthropic = SimpleNamespace(RateLimitError=RuntimeError, APIStatusError=RuntimeError)
    j.decide("x", [Q])
    assert {k: v for k, v in calls[0].items() if k == "temperature"} == sent


def test_reparse_revotes_a_self_consistency_checkpoint(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("reparse_checkpoints",
                                                  root / "scripts" / "reparse_checkpoints.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    row = {"state": "x", "questions": [{"name": "category", "type": "choice",
                                        "instructions": "classify",
                                        "options": ["spam", "order", "support"]}],
           "labels": {"category": "spam"}}
    samples = [{"text": reply("spam")}, {"text": reply("order")}, {"text": reply("spam")}]
    stale = {"idx": 0, "judgments": [{"question": "category", "decision": "order",
                                      "confidence": 1.0, "parse_status": "parsed",
                                      "raw": {"samples": samples, "votes": {}}}]}
    ckpt = tmp_path / "c.ckpt.jsonl"
    ckpt.write_text(json.dumps({"idx": -1, "run": {}}) + "\n" + json.dumps(stale) + "\n")
    assert mod.reparse(ckpt, [row], dry_run=False) == 1
    (j,) = json.loads(ckpt.read_text().splitlines()[1])["judgments"]
    assert (j["decision"], j["confidence"]) == ("spam", pytest.approx(2 / 3))
    assert j["raw"]["votes"] == {"spam": 2, "order": 1}
    assert mod.reparse(ckpt, [row], dry_run=True) == 0
