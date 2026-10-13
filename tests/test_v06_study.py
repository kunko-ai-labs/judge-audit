"""scripts/v06_study.py on synthetic checkpoints only: the split by item, the cross-fit and
its pooling, the exact bounds, Holm with a test not run, the clustered bootstrap, the
sensitivity subsets and the files that are never read. The study's own numbers are checked
by regenerating its report (`--check`)."""
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("v06_study", ROOT / "scripts" / "v06_study.py")
study = importlib.util.module_from_spec(spec)
sys.modules["v06_study"] = study
spec.loader.exec_module(study)

from judge_audit.metrics.selective import (  # noqa: E402
    paired_difference_ci,
    split_by_group,
)
from judge_audit.runner import sha256_of  # noqa: E402

LOCALES = ["en-US", "es-ES", "ca-ES"]
OPTIONS = ["alarm_set", "play_music", "weather_query"]
SCENARIO = {"alarm_set": "alarm", "play_music": "play", "weather_query": "weather"}
N_ITEMS = 300
MAJORITY_NO = {("ca-ES", 5)}                       # two of three localisation judges said no
ONE_NO = {("es-ES", 7)}                            # one said no: not a majority
OVERLAP = {("en-US", 9), ("ca-ES", 11)}            # text also in train or dev


# --- a synthetic study tree --------------------------------------------------------------


def _labels_row(locale: str, i: int) -> dict:
    meta = {"source": "synthetic", "locale": locale, "split": "test", "id": str(1000 + i),
            "scenario": SCENARIO[OPTIONS[i % 3]],
            "text_in_train_or_dev": (locale, i) in OVERLAP}
    if locale != "en-US":
        meta["intent_judgments"] = ([0, 0, 1] if (locale, i) in MAJORITY_NO
                                    else [0, 1, 1] if (locale, i) in ONE_NO else [1, 1, 1])
    return {"state": f"{locale} utterance {i}",
            "questions": [{"name": "intent", "type": "choice", "instructions": "Which?",
                           "options": OPTIONS}],
            "labels": {"intent": OPTIONS[i % 3]}, "_meta": meta}


def _wrong(i: int) -> str:
    return OPTIONS[(i + 1) % 3]


def _behaviour(slug: str, locale: str, i: int) -> tuple[str, float | None, str, dict]:
    """(decision, confidence, parse status, raw) of a synthetic judge on item i."""
    right = OPTIONS[i % 3]
    raw: dict = {"served": {"model": slug}}
    if slug == "jev":
        if locale == "en-US":                     # 2 errors, both less confident
            return (_wrong(i), 0.6, "parsed", raw) if i % 150 == 0 else (right, 0.95, "parsed",
                                                                          raw)
        k = 20 if locale == "ca-ES" else 5        # ca: 5 % wrong; es: 20 % wrong
        return (_wrong(i) if i % k == 0 else right), 0.95, "parsed", raw
    if slug == "gpt-6-luna":
        raw["native_confidence"] = 0.5 if i % 4 == 0 else 0.9
        if locale == "es-ES" and i % 50 == 0:     # a refusal: no answer, no confidence
            return "", None, "no_answer", {"served": {"model": slug}, "refusal": True}
        if locale == "en-US":
            return (_wrong(i), 0.55, "parsed", raw) if i % 150 == 0 else (right, 0.9, "parsed",
                                                                           raw)
        return (_wrong(i) if i % 8 == 0 else right), 0.9 if i % 8 else 0.7, "parsed", raw
    if slug == "claude-sonnet-4.5":               # English validates nothing: half wrong
        return (_wrong(i) if i % 2 == 0 else right), 0.95, "parsed", raw
    if slug == "decision2-kai-0.6b":              # exploratory, its own field elsewhere
        raw = {"entropy_confidence": 0.3 if i % 3 == 0 else 0.8}
        return (_wrong(i) if i % 3 == 0 else right), 0.4 if i % 3 == 0 else 0.7, "parsed", raw
    raise AssertionError(slug)


