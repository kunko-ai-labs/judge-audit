"""Results of the v0.6 study (#132), from its checkpoints. No model call.

The protocol was frozen before the study's first call; its sha256 is committed in
docs/v06-plan.sha256 and each amendment's in docs/v06-amendments.sha256. This script reads
the study's checkpoints in docs/runs/v06/ (`<slug>-<locale>.ckpt.jsonl`, for en-US, es-ES
and ca-ES) and the MASSIVE test files they judged, and writes docs/v06/results.json and the
report generated from it, docs/v06/README.md:

- the transfer tests: a threshold validated on English rows at a 5 % target error, applied
  unchanged to the same items in a target locale, both ways over two halves split by item,
  the two counts pooled, an exact one-sided bound; Holm across the six tests (3 primary
  judges x {ca-ES, es-ES}) with m = 6 fixed, a test not run counting as not resolved;
- overconfidence (mean confidence minus accuracy, usable rows), paired across locales, with
  a two-sided bootstrap clustered by item;
- the paired AUROC difference between a vendor's own confidence field and P(chosen option);
- per locale and judge: accuracy, AUROC, ECE, MCE, Brier, validated coverage, the
  high-confidence error rate, cost and latency, each on its own (no composite score);
- all of it again without the items a majority of localisation judges said do not match
  their intent, and again without the items whose text is also in MASSIVE train or dev
  (the item removed in all three locales).

The prediction of each transfer test is read at run time, never written here: from the
table of docs/v06-plan.md once that file's sha256 equals the one committed in
docs/v06-plan.sha256 (without the file, no prediction is shown), or from a JSON file given
with --predictions. A checkpoint that stopped before its last row is analysed on the rows it
completed and labelled partial everywhere. A file named `*.duplicate-writes.jsonl` enters no
figure: only its recorded cost is read, for the cost table.

  python scripts/v06_study.py           # writes docs/v06/results.json and README.md
  python scripts/v06_study.py --check   # exit 1 if either output differs; 2 if a checkpoint is missing

Deterministic: every interval is the repository's clustered bootstrap
(`metrics.selective`), seed 2026, 10,000 resamples, clustered by MASSIVE item (a repeated
text is not merged across items). The bootstraps run in parallel processes (`--jobs`); each
one is seeded on its own, so the output does not depend on how many there are.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_resumable import (  # noqa: E402
    acknowledged_unknowns,
    ceiling_of,
    ceiling_stop,
    recorded_cost,
)
from v05_study import (  # noqa: E402
    STATS,
    _f,
    _iv,
    _p,
    _pct,
    _r,
    _s,
    _shown,
    auroc_own,
    describe,
    status_of,
)

from judge_audit.metrics.calibration import _beta_quantile  # noqa: E402
from judge_audit.metrics.selective import (  # noqa: E402
    HIGH_CONFIDENCE_CUTS,
    bootstrap_defined,
    certify_threshold,
    coverage_at_risk,
    high_confidence_error,
    holm,
    min_rows_to_certify,
    paired_difference_ci,
    risk_upper_bound,
    split_by_group,
)
from judge_audit.report import DEGENERATE_NOTE  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    checkpoint_record,
    load_dataset,
    sha256_of,
    sha256_rows_of,
)

RUNS_DIR = ROOT / "docs" / "runs" / "v06"
OUT_DIR = ROOT / "docs" / "v06"
OUT_MD = OUT_DIR / "README.md"
OUT_JSON = OUT_DIR / "results.json"
PLAN = "docs/v06-plan.md"
PLAN_SHA = "docs/v06-plan.sha256"
PLAN_TABLE = ["id", "judge", "target locale", "prediction"]   # the predictions table's header
LABELS = "examples/massive/labels-test-{locale}.jsonl"

SEED = 2026
N_BOOT = 10_000
ALPHA = 0.05                  # family-wise, Holm
DELTA = 0.05                  # one-sided level of every exact bound
TRANSFER_TARGET = 0.05        # the error the English threshold is validated at
START_ERRORS = 2              # the walk starts at the cut that validates with 2 errors
TARGETS = [0.01, 0.02, 0.05, 0.10]
FAMILY_SIZE = 6

SOURCE = "en-US"
TARGET_LOCALES = ("ca-ES", "es-ES")
LOCALES = ("en-US", "es-ES", "ca-ES")
PRIMARY = ("jev", "gpt-6-luna", "claude-sonnet-4.5")
PAIRS = (("es-ES", "en-US"), ("ca-ES", "es-ES"))          # overconfidence, first − second
OUTCOMES = ("resolved", "not resolved")
# Where a vendor's own confidence field is kept in `raw`: `native_confidence`, except the
# decision2 adapter, which keeps its `confidence` field as `entropy_confidence`.
NATIVE_FIELD = {"decision2": "entropy_confidence"}
DUPLICATE_WRITES = "written by two processes at once; listed, never read"
CKPT_NAME = re.compile(r"^(?P<slug>.+)-(?P<locale>en-US|es-ES|ca-ES)\.ckpt\.jsonl$")
SENSITIVITY = {
    "without_majority_no": "Without the items a majority of localisation judges said do not "
                           "match their intent (any locale)",
    "without_train_dev_overlap": "Without the items whose text is also in MASSIVE train or "
                                 "dev (any locale)",
}
VC_SPLIT = ("validated coverage uses v0.5's own per-judge cross-fit split (by item, over "
            "the items that judge answered with a confidence); in the sensitivity analyses "
            "that split is redrawn on the remaining items; only the transfer-test halves are "
            "fixed")
CAVEAT = ("translated parallel data, not native traffic; labels from SLURP annotation "
          "carried over by localisation, so a label or localisation error counts as a judge "
          "error in every locale it affects")


class MissingCheckpoints(Exception):
    """One or more checkpoints of a primary judge is not there."""


# --- exact bounds -------------------------------------------------------------------------


def binomial_tail(errors: int, n: int, rate: float) -> float:
    """P(X >= errors) for X ~ Binomial(n, rate), in exact rational arithmetic (the float
    is the correctly rounded value of the exact sum, the same on every platform). This is
    the one-sided exact p-value of "the error rate is `rate` or less"; it is below alpha
    exactly when the Clopper–Pearson lower bound at 1 − alpha is above `rate`, so Holm on
    these p-values is the lower-bound rule at Holm's levels."""
    if n < 0 or not 0 <= errors <= n:
        raise ValueError(f"{errors} errors out of {n} rows")
    if errors == 0:
        return 1.0
    p = Fraction(str(rate))
    a, b, d = p.numerator, p.denominator - p.numerator, p.denominator
    below = 0                                   # sum_{k < errors} C(n, k) a^k b^(n−k)
    comb = 1
    for k in range(errors):
        below += comb * a ** k * b ** (n - k)
        comb = comb * (n - k) // (k + 1)
    return float(Fraction(d ** n - below, d ** n))


def error_lower_bound(errors: int, n: int, delta: float = DELTA,
                      rounding: bool = True) -> float | None:
    """Exact one-sided 1 − delta lower bound on an error rate (Clopper–Pearson):
    Beta(errors, n − errors + 1) at delta, the lower end of `calibration.clopper_pearson`
    at level 1 − 2·delta, unrounded. 0 with no error; None with no rows. Rounded **down**
    to 6 decimals, so the published bound is never above the exact one."""
    if n < 0 or not 0 <= errors <= n:
        raise ValueError(f"{errors} errors out of {n} rows")
    if n == 0:
        return None
    lo = 0.0 if errors == 0 else _beta_quantile(delta, errors, n - errors + 1)
    return math.floor(lo * 1e6 + 1e-9) / 1e6 if rounding else lo


