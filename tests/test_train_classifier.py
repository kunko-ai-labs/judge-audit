"""train_classifier.py pieces that decide what the model sees — no training, no download."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
torch = pytest.importorskip("torch")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


tc = _load("train_classifier")
split_heldout = _load("split_heldout")


def rows_of(labels):
    return [{"state": f"s{i}", "questions": [{"name": "q", "options": sorted(set(labels))}],
             "labels": {"q": lab}, "_meta": {}} for i, lab in enumerate(labels)]


def test_validation_carve_is_stratified_disjoint_and_seeded():
    rows = rows_of(["a"] * 10 + ["b"] * 10)
    train, val = tc.carve_validation(rows, list(range(20)), "q", (), seed=2026)
    assert sorted(train + val) == list(range(20)) and not set(train) & set(val)
    assert len(val) == 4 and sum(rows[i]["labels"]["q"] == "a" for i in val) == 2
    assert (train, val) == tc.carve_validation(rows, list(range(20)), "q", (), seed=2026)
    assert (train, val) != tc.carve_validation(rows, list(range(20)), "q", (), seed=1)
    # Only the given train indices are carved; the rest (the held-out half) is untouched.
    train, val = tc.carve_validation(rows, [0, 1, 2, 3, 4], "q", (), seed=2026)
    assert sorted(train + val) == [0, 1, 2, 3, 4] and len(val) == 1


def test_committed_split_carves_to_the_amendment_sizes():
    for dataset, (n_train, n_val) in {"email-routing": (80, 20), "task-routing": (48, 12)}.items():
        labels, q, meta = split_heldout.SPLITS[dataset]
        rows = split_heldout.load_jsonl(str(ROOT / labels))
        s = split_heldout.load_split(split_heldout.split_path(dataset))
        train, val = tc.carve_validation(rows, s["train"], q, meta, 2026)
        assert (len(train), len(val)) == (n_train, n_val)
        assert not set(val) & set(s["heldout"]) and not set(train) & set(s["heldout"])


def test_fit_temperature_recovers_a_known_scale_and_reports_bounds():
    torch.manual_seed(0)
    base = torch.randn(400, 5)
    targets = torch.distributions.Categorical(logits=base).sample()
    # Logits sharpened by 4x need T ~ 4 to be calibrated again.
    t, before, after, bounded = tc.fit_temperature(base * 4, targets)
    assert 3.0 < t < 5.5 and after < before and not bounded
    # T = 1 already optimal when the logits are the true ones (within noise).
    t, before, after, bounded = tc.fit_temperature(base, targets)
    assert 0.7 < t < 1.4 and after <= before + 1e-6
    # A perfectly classified slice has no minimum: the search stops at the lower bound and says so.
    t, _b, _a, bounded = tc.fit_temperature(base, base.argmax(-1))
    assert bounded and math.isclose(t, tc.T_BOUNDS[0], rel_tol=1e-2)


def test_early_stopping_constants_are_the_amendment_protocol():
    assert (tc.RUN2_STOP_LOSS, tc.RUN2_PATIENCE, tc.RUN2_MAX_EPOCHS) == (0.05, 3, 40)
    assert tc.RUN2_VAL_FRAC == 0.2 and tc.T_BOUNDS == (0.1, 10.0)