def _write_checkpoint(path: Path, labels_path: Path, slug: str, locale: str,
                      adapter: str, rows: int = N_ITEMS, **run_extra) -> None:
    header = {"idx": -1, "run": {**run_extra,
        "timestamp_utc": "2026-10-13T00:00:00+00:00", "judge_audit_version": "test",
        "judge": {"name": adapter, "model": slug},
        "dataset": {"path": f"examples/massive/{labels_path.name}",
                    "sha256": sha256_of(str(labels_path)), "rows": N_ITEMS}}}
    lines = [json.dumps(header)]
    for i in range(rows):
        d, c, st, raw = _behaviour(slug, locale, i)
        lines.append(json.dumps({"idx": i, "judgments": [
            {"question": "intent", "decision": d, "confidence": c, "latency_s": 0.5,
             "cost_usd": 0.001, "raw": raw, "parse_status": st}]}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


ADAPTER = {"jev": "jev", "gpt-6-luna": "openai-decisions", "claude-sonnet-4.5": "llm",
           "decision2-kai-0.6b": "decision2"}


def build(tmp: Path, judges=tuple(ADAPTER), predictions: bool = True) -> dict:
    massive = tmp / "examples" / "massive"
    massive.mkdir(parents=True)
    for loc in LOCALES:
        (massive / f"labels-test-{loc}.jsonl").write_text(
            "".join(json.dumps(_labels_row(loc, i)) + "\n" for i in range(N_ITEMS)),
            encoding="utf-8")
    runs = tmp / "docs" / "runs" / "v06"
    runs.mkdir(parents=True)
    for slug in judges:
        for loc in LOCALES:
            _write_checkpoint(runs / f"{slug}-{loc}.ckpt.jsonl",
                              massive / f"labels-test-{loc}.jsonl", slug, loc, ADAPTER[slug])
    pred = None
    if predictions:
        pred = tmp / "predictions.json"
        tests = {}
        for n, (loc, judge) in enumerate(((loc, j) for loc in ("ca-ES", "es-ES")
                                          for j in study.PRIMARY), 1):
            tests[f"T{n}"] = {"judge": judge, "target_locale": loc,
                              "prediction": ("resolved" if (judge, loc) == ("gpt-6-luna", "es-ES")
                                             else "not resolved")}
        pred.write_text(json.dumps({"tests": tests}), encoding="utf-8")
    return {"root": tmp, "runs": runs, "predictions": pred}


def compute(tree: dict, **kw) -> dict:
    return study.compute(tree["runs"], tree["root"], tree["predictions"],
                         n_boot=kw.pop("n_boot", 40), jobs=kw.pop("jobs", 1), **kw)


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> dict:
    return build(tmp_path_factory.mktemp("v06"))


@pytest.fixture(scope="module")
def result(tree) -> dict:
    return compute(tree)


# --- the split is by item -----------------------------------------------------------------


def test_the_halves_are_split_by_item_with_the_seed_and_hold_every_item_once():
    ids = [str(1000 + i) for i in range(N_ITEMS)]
    a, b = study.item_halves(ids)
    assert (a, b) == split_by_group(ids, 2026)
    assert sorted(a + b) == list(range(N_ITEMS)) and not set(a) & set(b)
    assert len(a) == (N_ITEMS + 1) // 2


def test_an_item_falls_on_the_same_side_in_every_locale(result):
    """One split for the three locales: the halves are indices of items, and row k is the
    same item in every file, so its three languages are always on the same side."""
    h = result["analyses"]["primary"]["halves"]
    ids = [str(1000 + i) for i in range(N_ITEMS)]
    assert h["sizes"] == [len(x) for x in split_by_group(ids, 2026)]
    assert h["seed"] == 2026 and h["unit"] == "item"


def test_files_whose_items_differ_are_refused(tmp_path):
    t = build(tmp_path, judges=("jev",), predictions=False)
    p = t["root"] / "examples" / "massive" / "labels-test-ca-ES.jsonl"
    rows = p.read_text(encoding="utf-8").splitlines()
    rows[0], rows[1] = rows[1], rows[0]
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="same items in the same order"):
        study.load_all_labels(t["root"])


# --- exact bounds and the binomial tail ---------------------------------------------------


@pytest.mark.parametrize("errors, n, p", [(0, 10, 1.0), (1, 1, 0.05), (2, 2, 0.0025)])
def test_the_exact_tail_has_known_values(errors, n, p):
    assert study.binomial_tail(errors, n, 0.05) == pytest.approx(p, rel=1e-12)


def test_the_exact_tail_matches_a_direct_sum():
    direct = math.fsum(math.comb(177, k) * 0.05 ** k * 0.95 ** (177 - k)
                       for k in range(11, 178))
    assert study.binomial_tail(11, 177, 0.05) == pytest.approx(direct, rel=1e-9)


def test_the_lower_bound_has_known_values():
    assert study.error_lower_bound(0, 50) == 0.0
    assert study.error_lower_bound(1, 1) == pytest.approx(0.05, abs=1e-6)
    assert study.error_lower_bound(2, 2) == pytest.approx(math.sqrt(0.05), abs=1e-6)
    assert study.error_lower_bound(0, 0) is None


def test_the_upper_bound_is_the_repository_one_rounded_up():
    assert study.error_upper_bound(0, 299) <= 0.01 < study.error_upper_bound(0, 298)
    assert study.error_upper_bound(0, 0) is None


@pytest.mark.parametrize("n", [20, 100, 177, 500])
def test_the_lower_bound_exceeds_the_target_exactly_when_the_tail_is_below_alpha(n):
    """Clopper–Pearson duality: the one-sided 95 % lower bound is above 5 % if and only if
    P(X >= errors | 5 %) < 0.05, which is what lets Holm adjust the transfer tests."""
    for e in range(n + 1):
        lower = study.error_lower_bound(e, n, rounding=False)
        assert (lower > 0.05) == (study.binomial_tail(e, n, 0.05) < 0.05), (e, n)


# --- the transfer test: cross-fit and pooling ---------------------------------------------


def _rows(spec: list[tuple[float | None, bool]]) -> list[dict]:
    return [{"status": "scored" if c is not None else "no_answer", "confidence": c,
             "correct": ok} for c, ok in spec]


def test_each_half_validates_on_english_and_counts_the_other_halfs_target_rows():
    """English: every row right at 0.9, so each half validates 0.9. Target: right at 0.95
    except every 5th item, wrong at 0.95; items 3 mod 10 at 0.5, below the threshold. The
    pooled count is every target row at or above 0.9, from both halves, once each."""
    n = 400
    halves = study.item_halves([str(i) for i in range(n)])
    source = _rows([(0.9, True)] * n)
    target = _rows([(0.5 if i % 10 == 3 else 0.95, i % 5 != 0) for i in range(n)])
    t = study.transfer_test(source, target, halves)
    assert t["run"] and [f["threshold"] for f in t["folds"]] == [0.9, 0.9]
    above = [i for i in range(n) if i % 10 != 3]
    assert t["pooled"]["n"] == len(above) == 360
    assert t["pooled"]["errors"] == sum(1 for i in above if i % 5 == 0) == 80
    for f, test_half in zip(t["folds"], (halves[1], halves[0]), strict=True):
        assert f["target"]["covered"] == sum(1 for i in test_half if i % 10 != 3)
    assert t["pooled"]["n"] == sum(f["target"]["covered"] for f in t["folds"])
    assert t["control"] == {"n": n, "errors": 0, "error_rate": 0.0,
                            "upper_95": study.error_upper_bound(0, n)}
    assert t["pooled"]["lower_95"] > 0.05 and t["pooled"]["p_exact"] < 1e-6


def test_target_rows_without_a_confidence_are_never_above_the_threshold():
    n = 400
    halves = study.item_halves([str(i) for i in range(n)])
    target = _rows([(None, False) if i % 2 else (0.95, True) for i in range(n)])
    t = study.transfer_test(_rows([(0.9, True)] * n), target, halves)
    assert t["pooled"]["n"] == n // 2 and t["pooled"]["errors"] == 0


def test_the_start_rule_needs_the_two_error_cut():
    """124 rows validate 5 % with 2 errors: a half of 240 English rows validates, a half of
    120 cannot start, and the test is not run, with the reason."""
    ok = study.transfer_test(_rows([(0.9, True)] * 480), _rows([(0.9, True)] * 480),
                             study.item_halves([str(i) for i in range(480)]))
    assert ok["run"]
    small = study.transfer_test(_rows([(0.9, True)] * 240), _rows([(0.9, True)] * 240),
                                study.item_halves([str(i) for i in range(240)]))
    assert not small["run"] and "fewer than the 124" in small["reason"]
    assert small["pooled"]["p_exact"] is None


def test_one_half_that_validates_is_enough_to_run_the_test():
    """English validates on half A only (half A all right, half B half wrong): the test runs
    on what half A's threshold admits in half B's target rows; half B adds nothing."""
    n = 400
    a, b = study.item_halves([str(i) for i in range(n)])
    in_b = set(b)
    source = _rows([(0.9, not (i in in_b and i % 2 == 0)) for i in range(n)])
    t = study.transfer_test(source, _rows([(0.95, True)] * n), (a, b))
    assert [f["threshold"] is not None for f in t["folds"]] == [True, False]
    assert t["run"] and t["pooled"]["n"] == len(b)
    assert t["folds"][1]["target"]["covered"] == 0 and t["folds"][1]["reason"]


# --- Holm across the six with m = 6 fixed -------------------------------------------------


def test_holm_keeps_six_tests_and_a_test_not_run_counts_as_not_resolved():
    tests = {"T1": {"run": True, "pooled": {"p_exact": 0.001, "n": 200, "errors": 22}},
             "T2": {"run": True, "pooled": {"p_exact": 0.009, "n": 300, "errors": 25}},
             "T3": {"run": False, "pooled": {"p_exact": None}},
             "T4": {"run": True, "pooled": {"p_exact": 0.02}},
             "T5": {"run": True, "pooled": {"p_exact": 0.5}},
             "T6": {"run": True, "pooled": {"p_exact": 0.3}}}
    study.settle(tests)
    assert tests["T1"]["p_holm"] == pytest.approx(0.006)     # 6 x, not 5 x
    assert tests["T2"]["p_holm"] == pytest.approx(0.045)
    assert tests["T4"]["p_holm"] == pytest.approx(0.08)
    assert [tests[t]["resolved"] for t in tests] == [True, True, False, False, False, False]
    assert tests["T3"]["p_for_holm"] == 1.0 and tests["T3"]["outcome"] == "not run"
    # the bound at the level of each test's Holm step: 0.05 / 6 for the smallest p, then / 5
    assert tests["T1"]["holm_level"] == pytest.approx(0.05 / 6)
    assert tests["T2"]["holm_level"] == pytest.approx(0.05 / 5)
    assert tests["T1"]["lower_at_holm_level"] == study.error_lower_bound(22, 200, 0.05 / 6)
    assert tests["T2"]["lower_at_holm_level"] == study.error_lower_bound(25, 300, 0.05 / 5)
    assert tests["T2"]["lower_at_holm_level"] < study.error_lower_bound(25, 300)
    assert tests["T3"]["lower_at_holm_level"] is None and tests["T4"]["holm_level"] == 0.05 / 4


def test_the_holm_level_bound_is_not_shown_after_the_first_failing_step():
    """32 / 407 fails at α/6; 37 / 491 has p below α/5 but Holm has already stopped, so its
    bound at α/5 (above 5 %) would contradict "not resolved": it is not shown."""
    p1, p2 = study.binomial_tail(32, 407, 0.05), study.binomial_tail(37, 491, 0.05)
    assert 0.05 / 6 < p1 < p2 < 0.05 / 5
    assert study.error_lower_bound(37, 491, 0.05 / 5) > 0.05
    tests = {"T1": {"run": True, "pooled": {"p_exact": p1, "n": 407, "errors": 32}},
             "T2": {"run": True, "pooled": {"p_exact": p2, "n": 491, "errors": 37}},
             "T3": {"run": True, "pooled": {"p_exact": 0.4, "n": 300, "errors": 16}},
             "T4": {"run": True, "pooled": {"p_exact": 0.6, "n": 300, "errors": 14}},
             "T5": {"run": False, "pooled": {"p_exact": None}},
             "T6": {"run": True, "pooled": {"p_exact": 0.9, "n": 300, "errors": 10}}}
    study.settle(tests)
    assert [tests[t]["outcome"] for t in ("T1", "T2")] == ["not resolved", "not resolved"]
    assert tests["T1"]["lower_at_holm_level"] == study.error_lower_bound(32, 407, 0.05 / 6)
    assert tests["T1"]["lower_at_holm_level"] <= 0.05 and not tests["T1"]["holm_stopped"]
    for t in ("T2", "T3", "T4", "T5", "T6"):
        assert tests[t]["lower_at_holm_level"] is None and tests[t]["holm_stopped"], t
    stub = {"judge": "j", "target_locale": "x-X", "partial": [], "prediction": None,
            "as_predicted": None, "folds": [], "control": {"n": 0, "errors": 0}}
    empty = {"n": 0, "errors": 0, "error_rate": None, "lower_95": None, "upper_95": None}
    rows: list[str] = []
    study._transfer_table(rows.append,
                          {k: {**v, **stub, "pooled": {**empty, **v["pooled"]}}
                           for k, v in tests.items()}, full=True, plabels={})
    t2 = next(r for r in rows if r.startswith("| T2 "))
    assert "— (Holm stopped at an earlier step)" in t2 and "(α / 5)" not in t2


def test_holm_refuses_a_family_that_is_not_six():
    with pytest.raises(ValueError, match="6"):
        study.settle({"T1": {"run": True, "pooled": {"p_exact": 0.01}}})


def test_the_study_family_on_synthetic_checkpoints(result):
    T = result["analyses"]["primary"]["transfer"]
    assert list(T) == ["T1", "T2", "T3", "T4", "T5", "T6"]
    by = {(v["judge"], v["target_locale"]): v for v in T.values()}
    jev_ca, jev_es = by[("jev", "ca-ES")], by[("jev", "es-ES")]
    # every jev target row is at 0.95, above any English threshold: all 300 items counted
    assert (jev_ca["pooled"]["n"], jev_ca["pooled"]["errors"]) == (300, 15)
    assert (jev_es["pooled"]["n"], jev_es["pooled"]["errors"]) == (300, 60)
    assert jev_es["resolved"] and not jev_ca["resolved"]
    assert [f["validated_on"] for f in jev_ca["folds"]] == ["A", "B"]
    assert all(f["threshold"] is not None for f in jev_ca["folds"])
    assert jev_ca["partial"] == []
    for loc in ("ca-ES", "es-ES"):
        c = by[("claude-sonnet-4.5", loc)]
        assert not c["run"] and c["outcome"] == "not run" and c["reason"]
    assert jev_ca["prediction"] == "not resolved" and jev_ca["as_predicted"] is True
    assert jev_es["prediction"] == "not resolved" and jev_es["as_predicted"] is False


# --- predictions are read, never written ---------------------------------------------------


def test_without_predictions_the_tests_are_named_by_judge_and_locale(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"), predictions=False)
    r = compute(t)
    T = r["analyses"]["primary"]["transfer"]
    assert "jev/ca-ES" in T and T["jev/ca-ES"]["prediction"] is None
    assert T["jev/ca-ES"]["as_predicted"] is None and r["inputs"]["predictions"] is None


PLAN_TABLE = """# plan

## 6. Tests

| id | judge | target locale | prediction |
|---|---|---|---|
| T1 | Jev | `ca-ES` | resolved (some words) |
| T2 | gpt-6-luna | `ca-ES` | not resolved |
| T3 | claude-sonnet-4.5 | `ca-ES` | not resolved |
| T4 | Jev | `es-ES` | not resolved |
| T5 | gpt-6-luna | `es-ES` | resolved (some words) |
| T6 | claude-sonnet-4.5 | `es-ES` | not resolved |

| id | something else | prediction |
|---|---|---|
| T1 Jev `ca-ES` | 1 | resolved |
"""


def _plan(root: Path, text: str = PLAN_TABLE, sha: str | None = None) -> Path:
    plan = root / "docs" / "v06-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(text, encoding="utf-8")
    (root / "docs" / "v06-plan.sha256").write_text(
        f"{sha or sha256_of(str(plan))}  v06-plan.md\n", encoding="utf-8")
    return plan


def test_the_predictions_are_parsed_from_the_plan_once_its_hash_matches(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"), predictions=False)
    plan = _plan(tmp_path)
    r = compute(t)
    T = r["analyses"]["primary"]["transfer"]
    assert list(T) == ["T1", "T2", "T3", "T4", "T5", "T6"]
    assert (T["T1"]["judge"], T["T1"]["target_locale"], T["T1"]["prediction"]) == (
        "jev", "ca-ES", "resolved")
    assert T["T5"]["prediction"] == "resolved" and T["T6"]["prediction"] == "not resolved"
    assert r["inputs"]["predictions"] == {"path": "docs/v06-plan.md",
                                          "sha256": sha256_of(str(plan)),
                                          "verified_against": "docs/v06-plan.sha256"}


def test_a_plan_whose_hash_differs_is_refused(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"), predictions=False)
    _plan(tmp_path, sha="0" * 64)
    with pytest.raises(SystemExit, match="sha256"):
        compute(t)


def test_a_plan_without_the_table_is_refused(tmp_path):
    _plan(tmp_path, text="# plan\n\nno table here\n")
    with pytest.raises(SystemExit, match="table"):
        study.load_plan_predictions(tmp_path)


def test_an_explicit_predictions_file_overrides_the_plan(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    _plan(tmp_path, sha="0" * 64)             # never read when a file is given
    r = compute(t)
    assert r["inputs"]["predictions"]["path"] == "predictions.json"


def test_a_predictions_file_must_cover_the_six_tests(tmp_path):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"tests": {"T1": {"judge": "jev", "target_locale": "ca-ES",
                                              "prediction": "resolved"}}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="six"):
        study.load_predictions(p, tmp_path)
    p.write_text(json.dumps({"tests": {f"T{i}": {"judge": j, "target_locale": loc,
                                                 "prediction": "maybe"}
                                       for i, (loc, j) in enumerate(
                                           ((loc, j) for loc in ("ca-ES", "es-ES")
                                            for j in study.PRIMARY), 1)}}),
                 encoding="utf-8")
    with pytest.raises(SystemExit, match="prediction"):
        study.load_predictions(p, tmp_path)


# --- overconfidence, paired and clustered -------------------------------------------------


def _expected_overconfidence(slug: str, locale: str, items) -> float:
    rs = [_behaviour(slug, locale, i) for i in items]
    conf = [c for _, c, st, _ in rs]
    ok = [d == OPTIONS[i % 3] for (d, *_), i in zip(rs, items, strict=True)]
    return sum(conf) / len(conf) - sum(ok) / len(ok)


def test_overconfidence_is_mean_confidence_minus_accuracy_on_items_usable_in_both(result):
    h = result["analyses"]["primary"]["overconfidence"]["gpt-6-luna"]["es-ES - en-US"]
    pair = [i for i in range(N_ITEMS) if i % 50 != 0]        # es-ES refusals left out
    assert h["items"] == len(pair) == 294
    exp = (_expected_overconfidence("gpt-6-luna", "es-ES", pair)
           - _expected_overconfidence("gpt-6-luna", "en-US", pair))
    assert h["difference"] == pytest.approx(exp, abs=1e-6)
    lo, hi = h["ci"]
    assert lo <= h["difference"] <= hi
    assert h["resolved"] == (lo > 0 or hi < 0)
    assert h["sign"] == "+"                                 # +0.098: es above en
    assert result["analyses"]["primary"]["overconfidence"]["claude-sonnet-4.5"][
        "es-ES - en-US"]["sign"] == "0"


def test_the_sign_of_a_paired_difference():
    assert study.sign_of(0.01) == "+"
    assert study.sign_of(-0.01) == "−"
    assert study.sign_of(0.0) == "0"
    assert study.sign_of(None) is None


def test_the_bootstrap_is_deterministic_and_does_not_depend_on_the_processes(tree):
    one = compute(tree, jobs=1)
    again = compute(tree, jobs=1)
    two = compute(tree, jobs=2)
    assert one == again == two


def test_the_overconfidence_interval_is_the_seeded_clustered_bootstrap():
    import random
    rng = random.Random(7)
    a = [(rng.random(), rng.random() < 0.7) for _ in range(120)]
    b = [(rng.random(), rng.random() < 0.7) for _ in range(120)]
    ids = [f"i{k}" for k in range(120)]
    got = study.paired_overconfidence(a, b, ids, n_boot=300)
    ref = paired_difference_ci(a, b, study.overconfidence, 300, 2026, ids)
    other = paired_difference_ci(a, b, study.overconfidence, 300, 2027, ids)
    assert got["ci"] == [round(x, 6) for x in ref.ci[:2]]
    assert got["ci"] != [round(x, 6) for x in other.ci[:2]]


def test_the_paired_bootstrap_resamples_items():
    a = [(0.9, True), (0.8, False), (0.7, True)]
    b = [(0.6, True), (0.6, True), (0.5, False)]
    ids = ["x", "y", "z"]
    r1 = study.paired_overconfidence(a, b, ids, n_boot=200)
    r2 = study.paired_overconfidence(a, b, ids, n_boot=200)
    assert r1 == r2
    assert r1["difference"] == pytest.approx((0.8 - 2 / 3) - (17 / 30 - 2 / 3), abs=1e-6)


# --- E1: a vendor's own field against P(chosen option) ------------------------------------


def test_e1_is_computed_only_where_a_native_field_is_recorded(result):
    e1 = result["analyses"]["primary"]["e1"]
    assert {k.split("/")[0] for k in e1} == {"gpt-6-luna", "decision2-kai-0.6b"}
    g = e1["gpt-6-luna/en-US"]
    assert g["field"] == "native_confidence" and g["rows"] == N_ITEMS
    assert e1["decision2-kai-0.6b/en-US"]["field"] == "entropy_confidence"
    assert g["difference"] == pytest.approx(g["auroc_native"] - g["auroc_chosen"], abs=2e-6)


# --- secondary metrics ----------------------------------------------------------------------


def test_secondary_metrics_per_locale_and_judge(result):
    m = result["analyses"]["primary"]["metrics"]
    jev = m["jev/en-US"]
    assert jev["role"] == "primary" and jev["n"] == N_ITEMS and jev["right"] == 298
    assert jev["accuracy_wilson"][0] < jev["accuracy"] < jev["accuracy_wilson"][1]
    assert {"auroc", "ece", "mce", "brier", "cost_usd", "latency_p50_s"} <= set(jev)
    assert set(jev["validated_coverage"]) == {"0.01", "0.02", "0.05", "0.1"}
    assert [x["confidence_at_least"] for x in jev["high_confidence_error"]] == [0.9, 0.95, 0.99]
    assert m["decision2-kai-0.6b/en-US"]["role"] == "exploratory"
    luna = m["gpt-6-luna/es-ES"]
    assert luna["no_answer"] == 6 and luna["scored"] == 294
    assert "composite" not in json.dumps(result)


# --- sensitivity: items removed in all three locales ---------------------------------------


def test_majority_no_rows_remove_the_item_in_every_locale(result):
    s = result["analyses"]["without_majority_no"]
    assert s["removed_items"] == 1 and s["items"] == N_ITEMS - 1
    assert result["items"]["majority_no"] == {"es-ES": 0, "ca-ES": 1, "items": 1}
    assert s["metrics"]["jev/en-US"]["n"] == N_ITEMS - 1      # removed in English too


def test_the_sensitivity_analyses_keep_the_primary_halves(result):
    """Same halves minus the removed items: never a new split of what remains."""
    a, b = split_by_group([str(1000 + i) for i in range(N_ITEMS)], 2026)
    side = 0 if 5 in a else 1
    sizes = [len(a), len(b)]
    sizes[side] -= 1
    assert result["analyses"]["without_majority_no"]["halves"]["sizes"] == sizes
    o = [len(a), len(b)]
    for i in (9, 11):
        o[0 if i in a else 1] -= 1
    assert result["analyses"]["without_train_dev_overlap"]["halves"]["sizes"] == o
    assert study.subset_halves((a, b), [i for i in range(N_ITEMS) if i != 5]) == (
        [x - (x > 5) for x in a if x != 5], [x - (x > 5) for x in b if x != 5])


def test_text_overlap_removes_the_union_of_items(result):
    s = result["analyses"]["without_train_dev_overlap"]
    assert s["removed_items"] == 2 and s["items"] == N_ITEMS - 2
    assert result["items"]["train_dev_overlap"] == {"en-US": 1, "es-ES": 0, "ca-ES": 1,
                                                    "items": 2}
    assert set(s["transfer"]) == set(result["analyses"]["primary"]["transfer"])


# --- inputs: hashes, files never read -------------------------------------------------------


def test_every_input_is_hashed_and_paths_are_relative(result, tree):
    inp = result["inputs"]
    assert set(inp["labels"]) == set(LOCALES)
    for v in inp["labels"].values():
        assert v["sha256"] == sha256_of(str(tree["root"] / v["path"]))
    ck = inp["checkpoints"]["jev/en-US"]
    assert ck["sha256"] == sha256_of(str(tree["runs"] / "jev-en-US.ckpt.jsonl"))
    assert ck["rows"] == N_ITEMS and not ck["path"].startswith("/")
    assert inp["predictions"]["sha256"] == sha256_of(str(tree["predictions"]))
    assert str(tree["root"]) not in json.dumps(result)


def test_a_duplicate_writes_file_enters_no_figure_and_only_its_cost_is_read(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    clean = compute(t)
    bad = t["runs"] / "jev-en-US.ckpt.duplicate-writes.jsonl"
    good = (t["runs"] / "jev-en-US.ckpt.jsonl").read_text(encoding="utf-8").splitlines()
    # every row twice, all answers wrong: a figure computed from it would move
    rows = [json.loads(ln) for ln in good[1:]]
    for rec in rows:
        rec["judgments"][0]["decision"] = "nonsense"
    bad.write_text("\n".join([good[0]] + [json.dumps(x) for x in rows + rows]) + "\n",
                   encoding="utf-8")
    r = compute(t)
    assert r["analyses"] == clean["analyses"]
    assert r["inputs"]["excluded"] == [{"file": bad.name, "sha256": sha256_of(str(bad)),
                                        "reason": study.DUPLICATE_WRITES}]
    inc = r["cost"]["excluded"]
    assert inc == [{"file": bad.name, "lines": 2 * N_ITEMS, "recorded_usd": 0.6,
                    "unknown_cost_judgments": 0}]
    assert r["cost"]["total_usd"] == pytest.approx(r["cost"]["read_usd"] + 0.6)


def test_an_unreadable_duplicate_writes_file_has_no_recorded_cost(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    bad = t["runs"] / "jev-en-US.ckpt.duplicate-writes.jsonl"
    bad.write_text("this is not json\n", encoding="utf-8")
    r = compute(t)
    assert r["cost"]["excluded"][0]["recorded_usd"] is None
    assert r["cost"]["excluded"][0]["note"] == "unreadable"


def test_the_cost_table_per_judge_and_locale(result):
    c = result["cost"]
    assert c["per_judge"]["jev"] == {"en-US": 0.3, "es-ES": 0.3, "ca-ES": 0.3, "total": 0.9}
    ck = c["checkpoints"]["jev/en-US"]
    assert ck == {"recorded_usd": 0.3, "unknown_cost_judgments": 0, "max_usd": None,
                  "max_usd_history": []}
    assert c["read_usd"] == pytest.approx(0.3 * 12) and c["excluded"] == []


def test_a_checkpoint_with_a_row_written_twice_is_refused(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = t["runs"] / "jev-es-ES.ckpt.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines + [lines[5]]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="more than once"):
        compute(t)


def test_a_checkpoint_of_another_labels_file_is_refused(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = t["runs"] / "jev-es-ES.ckpt.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    head["run"]["dataset"]["sha256"] = "0" * 64
    p.write_text("\n".join([json.dumps(head)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="another labels file"):
        compute(t)


def test_a_slug_whose_judge_differs_across_locales_is_refused(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = t["runs"] / "jev-es-ES.ckpt.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    head["run"]["judge"]["model"] = "another-model"
    p.write_text("\n".join([json.dumps(head)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="another judge or model"):
        compute(t)


def test_a_row_index_outside_the_labels_is_refused(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = t["runs"] / "jev-es-ES.ckpt.jsonl"
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[1])
    rec["idx"] = N_ITEMS
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    with pytest.raises(SystemExit, match="outside"):
        compute(t)


def test_a_missing_primary_checkpoint_stops_the_analysis(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna"))
    with pytest.raises(study.MissingCheckpoints, match="claude-sonnet-4.5/en-US"):
        compute(t)


def test_an_incomplete_checkpoint_is_analysed_on_its_completed_rows_only(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    massive = t["root"] / "examples" / "massive"
    _write_checkpoint(t["runs"] / "jev-ca-ES.ckpt.jsonl", massive / "labels-test-ca-ES.jsonl",
                      "jev", "ca-ES", "jev", rows=250)
    r = compute(t)
    m = r["analyses"]["primary"]["metrics"]["jev/ca-ES"]
    assert m["n"] == 250 and m["missing"] == 0                # unjudged rows never wrong
    assert m["right"] == sum(1 for i in range(250) if i % 20)
    label = "partial: 250 of 300 (incomplete)"
    assert m["partial"] == label
    assert r["inputs"]["checkpoints"]["jev/ca-ES"]["partial"] == label
    T = {(v["judge"], v["target_locale"]): v
         for v in r["analyses"]["primary"]["transfer"].values()}
    assert T[("jev", "ca-ES")]["run"] and T[("jev", "ca-ES")]["pooled"]["n"] == 250
    assert T[("jev", "ca-ES")]["partial"] == ["jev/ca-ES"]
    assert T[("jev", "es-ES")]["partial"] == []
    assert r["analyses"]["primary"]["overconfidence"]["jev"]["ca-ES - es-ES"]["partial"] == [
        "jev/ca-ES"]
    md = study.markdown(r)
    assert md.count(label) >= 5


def test_a_checkpoint_stopped_at_its_ceiling_says_so(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    massive = t["root"] / "examples" / "massive"
    _write_checkpoint(t["runs"] / "jev-ca-ES.ckpt.jsonl", massive / "labels-test-ca-ES.jsonl",
                      "jev", "ca-ES", "jev", rows=250, max_usd=0.25,
                      max_usd_history=[{"max_usd": 0.1, "until_rows": 90}])
    r = compute(t)
    assert r["inputs"]["checkpoints"]["jev/ca-ES"]["partial"] == (
        "partial: 250 of 300 (stopped at its ceiling)")
    ck = r["cost"]["checkpoints"]["jev/ca-ES"]
    assert "$0.25 |" in study.markdown(r)
    assert ck["max_usd"] == 0.25 and ck["max_usd_history"] == [{"max_usd": 0.1,
                                                                "until_rows": 90}]


def test_a_served_model_that_changes_is_reported_by_segment(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = t["runs"] / "jev-es-ES.ckpt.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    out = [lines[0]]
    for ln in lines[1:]:
        rec = json.loads(ln)
        if rec["idx"] >= 200:
            rec["judgments"][0]["raw"]["served"]["model"] = "jev-next"
        out.append(json.dumps(rec))
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    r = compute(t)
    assert r["inputs"]["checkpoints"]["jev/es-ES"]["served"] == {"jev": 200, "jev-next": 100}
    seg = r["analyses"]["primary"]["served_segments"]["jev/es-ES"]
    assert [s["n"] for s in seg.values()] == [200, 100]


# --- outputs and --check ---------------------------------------------------------------------


def test_a_ceiling_is_printed_exactly_as_its_header_records_it(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    massive = t["root"] / "examples" / "massive"
    _write_checkpoint(t["runs"] / "gpt-6-luna-es-ES.ckpt.jsonl",
                      massive / "labels-test-es-ES.jsonl", "gpt-6-luna", "es-ES",
                      "openai-decisions", max_usd=2.718281,
                      max_usd_history=[{"max_usd": 1.234567, "until_rows": 12}])
    md = study.markdown(compute(t))
    assert "$2.718281" in md and "$2.71828 " not in md and "$2.71828|" not in md
    assert "ceiling $1.234567 until row 12" in md


def test_check_mode_regenerates_and_diffs(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    md, js = tmp_path / "README.md", tmp_path / "results.json"
    args = ["--runs", str(t["runs"]), "--root", str(t["root"]), "--predictions",
            str(t["predictions"]), "--out-md", str(md), "--out-json", str(js),
            "--n-boot", "30", "--jobs", "1"]
    assert study.main(args) == 0
    assert study.main(args + ["--check"]) == 0
    md.write_text(md.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
    assert study.main(args + ["--check"]) == 1
    text = js.read_text(encoding="utf-8")
    assert json.loads(text)["parameters"]["n_boot"] == 30


def test_the_report_carries_the_caveats_and_no_banned_wording(result):
    md = study.markdown(result)
    assert "translated parallel data, not native traffic" in md
    assert "exploratory" in md and "Holm" in md
    assert "lower at its Holm level" in md and "sign" in md
    assert "## 10. Cost" in md
    assert md.count("only the transfer-test halves are fixed") == 2      # §5 and §7
    assert "‡" in md and md.index("‡") == md.index(study.DEGENERATE_NOTE) + 2
    low = md.lower()
    for word in ("certified", "guaranteed", "compliant", "at most"):
        assert word not in low, word
    for line in md.splitlines():
        if "decision2-kai-0.6b" in line and line.startswith("|"):
            assert "exploratory" in line


# --- exploratory refusal views (amendment A4) -----------------------------------------------


def test_refusal_views_cover_every_locale_of_a_judge_that_refused(result):
    v = result["exploratory_refusals"]
    assert v["label"] == "exploratory, not pre-registered (amendment A4)"
    assert list(v["views"]) == ["gpt-6-luna/en-US", "gpt-6-luna/es-ES", "gpt-6-luna/ca-ES"]
    assert [v["views"][k]["refused"] for k in v["views"]] == [0, 6, 0]


def test_metrics_without_refused_rows_sit_next_to_the_plans(result):
    es = result["exploratory_refusals"]["views"]["gpt-6-luna/es-ES"]
    plan = result["analyses"]["primary"]["metrics"]["gpt-6-luna/es-ES"]
    assert es["plan"]["n"] == plan["n"] == N_ITEMS
    assert es["plan"]["accuracy"] == plan["accuracy"]
    w = es["without_refusals"]
    assert w["n"] == N_ITEMS - 6 and w["no_answer"] == 0
    right = sum(1 for i in range(N_ITEMS) if i % 50 and i % 8)
    assert w["right"] == right == plan["right"]
    assert w["accuracy"] == round(right / (N_ITEMS - 6), 6) > plan["accuracy"]
    assert set(w["validated_coverage"]) == {"0.01", "0.02", "0.05", "0.1"}
    for key in ("auroc", "ece", "mce", "brier"):
        assert key in w and key in es["plan"]


def test_refusals_are_counted_by_scenario_and_by_gold_intent(result):
    es = result["exploratory_refusals"]["views"]["gpt-6-luna/es-ES"]
    # refused items 0, 50, …, 250: two per intent, each intent holds 100 of the 300 rows
    assert es["by_scenario"] == {s: {"refused": 2, "rows": 100, "share": 0.02}
                                 for s in ("alarm", "play", "weather")}
    assert es["by_intent"] == {o: {"refused": 2, "rows": 100, "share": 0.02} for o in OPTIONS}
    en = result["exploratory_refusals"]["views"]["gpt-6-luna/en-US"]
    assert en["by_scenario"] == {} and en["by_intent"] == {}


def test_refusal_views_enter_no_test(tmp_path):
    """The same checkpoints without the refusal flag give the same tests, overconfidence
    and plan metrics: the views add a key, nothing else."""
    flagged = build(tmp_path / "a", judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    plain = build(tmp_path / "b", judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    p = plain["runs"] / "gpt-6-luna-es-ES.ckpt.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace(', "refusal": true', ""),
                 encoding="utf-8")
    a, b = compute(flagged), compute(plain)
    assert a["analyses"] == b["analyses"]
    assert a["exploratory_refusals"]["views"] and not b["exploratory_refusals"]["views"]


def test_a_refused_row_of_a_partial_checkpoint_counts_once_and_unjudged_rows_never(tmp_path):
    t = build(tmp_path, judges=("jev", "gpt-6-luna", "claude-sonnet-4.5"))
    massive = t["root"] / "examples" / "massive"
    _write_checkpoint(t["runs"] / "gpt-6-luna-es-ES.ckpt.jsonl",
                      massive / "labels-test-es-ES.jsonl", "gpt-6-luna", "es-ES",
                      "openai-decisions", rows=120)
    es = compute(t)["exploratory_refusals"]["views"]["gpt-6-luna/es-ES"]
    assert es["refused"] == 3 and es["judged"] == 120 and es["partial"]
    assert es["without_refusals"]["n"] == 117
    assert sum(x["rows"] for x in es["by_intent"].values()) == 120


def test_every_refusal_row_of_the_report_carries_the_label(result):
    md = study.markdown(result)
    sec = md[md.index("## 11."):]
    label = "exploratory, not pre-registered (amendment A4)"
    rows = [ln for ln in sec.splitlines() if ln.startswith("| gpt-6-luna")]
    assert rows and all(label in ln for ln in rows)
    assert "without refused rows" in sec and "plan's figures" in sec