def error_upper_bound(errors: int, n: int, delta: float = DELTA) -> float | None:
    """`risk_upper_bound` (exact one-sided 1 − delta), rounded **up** to 6 decimals as
    `high_confidence_error` publishes it. None with no rows."""
    if n == 0:
        return None
    return math.ceil(risk_upper_bound(errors, n, delta) * 1e6 - 1e-9) / 1e6


# --- reading ------------------------------------------------------------------------------


def load_labels(locale: str, root: Path = ROOT) -> dict:
    path = root / LABELS.format(locale=locale)
    rows, _ = load_dataset(str(path))
    for i, row in enumerate(rows):
        if len(row["questions"]) != 1:
            raise SystemExit(f"{LABELS.format(locale=locale)} row {i}: one question expected")
    metas = [row.get("_meta") or {} for row in rows]
    return {
        "path": LABELS.format(locale=locale), "rows": rows,
        "sha256": sha256_of(str(path)), "sha256_rows": sha256_rows_of(str(path)),
        "ids": [str(m.get("id")) for m in metas],
        "intents": [row["labels"][row["questions"][0]["name"]] for row in rows],
        "majority_no": [sum(1 for x in m.get("intent_judgments") or [] if x == 0) * 2
                        > len(m.get("intent_judgments") or []) for m in metas],
        "overlap": [bool(m.get("text_in_train_or_dev")) for m in metas],
    }


def load_all_labels(root: Path = ROOT) -> dict[str, dict]:
    """The three locales, checked to be the same items in the same order, with the same
    intent: row k is one item in every file, which is what makes a split by row index a
    split by item."""
    labels = {loc: load_labels(loc, root) for loc in LOCALES}
    ref = labels[SOURCE]
    if len(set(ref["ids"])) != len(ref["ids"]):
        raise SystemExit(f"{ref['path']}: an item id appears twice")
    for loc in LOCALES:
        if labels[loc]["ids"] != ref["ids"] or labels[loc]["intents"] != ref["intents"]:
            raise SystemExit(f"{labels[loc]['path']} and {ref['path']} do not hold the same "
                             "items in the same order with the same intent")
    return labels


def discover(runs_dir: Path) -> tuple[dict[tuple[str, str], Path], list[dict]]:
    """Study checkpoints by (slug, locale), and every other .jsonl file, listed with its
    sha256 and the reason it is not read."""
    found: dict[tuple[str, str], Path] = {}
    excluded = []
    for p in sorted(runs_dir.iterdir()) if runs_dir.is_dir() else []:
        if not p.is_file() or not p.name.endswith(".jsonl"):
            continue
        if p.name.endswith(".duplicate-writes.jsonl"):
            excluded.append({"file": p.name, "sha256": sha256_of(str(p)),
                             "reason": DUPLICATE_WRITES})
            continue
        m = CKPT_NAME.match(p.name)
        if not m:
            excluded.append({"file": p.name, "sha256": sha256_of(str(p)),
                             "reason": "not named <slug>-<locale>.ckpt.jsonl; not read"})
            continue
        found[(m["slug"], m["locale"])] = p
    return found, excluded


def load_run(path: Path, labels: dict, root: Path) -> dict:
    """The checkpoint's header, checked against the labels file it judged, and one record
    per labels row (`runner.checkpoint_record`; None where the checkpoint holds no answer).
    A row written more than once is refused: which answer counts would be a choice made
    after the fact. So is a row index outside the labels file."""
    done: dict[int, dict] = {}
    twice: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] in done:
            twice.append(rec["idx"])
        done[rec["idx"]] = rec
    shown = _rel(path, root)
    outside = sorted(k for k in done if k != -1 and not 0 <= k < len(labels["rows"]))
    if outside:
        raise SystemExit(f"{shown}: {len(outside)} rows outside 0..{len(labels['rows']) - 1} "
                         f"(first: {outside[:5]})")
    if twice:
        raise SystemExit(f"{shown}: {len(twice)} rows written more than once "
                         f"(first: {sorted(set(twice))[:5]})")
    if -1 not in done:
        raise SystemExit(f"{shown}: no header line")
    header = done[-1]["run"]
    ds = header.get("dataset") or {}
    if not {ds.get("sha256"), ds.get("sha256_rows")} & {labels["sha256"], labels["sha256_rows"]}:
        raise SystemExit(f"{shown}: judged another labels file than {labels['path']}")
    records = []
    for idx, row in enumerate(labels["rows"]):
        q = row["questions"][0]["name"]
        j = next((j for j in (done.get(idx) or {}).get("judgments", [])
                  if j["question"] == q), None)
        records.append(None if j is None
                       else checkpoint_record(idx, row, j, row["labels"][q], header))
    judge = header.get("judge") or {}
    adapter = str(judge.get("name", "")).split(":")[0]
    served = Counter(_served(r["raw"]) for r in records if r is not None)
    served.pop(None, None)
    spent, unknown = recorded_cost((done[k] for k in done if k >= 0), header)
    judged = sum(1 for r in records if r is not None)
    return {"header": header, "records": records, "adapter": adapter,
            "path": shown, "sha256": sha256_of(str(path)),
            "rows": sum(1 for k in done if k >= 0), "served": dict(served),
            "partial": partial_label(judged, len(records), header, spent, unknown),
            "spent": spent,
            "cost": {"recorded_usd": _usd(spent), "unknown_cost_judgments": unknown,
                     "max_usd": header.get("max_usd"),
                     "max_usd_history": header.get("max_usd_history") or []}}


def partial_label(judged: int, total: int, header: dict, spent: Decimal,
                  unknown: int) -> str | None:
    """None for a complete checkpoint; else "partial: n of N (why)", the why read with the
    resumable driver's own stop rule (`ceiling_stop`) on the header's ceiling."""
    if judged >= total:
        return None
    why = "incomplete"
    if header.get("max_usd") is not None:
        stop = ceiling_stop(spent, unknown, ceiling_of(header["max_usd"]),
                            acknowledged_unknowns(header))
        if stop and stop.startswith("cost ceiling reached"):
            why = "stopped at its ceiling"
        elif stop:
            why = "stopped: a cost is unknown"
    return f"partial: {judged:,} of {total:,} ({why})"


def _usd(x: Decimal) -> float:
    return float(round(x, 6))


def incident_cost(path: Path) -> dict:
    """The recorded cost of a `*.duplicate-writes.jsonl` file, every line counted (each one
    was a request): the only thing read from it. Unreadable → no cost, said so."""
    try:
        lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
                 if ln.strip()]
        header = next((x["run"] for x in lines if x.get("idx") == -1), None)
        rows = [x for x in lines if x.get("idx") != -1]
        spent, unknown = recorded_cost(rows, header)
    except (ValueError, KeyError, AttributeError, TypeError):
        return {"file": path.name, "recorded_usd": None, "note": "unreadable"}
    return {"file": path.name, "lines": len(rows), "recorded_usd": _usd(spent),
            "unknown_cost_judgments": unknown}


def _judge_of(run: dict) -> tuple:
    j = run["header"].get("judge") or {}
    return (j.get("name"), j.get("model_id") or j.get("model"), j.get("loaded_revision"))


