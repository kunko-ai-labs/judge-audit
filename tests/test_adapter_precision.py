"""decision2 and laya record the precision they compute in (dtype of the weights and the
autocast policy), as decider and strands record `dtype`. Stubbed models, no download."""
from __future__ import annotations

from types import SimpleNamespace

from judge_audit.judges import decision2
from judge_audit.judges.base import Question, QuestionType
from judge_audit.judges.laya import LayaJudge, laya_precision


class _Param:
    def __init__(self, dtype: str):
        self.dtype = dtype


class _Module:
    """Stands in for a torch module: `parameters()` yields objects with a `dtype`."""

    def __init__(self, *dtypes: str):
        self._params = [_Param(d) for d in dtypes]

    def parameters(self):
        return iter(self._params)


def test_decision2_records_the_weights_dtype_and_no_autocast_off_cuda():
    backend = SimpleNamespace(model=_Module("torch.float32"), device="cpu")
    assert decision2.precision_of(backend) == {"dtype": "float32", "autocast": None}
    backend = SimpleNamespace(model=_Module("torch.float32"), device="mps")
    assert decision2.precision_of(backend) == {"dtype": "float32", "autocast": None}


def test_decision2_on_cuda_records_the_runtime_s_bfloat16_autocast():
    backend = SimpleNamespace(model=_Module("torch.float32"), device="cuda:0")
    assert decision2.precision_of(backend) == {"dtype": "float32", "autocast": "bfloat16"}


def test_decision2_weights_of_mixed_dtypes_are_all_listed():
    backend = SimpleNamespace(model=_Module("torch.float32", "torch.bfloat16"), device="cpu")
    assert decision2.precision_of(backend)["dtype"] == "bfloat16,float32"


def test_decision2_without_a_readable_model_records_unknown_not_a_guess():
    assert decision2.precision_of(SimpleNamespace(device="cpu")) == {
        "dtype": None, "autocast": None}


class _Agent:
    """A Laya agent stub with its autocast state and gate, as Laya 0.3.20 has them."""
    cfg = {"max_len": 512, "head_max_len": 192}

    def __init__(self, device="mps", amp_enabled=True, dtype="torch.float16", min_rows=5,
                 weights="torch.float32", answers=None):
        self.device = device
        self.model = _Module(weights)
        self.amp_enabled = amp_enabled
        self.dtype = dtype
        self.mps_amp_min_rows = min_rows
        self.answers = answers or {}

    def _amp_enabled_for(self, rows: int) -> bool:
        if not self.amp_enabled:
            return False
        return not (self.device == "mps" and rows < self.mps_amp_min_rows)

    def predict(self, state, questions, **kwargs):
        return {"answers": {k: v for k, v in self.answers.items() if k in questions}}


def test_laya_on_mps_records_the_autocast_condition():
    assert laya_precision(_Agent()) == {
        "dtype": "float32", "autocast": {"dtype": "float16", "min_rows": 5}}


def test_laya_on_cuda_autocasts_every_forward():
    got = laya_precision(_Agent(device="cuda", dtype="torch.bfloat16"))
    assert got["autocast"] == {"dtype": "bfloat16", "min_rows": None}


def test_laya_with_autocast_off_records_none():
    got = laya_precision(_Agent(device="cpu", amp_enabled=False, dtype="torch.float32"))
    assert got == {"dtype": "float32", "autocast": None}


def test_laya_precision_reaches_the_provenance():
    judge = LayaJudge(agent=_Agent(), version="0.3.20", loaded_revision="abc123",
                      token_counts=lambda *a: (5, [3], 10))
    d = judge.describe()
    assert d["dtype"] == "float32" and d["autocast"] == {"dtype": "float16", "min_rows": 5}


def test_laya_an_agent_without_these_attributes_records_unknown():
    bare = SimpleNamespace(cfg={}, device="cpu")
    assert laya_precision(bare) == {"dtype": None, "autocast": None}


