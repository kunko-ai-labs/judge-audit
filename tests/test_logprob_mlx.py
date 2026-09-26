"""The MLX scoring path of LogprobJudge on a tiny random model: runs where mlx and mlx-lm
are installed (Apple silicon, or Linux CPU), skipped elsewhere."""
from __future__ import annotations

import pytest

from judge_audit.judges.logprob import SYSTEM, option_distribution

# --- the MLX path, on a tiny random model --------------------------------------------------

mx = pytest.importorskip("mlx.core")
llama = pytest.importorskip("mlx_lm.models.llama")


class CharTokenizer:
    """One token per character; id 1 is the end of turn."""

    eos_token_ids = {1}
    eos_token_id = 1

    def encode(self, text, add_special_tokens=False):
        return [2 + (ord(ch) % 38) for ch in text]

    def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=False,
                            **kwargs):
        assert kwargs.get("enable_thinking") is False and not tokenize
        return "".join(f"<{m['role']}>{m['content']}" for m in messages) + "<assistant>"


@pytest.fixture(scope="module")
def backend():
    from judge_audit.judges.logprob import MLXBackend

    args = llama.ModelArgs(model_type="llama", hidden_size=32, num_hidden_layers=2,
                           intermediate_size=64, num_attention_heads=4, rms_norm_eps=1e-5,
                           vocab_size=40, num_key_value_heads=2)
    mx.random.seed(0)
    model = llama.Model(args)
    mx.eval(model.parameters())
    return MLXBackend(model, CharTokenizer())


def _naive(backend, prompt, label):
    """Independent reference: one full forward pass, the sum written out by hand."""
    ids = backend.encode(prompt) + backend.encode(label)
    logits = backend.model(mx.array([ids]))[0]
    logp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    n = len(backend.encode(prompt))
    total = sum(float(logp[i - 1, ids[i]]) for i in range(n, len(ids)))
    end = float(mx.logsumexp(logp[len(ids) - 1, mx.array(sorted(backend.end_ids))]))
    return total + end


def test_cached_scores_equal_a_full_forward_pass(backend):
    prompt = backend.prompt_text(SYSTEM, "STATE:\nwhere is my card")
    labels = ["card", "card_arrival", "top_up", "x"]
    cached = backend.option_logprobs(prompt, labels)
    assert backend.cache_mode == "trim"
    fresh = backend.option_logprobs(prompt, labels, recompute=True)
    assert backend.cache_mode == "recompute"
    for lab in labels:
        assert cached[lab] == pytest.approx(_naive(backend, prompt, lab), abs=1e-4)
        assert cached[lab] == pytest.approx(fresh[lab], abs=1e-4)


def test_a_label_that_starts_another_is_not_credited_with_it(backend):
    prompt = backend.prompt_text(SYSTEM, "STATE:\ntop up")
    both = backend.option_logprobs(prompt, ["top_up", "top_up_failed"])
    probs, mass = option_distribution(both)
    assert sum(probs.values()) == pytest.approx(1.0) and 0 < mass < 1
    # the end-of-turn term is part of the score: it is strictly below the tokens-only sum
    ids = backend.encode(prompt) + backend.encode("top_up")
    logits = backend.model(mx.array([ids]))[0]
    logp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
    n = len(backend.encode(prompt))
    tokens_only = sum(float(logp[i - 1, ids[i]]) for i in range(n, len(ids)))
    assert both["top_up"] < tokens_only


def test_selfcheck_passes_on_a_model_whose_cache_is_exact(backend, tmp_path, monkeypatch, capsys):
    import importlib.util
    import json
    import sys
    from pathlib import Path

    from judge_audit.judges.logprob import LogprobJudge

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("logprob_selfcheck",
                                                  root / "scripts" / "logprob_selfcheck.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["logprob_selfcheck"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "LogprobJudge",
                        lambda model=None: LogprobJudge(model="tiny", backend=backend))
    labels = tmp_path / "labels.jsonl"
    rows = [{"state": f"message {i}",
             "questions": [{"name": "intent", "type": "choice", "instructions": "Which?",
                            "options": ["card", "card_arrival", "top_up"]}],
             "labels": {"intent": "card"}} for i in range(3)]
    labels.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert mod.main([str(labels), "--rows", "3"]) == 0
    assert "decisions changed 0" in capsys.readouterr().out
