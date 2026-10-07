"""decision2 and laya record the precision they compute in (dtype of the weights and the
autocast policy), as decider and strands record `dtype`. Stubbed models, no download."""
from __future__ import annotations

from types import SimpleNamespace

from judge_audit.judges import decision2
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
    cfg = {"max_len": 512, "head_max_len": 192}
    device = "mps"

    def __init__(self, amp_enabled=True, dtype="torch.float16", min_rows=5,
                 weights="torch.float32"):
        self.model = _Module(weights)
        self.amp_enabled = amp_enabled
        self.dtype = dtype
        self.mps_amp_min_rows = min_rows


def test_laya_records_weights_and_its_autocast_policy():
    assert laya_precision(_Agent()) == {
        "dtype": "float32",
        "autocast": {"enabled": True, "dtype": "float16", "mps_min_rows": 5}}


def test_laya_with_autocast_off_records_it_off():
    got = laya_precision(_Agent(amp_enabled=False, dtype="torch.float32"))
    assert got["autocast"] == {"enabled": False, "dtype": "float32", "mps_min_rows": 5}


def test_laya_precision_reaches_the_provenance():
    judge = LayaJudge(agent=_Agent(), version="0.3.20", loaded_revision="abc123",
                      token_counts=lambda *a: (5, [3], 10))
    d = judge.describe()
    assert d["dtype"] == "float32"
    assert d["autocast"]["enabled"] is True and d["autocast"]["mps_min_rows"] == 5


def test_laya_an_agent_without_these_attributes_records_unknown():
    bare = SimpleNamespace(cfg={}, device="cpu")
    assert laya_precision(bare) == {"dtype": None, "autocast": None}
