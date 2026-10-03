"""Results of the v0.5 study (#91), as pre-registered in docs/v05-plan.md. No model call.

The plan was frozen at tag `v05-plan-freeze` before the study's first call; amendments 1 and
2 (§11) were committed before the calls or the analysis they govern. This script reads the
study's checkpoints in docs/runs/v05/ and the labels they judged, and writes
docs/v05-results.md and .json: the confirmatory tests of §6 with Holm, under the
pre-registered scoring rule and amendment 2's declared re-reading; the verdict of record;
the secondary metrics and the certification table of §7; the log-probability near-ties of
amendment 1; the exploratory studies E1 and E2 (§6b) and the repeats (§5).

  python scripts/v05_study.py            # writes docs/v05-results.md and .json
  python scripts/v05_study.py --check    # exit 1 if either differs; 2 if a checkpoint is missing

Deterministic: every interval and test is the repository's clustered bootstrap
(`metrics.selective`), seed 2026, 10,000 resamples, texts grouped by the repository's
normalisation (lower case, runs of whitespace collapsed). The bootstraps run in parallel
processes (`--jobs`); each one is seeded on its own, so the output does not depend on how
many there are.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_resumable import load_checkpoint  # noqa: E402
from relabel import wilson_interval  # noqa: E402

from judge_audit.judges.llm import parse_reply, vote  # noqa: E402
from judge_audit.metrics.calibration import (  # noqa: E402
    brier_score,
    expected_calibration_error,
    negative_log_likelihood,
    nll_infinite,
    worst_calibration_bin,
    zero_error_coverage,
)
from judge_audit.metrics.selective import (  # noqa: E402
    aurc,
    bootstrap_defined,
    coverage_at_risk_crossfit,
    failure_auroc,
    holm,
    mcnemar_exact,
    paired_difference_ci,
    paired_difference_test,
)
from judge_audit.runner import (  # noqa: E402
    checkpoint_record,
    is_correct,
    load_dataset,
    questions_of,
    sha256_of,
)

RUNS_DIR = ROOT / "docs" / "runs" / "v05"
OUT_MD = ROOT / "docs" / "v05-results.md"
OUT_JSON = ROOT / "docs" / "v05-results.json"
SEED = 2026
N_BOOT = 10_000
ALPHA = 0.05
TARGETS = [0.01, 0.02, 0.05, 0.10]            # §7, D2
PLAIN = {0.01: "at most 1 in 100 automated decisions wrong",
         0.02: "at most 1 in 50 automated decisions wrong",
         0.05: "at most 1 in 20 automated decisions wrong",
         0.10: "at most 1 in 10 automated decisions wrong"}
START_ERRORS = 2                               # §7, D3
SPREAD_SEEDS = list(range(2027, 2037))         # §7: the split's spread over seeds, secondary
NEAR_TIE = 0.5                                 # amendment 1: top-two log-odds margin
MARGIN_TOL = 2e-6      # the checkpoint rounds each log-probability to 1e-6 (error 5e-7
                       # each), so a margin is known to within 1e-6; twice that, so float
                       # arithmetic never decides a margin bfloat16 put exactly on 0.5
READINGS = ("strict", "reread")                # amendment 2

REAL = ["banking77", "clinc150"]
SYNTHETIC = ["email-routing-v2", "email-routing-adversarial-v2", "task-routing-v2"]
LABELS = {"banking77": "examples/banking77/labels-test.jsonl",
          "clinc150": "examples/clinc150/labels-test-banking-credit.jsonl",
          **{d: f"examples/{d}/labels.jsonl" for d in SYNTHETIC}}
SPLITS = {d: f"examples/{d}/split-templates.json" for d in SYNTHETIC}
NAME = {"banking77": "BANKING77", "clinc150": "CLINC150", **{d: d for d in SYNTHETIC}}

# slug -> (judge, method, adapter, samples, prompt template); prompt digests from §6b
QWEN, GEMINI, JEV, LAYA = "Qwen3-8B", "gemini-3.6-flash", "Jev", "Laya"
METHODS = {
    "jev": (JEV, "native probability", "jev", 1, None),
    "jev-r2": (JEV, "native probability, repeat 2", "jev", 1, None),
    "jev-r3": (JEV, "native probability, repeat 3", "jev", 1, None),
    "laya": (LAYA, "probability of the chosen option", "laya", 1, None),
    "llm-qwen3-8b": (QWEN, "verbalized", "llm", 1, "v1"),
    "llm-qwen3-8b-r2": (QWEN, "verbalized, repeat 2", "llm", 1, "v1"),
    "llm-qwen3-8b-r3": (QWEN, "verbalized, repeat 3", "llm", 1, "v1"),
    "llm-qwen3-8b-prompt-v2": (QWEN, "verbalized, prompt v2", "llm", 1, "v2"),
    "llm-qwen3-8b-sc10": (QWEN, "self-consistency (k = 10)", "llm", 10, "v1"),
    "logprob-qwen3-8b": (QWEN, "token log-probability", "logprob", 1, "v1"),
    "logprob-qwen3-8b-prompt-v2": (QWEN, "token log-probability, prompt v2", "logprob", 1, "v2"),
    "llm-gemini-3.6-flash": (GEMINI, "verbalized", "llm", 1, "v1"),
    "llm-gemini-3.6-flash-prompt-v2": (GEMINI, "verbalized, prompt v2", "llm", 1, "v2"),
    "llm-gemini-3.6-flash-sc5": (GEMINI, "self-consistency (k = 5)", "llm", 5, "v1"),
}
PROMPT_SHA = {("llm", "v1"): "fe16e59a", ("llm", "v2"): "ab4f0875",
              ("logprob", "v1"): "e3f03049", ("logprob", "v2"): "3b739001"}
QWEN_REVISION = "545dc4251c05440727734bcd94334791f6ab0192"
LAYA_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"

PRIMARY = ["jev", "laya", "llm-qwen3-8b", "llm-qwen3-8b-sc10", "logprob-qwen3-8b",
           "llm-gemini-3.6-flash", "llm-gemini-3.6-flash-sc5"]
PLANNED = {
    "banking77": PRIMARY + ["jev-r2", "jev-r3", "llm-qwen3-8b-r2", "llm-qwen3-8b-r3",
                            "llm-qwen3-8b-prompt-v2", "logprob-qwen3-8b-prompt-v2",
                            "llm-gemini-3.6-flash-prompt-v2"],
    "clinc150": PRIMARY,
    **{d: ["jev", "laya", "llm-qwen3-8b", "logprob-qwen3-8b", "llm-gemini-3.6-flash"]
       for d in SYNTHETIC},
}
BEST_OF = {QWEN: ["logprob-qwen3-8b", "llm-qwen3-8b", "llm-qwen3-8b-sc10"],
           GEMINI: ["llm-gemini-3.6-flash", "llm-gemini-3.6-flash-sc5"]}
# §6: id, method A, method B (A − B), dataset; "best:<model>" is resolved on BANKING77
TESTS = [("T1", "logprob-qwen3-8b", "llm-qwen3-8b", "banking77"),
         ("T2", "logprob-qwen3-8b", "llm-qwen3-8b", "clinc150"),
         ("T3", "llm-qwen3-8b-sc10", "llm-qwen3-8b", "banking77"),
         ("T4", "llm-qwen3-8b-sc10", "llm-qwen3-8b", "clinc150"),
         ("T5", "llm-gemini-3.6-flash-sc5", "llm-gemini-3.6-flash", "banking77"),
         ("T6", "llm-gemini-3.6-flash-sc5", "llm-gemini-3.6-flash", "clinc150"),
         ("T7", "jev", f"best:{QWEN}", "clinc150"),
         ("T8", "jev", f"best:{GEMINI}", "clinc150")]
PREDICTED = {"T1": True, "T2": True, "T3": False, "T4": False, "T5": False, "T6": False,
             "T7": True, "T8": True}           # True = positive and resolved (§6)
HYPOTHESES = [("H1-lp", QWEN, ["T1", "T2"]), ("H1-sc", QWEN, ["T3", "T4"]),
              ("H1-sc", GEMINI, ["T5", "T6"]), ("H2", QWEN, ["T7"]), ("H2", GEMINI, ["T8"])]
E1_PAIRS = [("llm-qwen3-8b", "llm-qwen3-8b-prompt-v2"),
            ("logprob-qwen3-8b", "logprob-qwen3-8b-prompt-v2"),
            ("llm-gemini-3.6-flash", "llm-gemini-3.6-flash-prompt-v2")]
REPEATS = [["jev", "jev-r2", "jev-r3"], ["llm-qwen3-8b", "llm-qwen3-8b-r2", "llm-qwen3-8b-r3"]]


class MissingCheckpoints(Exception):
    """One or more planned checkpoints is not there."""


# --- reading ---------------------------------------------------------------------------


def normalise(text: str) -> str:
    """scripts/fetch_real_datasets.py's rule for "the same text"."""
    return " ".join(text.lower().split())