def check_same_judge(runs: dict) -> None:
    """A slug's three locales must name the same judge, model and revision in their
    headers: a checkpoint renamed from another run would otherwise enter a test."""
    by: dict[str, dict[str, tuple]] = {}
    for (s, loc), run in runs.items():
        by.setdefault(s, {})[loc] = _judge_of(run)
    for s, locs in by.items():
        if len(set(locs.values())) > 1:
            raise SystemExit(f"{s}: a checkpoint names another judge or model than the "
                             f"other locales: {locs}")


def _served(raw: object) -> str | None:
    s = raw.get("served") if isinstance(raw, dict) else None
    m = s.get("model") if isinstance(s, dict) else None
    return None if m is None else str(m)


def _number(x: object) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x)


def read_rows(run: dict) -> list[dict]:
    """One {status, confidence, correct, native, served} per labels row. Only a scored row
    (an answer with a confidence) has a confidence; every other row counts wrong in
    accuracy and is never above a threshold (v0.5 §3)."""
    field = NATIVE_FIELD.get(run["adapter"], "native_confidence")
    out = []
    for rec in run["records"]:
        st = status_of(rec)
        if rec is None:
            out.append({"status": st, "confidence": None, "correct": False, "native": None,
                        "served": None})
            continue
        raw = rec["raw"] if isinstance(rec["raw"], dict) else {}
        out.append({"status": st, "confidence": rec["confidence"] if st == "scored" else None,
                    "correct": bool(rec["correct"]) and st == "scored",
                    "native": _number(raw.get(field)) if st == "scored" else None,
                    "served": _served(raw)})
    return out


def load_predictions(path: Path | None, root: Path) -> dict | None:
    """The transfer tests' predictions: {"tests": {id: {"judge", "target_locale",
    "prediction"}}}, exactly the six (primary judge, target locale) pairs, each predicted
    "resolved" or "not resolved"."""
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tests = data.get("tests") if isinstance(data, dict) else None
    _check_predictions(tests, _rel(Path(path), root))
    return {"path": _rel(Path(path), root), "sha256": sha256_of(str(path)), "tests": tests}


def _check_predictions(tests: object, where: str) -> None:
    want = {(j, loc) for loc in TARGET_LOCALES for j in PRIMARY}
    got = ([(t.get("judge"), t.get("target_locale")) for t in tests.values()]
           if isinstance(tests, dict) else [])
    if len(got) != FAMILY_SIZE or set(got) != want:
        raise SystemExit(f"{where}: the predictions must name the six tests, one per "
                         "primary judge and target locale")
    assert isinstance(tests, dict)
    for tid, t in tests.items():
        if t.get("prediction") not in OUTCOMES:
            raise SystemExit(f"{where}: {tid}: prediction must be one of {OUTCOMES}, got "
                             f"{t.get('prediction')!r}")


