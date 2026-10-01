"""The MLX scoring path of LogprobJudge on a tiny random model: runs where mlx and mlx-lm
are installed (Apple silicon, or Linux CPU), skipped elsewhere."""
from __future__ import annotations

import math

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


def test_the_trimmed_cache_equals_a_fresh_cache_per_option(backend):
    """The self-check's gate (plan amendment 1): scoring every option on one trimmed cache is
    exactly what a new cache per option computes (prefix prefilled, then the option)."""
    prompt = backend.prompt_text(SYSTEM, "STATE:\nwhere is my card")
    labels = ["card", "card_arrival", "top_up", "x"]
    trimmed = backend.option_logprobs(prompt, labels)
    fresh = backend.option_logprobs(prompt, labels, fresh=True)
    assert backend.cache_mode == "fresh"
    assert trimmed == fresh


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


def test_log_softmax_is_float32_whatever_the_logits_dtype():
    """In bfloat16 a large-vocabulary softmax rounds P(top) to a handful of values."""
    import math
    import random

    from judge_audit.judges.logprob import log_softmax

    rng = random.Random(0)
    worst = 0.0
    for _ in range(20):
        row = [rng.gauss(0, 3) for _ in range(50_000)]
        row[0] = 18 + 16 * rng.random()
        bf = mx.array(row).astype(mx.bfloat16)
        exact = [float(v) for v in bf.astype(mx.float32).tolist()]  # the same logits, float64
        top = max(exact)
        lse = top + math.log(math.fsum(math.exp(v - top) for v in exact))
        got = log_softmax(bf)
        assert got.dtype == mx.float32
        worst = max(worst, abs(math.exp(float(got[0])) - math.exp(exact[0] - lse)))
    assert worst < 1e-3


def test_a_bfloat16_model_scores_like_its_float64_reference(backend):
    import math

    from judge_audit.judges.logprob import MLXBackend

    model = backend.model
    model.set_dtype(mx.bfloat16)
    try:
        bf = MLXBackend(model, CharTokenizer())
        prompt = bf.prompt_text(SYSTEM, "STATE:\nwhere is my card")
        got = bf.option_logprobs(prompt, ["card", "top_up"])
        for lab in ("card", "top_up"):
            ids = bf.encode(prompt) + bf.encode(lab)
            logits = [[float(v) for v in r] for r in
                      model(mx.array([ids]))[0].astype(mx.float32).tolist()]

            def lp(r, t):
                top = max(r)
                return r[t] - top - math.log(math.fsum(math.exp(v - top) for v in r))

            n = len(bf.encode(prompt))
            ref = sum(lp(logits[i - 1], ids[i]) for i in range(n, len(ids)))
            last = logits[len(ids) - 1]
            ends = [lp(last, e) for e in bf.end_ids]
            ref += max(ends) + math.log(math.fsum(math.exp(e - max(ends)) for e in ends))
            assert got[lab] == pytest.approx(ref, abs=2e-3)
    finally:
        model.set_dtype(mx.float32)


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
    out = capsys.readouterr().out
    assert ("trimmed vs fresh cache: largest log-probability difference 0.00e+00 · "
            "decisions changed 0") in out
    assert "full forward pass (numerical spread, reported, not a gate)" in out


def _selfcheck_module(backend, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path

    from judge_audit.judges.logprob import LogprobJudge

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("logprob_selfcheck_gate",
                                                  root / "scripts" / "logprob_selfcheck.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["logprob_selfcheck_gate"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "LogprobJudge",
                        lambda model=None: LogprobJudge(model="tiny", backend=backend))
    return mod


def _labels(tmp_path):
    import json

    rows = [{"state": f"message {i}",
             "questions": [{"name": "intent", "type": "choice", "instructions": "Which?",
                            "options": ["card", "card_arrival", "top_up"]}],
             "labels": {"intent": "card"}} for i in range(2)]
    p = tmp_path / "labels.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def test_the_selfcheck_fails_when_trimming_breaks(backend, tmp_path, monkeypatch, capsys):
    """A cache that is not trimmed back between options scores later options after the
    earlier ones' tokens: the trimmed path then differs from a fresh cache, and the gate
    fails."""
    import mlx_lm.models.cache as cache_mod

    monkeypatch.setattr(cache_mod, "trim_prompt_cache", lambda cache, n: 0)
    mod = _selfcheck_module(backend, monkeypatch)
    assert mod.main([str(_labels(tmp_path)), "--rows", "2"]) == 1


def test_the_selfcheck_fails_on_a_large_full_pass_spread(backend, tmp_path, monkeypatch):
    """The full forward pass is not exact in bfloat16, but a changed decision whose
    trimmed-path margin is beyond the loose bound (four bfloat16 steps at logit magnitudes
    32-64) still fails the check."""
    mod = _selfcheck_module(backend, monkeypatch)
    real = backend.option_logprobs

    def skewed(prompt, labels, recompute=False, fresh=False):
        """The full pass alone puts top_up first: a changed decision whose trimmed-path
        margin is far above the bound."""
        out = real(prompt, labels, recompute=recompute, fresh=fresh)
        return {k: v + (30.0 if recompute and k == "top_up" else 0.0) for k, v in out.items()}

    monkeypatch.setattr(backend, "option_logprobs", skewed)
    assert mod.main([str(_labels(tmp_path)), "--rows", "2"]) == 1
    monkeypatch.setattr(backend, "option_logprobs", real)
    assert mod.main([str(_labels(tmp_path)), "--rows", "2"]) == 0


def test_log_odds_helpers():
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("logprob_selfcheck_h",
                                                  root / "scripts" / "logprob_selfcheck.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["logprob_selfcheck_h"] = mod
    spec.loader.exec_module(mod)
    # the diagnosed near-tie: 0.25 in log-odds on the top pair, within the bound
    a = {"x": 0.3924, "y": 0.3924, "z": 0.2152}
    b = {"x": 0.3453, "y": 0.4434, "z": 0.2113}
    assert mod.log_odds_shift(a, b) == pytest.approx(math.log(0.4434 / 0.3453))   # 0.25
    assert mod.margin(a) == 0.0 and mod.margin({"x": 1.0, "y": 0.0}) == math.inf
    # options under 1 % in either distribution are not compared: one option left, no pair
    assert mod.log_odds_shift({"x": 0.995, "y": 0.005}, {"x": 0.9, "y": 0.1}) == 0.0