def reread(decision: str, options: list[str], descriptions: dict[str, str]) -> str:
    """Amendment 2: `<option>: <its description>` read as the option. Split at the first
    ":"; the part before must equal an option byte for byte (no trimming, no case folding),
    the part after, stripped of surrounding whitespace, that option's description in the
    dataset file. Anything else is returned unchanged."""
    head, sep, tail = decision.partition(":")
    if not sep or head not in options or head not in descriptions:
        return decision
    return head if tail.strip() == descriptions[head] else decision


def load_labels(dataset: str, root: Path = ROOT) -> dict:
    path = root / LABELS[dataset]
    rows, _ = load_dataset(str(path))
    for i, row in enumerate(rows):
        if len(row["questions"]) != 1:
            raise SystemExit(f"{LABELS[dataset]} row {i}: one question per row expected")
    return {"rows": rows, "sha256": sha256_of(str(path)),
            "groups": [normalise(r["state"]) for r in rows]}


def load_run(dataset: str, slug: str, labels: dict, runs_dir: Path = RUNS_DIR) -> dict:
    """The checkpoint's header, checked against the plan, and one record per row
    (`runner.checkpoint_record`; None where the checkpoint holds no answer)."""
    path = runs_dir / dataset / f"{slug}.ckpt.jsonl"
    if not path.exists():
        raise MissingCheckpoints(f"{dataset}/{slug}")
    done = load_checkpoint(path)
    if -1 not in done:
        raise SystemExit(f"{path}: no header line")
    header = done[-1]["run"]
    judge = header.get("judge") or {}
    _, _, adapter, samples, template = METHODS[slug]
    name = str(judge.get("name", ""))
    problems = []
    if not name.split(":")[0].startswith(adapter):
        problems.append(f"judge {name!r}, expected the {adapter} adapter")
    if int(judge.get("samples") or 1) != samples:
        problems.append(f"{judge.get('samples')} samples, expected {samples}")
    if template and not str(judge.get("prompt_sha256", "")).startswith(
            PROMPT_SHA[(adapter, template)]):
        problems.append(f"prompt digest {judge.get('prompt_sha256')!r}, expected "
                        f"{PROMPT_SHA[(adapter, template)]}… ({template})")
    pinned = {"logprob": QWEN_REVISION, "laya": LAYA_REVISION}.get(adapter)
    if pinned and judge.get("loaded_revision") != pinned:
        problems.append(f"revision {judge.get('loaded_revision')!r}, pinned {pinned}")
    if (header.get("dataset") or {}).get("sha256") != labels["sha256"]:
        problems.append("judged another labels file")
    if problems:
        raise SystemExit(f"{path}: " + "; ".join(problems))
    records = []
    for idx, row in enumerate(labels["rows"]):
        q = row["questions"][0]["name"]
        j = next((j for j in (done.get(idx) or {}).get("judgments", [])
                  if j["question"] == q), None)
        records.append(None if j is None
                       else checkpoint_record(idx, row, j, row["labels"][q], header))
    return {"header": header, "records": records, "adapter": adapter, "samples": samples}


def status_of(rec: dict | None) -> str:
    """missing, no_answer, no_confidence or scored (§3: only a scored row enters AUROC,
    ECE and certification; every other row counts wrong in accuracy)."""
    if rec is None:
        return "missing"
    if rec["parse_status"] == "no_answer":
        return "no_answer"
    if rec["parse_status"] == "parsed" and rec["confidence"] is not None:
        return "scored"
    return "no_confidence"


def read_rows(run: dict, labels: dict, reading: str) -> tuple[list[dict], dict]:
    """One {status, decision, confidence, correct} per row under a reading, and what the
    reading changed: decisions (rows) and, for self-consistency, samples re-read. Under
    "strict" a self-consistency row is also re-voted from its samples, a check that the
    checkpoint's decision and share are what `vote` gives (`revote_mismatches`)."""
    out: list[dict] = []
    changed = {"rows": 0, "samples": 0, "decisions_changed": 0, "revote_mismatches": 0}
    for rec, row in zip(run["records"], labels["rows"], strict=True):
        st = status_of(rec)
        if rec is None:
            out.append({"status": st, "decision": "", "confidence": None, "correct": False})
            continue
        q = questions_of(row)[0]
        expected = row["labels"][q.name]
        decision, confidence = rec["decision"], rec["confidence"]
        if run["adapter"] == "llm" and run["samples"] > 1:
            parsed = [parse_reply(s["text"], [q]) for s in rec["raw"]["samples"]]
            d0, c0, s0, _ = vote(parsed, [q])[q.name]
            if (d0, c0 if s0 == "parsed" else None) != (decision, confidence):
                changed["revote_mismatches"] += 1
            if reading == "reread":
                fixed = []
                hit = 0
                for p in parsed:
                    d, c, ans, s = p[q.name]
                    r = reread(d, q.options, q.descriptions)
                    hit += r != d
                    fixed.append({q.name: (r, c, ans, s)})
                if hit:
                    changed["rows"] += 1
                    changed["samples"] += hit
                    d1, c1, s1, _ = vote(fixed, [q])[q.name]
                    changed["decisions_changed"] += d1 != decision
                    decision, confidence = d1, (c1 if s1 == "parsed" else None)
        elif run["adapter"] == "llm" and reading == "reread":
            r = reread(decision, q.options, q.descriptions)
            if r != decision:
                changed["rows"] += 1
                changed["decisions_changed"] += 1
                decision = r
        out.append({"status": st, "decision": decision,
                    "confidence": confidence if st == "scored" else None,
                    "correct": is_correct(decision, expected)})
    return out, changed