def load_plan_predictions(root: Path) -> dict | None:
    """The predictions as the frozen plan states them, read only once the plan's sha256
    equals the one committed at the freeze; None while the plan is not in the repository.
    The table is the one headed `| id | judge | target locale | prediction |`: judge
    names are lower-cased to slugs, locales unquoted, and a prediction cell is read by its
    first words ("not resolved" or "resolved"; anything after them is ignored)."""
    plan = root / PLAN
    if not plan.exists():
        return None
    sha_file = root / PLAN_SHA
    frozen = (sha_file.read_text(encoding="utf-8").split() or [None])[0] \
        if sha_file.exists() else None
    got = sha256_of(str(plan))
    if got != frozen:
        raise SystemExit(f"{PLAN}: sha256 {got} is not the frozen one in {PLAN_SHA} "
                         f"({frozen}); no prediction is read from it")
    lines = plan.read_text(encoding="utf-8").splitlines()

    def cells(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    start = next((i for i, ln in enumerate(lines)
                  if ln.lstrip().startswith("|") and cells(ln) == PLAN_TABLE), None)
    if start is None:
        raise SystemExit(f"{PLAN}: no predictions table headed {' | '.join(PLAN_TABLE)}")
    tests: dict[str, dict] = {}
    for ln in lines[start + 2:]:
        if not ln.lstrip().startswith("|"):
            break
        tid, judge, loc, pred = cells(ln)[:4]
        word = ("not resolved" if pred.startswith("not resolved")
                else "resolved" if pred.startswith("resolved") else pred)
        tests[tid] = {"judge": judge.lower(), "target_locale": loc.strip("`"),
                      "prediction": word}
    _check_predictions(tests, PLAN)
    return {"path": PLAN, "sha256": got, "verified_against": PLAN_SHA, "tests": tests}


def _rel(p: Path, root: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return Path(p).name


# --- the computations ---------------------------------------------------------------------


def item_halves(ids: list[str], seed: int = SEED) -> tuple[list[int], list[int]]:
    """Two halves of the positions, split by item (`split_by_group`, seed 2026)."""
    return split_by_group(ids, seed)


def subset_halves(halves: tuple[list[int], list[int]],
                  keep: list[int]) -> tuple[list[int], list[int]]:
    """The primary halves restricted to the kept positions, renumbered: the same split
    minus the removed items, never a new split of what remains."""
    pos = {orig: k for k, orig in enumerate(keep)}
    return ([pos[i] for i in halves[0] if i in pos], [pos[i] for i in halves[1] if i in pos])


def sign_of(diff: float | None) -> str | None:
    """The sign of a paired difference: "+" (first above second), "−" or "0"."""
    if diff is None:
        return None
    return "0" if diff == 0 else "+" if diff > 0 else "−"


def _order(slug: str) -> tuple:
    """Primary judges first, in the roster's order, then the others by name."""
    return (0, PRIMARY.index(slug), "") if slug in PRIMARY else (1, 0, slug)


def _scored(rows: list[dict]) -> tuple[list[float], list[bool]]:
    rs = [r for r in rows if r["status"] == "scored"]
    return [r["confidence"] for r in rs], [r["correct"] for r in rs]


def _count(n: int, errors: int) -> dict:
    return {"n": n, "errors": errors, "error_rate": _r(errors / n) if n else None,
            "upper_95": error_upper_bound(errors, n)}


def transfer_test(source: list[dict], target: list[dict],
                  halves: tuple[list[int], list[int]]) -> dict:
    """One transfer test. On each half, `coverage_at_risk` validates a threshold on the
    source (English) rows at TRANSFER_TARGET (exact one-sided 1 − DELTA, the walk starting
    at the cut that validates with START_ERRORS errors); the other half's target-language
    rows at or above it are counted, and its source rows as the control. The halves swap
    and the counts are pooled. A row without a confidence is never above a threshold.

    The test is run when at least one half validates a threshold (a half that validates
    none admits no row); with none, it is not run and `reason` says why."""
    a, b = halves
    folds = []
    for name, (cal, test) in zip("AB", ((a, b), (b, a)), strict=True):
        cc, co = _scored([source[i] for i in cal])
        tc, to = _scored([target[i] for i in test])
        sc, so = _scored([source[i] for i in test])
        r = coverage_at_risk(cc, co, tc, to, TRANSFER_TARGET, DELTA, START_ERRORS)
        ctl = coverage_at_risk(cc, co, sc, so, TRANSFER_TARGET, DELTA, START_ERRORS)["test"]
        fold = {"validated_on": name, "threshold": r["threshold"],
                "source_calibration": r["calibration"], "target": r["test"], "control": ctl}
        if r["threshold"] is None:
            fold["reason"] = _why_none(cc, co, r["min_covered"])
        folds.append(fold)
    run = any(f["threshold"] is not None for f in folds)
    n = sum(f["target"]["covered"] for f in folds)
    e = sum(f["target"]["errors"] for f in folds)
    cn = sum(f["control"]["covered"] for f in folds)
    ce = sum(f["control"]["errors"] for f in folds)
    out = {"run": run, "folds": folds,
           "pooled": {**_count(n, e), "lower_95": error_lower_bound(e, n),
                      "p_exact": binomial_tail(e, n, TRANSFER_TARGET) if run else None},
           "control": _count(cn, ce)}
    if not run:
        out["reason"] = (f"English validates no threshold at {_pct(TRANSFER_TARGET, 0)} on either "
                         "half: " + "; ".join(f"half {f['validated_on']}: {f['reason']}"
                                              for f in folds))
    return out


def _why_none(conf: list[float], ok: list[bool], start: int) -> str:
    """Why English validates no threshold on a half, in rows: too few to reach the walk's
    starting cut, or that cut already over the bound (`certify_threshold`'s first cut)."""
    if len(conf) < start:
        return (f"{len(conf)} English rows with a confidence, fewer than the {start} the "
                "walk starts at")
    c = certify_threshold(conf, ok, TRANSFER_TARGET, DELTA, START_ERRORS)["first_cut"]
    return (f"the first cut tested holds {c['units']} rows with {c['errors']} errors, upper "
            f"bound {_pct(c['risk_upper'], 2)} above {_pct(TRANSFER_TARGET, 0)}")


def settle(tests: dict[str, dict]) -> dict[str, dict]:
    """Holm across the family at ALPHA, with m = FAMILY_SIZE fixed: a test not run enters
    with p = 1, so it is not resolved and the others are adjusted as if it had run and
    failed. Resolved when the Holm-adjusted exact p is below ALPHA. Each test also gets
    the pooled lower bound at the level of its Holm step (ALPHA / (m − i) for the i-th
    smallest p), beside the unadjusted one-sided 95 % bound, up to the first step that
    fails: Holm is step-down and stops there, so a later test is not resolved whatever
    its own p, and its bound at its level (`holm_stopped`) is not given."""
    if len(tests) != FAMILY_SIZE:
        raise ValueError(f"the family has {FAMILY_SIZE} tests, got {len(tests)}")
    p = {k: (v["pooled"]["p_exact"] if v["run"] else 1.0) for k, v in tests.items()}
    adj = holm(p, ALPHA)
    stopped = False
    for i, (k, _) in enumerate(sorted(p.items(), key=lambda kv: kv[1])):   # holm's order
        v, level = tests[k], ALPHA / (FAMILY_SIZE - i)
        pooled = v["pooled"]
        v["holm_level"] = level
        v["holm_stopped"] = stopped
        v["lower_at_holm_level"] = (error_lower_bound(pooled["errors"], pooled["n"], level)
                                    if v["run"] and pooled.get("n") and not stopped else None)
        stopped = stopped or not adj[k]["resolved"]
    for k, v in tests.items():
        v["p_for_holm"] = p[k]
        v["p_holm"] = adj[k]["p_adjusted"]
        v["resolved"] = bool(v["run"] and adj[k]["resolved"])
        v["outcome"] = ("not run" if not v["run"]
                        else "resolved" if v["resolved"] else "not resolved")
    return tests


def overconfidence(rs: list) -> float | None:
    """Mean confidence minus accuracy over (confidence, correct) pairs."""
    if not rs:
        return None
    return math.fsum(c for c, _ in rs) / len(rs) - sum(1 for _, ok in rs if ok) / len(rs)


BOOT_STATS = {**STATS, "overconfidence": overconfidence}


def paired_overconfidence(a: list, b: list, ids: list[str], n_boot: int = N_BOOT) -> dict:
    """overconfidence(A) − overconfidence(B) on the same items, with the two-sided 95 %
    bootstrap interval clustered by item (seed 2026). Resolved when it excludes 0."""
    return _paired_result(_job((None, "paired_ci", "overconfidence", a, b, ids, n_boot))[1],
                          overconfidence(a), overconfidence(b), len(a))


def _paired_result(boot: dict, sa: float | None, sb: float | None, n: int) -> dict:
    ci = boot["ci"]
    diff = None if sa is None or sb is None else sa - sb
    return {"items": n, "a": _r(sa), "b": _r(sb), "difference": _r(diff),
            "ci": [_r(x) for x in ci] if ci else None, "undefined": boot["undefined"],
            "resolved": bool(ci and (ci[0] > 0 or ci[1] < 0))}


def _job(spec: tuple) -> tuple:
    """One bootstrap, by name, so it can run in another process."""
    key, kind, stat, a, b, groups, n_boot = spec
    if kind == "ci":
        res = bootstrap_defined(a, BOOT_STATS[stat], n_boot, SEED, groups)
    else:
        res = paired_difference_ci(a, b, BOOT_STATS[stat], n_boot, SEED, groups)
    return key, {"ci": list(res.ci[:2]) if res.ci else None, "undefined": res.undefined}


def run_jobs(specs: list[tuple], jobs: int | None) -> dict:
    if jobs == 1 or len(specs) <= 1:
        return dict(_job(s) for s in specs)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return dict(pool.map(_job, specs, chunksize=1))


def metrics_of(rows: list[dict], ids: list[str], run: dict | None) -> dict:
    """Every secondary metric of one judge in one locale (v05's `describe`, grouped by
    item), with overconfidence and the high-confidence error rate (#134)."""
    d = describe(rows, ids, run)
    d["validated_coverage"] = d.pop("certification")
    conf, ok = _scored(rows)
    d["overconfidence"] = _r(overconfidence(list(zip(conf, ok, strict=True))))
    d["high_confidence_error"] = high_confidence_error(conf, ok) if conf else [
        {"confidence_at_least": c, "n": 0, "errors": 0, "error_rate": None,
         "risk_upper": None} for c in HIGH_CONFIDENCE_CUTS]
    return d


def analyse(labels: dict, read: dict, runs: dict, keep: list[int], tests: dict,
            halves: tuple[list[int], list[int]], n_boot: int, jobs: int | None,
            primary: bool) -> dict:
    """The whole analysis on the items at positions `keep` (all three locales): the
    transfer tests, overconfidence, E1 and the secondary metrics. `primary` adds the
    secondary metrics' bootstrap intervals, cost and latency, and the served-model
    segments."""
    ids = [labels[SOURCE]["ids"][i] for i in keep]
    rows = {k: [v[i] for i in keep] for k, v in read.items()}
    halves = subset_halves(halves, keep)

    def partial(*keys: tuple[str, str]) -> list[str]:
        return [f"{s}/{loc}" for s, loc in keys if runs[(s, loc)]["partial"]]
    slugs = sorted({s for s, _ in rows}, key=_order)
    specs: list[tuple] = []

    transfer = {}
    for tid, t in tests.items():
        j, loc = t["judge"], t["target_locale"]
        transfer[tid] = {"judge": j, "target_locale": loc,
                         **transfer_test(rows[(j, SOURCE)], rows[(j, loc)], halves),
                         "partial": partial((j, SOURCE), (j, loc))}
    settle(transfer)
    for tid, t in tests.items():
        transfer[tid]["prediction"] = t.get("prediction")
        transfer[tid]["as_predicted"] = (None if t.get("prediction") is None
                                         else (transfer[tid]["outcome"] == "resolved")
                                         == (t["prediction"] == "resolved"))

    h2_in: dict[tuple, tuple] = {}
    for j in PRIMARY:
        for la, lb in PAIRS:
            both = [i for i, (x, y) in enumerate(zip(rows[(j, la)], rows[(j, lb)], strict=True))
                    if x["status"] == y["status"] == "scored"]
            a = [(rows[(j, la)][i]["confidence"], rows[(j, la)][i]["correct"]) for i in both]
            b = [(rows[(j, lb)][i]["confidence"], rows[(j, lb)][i]["correct"]) for i in both]
            h2_in[(j, la, lb)] = (a, b)
            specs.append((("h2", j, la, lb), "paired_ci", "overconfidence", a, b,
                          [ids[i] for i in both], n_boot))

    e1_in: dict[tuple, tuple] = {}
    for (s, loc), rs in sorted(rows.items(), key=lambda kv: (slugs.index(kv[0][0]),
                                                             LOCALES.index(kv[0][1]))):
        idx = [i for i, r in enumerate(rs) if r["native"] is not None]
        if not idx:
            continue
        a = [(rs[i]["native"], rs[i]["correct"]) for i in idx]
        b = [(rs[i]["confidence"], rs[i]["correct"]) for i in idx]
        e1_in[(s, loc)] = (a, b)
        specs.append((("e1", s, loc), "paired_ci", "auroc", a, b, [ids[i] for i in idx],
                      n_boot))

    metrics: dict[str, dict] = {}
    for s in slugs:
        for loc in LOCALES:
            if (s, loc) not in rows:
                continue
            done = [i for i, r in enumerate(rows[(s, loc)]) if r["status"] != "missing"]
            m = metrics_of([rows[(s, loc)][i] for i in done], [ids[i] for i in done],
                           runs[(s, loc)] if primary else None)
            metrics[f"{s}/{loc}"] = {"role": "primary" if s in PRIMARY else "exploratory",
                                     "partial": runs[(s, loc)]["partial"], **m}
            if primary:
                sc = [(r["confidence"], r["correct"]) for r in rows[(s, loc)]
                      if r["status"] == "scored"]
                gs = [g for g, r in zip(ids, rows[(s, loc)], strict=True)
                      if r["status"] == "scored"]
                for stat in STATS:
                    specs.append((("ci", s, loc, stat), "ci", stat, sc, None, gs, n_boot))

    boot = run_jobs(specs, jobs)

    h2: dict[str, dict] = {}
    for (j, la, lb), (a, b) in h2_in.items():
        r = _paired_result(boot[("h2", j, la, lb)], overconfidence(a), overconfidence(b),
                           len(a))
        r["sign"] = sign_of(r["difference"])
        r["partial"] = partial((j, la), (j, lb))
        h2.setdefault(j, {})[f"{la} - {lb}"] = r
    e1 = {}
    for (s, loc), (a, b) in e1_in.items():
        r = _paired_result(boot[("e1", s, loc)], auroc_own(a), auroc_own(b), len(a))
        e1[f"{s}/{loc}"] = {"role": "primary" if s in PRIMARY else "exploratory",
                            "field": NATIVE_FIELD.get(runs[(s, loc)]["adapter"],
                                                      "native_confidence"),
                            "partial": partial((s, loc)),
                            "rows": r.pop("items"), "auroc_native": r.pop("a"),
                            "auroc_chosen": r.pop("b"), **r}
    if primary:
        for key, m in metrics.items():
            s, loc = key.split("/")
            for stat in STATS:
                res = boot[("ci", s, loc, stat)]
                m[f"{stat}_ci"] = [_r(x) for x in res["ci"]] if res["ci"] else None
            m["auroc_ci_undefined"] = boot[("ci", s, loc, "auroc")]["undefined"]

    out = {"items": len(keep), "removed_items": len(labels[SOURCE]["ids"]) - len(keep),
           "halves": {"unit": "item", "seed": SEED, "sizes": [len(halves[0]), len(halves[1])]},
           "transfer": transfer, "overconfidence": h2, "e1": e1, "metrics": metrics}
    if primary:
        segs = {}
        for (s, loc), run in runs.items():
            if len(run["served"]) < 2:
                continue
            by: dict[str, list[int]] = {}
            for i, r in enumerate(rows[(s, loc)]):
                if r["served"] is not None:
                    by.setdefault(r["served"], []).append(i)
            segs[f"{s}/{loc}"] = {k: describe([rows[(s, loc)][i] for i in v],
                                              [ids[i] for i in v], certify=False)
                                  for k, v in by.items()}
        out["served_segments"] = segs
    return out


def compute(runs_dir: Path = RUNS_DIR, root: Path = ROOT, predictions: Path | None = None,
            n_boot: int = N_BOOT, jobs: int | None = None) -> dict:
    labels = load_all_labels(root)
    found, excluded = discover(runs_dir)
    missing = [f"{s}/{loc}" for s in PRIMARY for loc in LOCALES if (s, loc) not in found]
    if missing:
        raise MissingCheckpoints(", ".join(missing))
    runs = {k: load_run(p, labels[k[1]], root) for k, p in found.items()}
    check_same_judge(runs)
    read = {k: read_rows(run) for k, run in runs.items()}
    pred = (load_predictions(predictions, root) if predictions is not None
            else load_plan_predictions(root))
    tests = (dict(pred["tests"]) if pred else
             {f"{j}/{loc}": {"judge": j, "target_locale": loc}
              for loc in TARGET_LOCALES for j in PRIMARY})

    n = len(labels[SOURCE]["ids"])
    majority = [any(labels[loc]["majority_no"][i] for loc in LOCALES) for i in range(n)]
    overlap = [any(labels[loc]["overlap"][i] for loc in LOCALES) for i in range(n)]
    keeps = {"primary": list(range(n)),
             "without_majority_no": [i for i in range(n) if not majority[i]],
             "without_train_dev_overlap": [i for i in range(n) if not overlap[i]]}
    halves = item_halves(labels[SOURCE]["ids"])
    analyses = {name: analyse(labels, read, runs, keep, tests, halves, n_boot, jobs,
                              primary=name == "primary")
                for name, keep in keeps.items()}

    order = sorted(runs, key=lambda k: (_order(k[0]), LOCALES.index(k[1])))
    per_judge: dict[str, dict] = {}
    for s, loc in order:
        per_judge.setdefault(s, {})[loc] = runs[(s, loc)]["cost"]["recorded_usd"]
    for s in per_judge:
        per_judge[s]["total"] = _usd(sum((runs[(s, loc)]["spent"] for loc in LOCALES
                                          if (s, loc) in runs), Decimal(0)))
    incidents = [incident_cost(runs_dir / e["file"]) for e in excluded
                 if e["reason"] == DUPLICATE_WRITES]
    read_usd = sum((run["spent"] for run in runs.values()), Decimal(0))
    excl_usd = sum((Decimal(repr(c["recorded_usd"])) for c in incidents
                    if c["recorded_usd"] is not None), Decimal(0))
    cost = {"checkpoints": {f"{s}/{loc}": runs[(s, loc)]["cost"] for s, loc in order},
            "per_judge": per_judge, "excluded": incidents, "read_usd": _usd(read_usd),
            "excluded_usd": _usd(excl_usd), "total_usd": _usd(read_usd + excl_usd)}

    plan = root / "docs" / "v06-plan.sha256"
    amend = root / "docs" / "v06-amendments.sha256"
    return {
        "study": "v0.6",
        "plan_sha256": plan.read_text(encoding="utf-8").split()[0] if plan.exists() else None,
        "amendments_sha256": ([ln for ln in amend.read_text(encoding="utf-8").splitlines()
                               if ln.strip()] if amend.exists() else []),
        "parameters": {"seed": SEED, "n_boot": n_boot, "alpha": ALPHA, "delta": DELTA,
                       "transfer_target": TRANSFER_TARGET, "start_errors": START_ERRORS,
                       "family_size": FAMILY_SIZE, "targets": TARGETS,
                       "high_confidence_cuts": list(HIGH_CONFIDENCE_CUTS),
                       "cluster": "MASSIVE item id", "primary": list(PRIMARY)},
        "inputs": {
            "labels": {loc: {"path": v["path"], "sha256": v["sha256"], "rows": len(v["rows"])}
                       for loc, v in labels.items()},
            "checkpoints": {
                f"{s}/{loc}": {
                    "path": run["path"], "sha256": run["sha256"], "rows": run["rows"],
                    "judge": (run["header"].get("judge") or {}).get("name"),
                    "model": ((run["header"].get("judge") or {}).get("model_id")
                              or (run["header"].get("judge") or {}).get("model")),
                    "revision": (run["header"].get("judge") or {}).get("loaded_revision"),
                    "started": run["header"].get("timestamp_utc"),
                    "judge_audit_version": run["header"].get("judge_audit_version"),
                    "partial": run["partial"], "served": run["served"]}
                for (s, loc), run in sorted(runs.items(), key=lambda kv: (
                    _order(kv[0][0]), LOCALES.index(kv[0][1])))},
            "excluded": excluded,
            "predictions": ({k: v for k, v in pred.items() if k != "tests"} if pred
                            else None),
        },
        "items": {
            "n": n,
            "majority_no": {**{loc: sum(labels[loc]["majority_no"]) for loc in LOCALES
                               if loc != SOURCE}, "items": sum(majority)},
            "train_dev_overlap": {**{loc: sum(labels[loc]["overlap"]) for loc in LOCALES},
                                  "items": sum(overlap)},
        },
        "analyses": analyses,
        "cost": cost,
    }


# --- the report -----------------------------------------------------------------------------


def _who(key: str, role: str, partial: str | None = None) -> str:
    s = key.split("/")[0]
    return ((s if role == "primary" else f"{s} (exploratory)")
            + (f" — {partial}" if partial else ""))


def _mark(key: str, partial: str | None = None) -> str:
    return (("" if key.split("/")[0] in PRIMARY else " (exploratory)")
            + (f" — {partial}" if partial else ""))


def _flag(keys: list[str], plabels: dict[str, str]) -> str:
    """The partial checkpoints a row rests on, named with their label."""
    return "".join(f" — `{k}` {plabels[k]}" for k in keys)


def _per_locale(c: dict) -> str:
    return (", ".join(f"`{k}` {v}" for k, v in c.items() if k != "items")
            + f", {c['items']} items in all")


def _cov(x: dict) -> str:
    p = x["pooled"]
    if x["reason"] and not p["covered"]:
        return "none validated †"
    return (f"{_pct(p['coverage'])} ({p['errors']} / {p['covered']}) · "
            f"{_pct(x['spread_coverage'][0])}–{_pct(x['spread_coverage'][1])}")


def _holm_bound(v: dict) -> str:
    if v["run"] and v.get("holm_stopped"):
        return "— (Holm stopped at an earlier step)"
    if v["lower_at_holm_level"] is None:
        return "—"
    return f"{_pct(v['lower_at_holm_level'], 2)} (α / {round(ALPHA / v['holm_level'])})"


def _transfer_table(add, T: dict, full: bool, plabels: dict[str, str]) -> None:
    if full:
        add("| test | judge | target | English threshold: half A / B | target rows above / "
            "errors | error | 95 % lower | lower at its Holm level | p (exact) | Holm p | "
            "outcome | 95 % upper | English control: rows / errors | prediction | "
            "as predicted |")
        add("|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|---|")
    else:
        add("| test | judge | target | English threshold: half A / B | rows above / errors | "
            "error | 95 % lower | lower at its Holm level | Holm p | outcome | 95 % upper |")
        add("|---|---|---|---|---:|---:|---:|---:|---:|---|---:|")
    for tid, v in T.items():
        p, c = v["pooled"], v["control"]
        th = " / ".join(f"{f['validated_on']} {_f(f['threshold'], 4)}" for f in v["folds"])
        base = (f"| {tid} | {v['judge']}{_flag(v['partial'], plabels)} | "
                f"`{v['target_locale']}` | {th} | ")
        if full:
            pred = v["prediction"] or "—"
            asp = "—" if v["as_predicted"] is None else ("yes" if v["as_predicted"] else "no")
            add(base + f"{p['n']} / {p['errors']} | {_pct(p['error_rate'])} | "
                f"{_pct(p['lower_95'], 2)} | {_holm_bound(v)} | {_p(p['p_exact'])} | "
                f"{_p(v['p_holm'])} | **{v['outcome']}** | {_pct(p['upper_95'], 2)} | "
                f"{c['n']} / {c['errors']} | {pred} | {asp} |")
        else:
            add(base + f"{p['n']} / {p['errors']} | {_pct(p['error_rate'])} | "
                f"{_pct(p['lower_95'], 2)} | {_holm_bound(v)} | {_p(v['p_holm'])} | "
                f"**{v['outcome']}** | {_pct(p['upper_95'], 2)} |")


def _h2_table(add, H: dict, plabels: dict[str, str]) -> None:
    add("| judge | pair | items | overconfidence: first | second | difference | "
        "95 % CI (clustered by item) | interval excludes 0 | sign |")
    add("|---|---|---:|---:|---:|---:|---|---|---|")
    for j, pairs in H.items():
        for pair, v in pairs.items():
            add(f"| {j}{_flag(v['partial'], plabels)} | `{pair.replace(' - ', '` − `')}` | "
                f"{v['items']} | {_s(v['a'])} | {_s(v['b'])} | {_s(v['difference'])} | "
                f"{_iv(v['ci'], signed=True)} | {'yes' if v['resolved'] else 'no'} | "
                f"{v['sign'] or '—'} |")


def _e1_table(add, E: dict, plabels: dict[str, str]) -> None:
    add("| judge | locale | field | rows | AUROC, own field | AUROC, P(chosen) | "
        "own − P(chosen) [95 % CI] |")
    add("|---|---|---|---:|---:|---:|---|")
    for k, v in E.items():
        add(f"| {_who(k, v['role'], plabels.get(k))} | `{k.split('/')[1]}` | `{v['field']}` | {v['rows']} | "
            f"{_f(v['auroc_native'])} | {_f(v['auroc_chosen'])} | {_s(v['difference'])} "
            f"{_iv(v['ci'], signed=True)} |")


def markdown(r: dict) -> str:
    L: list[str] = []
    add = L.append
    P = r["analyses"]["primary"]
    par = r["parameters"]
    plabels = {k: c["partial"] for k, c in r["inputs"]["checkpoints"].items() if c["partial"]}
    add("# v0.6 study — results")
    add("")
    add("Generated by `scripts/v06_study.py` from the checkpoints in `docs/runs/v06/` and "
        "`results.json` next to this file; `--check` regenerates both and fails on any "
        "difference. The protocol was frozen before the study's first call"
        + (f" (sha256 `{r['plan_sha256']}`, `docs/v06-plan.sha256`)" if r["plan_sha256"]
           else "")
        + f", with {len(r['amendments_sha256'])} dated amendment(s) whose sha256 are in "
        "`docs/v06-amendments.sha256`. Every result is published whether or not its "
        "prediction held. A test that is not resolved is **not resolved**: it does not show "
        "that the threshold holds, and its upper bound says how large the error could be.")
    add("")
    add(f"**Read with these caveats.** MASSIVE 1.1 test, {r['items']['n']:,} items in three "
        f"locales: {CAVEAT}. Public since 2022, so probably in the pretraining data of the "
        "judges audited. Judges marked *exploratory* are in no test and no Holm family; the "
        "mark is on every row that reports them. A checkpoint that stopped before its last "
        "row is analysed on the rows it completed, never counting the others as wrong, and "
        "is marked *partial* on every row that rests on it. No composite score: each "
        "number stands on its own.")
    add("")
    add(DEGENERATE_NOTE)
    add("")

    add("## 1. Transfer tests")
    add("")
    add(f"Items split in two halves by item (seed {par['seed']}, "
        f"{P['halves']['sizes'][0]:,} / {P['halves']['sizes'][1]:,}; an item's three "
        "languages on the same side). On one half the English rows validate a threshold at "
        f"a {_pct(par['transfer_target'], 0)} target error (`coverage_at_risk`, exact one-sided "
        f"95 %, the walk starting at the cut that validates with {par['start_errors']} "
        "errors); on the other half the target-language rows at or above it are counted. "
        "The halves swap and the counts are pooled. Exact one-sided 95 % lower and upper "
        "bounds on the pooled error; p is the exact binomial P(errors ≥ observed | "
        f"{_pct(par['transfer_target'], 0)}), equivalent to the lower bound. **Resolved** when "
        f"the Holm-adjusted p across the {par['family_size']} tests is below "
        f"{par['alpha']}, with m = {par['family_size']} fixed (a test not run counts as not "
        "resolved). A half on which English validates no threshold admits no row; the test "
        "is not run only when neither half validates one. \"Lower at its Holm level\" is "
        "the pooled lower bound at the one-sided level of the test's Holm step (α / 6 for "
        "the smallest p, then α / 5, …), next to the unadjusted 95 % bound, up to the first "
        "step that fails: Holm stops there, and no later bound is given. A row without a "
        "confidence is never above a threshold. The English control is the English rows of "
        "the same halves above the same thresholds.")
    add("")
    _transfer_table(add, P["transfer"], full=True, plabels=plabels)
    add("")
    notrun = {t: v["reason"] for t, v in P["transfer"].items() if not v["run"]}
    if notrun:
        add("Not run: " + "; ".join(f"{t}: {why}" for t, why in notrun.items()) + ".")
        add("")

    add("## 2. Overconfidence, paired across locales")
    add("")
    add(f"Overconfidence = mean confidence − accuracy, on the items usable (answered with a "
        f"confidence) in both locales of the pair. Two-sided 95 % bootstrap interval "
        f"clustered by item, {par['n_boot']:,} resamples, seed {par['seed']}; no Holm; "
        "reported as resolved when the interval excludes 0. Sign: + when the first locale's "
        "overconfidence is above the second's, − when below.")
    add("")
    _h2_table(add, P["overconfidence"], plabels)
    add("")

    add("## 3. A vendor's own confidence field against P(chosen option)")
    add("")
    add("Exploratory, no test. AUROC of each confidence for the same decisions' correctness, "
        "on the rows where both are recorded; paired bootstrap clustered by item.")
    add("")
    if P["e1"]:
        _e1_table(add, P["e1"], plabels)
    else:
        add("No checkpoint records a vendor's own confidence field.")
    add("")

    add("## 4. Every judge, per locale")
    add("")
    add("Accuracy counts a row without an answer or a confidence as wrong (Wilson 95 % "
        "interval); AUROC, ECE (10 equal-width bins), MCE (its worst bin's rows in "
        "parentheses), Brier and overconfidence use the rows answered with a confidence; "
        "intervals are the bootstrap clustered by item. Cost is the recorded list-price "
        "cost (the bill may be higher). No composite score. ‡ as defined above.")
    add("")
    for loc in LOCALES:
        add(f"### `{loc}`")
        add("")
        add("| judge | scored / judged | no answer / no conf. | accuracy | "
            "AUROC [95 % CI] | ECE [95 % CI] | MCE [95 % CI] (rows) | Brier | "
            "overconfidence | cost | p50 latency |")
        add("|---|---:|---:|---|---|---|---|---:|---:|---:|---:|")
        for k, m in P["metrics"].items():
            if k.split("/")[1] != loc:
                continue
            cost = "—" if m.get("cost_usd") is None else f"${m['cost_usd']:.4f}"
            add(f"| {_who(k, m['role'], m['partial'])} | {m['scored']} / {m['n']} | "
                f"{m['no_answer']} / {m['no_confidence']} | {_f(m['accuracy'])} "
                f"{_iv(m['accuracy_wilson'])} | {_f(m['auroc'])} {_iv(m.get('auroc_ci'))} | "
                f"{_f(m['ece'])} {_iv(m.get('ece_ci'))} | {_f(m['mce'])} "
                f"{_iv(m.get('mce_ci'))} ({m['mce_bin_rows']}) | {_f(m['brier'])} | "
                f"{_s(m['overconfidence'])} | {cost} | {_f(m.get('latency_p50_s'), 2)} s |")
        add("")

    add("## 5. Validated coverage")
    add("")
    add(f"`coverage_at_risk_crossfit` per locale: two halves split by item (seed "
        f"{par['seed']}), a threshold validated on one half (exact one-sided 95 %, the walk "
        f"starting at the cut that validates with {par['start_errors']} errors) and applied "
        "to the other, the halves pooled; coverage is the share of items automated, with "
        "errors / automated, and the pooled coverage over seeds 2027–2036. Target error: "
        "1, 2, 5 or 10 errors in 100 automated decisions. Note: " + VC_SPLIT + ".")
    add("")
    add("| judge | locale | 1 % | 2 % | 5 % | 10 % |")
    add("|---|---|---|---|---|---|")
    short: list[float] = []
    for k, m in P["metrics"].items():
        vc = m["validated_coverage"]
        cells = []
        for t in par["targets"]:
            x = vc[f"{t:g}"]
            cells.append(_cov(x))
            if x["reason"] and not x["pooled"]["covered"] and t not in short:
                short.append(t)
        add(f"| {_who(k, m['role'], m['partial'])} | `{k.split('/')[1]}` | "
            + " | ".join(cells) + " |")
    add("")
    if short:
        add("† The walk starts at the cut holding "
            + ", ".join(f"{min_rows_to_certify(t, par['delta'], par['start_errors'])} items "
                        f"at {_pct(t, 0)}" for t in sorted(short))
            + "; a half held fewer items with a confidence, so nothing can be validated "
              "there by construction, whatever the judge (the reason is in `results.json`).")
        add("")
    add("0.0 % (0 / 0): no item was automated on either half, because no threshold was "
        "validated on the other half at that target.")
    add("")

    add("## 6. High-confidence error rate")
    add("")
    add("Decisions declaring at least the confidence shown: wrong / rows, the rate and its "
        "exact one-sided 95 % upper bound (#134). A fixed cut, not a validated threshold.")
    add("")
    cuts = par["high_confidence_cuts"]
    add("| judge | locale | " + " | ".join(f"≥ {c:g}" for c in cuts) + " |")
    add("|---|---|" + "---|" * len(cuts))
    for k, m in P["metrics"].items():
        cells = ["—" if h["n"] == 0 else
                 f"{h['errors']} / {h['n']} ({_pct(h['error_rate'])}, upper "
                 f"{_pct(h['risk_upper'], 2)})" for h in m["high_confidence_error"]]
        add(f"| {_who(k, m['role'], m['partial'])} | `{k.split('/')[1]}` | "
            + " | ".join(cells) + " |")
    add("")

    add("## 7. Sensitivity analyses")
    add("")
    add("Every test and metric recomputed on fewer items, each item removed in all three "
        "locales; the transfer tests keep the primary halves minus the removed items (no "
        "new split). Note: " + VC_SPLIT + ". "
        f"Majority-no rows: {_per_locale(r['items']['majority_no'])}; text also in train "
        f"or dev: {_per_locale(r['items']['train_dev_overlap'])}.")
    add("")
    for name, what in SENSITIVITY.items():
        S = r["analyses"][name]
        add(f"### {what}")
        add("")
        add(f"{S['items']:,} items ({S['removed_items']} removed).")
        add("")
        _transfer_table(add, S["transfer"], full=False, plabels=plabels)
        add("")
        _h2_table(add, S["overconfidence"], plabels)
        add("")
        if S["e1"]:
            _e1_table(add, S["e1"], plabels)
            add("")
        add("| judge | locale | n | accuracy | AUROC | ECE | MCE | Brier | overconfidence | "
            "validated coverage at 5 % |")
        add("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for k, m in S["metrics"].items():
            add(f"| {_who(k, m['role'], m['partial'])} | `{k.split('/')[1]}` | {m['n']} | "
                f"{_f(m['accuracy'])} | {_f(m['auroc'])} | {_f(m['ece'])} | {_f(m['mce'])} | "
                f"{_f(m['brier'])} | {_s(m['overconfidence'])} | "
                f"{_cov(m['validated_coverage']['0.05'])} |")
        add("")

    add("## 8. Served model")
    add("")
    add("The model id each reply says it served (`raw.served`), rows per id. Where it "
        "changed within a checkpoint, each id's rows are reported separately below.")
    add("")
    add("| checkpoint | served (rows) |")
    add("|---|---|")
    for k, c in r["inputs"]["checkpoints"].items():
        add(f"| `{k}`{_mark(k, c['partial'])} | " + (", ".join(f"`{m}` ({n})" for m, n in c["served"].items())
                             or "not recorded") + " |")
    add("")
    for k, segs in P["served_segments"].items():
        add(f"`{k}`{_mark(k, plabels.get(k))}: " + "; ".join(f"`{m}`: {s['n']} rows, accuracy {_f(s['accuracy'])}, "
                                   f"AUROC {_f(s['auroc'])}, ECE {_f(s['ece'])}"
                                   for m, s in segs.items()) + ".")
        add("")

    add("## 9. Inputs")
    add("")
    add("| file | rows | sha256 |")
    add("|---|---:|---|")
    for v in r["inputs"]["labels"].values():
        add(f"| `{v['path']}` | {v['rows']} | `{v['sha256']}` |")
    for k, v in r["inputs"]["checkpoints"].items():
        add(f"| `{v['path']}`{_mark(k, v['partial'])} | {v['rows']} | `{v['sha256']}` |")
    pr = r["inputs"]["predictions"]
    if pr:
        how = (f", sha256 checked against `{pr['verified_against']}`"
               if pr.get("verified_against") else "")
        add(f"| `{pr['path']}` (predictions{how}) | — | `{pr['sha256']}` |")
    add("")
    if not pr:
        add("No prediction was read: the plan is not in the repository yet.")
        add("")
    if r["inputs"]["excluded"]:
        add("Not read: " + "; ".join(f"`{e['file']}` (sha256 `{e['sha256']}`): {e['reason']}"
                                     for e in r["inputs"]["excluded"]) + ".")
        add("")

    C = r["cost"]
    add("## 10. Cost")
    add("")
    add("Recorded list-price cost (`cost_usd`) per checkpoint, its ceiling (`max_usd`) and "
        "any change of ceiling recorded in its header (`max_usd_history`). The provider's "
        "bill can be higher. A judgment of unknown cost is counted, never priced at $0.")
    add("")
    add("| judge | " + " | ".join(f"`{loc}`" for loc in LOCALES)
        + " | total | ceiling per locale | ceiling changes | unknown-cost judgments |")
    add("|---|" + "---:|" * len(LOCALES) + "---:|---|---:|---:|")
    for s, by in C["per_judge"].items():
        cks = {loc: C["checkpoints"].get(f"{s}/{loc}") for loc in LOCALES}
        cells = ["—" if by.get(loc) is None else f"${by[loc]:.4f}" for loc in LOCALES]
        ceil = " / ".join("—" if not c or c["max_usd"] is None else f"${c['max_usd']!r}"
                          for c in cks.values())
        changes = sum(len(c["max_usd_history"]) for c in cks.values() if c)
        unknown = sum(c["unknown_cost_judgments"] for c in cks.values() if c)
        add(f"| {_who(s, 'primary' if s in PRIMARY else 'exploratory')} | "
            + " | ".join(cells) + f" | ${by['total']:.4f} | {ceil} | {changes} | {unknown} |")
    add("")
    for k, c in C["checkpoints"].items():
        for h in c["max_usd_history"]:
            add(f"- `{k}`: ceiling ${h.get('max_usd')} until row {h.get('until_rows')}"
                + (f", amendment {h['amendment']}" if h.get("amendment") else "") + ".")
    if any(c["max_usd_history"] for c in C["checkpoints"].values()):
        add("")
    add(f"Checkpoints read: **${C['read_usd']:.4f}**.")
    add("")
    if C["excluded"]:
        add("Files that enter no figure, listed with their recorded cost only (every line "
            "counted, each one a request): "
            + "; ".join(f"`{e['file']}` " + ("unreadable, cost unknown"
                                             if e["recorded_usd"] is None else
                                             f"${e['recorded_usd']:.4f} over {e['lines']} "
                                             f"lines, {e['unknown_cost_judgments']} of "
                                             "unknown cost")
                        for e in C["excluded"])
            + f". Total recorded cost of the study: **${C['total_usd']:.4f}**.")
        add("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--runs", type=Path, default=RUNS_DIR)
    ap.add_argument("--root", type=Path, default=ROOT, help="where examples/massive/ is")
    ap.add_argument("--predictions", type=Path, default=None,
                    help="a JSON file of the transfer tests' predictions, read instead of the "
                         f"plan's table (local use; by default {PLAN}, once its sha256 "
                         f"matches {PLAN_SHA})")
    ap.add_argument("--out-md", type=Path, default=OUT_MD)
    ap.add_argument("--out-json", type=Path, default=OUT_JSON)
    ap.add_argument("--n-boot", type=int, default=N_BOOT, help=argparse.SUPPRESS)
    ap.add_argument("--jobs", type=int, default=os.cpu_count(),
                    help="parallel bootstrap processes (the output does not depend on it)")
    args = ap.parse_args(argv)
    try:
        d = compute(args.runs, args.root, args.predictions, args.n_boot, args.jobs)
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
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(md, encoding="utf-8")
    args.out_json.write_text(js, encoding="utf-8")
    print(f"wrote {_shown(args.out_md)} and {_shown(args.out_json)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