def _choice(name: str) -> Question:
    return Question(name=name, type=QuestionType.CHOICE, instructions="Which?",
                    options=["a", "b"])


ANSWER = {"type": "choice", "choice": "a", "probabilities": {"a": 0.8, "b": 0.2}}


def _decide(n_questions: int, **agent_kwargs):
    names = [f"q{i}" for i in range(n_questions)]
    agent = _Agent(answers={n: ANSWER for n in names}, **agent_kwargs)
    judge = LayaJudge(agent=agent, token_counts=lambda *a: (5, [3, 3], 10))
    return judge.decide("state", [_choice(n) for n in names])


def test_each_judgment_says_whether_its_request_was_autocast():
    # On MPS the gate is 5 rows, one row per question sent: 4 questions run in the weights'
    # dtype, 5 run under float16 autocast.
    four, five = _decide(4), _decide(5)
    assert len(four) == 4 and len(five) == 5
    assert all(j.raw["autocast"] == {"requested": False, "effective": False} for j in four)
    assert all(j.raw["autocast"] == {"requested": True, "effective": True} for j in five)


class _FallbackAgent(_Agent):
    """Laya's fallback: the autocast forward fails, Laya turns autocast off and retries in
    float32 within the same call."""

    def predict(self, state, questions, **kwargs):
        self.amp_enabled = False
        self.dtype = "torch.float32"
        return super().predict(state, questions, **kwargs)


def test_a_fallback_inside_the_call_is_recorded_as_not_autocast():
    names = [f"q{i}" for i in range(5)]
    agent = _FallbackAgent(answers={n: ANSWER for n in names})
    judge = LayaJudge(agent=agent, token_counts=lambda *a: (5, [3, 3], 10))
    got = judge.decide("state", [_choice(n) for n in names])
    assert len(got) == 5
    assert all(j.raw["autocast"] == {"requested": True, "effective": False} for j in got)


def test_without_autocast_no_request_is_autocast():
    got = _decide(6, device="cpu", amp_enabled=False, dtype="torch.float32")
    assert len(got) == 6
    assert all(j.raw["autocast"] == {"requested": False, "effective": False} for j in got)


def test_an_agent_without_a_gate_records_unknown_per_request():
    class NoGate(_Agent):
        _amp_enabled_for = None
    judge = LayaJudge(agent=NoGate(answers={"q0": ANSWER}),
                      token_counts=lambda *a: (5, [3, 3], 10))
    assert judge.decide("state", [_choice("q0")])[0].raw["autocast"] is None


def test_decision2_load_writes_dtype_and_autocast_into_the_provenance(monkeypatch, tmp_path):
    """`_load` with transformers' loader stubbed: no network, no download."""
    import sys

    snap = tmp_path / "snapshots" / ("c" * 40)
    snap.mkdir(parents=True)
    (snap / "tokenizer.json").write_text("{}", encoding="utf-8")
    backend = SimpleNamespace(model=_Module("torch.float32"), device="cpu", tokenizer=None,
                              temperatures={"choice": 1.0}, share_context=False)
    model = SimpleNamespace(_source=str(snap), config=SimpleNamespace(),
                            manifest={"model_name": "stub"},
                            runtime=SimpleNamespace(backend=backend))
    fake_tf = SimpleNamespace(__version__="5.17.0",
                              AutoModel=SimpleNamespace(from_pretrained=lambda *a, **k: model))
    monkeypatch.setitem(sys.modules, "transformers", fake_tf)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(__version__="2.14.0"))
    monkeypatch.setattr(decision2, "tokenizer_check", lambda tok, path: {"stub": True})
    _, info = decision2._load("stub/model", "c" * 40, None)
    assert info["dtype"] == "float32" and info["autocast"] is None
    backend.device = "cuda:0"
    _, info = decision2._load("stub/model", "c" * 40, "cuda:0")
    assert info["autocast"] == "bfloat16"