def option_margin(raw: dict) -> float:
    """Top-two log-odds margin of a log-probability decision: the difference of the two
    largest recorded option log-probabilities (`raw.logprobs`, the trimmed path's scores
    that amendment 1 defines it on; the normalisation over the options cancels). Each is
    rounded to 1e-6 in the checkpoint, so the margin is known to within MARGIN_TOL. inf
    with fewer than two options."""
    lps = sorted((float(v) for v in (raw.get("logprobs") or {}).values()), reverse=True)
    if len(lps) < 2 or not math.isfinite(lps[1]):
        return math.inf
    return lps[0] - lps[1]


# --- statistics --------------------------------------------------------------------------


def _scored(rs: list) -> tuple[list[float], list[bool]]:
    cs = [(c, ok) for c, ok in rs if c is not None]
    return [c for c, _ in cs], [ok for _, ok in cs]


def auroc_own(rs: list) -> float | None:
    """AUROC of each method's confidence for its own correctness, on its usable rows
    (§6): a row without a confidence (None) is left out."""
    conf, ok = _scored(rs)
    return failure_auroc(conf, ok) if conf else None


def ece_own(rs: list) -> float | None:
    conf, ok = _scored(rs)
    return expected_calibration_error(conf, ok) if conf else None


def mce_own(rs: list) -> float | None:
    conf, ok = _scored(rs)
    return worst_calibration_bin(conf, ok)["gap"] if conf else None


STATS = {"auroc": auroc_own, "ece": ece_own, "mce": mce_own}


def pairs_of(rows: list[dict]) -> list[tuple[float | None, bool]]:
    return [(r["confidence"], r["correct"]) for r in rows]


def _job(spec: tuple) -> tuple:
    """One bootstrap, by name, so it can run in another process."""
    key, kind, stat, a, b, groups, n_boot = spec
    if kind == "ci":
        res = bootstrap_defined(a, STATS[stat], n_boot, SEED, groups)
        return key, {"ci": list(res.ci[:2]) if res.ci else None, "undefined": res.undefined}
    if kind == "paired_ci":
        res = paired_difference_ci(a, b, STATS[stat], n_boot, SEED, groups)
        return key, {"ci": list(res.ci[:2]) if res.ci else None, "undefined": res.undefined}
    t = paired_difference_test(a, b, STATS[stat], n_boot, SEED, groups)
    return key, {"difference": t.difference, "ci": list(t.ci[:2]) if t.ci else None,
                 "p": t.p_value, "n_defined": t.n_defined, "undefined": t.undefined}


def run_jobs(specs: list[tuple], jobs: int | None) -> dict:
    if jobs == 1:
        return dict(_job(s) for s in specs)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return dict(pool.map(_job, specs, chunksize=1))


def _r(x: float | None, d: int = 6) -> float | None:
    return None if x is None else round(x, d)


def certification(conf: list[float], ok: list[bool], groups: list[str]) -> dict:
    out = {}
    for t in TARGETS:
        res = coverage_at_risk_crossfit(conf, ok, t, groups=groups, seed=SEED,
                                        start_errors=START_ERRORS)
        spread = [coverage_at_risk_crossfit(conf, ok, t, groups=groups, seed=s,
                                            start_errors=START_ERRORS)["pooled"]["coverage"]
                  for s in SPREAD_SEEDS]
        out[f"{t:g}"] = {
            "pooled": res["pooled"],
            "thresholds": [f.get("threshold") for f in res["folds"]],
            "reason": res.get("reason"),
            "spread_seeds": [SPREAD_SEEDS[0], SPREAD_SEEDS[-1]],
            "spread_coverage": [min(spread), max(spread)],
        }
    return out


def describe(rows: list[dict], groups: list[str], run: dict | None = None,
             certify: bool = True) -> dict:
    """Every point metric of §6's secondary list for one run under one reading."""
    n = len(rows)
    counts = Counter(r["status"] for r in rows)
    right = sum(1 for r in rows if r["status"] == "scored" and r["correct"])
    idx = [i for i, r in enumerate(rows) if r["status"] == "scored"]
    conf = [rows[i]["confidence"] for i in idx]
    ok = [rows[i]["correct"] for i in idx]
    g = [groups[i] for i in idx]
    worst = worst_calibration_bin(conf, ok) if conf else None
    d = {
        "n": n, "scored": counts["scored"], "no_answer": counts["no_answer"],
        "no_confidence": counts["no_confidence"], "missing": counts["missing"],
        "right": right, "accuracy": _r(right / n), "accuracy_wilson": [
            _r(x) for x in wilson_interval(right, n)],
        "auroc": _r(failure_auroc(conf, ok)) if conf else None,
        "ece": _r(expected_calibration_error(conf, ok)) if conf else None,
        "mce": _r(worst["gap"]) if worst else None,
        "mce_bin_rows": worst["n"] if worst else None,
        "aurc": _r(aurc(conf, ok)) if conf else None,
        "brier": _r(brier_score(conf, ok)) if conf else None,
        "nll": (_r(negative_log_likelihood(conf, ok))
                if conf and not nll_infinite(conf, ok) else None),
        "nll_infinite": nll_infinite(conf, ok) if conf else 0,
        "zero_error_coverage": (zero_error_coverage(conf, ok)["coverage"] if conf else None),
        "distinct_confidences": len(set(conf)),
    }
    if certify:
        d["certification"] = certification(conf, ok, g)
    if run is not None:
        recs = [r for r in run["records"] if r is not None]
        costs = [r["cost_usd"] for r in recs]
        lats = sorted(r["latency_s"] for r in recs if r.get("latency_s") is not None)
        d["cost_usd"] = (None if any(c is None for c in costs)
                         else _r(math.fsum(costs), 4))
        d["latency_p50_s"] = _r(lats[len(lats) // 2], 3) if lats else None
    return d


# --- the decision rules of §6 and amendment 2 -------------------------------------------


def settle(family: dict[str, dict]) -> dict[str, dict]:
    """Holm across the family (§6), then each test's outcome: resolved when its adjusted p
    is below ALPHA **and** its difference has the predicted (+) sign; `opposite_sign` when
    the adjusted p is below ALPHA with a negative difference (not resolved, reported)."""
    adj = holm({k: v["p"] for k, v in family.items()}, ALPHA)
    for k, v in family.items():
        v["p_holm"] = _r(adj[k]["p_adjusted"])
        v["resolved"] = bool(adj[k]["resolved"] and v["difference"] > 0)
        v["opposite_sign"] = bool(adj[k]["resolved"] and v["difference"] < 0)
        v["as_predicted"] = v["resolved"] == PREDICTED[k]
    return family


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def verdicts_of(tests: dict[str, dict[str, dict]]) -> list[dict]:
    """Amendment 2: a test depends on the scoring rule when the two readings disagree on
    whether it is resolved or on its sign; a hypothesis (§6: supported when every one of
    its tests is resolved) depends on it when any of its tests does. The verdict of record
    is the pre-registered reading's. Marks each strict test in place."""
    for tid, s in tests["strict"].items():
        r = tests["reread"][tid]
        s["depends_on_scoring_rule"] = (s["resolved"] != r["resolved"]
                                        or _sign(s["difference"]) != _sign(r["difference"]))
    out = []
    for h, model, ids in HYPOTHESES:
        v = {"hypothesis": h, "model": model, "tests": ids}
        for reading in READINGS:
            v[reading] = all(tests[reading][t]["resolved"] for t in ids)
        v["depends_on_scoring_rule"] = any(tests["strict"][t]["depends_on_scoring_rule"]
                                           for t in ids)
        out.append(v)
    return out


# --- the analysis ----------------------------------------------------------------------


def compute(runs_dir: Path = RUNS_DIR, root: Path = ROOT, n_boot: int = N_BOOT,
            jobs: int | None = None) -> dict:
    labels = {d: load_labels(d, root) for d in REAL + SYNTHETIC}
    runs, missing = {}, []
    for d, slugs in PLANNED.items():
        for s in slugs:
            try:
                runs[(d, s)] = load_run(d, s, labels[d], runs_dir)
            except MissingCheckpoints as e:
                missing.append(str(e))
    if missing:
        raise MissingCheckpoints(", ".join(missing))

    read: dict[tuple, dict] = {}
    changes: dict[tuple, dict] = {}
    for (d, s), run in runs.items():
        for reading in READINGS:
            read[(d, s, reading)], ch = read_rows(run, labels[d], reading)
            if reading == "reread":
                changes[(d, s)] = ch
            elif ch["revote_mismatches"]:
                raise SystemExit(f"{d}/{s}: {ch['revote_mismatches']} self-consistency rows "
                                 "do not re-vote to the recorded decision")

    def same(d: str, s: str) -> bool:
        return changes[(d, s)]["rows"] == 0

    # descriptive metrics: strict for every run; the re-read only where it changed a row
    metrics: dict[str, dict] = {}
    for (d, s), run in runs.items():
        entry = {"strict": describe(read[(d, s, "strict")], labels[d]["groups"], run)}
        if not same(d, s):
            entry["reread"] = describe(read[(d, s, "reread")], labels[d]["groups"], run)
        entry["reread_changes"] = {k: v for k, v in changes[(d, s)].items()
                                   if k != "revote_mismatches"}
        metrics[f"{d}/{s}"] = entry

    # §6's "best method" on BANKING77, by AUROC point estimate; the same under both readings
    best = {}
    for model, cands in BEST_OF.items():
        by = {r: {c: auroc_own(pairs_of(read[("banking77", c, r)])) for c in cands}
              for r in READINGS}
        picks = {r: max(cands, key=lambda c, r=r: by[r][c]) for r in READINGS}
        if picks["strict"] != picks["reread"]:
            raise SystemExit(f"best method of {model} differs between readings: {picks}")
        best[model] = {"method": picks["strict"],
                       "auroc_banking77": {c: _r(by["strict"][c]) for c in cands}}

    def resolve(slug: str) -> str:
        return best[slug.split(":", 1)[1]]["method"] if slug.startswith("best:") else slug

    # every bootstrap, in one pool
    specs: list[tuple] = []
    for (d, s) in runs:
        if d not in REAL:
            continue
        for reading in ("strict",) if same(d, s) else READINGS:
            rows = read[(d, s, reading)]
            sc = [(r["confidence"], r["correct"]) for r in rows if r["status"] == "scored"]
            gs = [g for g, r in zip(labels[d]["groups"], rows, strict=True)
                  if r["status"] == "scored"]
            for stat in STATS:
                specs.append((("ci", d, s, reading, stat), "ci", stat, sc, None, gs, n_boot))
    for tid, a, b, d in TESTS:
        a, b = resolve(a), resolve(b)
        for reading in READINGS:
            pa, pb = pairs_of(read[(d, a, reading)]), pairs_of(read[(d, b, reading)])
            g = labels[d]["groups"]
            specs.append((("test", tid, reading), "test", "auroc", pa, pb, g, n_boot))
            specs.append((("ece", tid, reading), "paired_ci", "ece", pa, pb, g, n_boot))
    for v1, v2 in E1_PAIRS:
        pa = pairs_of(read[("banking77", v2, "strict")])
        pb = pairs_of(read[("banking77", v1, "strict")])
        specs.append((("e1", v2), "test", "auroc", pa, pb, labels["banking77"]["groups"],
                      n_boot))
    boot = run_jobs(specs, jobs)

    for (d, s) in runs:
        if d not in REAL:
            continue
        for reading in ("strict",) if same(d, s) else READINGS:
            m = metrics[f"{d}/{s}"][reading]
            for stat in STATS:
                res = boot[("ci", d, s, reading, stat)]
                m[f"{stat}_ci"] = [_r(x) for x in res["ci"]] if res["ci"] else None
                if stat == "auroc":
                    m["auroc_ci_undefined"] = res["undefined"]

    # §6: the tests, Holm under each reading, verdicts
    tests: dict[str, dict] = {}
    for reading in READINGS:
        family = {}
        for tid, a, b, d in TESTS:
            ra, rb = resolve(a), resolve(b)
            t = boot[("test", tid, reading)]
            e = boot[("ece", tid, reading)]
            ca = [r["status"] == "scored" and r["correct"] for r in read[(d, ra, reading)]]
            cb = [r["status"] == "scored" and r["correct"] for r in read[(d, rb, reading)]]
            family[tid] = {
                "a": ra, "b": rb, "dataset": d,
                "auroc_a": _r(auroc_own(pairs_of(read[(d, ra, reading)]))),
                "auroc_b": _r(auroc_own(pairs_of(read[(d, rb, reading)]))),
                "difference": _r(t["difference"]), "ci": [_r(x) for x in t["ci"]],
                "p": _r(t["p"]), "n_defined": t["n_defined"], "undefined": t["undefined"],
                "ece_difference_ci": [_r(x) for x in e["ci"]] if e["ci"] else None,
                "accuracy_mcnemar": mcnemar_exact(ca, cb),
            }
        tests[reading] = settle(family)
    verdicts = verdicts_of(tests)

    # amendment 1: near-ties of the log-probability runs and the self-check's figures
    near = {}
    for (d, s), run in runs.items():
        if run["adapter"] != "logprob":
            continue
        margins = [option_margin(r["raw"]) for r in run["records"] if r is not None]
        near[f"{d}/{s}"] = {
            "decisions": len(margins),
            "near_ties": sum(1 for m in margins if m <= NEAR_TIE + MARGIN_TOL),
            "at_the_bound": sum(1 for m in margins if abs(m - NEAR_TIE) <= MARGIN_TOL),
            "exact_ties": sum(1 for m in margins if m <= MARGIN_TOL)}
    selfcheck = [ln for ln in (runs_dir / "logprob-selfcheck.txt").read_text(
        encoding="utf-8").splitlines() if ln and not ln.startswith("row ")]

    # E1: v2 − v1 per judge and method, BANKING77, no Holm
    e1 = []
    for v1, v2 in E1_PAIRS:
        t = boot[("e1", v2)]
        e1.append({"v1": v1, "v2": v2, "difference": _r(t["difference"]),
                   "ci": [_r(x) for x in t["ci"]], "p_unadjusted": _r(t["p"]),
                   "undefined": t["undefined"]})
    order = {tpl: [s for s in sorted(
        (v1 if tpl == "v1" else v2 for v1, v2 in E1_PAIRS),
        key=lambda s: -metrics[f"banking77/{s}"]["strict"]["auroc"])] for tpl in ("v1", "v2")}
    e1_order_same = ([METHODS[s][:2] for s in order["v1"]]
                     == [(METHODS[s][0], METHODS[s][1].replace(", prompt v2", ""))
                         for s in order["v2"]])

    # repeats (§5): spread of the three runs, and rows with the same decision in all three
    repeats = []
    for trio in REPEATS:
        rows = [read[("banking77", s, "strict")] for s in trio]
        same_dec = sum(1 for xs in zip(*rows, strict=True)
                       if len({x["decision"] for x in xs}) == 1)
        ms = [metrics[f"banking77/{s}"]["strict"] for s in trio]
        identical = {f"{a}|{b}": sum(1 for x, y in zip(rows[i], rows[j], strict=True)
                                     if (x["decision"], x["confidence"])
                                     == (y["decision"], y["confidence"]))
                     for (i, a), (j, b) in ((p, q) for p in enumerate(trio)
                                            for q in enumerate(trio) if p[0] < q[0])}
        repeats.append({"runs": trio, "same_decision_rows": same_dec,
                        "identical_decision_and_confidence": identical,
                        "n": len(rows[0]),
                        **{f"{k}_range": [min(m[k] for m in ms), max(m[k] for m in ms)]
                           for k in ("accuracy", "auroc", "ece")}})

    # E2: every planned run per dataset and template half
    e2 = {}
    for d in SYNTHETIC:
        split = json.loads((root / SPLITS[d]).read_text(encoding="utf-8"))
        parts = {"all": list(range(len(labels[d]["rows"]))),
                 "development": sorted(split["dev"]), "held-out": sorted(split["heldout"])}
        e2[d] = {}
        for s in PLANNED[d]:
            readings = ("strict",) if same(d, s) else READINGS
            e2[d][s] = {reading: {part: describe(
                [read[(d, s, reading)][i] for i in idx],
                [labels[d]["groups"][i] for i in idx])
                for part, idx in parts.items()} for reading in readings}

    cost = math.fsum(m["strict"]["cost_usd"] or 0.0 for m in metrics.values())
    notes_path = runs_dir / "run-notes.json"
    notes = json.loads(notes_path.read_text(encoding="utf-8")) if notes_path.exists() else {}
    provenance = {}
    for (d, s), run in runs.items():
        j = run["header"].get("judge") or {}
        provenance[f"{d}/{s}"] = {
            "judge": j.get("name"), "model": j.get("model_id") or j.get("model"),
            "revision": j.get("loaded_revision") or j.get("revision"),
            "prompt_template": j.get("prompt_template"),
            "prompt_sha256": (j.get("prompt_sha256") or "")[:8] or None,
            "samples": run["samples"], "started": run["header"].get("timestamp_utc"),
            "judge_audit_version": run["header"].get("judge_audit_version")}
    return {
        "plan": "docs/v05-plan.md (tag v05-plan-freeze; amendments 1 and 2)",
        "seed": SEED, "n_boot": n_boot, "alpha": ALPHA, "targets": TARGETS,
        "start_errors": START_ERRORS, "near_tie_margin": NEAR_TIE,
        "margin_tolerance": MARGIN_TOL,
        "best_method": best, "tests": tests, "verdicts": verdicts,
        "metrics": metrics, "near_ties": near, "selfcheck": selfcheck,
        "e1": {"pairs": e1, "order": order, "order_same": e1_order_same},
        "repeats": repeats, "e2": e2,
        "cost": {"recorded_usd": round(cost, 4), "ceiling_recorded_usd": 45,
                 "ceiling_bill_usd": 70, "billing_console": notes.get("billing_console")},
        "provenance": provenance,
    }


# --- the report --------------------------------------------------------------------------


def _f(x: float | None, d: int = 3) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def _s(x: float | None, d: int = 3) -> str:
    return "—" if x is None else f"{x:+.{d}f}"


def _iv(iv: list | None, d: int = 3, signed: bool = False) -> str:
    if not iv:
        return "—"
    f = _s if signed else _f
    return f"[{f(iv[0], d)}, {f(iv[1], d)}]"


def _pct(x: float | None, d: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{d}f} %"


def _p(p: float | None) -> str:
    if p is None:
        return "—"
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"


def label(slug: str) -> str:
    judge, method, *_ = METHODS[slug]
    return f"{judge} {method}"


def row_label(slug: str) -> str:
    """The label of a table row, with the role the plan gives the run next to it."""
    if slug.endswith(("-r2", "-r3", "-prompt-v2")):
        return f"{label(slug)} (exploratory)"
    if slug == "laya":
        return f"{label(slug)} (context only)"
    return label(slug)


def outcome(v: dict) -> str:
    """§6: resolved needs Holm p < 0.05 **and** the predicted (+) sign; a difference
    below 0 at Holm p < 0.05 is not resolved, and the table says which way it went."""
    if v["resolved"]:
        return "resolved (+)"
    if v["opposite_sign"]:
        return "not resolved: opposite sign (−) at Holm p < 0.05"
    return "not resolved"


def _yes(b: bool) -> str:
    return "yes" if b else "no"


def markdown(r: dict) -> str:
    T = r["tests"]
    L: list[str] = []
    add = L.append
    add("# v0.5 study — results")
    add("")
    add("Generated by `scripts/v05_study.py` from the checkpoints in `docs/runs/v05/`; CI "
        "regenerates it and fails on any difference. The protocol is "
        "[docs/v05-plan.md](v05-plan.md), frozen at tag `v05-plan-freeze` before the study's "
        "first call, with amendments 1 and 2 (§11). Every result is published whether or not "
        "its prediction held. A test that is not resolved is **not resolved**, not evidence "
        "of no difference.")
    add("")
    add("**Read with these caveats.** (1) No external human reviewer read the plan before "
        "the study ran (§12.6). (2) Label noise was not measured (D4): every error rate and "
        "certified bound below includes the datasets' own label errors, and the #86 relabel "
        "will be a sensitivity analysis, never the primary labels. (3) An interim look on "
        "2026-10-02, before amendment 2, computed descriptive metrics on the runs complete "
        "that day (accuracy, AUROC, certified coverage at 5 and 10 %) and raw, un-adjusted "
        "results for T3, T5, T6 and T8 (2,000 resamples); it is disclosed in amendment 2, "
        "with its script and full output in `docs/runs/v05/interim-2026-10-02/`. (4) BANKING77 (2020) and CLINC150 (2019) are "
        "public and probably in the judges' pretraining data. (5) Laya ran with budgets "
        "outside the shipped ones (640 / 1,024) and is context only.")
    add("")

    add("## 1. Verdicts")
    add("")
    add("A hypothesis is supported for a model only when every test listed for it is "
        "resolved: Holm-adjusted p below 0.05 across the 8 tests, with the predicted (+) "
        "sign. The verdict of record is the pre-registered scoring rule's (amendment 2); the "
        "re-reading is a declared sensitivity analysis.")
    add("")
    add("| hypothesis | model | tests | verdict of record (pre-registered rule) | "
        "re-reading (sensitivity) | |")
    add("|---|---|---|---|---|---|")
    best = {m: label(b["method"]).replace(m + " ", "") for m, b in r["best_method"].items()}
    for v in r["verdicts"]:
        notes = []
        if v["depends_on_scoring_rule"]:
            which = [t for t in v["tests"] if T["strict"][t]["depends_on_scoring_rule"]]
            same = v["strict"] == v["reread"]
            notes.append(f"**depends on the scoring rule** ({', '.join(which)}"
                         + ("; the verdict is the same under both readings" if same else "")
                         + ")")
        if v["hypothesis"] == "H2":
            notes.append(f"against {v['model']}'s method chosen on BANKING77 ({best[v['model']]})"
                         ", tested on CLINC150 only")
        note = "; ".join(notes)
        add(f"| {v['hypothesis']} | {v['model']} | {', '.join(v['tests'])} | "
            f"{'supported' if v['strict'] else 'not supported'} | "
            f"{'supported' if v['reread'] else 'not supported'} | {note} |")
    add("")
    dep = [t for t, v in T["strict"].items() if v["depends_on_scoring_rule"]]
    if dep:
        changed = [(k, v["reread_changes"]) for k, v in r["metrics"].items()
                   if v["reread_changes"]["rows"] and k.split("/")[0] in REAL]
        add(f"Tests whose resolution or sign depends on the scoring rule: {', '.join(dep)}. "
            "The difference is due to an output format, not to what the model declared: the "
            "re-reading "
            "reads an answer written as an option followed by its own description (e.g. "
            "`out_of_scope: the request asks for none of the other intents`) as that option, "
            "where the pre-registered rule scores it wrong. It changed "
            + "; ".join(f"{label(k.split('/')[1])} on {NAME[k.split('/')[0]]}: {c['rows']} rows"
                        + (f" ({c['samples']} samples, {c['decisions_changed']} voted "
                           "decisions)" if c["samples"] else "")
                        for k, c in changed)
            + "; no other run on these datasets. For self-consistency the vote share, its "
              "confidence, is recomputed after the re-reading.")
        add("")
        for tid in dep:
            mc = T["reread"][tid]["accuracy_mcnemar"]
            if mc["p_value"] < ALPHA and mc["b_only"] > mc["a_only"]:
                v = T["reread"][tid]
                add(f"Under the re-reading, {label(v['b'])} is also more accurate than "
                    f"{label(v['a'])} on {NAME[v['dataset']]} (McNemar {mc['a_only']} / "
                    f"{mc['b_only']}, p {_p(mc['p_value'])}; secondary, §2).")
                add("")

    add("## 2. Confirmatory tests (§6)")
    add("")
    add(f"AUROC of each method's confidence for its own correctness, on its usable rows; "
        f"difference A − B; two-sided paired bootstrap clustered by text, "
        f"{r['n_boot']:,} resamples, seed {r['seed']}; Holm across the 8 tests under each "
        "reading. \"Best method\" (T7, T8) was chosen on BANKING77 by AUROC point estimate: "
        + "; ".join(f"{m}: {label(b['method'])} ("
                    + ", ".join(f"{label(c).replace(m + ' ', '')} {_f(a)}"
                                for c, a in b['auroc_banking77'].items()) + ")"
                    for m, b in r["best_method"].items())
        + ". Neither choice changes under the re-reading.")
    add("")
    for reading, title in (("strict", "Pre-registered rule (verdict of record)"),
                           ("reread", "Re-reading of amendment 2 (sensitivity)")):
        add(f"**{title}**")
        add("")
        add("| id | A − B | dataset | AUROC A | AUROC B | difference | 95 % CI | p | Holm p | "
            "outcome | predicted | as predicted |")
        add("|---|---|---|---:|---:|---:|---|---:|---:|---|---|---|")
        for tid, v in T[reading].items():
            pred = "+ and resolved" if PREDICTED[tid] else "not resolved"
            add(f"| {tid} | {label(v['a'])} − {label(v['b'])} | {NAME[v['dataset']]} | "
                f"{_f(v['auroc_a'])} | {_f(v['auroc_b'])} | {_s(v['difference'])} | "
                f"{_iv(v['ci'], signed=True)} | {_p(v['p'])} | {_p(v['p_holm'])} | "
                f"{outcome(v)} | {pred} | {_yes(v['as_predicted'])} |")
        add("")
        undefined = {t: v["undefined"] for t, v in T[reading].items() if v["undefined"]}
        add("Resamples where either AUROC was undefined (not used): "
            + (", ".join(f"{t} {n}" for t, n in undefined.items()) if undefined else "none")
            + ". The smallest p-value a test can give is 2 / (B + 1) ≈ "
            + f"{2 / (r['n_boot'] + 1):.4f}.")
        add("")
    s2, r2 = T["strict"]["T2"], T["reread"]["T2"]
    if s2["p_holm"] != r2["p_holm"]:
        add(f"T2's Holm p is {_p(s2['p_holm'])} under the pre-registered rule and "
            f"{_p(r2['p_holm'])} under the re-reading, with the same raw p: Holm is a "
            "step-down over the family, and T8's p moves with the reading.")
        add("")
    lp = [k for k in r["near_ties"] if k.split("/")[1] == "logprob-qwen3-8b"
          and k.split("/")[0] in REAL]
    add("T1, T2 and T7 read Qwen3-8B's token log-probability, whose near-ties are unstable "
        "at bfloat16 scale (amendment 1, §5 below): "
        + "; ".join(f"{r['near_ties'][k]['near_ties']} of {r['near_ties'][k]['decisions']} "
                    f"decisions on {NAME[k.split('/')[0]]}" for k in lp) + ".")
    add("")
    e1 = {e["v1"]: e for e in r["e1"]["pairs"]}
    if "logprob-qwen3-8b" in e1 and "llm-qwen3-8b" in e1:
        a2 = r["metrics"]["banking77/logprob-qwen3-8b-prompt-v2"]["strict"]["auroc"]
        b2 = r["metrics"]["banking77/llm-qwen3-8b-prompt-v2"]["strict"]["auroc"]
        add(f"Exploratory, next to T1 (E1, §6 below): with prompt template v2 the same "
            f"BANKING77 gap, log-probability − verbalized, is {_s(a2 - b2)} "
            f"({_f(a2)} − {_f(b2)}), against T1's {_s(T['strict']['T1']['difference'])}: "
            "with another wording of the same prompt the gap is smaller. Not tested, outside "
            "the Holm family, one alternative wording only.")
        add("")
    add("Secondary, not confirmatory, same pairs, under both readings: paired ECE "
        "difference A − B with its clustered 95 % interval, and exact McNemar on accuracy "
        "(rows without an answer or a confidence count wrong). No Holm; no composite.")
    add("")
    add("| id | reading | ECE difference 95 % CI | McNemar: A right only / B right only | "
        "McNemar p |")
    add("|---|---|---|---|---:|")
    for tid in T["strict"]:
        for reading in READINGS:
            v = T[reading][tid]
            mc = v["accuracy_mcnemar"]
            tag = "pre-registered" if reading == "strict" else "re-read"
            add(f"| {tid} | {tag} | {_iv(v['ece_difference_ci'], signed=True)} | "
                f"{mc['a_only']} / {mc['b_only']} | {_p(mc['p_value'])} |")
    add("")

    add("## 3. Every run on the real datasets (secondary metrics)")
    add("")
    add("Accuracy counts a row without an answer or a confidence as wrong (Wilson 95 % "
        "interval); AUROC, ECE (10 equal-width bins), MCE (its worst bin's rows in "
        "parentheses; a maximum tends to rise on resamples, so its point can sit low in its "
        "interval), AURC, Brier and NLL use the scored rows only; intervals are the "
        "clustered bootstrap, 10,000 resamples, seed 2026. NLL is printed only when no "
        "scored row has confidence 1 and is wrong (the count of such rows is printed). "
        "Zero-error coverage is the largest top slice with no error. Cost is the recorded "
        "list-price cost (the bill may be higher, §9). No composite score.")
    add("")
    for d in REAL:
        add(f"### {NAME[d]}")
        add("")
        add("| judge and method | reading | scored / n | no answer / no conf. | accuracy | "
            "AUROC [95 % CI] | ECE [95 % CI] | MCE [95 % CI] (rows) | AURC | Brier | "
            "NLL (∞ rows) | "
            "zero-error cov. | cost | p50 latency |")
        add("|---|---|---:|---:|---|---|---|---|---:|---:|---|---:|---:|---:|")
        for s in PLANNED[d]:
            entry = r["metrics"][f"{d}/{s}"]
            for reading in ("strict", "reread"):
                if reading not in entry:
                    continue
                m = entry[reading]
                tag = "pre-registered" if reading == "strict" else "re-read"
                nll = "—" if m["nll"] is None else _f(m["nll"])
                cost = "—" if m["cost_usd"] is None else f"${m['cost_usd']:.2f}"
                add(f"| {row_label(s)} | {tag} | {m['scored']} / {m['n']} | "
                    f"{m['no_answer']} / {m['no_confidence']} | {_f(m['accuracy'])} "
                    f"{_iv(m['accuracy_wilson'])} | {_f(m['auroc'])} {_iv(m.get('auroc_ci'))} | "
                    f"{_f(m['ece'])} {_iv(m.get('ece_ci'))} | {_f(m['mce'])} "
                    f"{_iv(m.get('mce_ci'))} ({m['mce_bin_rows']}) | {_f(m['aurc'])} | "
                    f"{_f(m['brier'])} | "
                    f"{nll} ({m['nll_infinite']}) | {_pct(m['zero_error_coverage'])} | "
                    f"{cost} | "
                    f"{_f(m['latency_p50_s'], 2)} s |")
        add("")
        rr = [(s, r["metrics"][f"{d}/{s}"]["reread_changes"]) for s in PLANNED[d]
              if METHODS[s][2] == "llm"]
        add("Amendment 2's re-reading changed: "
            + "; ".join(f"{label(s)} {c['rows']} rows"
                        + (f" ({c['samples']} samples, {c['decisions_changed']} voted "
                           "decisions changed)" if METHODS[s][3] > 1 else "")
                        for s, c in rr) + ".")
        add("")

    add("## 4. Certification (§7)")
    add("")
    add("How much traffic a judge can automate at a target error rate, certified: "
        "`coverage_at_risk_crossfit`, two halves split by text (seed 2026), the threshold "
        "certified on one half with an exact one-sided 95 % bound and applied unchanged to "
        "the other, the test halves pooled; the fixed sequence starts at the cut holding the "
        "rows needed with 2 errors (D3). Coverage is the share of texts automated; observed "
        "risk is the errors among them. The spread is the pooled coverage over seeds "
        "2027–2036 (secondary). Every bound includes the datasets' unmeasured label noise "
        "(D4). Pre-registered scoring rule; amendment 2's re-reading on its own row where "
        "it changed a decision.")
    add("")
    for t in TARGETS:
        add(f"- **{_pct(t, 0)}**: {PLAIN[t]}.")
    add("")
    for d in REAL:
        add(f"### {NAME[d]}")
        add("")
        add("| judge and method | " + " | ".join(
            f"{_pct(t, 0)} ({PLAIN[t].replace('at most ', '≤ ').replace(' automated decisions', '')}"
            "): coverage (errors / automated) · seeds" for t in TARGETS) + " |")
        add("|---|" + "---|" * len(TARGETS))
        notes = []
        for s in PLANNED[d]:
            if s.endswith(("-r2", "-r3")):
                continue
            entry = r["metrics"][f"{d}/{s}"]
            for reading in ("strict", "reread"):
                if reading not in entry:
                    continue
                c = entry[reading]["certification"]
                cells = []
                for t in TARGETS:
                    x = c[f"{t:g}"]
                    p = x["pooled"]
                    cell = (f"{_pct(p['coverage'])} ({p['errors']} / {p['covered']}) · "
                            f"{_pct(x['spread_coverage'][0])}–"
                            f"{_pct(x['spread_coverage'][1])}")
                    if x["reason"] and not p["covered"]:
                        cell = "cannot certify: half too small †"
                        notes.append(x["reason"])
                    cells.append(cell)
                tag = "" if reading == "strict" else " (re-read, sensitivity)"
                add(f"| {row_label(s)}{tag} | " + " | ".join(cells) + " |")
        add("")
        if notes:
            add(f"† {notes[0]}. At this target a half of {NAME[d]} holds fewer texts than the "
                "sequence's starting cut, so no threshold can be certified by construction "
                "(§7), whatever the judge.")
            add("")
        add("0.0 % (0 / 0): no text was automated on either test half, because no "
            "threshold was certified on the calibration halves at that target.")
        add("")
        if d == "clinc150" and not notes:
            one = [row_label(s) + ("" if rd == "strict" else " (re-read)")
                   for s in PLANNED[d] for rd in ("strict", "reread")
                   if rd in r["metrics"][f"{d}/{s}"]
                   and r["metrics"][f"{d}/{s}"][rd]["certification"]["0.01"]["pooled"]["covered"]]
            add("**Deviation from §7 (D3).** The plan expected a CLINC150 half not to certify "
                "at 1 % by construction and the table to say so. A half holds 950 texts, more "
                "than the 628 the starting cut needs, so certification at 1 % was possible and "
                "the table prints what was computed"
                + (f": {', '.join(one)} certified at 1 %"
                   if one else "") + ". The plan's sentence was wrong; nothing was changed.")
            add("")

    add("## 5. Token log-probability: numerical noise (amendment 1)")
    add("")
    add("The passing amended self-check (`docs/runs/v05/logprob-selfcheck.txt`, BANKING77 "
        "test rows 0–4):")
    add("")
    for ln in r["selfcheck"]:
        add(f"> {ln}")
        add(">")
    if L[-1] == ">":
        L.pop()
    add("")
    add(f"A **near-tie** is a decision whose top-two log-odds margin is at most "
        f"{r['near_tie_margin']} (two bfloat16 steps), read from the recorded option "
        "log-probabilities of the trimmed path (`raw.logprobs`). Those are rounded to 1e-6, "
        "so a margin is known to within 1e-6, and the bfloat16 grid puts many margins "
        f"exactly on 0.5: a margin within {r['margin_tolerance']:g} of 0.5 counts as a "
        "near-tie, and those are counted on their own. A near-tie's decision and confidence "
        "are unstable at that scale: another kernel path can flip them.")
    add("")
    add("| run | decisions | near-ties | of which at 0.5 | exact ties (margin 0) |")
    add("|---|---:|---:|---:|---:|")
    for k, v in r["near_ties"].items():
        d, s = k.split("/")
        add(f"| {row_label(s)}, {NAME[d]} | {v['decisions']} | {v['near_ties']} | "
            f"{v['at_the_bound']} | {v['exact_ties']} |")
    add("")

    add("## 6. Exploratory: E1, prompt sensitivity (BANKING77)")
    add("")
    add("**Exploratory**, outside the Holm family. Template v2 against v1, same task, "
        "options, decision rule and confidence definition; BANKING77 has no re-read "
        "decision, so both readings are the same here.")
    add("")
    add("| judge and method | AUROC v1 | AUROC v2 | v2 − v1 [95 % CI] | p (unadjusted) | "
        "accuracy v1 | accuracy v2 | ECE v1 | ECE v2 |")
    add("|---|---:|---:|---|---:|---:|---:|---:|---:|")
    for e in r["e1"]["pairs"]:
        m1 = r["metrics"][f"banking77/{e['v1']}"]["strict"]
        m2 = r["metrics"][f"banking77/{e['v2']}"]["strict"]
        add(f"| {label(e['v1'])} | {_f(m1['auroc'])} | {_f(m2['auroc'])} | "
            f"{_s(e['difference'])} {_iv(e['ci'], signed=True)} | {_p(e['p_unadjusted'])} | "
            f"{_f(m1['accuracy'])} | {_f(m2['accuracy'])} | {_f(m1['ece'])} | "
            f"{_f(m2['ece'])} |")
    add("")
    add("Order of the three runs by AUROC point estimate: v1 "
        + " > ".join(label(s) for s in r["e1"]["order"]["v1"]) + "; v2 "
        + " > ".join(label(s) for s in r["e1"]["order"]["v2"]) + ". "
        + ("The order does not change between templates." if r["e1"]["order_same"]
           else "**The order changes between templates.**"))
    add("")

    add("## 7. Exploratory: repeats (BANKING77)")
    add("")
    add("**Exploratory** (#90): two more runs of Jev and of Qwen3-8B verbalized, the "
        "between-run spread next to the primary numbers, never replacing them.")
    add("")
    add("| judge | same decision in all three runs | accuracy range | AUROC range | "
        "ECE range |")
    add("|---|---:|---|---|---|")
    for rep in r["repeats"]:
        add(f"| {METHODS[rep['runs'][0]][0]} {METHODS[rep['runs'][0]][1]} | "
            f"{rep['same_decision_rows']} / {rep['n']} | {_iv(rep['accuracy_range'])} | "
            f"{_iv(rep['auroc_range'])} | {_iv(rep['ece_range'])} |")
    add("")
    add("Rows with the same decision **and** the same confidence, run by run: "
        + "; ".join(f"{label(k.split('|')[0])} vs {METHODS[k.split('|')[1]][1]} {n} / "
                    f"{rep['n']}" for rep in r["repeats"]
                    for k, n in rep["identical_decision_and_confidence"].items()) + ".")
    add("")

    add("## 8. Exploratory: E2, v2 synthetic stress sets")
    add("")
    add("**Exploratory.** Synthetic rows, ground truth by construction (GT-1), no human "
        "check; rows of one template differ only in their fills (near-duplicates by design), "
        "so these numbers say how a judge behaves on these templates, not on real traffic. "
        "Development and held-out halves are the committed template splits. Point "
        "estimates; certified coverage at 1 / 2 / 5 / 10 % (— where a half is too small for "
        "the starting cut).")
    add("")
    rr = {k: v["reread_changes"]["rows"] for k, v in r["metrics"].items()
          if k.split("/")[0] in SYNTHETIC and METHODS[k.split("/")[1]][2] == "llm"}
    add("Amendment 2's re-reading changed "
        + ("no decision on these sets: the pre-registered reading is the only one shown."
           if not any(rr.values()) else
           "; ".join(f"{k} {n} rows" for k, n in rr.items()) + "."))
    add("")
    for d, by in r["e2"].items():
        add(f"### {d}")
        add("")
        add("| judge and method | reading | half | n | accuracy | AUROC | ECE | MCE | "
            "zero-error cov. | certified 1 / 2 / 5 / 10 % |")
        add("|---|---|---|---:|---:|---:|---:|---:|---:|---|")
        for s, readings in by.items():
            for reading, parts in readings.items():
                for part, m in parts.items():
                    cert = " / ".join(
                        "—" if (m["certification"][f"{t:g}"]["reason"]
                                and not m["certification"][f"{t:g}"]["pooled"]["covered"])
                        else _pct(m["certification"][f"{t:g}"]["pooled"]["coverage"], 0)
                        for t in TARGETS)
                    tag = "pre-registered" if reading == "strict" else "re-read"
                    add(f"| {row_label(s)} | {tag} | {part} | {m['n']} | {_f(m['accuracy'])} | "
                        f"{_f(m['auroc'])} | {_f(m['ece'])} | {_f(m['mce'])} | "
                        f"{_pct(m['zero_error_coverage'])} | {cert} |")
        add("")

    c = r["cost"]
    add("## 9. Cost")
    add("")
    bill = c["billing_console"]
    add(f"Recorded at list price, every study run: **${c['recorded_usd']:.2f}** (stop rule "
        f"${c['ceiling_recorded_usd']} recorded; ceiling ${c['ceiling_bill_usd']} on the "
        "provider's bill, D7). Billing console: "
        + (f"{bill['amount']} {bill['currency']} ({bill.get('covers', '')}). The "
           "checkpoints do not separate list price, currency, tax or retried calls, so they "
           "do not explain a gap between the two." if bill
           else "not yet reported by the maintainer (§9 reports it next to the recorded "
                "figure once it is)."))
    add("")

    add("## 10. Provenance")
    add("")
    add("| checkpoint | judge | model | revision | prompt | samples | started (UTC) |")
    add("|---|---|---|---|---|---:|---|")
    for k, p in r["provenance"].items():
        rev = (p["revision"] or "")[:12] or "—"
        prompt = f"{p['prompt_template']} `{p['prompt_sha256']}…`" if p["prompt_sha256"] else "—"
        add(f"| `{k}` | {p['judge']} | {p['model']} | {rev} | {prompt} | {p['samples']} | "
            f"{p['started']} |")
    add("")
    return "\n".join(L)


def _shown(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--runs", type=Path, default=RUNS_DIR)
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--jobs", type=int, default=os.cpu_count(),
                    help="parallel bootstrap processes (the output does not depend on it)")
    args = ap.parse_args(argv)
    try:
        d = compute(args.runs, ROOT, N_BOOT, args.jobs)
    except MissingCheckpoints as e:
        print(f"missing checkpoint(s): {e}", file=sys.stderr)
        return 2
    md, js = markdown(d), json.dumps(d, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        stale = [p for p, text in ((args.out_md, md), (args.out_json, js))
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"differs: {_shown(p)}")
        return 1 if stale else 0
    args.out_md.write_text(md, encoding="utf-8")
    args.out_json.write_text(js, encoding="utf-8")
    print(f"wrote {_shown(args.out_md)} and {_shown(args.out_json)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
