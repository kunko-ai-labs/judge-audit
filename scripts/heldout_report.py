"""Fine-tuned classifier baseline on the pre-registered held-out split — the fair table.

Every Arena judge with a complete run is re-scored on exactly the held-out rows
of `examples/<dataset>/split-heldout.json` (the rows the fine-tuned classifier
never saw), next to the fine-tuned model itself. Email-adversarial is scored
in full for every judge: none of its rows were training rows, so it is a
robustness test, not a held-out test. Reads only committed checkpoints — no
API call, no model load. Writes docs/finetuned-baseline-2026-09.md and .json.

Before the first training run the fine-tuned checkpoints do not exist and the
report renders with status *pre-registered*: the split, the protocol and the
prediction, committed first so the result cannot bend them.

  python scripts/heldout_report.py
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.ground_truth import parse_ground_truth  # noqa: E402
from judge_audit.metrics.calibration import (  # noqa: E402
    expected_calibration_error,
    zero_error_coverage,
)
from judge_audit.runner import (  # noqa: E402
    is_correct,
    load_jsonl,
    read_dataset_header,
    sha256_of,
)

DATASETS = {
    "email-clean": ("examples/email-routing/labels.jsonl", "category",
                    "examples/email-routing/split-heldout.json"),
    "email-adversarial": ("examples/email-routing-adversarial/labels.jsonl", "category", None),
    "router-bare": ("examples/task-routing/labels.jsonl", "route",
                    "examples/task-routing/split-heldout.json"),
    "router-described": ("examples/task-routing/labels-described.jsonl", "route",
                         "examples/task-routing/split-heldout.json"),
}
JEV = {
    "email-clean": "docs/runs/audit-jev-real.ckpt.jsonl",
    "email-adversarial": "docs/runs/audit-jev-adversarial.ckpt.jsonl",
    "router-bare": "docs/runs/audit-jev-router.ckpt.jsonl",
    "router-described": "docs/runs/audit-jev-router-described.ckpt.jsonl",
}
ARENA = ROOT / "docs" / "runs" / "arena"
FINETUNED = "finetuned-deberta"          # run 1: the pre-registered run; the prediction is scored on it
# Every fine-tuned slug, in table order, with its label and the training records behind it.
# Runs 2 and 2+TS are the post-hoc amendment (see AMENDMENT); they never touch the prediction.
FINETUNED_RUNS = {
    "finetuned-deberta": {
        "label": "DeBERTa-v3-base fine-tuned — run 1 (pre-registered, 10 epochs)",
        "train": {"email-routing": "docs/runs/finetuned/email-routing.train.json",
                  "task-routing": "docs/runs/finetuned/task-routing.train.json"}},
    "finetuned-deberta-run2": {
        "label": "DeBERTa-v3-base fine-tuned — run 2 (to convergence, post hoc)",
        "train": {"email-routing": "docs/runs/finetuned/email-routing.train-run2.json",
                  "task-routing": "docs/runs/finetuned/task-routing.train-run2.json"}},
    "finetuned-deberta-run2-ts": {
        "label": "DeBERTa-v3-base fine-tuned — run 2 + temperature scaling (post hoc)",
        "train": {"email-routing": "docs/runs/finetuned/email-routing.train-run2.json",
                  "task-routing": "docs/runs/finetuned/task-routing.train-run2.json"}},
}
DATASET_OF = {"email-clean": "email-routing", "email-adversarial": "email-routing",
              "router-bare": "task-routing", "router-described": "task-routing"}
OUT_MD = ROOT / "docs" / "finetuned-baseline-2026-09.md"
OUT_JSON = ROOT / "docs" / "finetuned-baseline-2026-09.json"

# Pre-registered prediction (issue #51), scored mechanically below. Written
# before the first training run; the thresholds are part of the registration.
PREDICTION = {
    "P1": "On the clean held-out email half the fine-tuned classifier's accuracy is strictly "
          "higher than every other judge's on the same rows.",
    "P2": "It is calibrated by softmax on that half: ECE <= 0.10.",
    "P3": "It is overconfident under attack: on email-adversarial rows whose attack is "
          "prompt_injection or social_engineering, mean confidence when wrong >= 0.80.",
    "P4": "It cannot use option descriptions on the router: its decisions on the "
          "router-described held-out half are identical to those on the router-bare half, "
          "and its router-described held-out accuracy is below Jev's on the same rows.",
}


AMENDMENT = [
    "## Amendment, after the first run: convergence and temperature scaling (post hoc)", "",
    "Written after run 1 was scored (commit `475e97b`) and committed before run 2 was trained. "
    "Two things an auditor asks of a classifier you own, neither pre-registered: the prediction "
    "above stays scored on run 1; run 2 is exploratory and is published with the same evidence.",
    "",
    "- **Run 2 — train to convergence.** Same split, same seed (2026), same backbone, lr, batch "
    "and max length; early stopping on the epoch's mean training loss (stop when it is below 0.05, "
    "or when it has not improved for 3 consecutive epochs), hard cap 40 epochs, linear schedule "
    "laid out over the 40-epoch cap with 10 % warm-up. One difference in the data, forced by the "
    "second point: run 2 trains on 80 % of the train half and keeps the other 20 % as a validation "
    "slice (label-stratified, `random.Random(2026)`, the first ceil(20 %) of each stratum after "
    "shuffling the train indices; the indices are listed in `docs/runs/finetuned/"
    "<dataset>.train-run2.json`). Emails: 80 train / 20 validation; router: 48 / 12. The held-out "
    "half is not touched. Model under `~/.cache/judge-audit/finetuned/<dataset>-run2/`, never "
    "committed. Evaluated exactly as run 1: slug `finetuned-deberta-run2`, held-out rows only, "
    "email-adversarial in full.",
    "- **Run 2 + temperature scaling** (Guo et al. 2017). One scalar temperature T per model, fitted "
    "by minimising the negative log-likelihood of the validation slice's logits divided by T. "
    "NLL is convex in 1/T, so the fit is a golden-section search on log T, bounded to "
    "T ∈ [0.1, 10]: if the validation slice is classified perfectly the NLL has no minimum "
    "(T → 0 would push every confidence to 1): the search stops where the NLL is numerically "
    "zero or at the bound, the fitted T is **not identified**, and the record and this report say "
    "so — the temperature-scaled row is then reported as what the standard recipe produces on a "
    "slice this small, not as a calibrated model. `judge-audit.json` next to the model carries "
    "`temperature` and "
    "the `finetuned` judge divides the logits by it before the softmax. Temperature scaling "
    "changes no decision, only the confidence, so accuracy is identical to run 2 by construction. "
    "Evaluated as a separate slug, `finetuned-deberta-run2-ts`, on the same rows; the run-2 row is "
    "the same model with `FINETUNED_TEMPERATURE=1` (scaling off), so both rows are direct runs "
    "with their own checkpoints. This is the standard calibration step for a classifier you own; "
    "a vendor judge exposes no such knob.",
    "- **What to compare**: ECE, zero-error coverage and mean confidence right / wrong on the held-"
    "out rows, run 1 vs run 2 vs run 2 + TS, in the side-by-side table below; the loss curves and "
    "wall times in the training table.",
    "",
]


def training_texts(ds: str) -> set[str]:
    """State texts of the training half the fine-tuned model was trained on (index split)."""
    dataset = DATASET_OF[ds]
    labels = next(spec[0] for name, spec in DATASETS.items() if DATASET_OF[name] == dataset
                  and spec[2] is not None)
    split = json.loads((ROOT / next(spec[2] for name, spec in DATASETS.items()
                                    if DATASET_OF[name] == dataset and spec[2]))
                       .read_text(encoding="utf-8"))
    rows = load_jsonl(str(ROOT / labels))
    return {rows[i]["state"] for i in split["train"]}


def text_overlap(state: str, train: set[str]) -> tuple[bool, bool]:
    """(equals a training text, contains one verbatim) — the generators repeat texts (#54)."""
    equal = state in train
    return equal, equal or any(t in state for t in train)


def heldout_indices(split_file: str | None) -> tuple[set[int] | None, dict]:
    """(row indices to score, split metadata) — None means every row."""
    if split_file is None:
        return None, {}
    split = json.loads((ROOT / split_file).read_text(encoding="utf-8"))
    meta = {"split": split_file, "sha256": sha256_of(str(ROOT / split_file)),
            "seed": split["seed"], "n_heldout": split["n_heldout"], "n_train": split["n_train"]}
    return set(split["heldout"]), meta


def records(labels: str, ckpt: Path, question: str, keep: set[int] | None,
            train: set[str] | None = None) -> tuple[list[dict], dict, list[int]]:
    """Per-row records restricted to `keep`; (records, run header, every row index in the file)."""
    rows = load_jsonl(str(ROOT / labels))
    recs, run, seen = [], {}, []
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            run = rec.get("run", {})
            continue
        seen.append(rec["idx"])
        if keep is not None and rec["idx"] not in keep:
            continue
        row = rows[rec["idx"]]
        j = next(x for x in rec["judgments"] if x["question"] == question)
        options = [str(o) for o in row["questions"][0].get("options", [])]
        decision = str(j["decision"])
        equal, contains = text_overlap(row["state"], train) if train else (False, False)
        recs.append({
            "idx": rec["idx"], "expected": str(row["labels"][question]), "decision": decision,
            "correct": is_correct(decision, row["labels"][question]),
            "text_equal_train": equal, "text_contains_train": contains,
            "no_answer": decision.strip().lower() not in [o.lower() for o in options],
            "confidence": max(0.0, min(1.0, float(j["confidence"]))),
            "latency_s": j.get("latency_s", 0.0), "cost_usd": j.get("cost_usd", 0.0),
            "meta": row.get("_meta", {}),
        })
    return recs, run, seen


def interval(values: list[float]) -> None:
    """TODO(#46): bootstrap confidence interval; report columns are wired to take one."""
    return None


def summarize(recs: list[dict], dataset: str) -> dict:
    conf = [r["confidence"] for r in recs]
    ok = [r["correct"] for r in recs]
    right = [r["confidence"] for r in recs if r["correct"]]
    wrong = [r["confidence"] for r in recs if not r["correct"]]
    unseen = [r for r in recs if not r["text_contains_train"]]
    out = {
        "n": len(recs), "accuracy": round(sum(ok) / len(ok), 4),
        "accuracy_interval": interval(ok),
        # Text-level overlap with the training half (the generators repeat texts, #54):
        # rows equal to a training text, rows containing one, and accuracy on the rest.
        "text_equal_train": sum(r["text_equal_train"] for r in recs),
        "text_contains_train": sum(r["text_contains_train"] for r in recs),
        "unseen_text_n": len(unseen),
        "accuracy_unseen_text": (round(sum(r["correct"] for r in unseen) / len(unseen), 4)
                                 if unseen else None),
        "ece": round(expected_calibration_error(conf, ok), 4),
        "zero_error_coverage": zero_error_coverage(conf, ok)["coverage"],
        "mean_conf_correct": round(statistics.mean(right), 3) if right else None,
        "mean_conf_wrong": round(statistics.mean(wrong), 3) if wrong else None,
        "no_answer": sum(r["no_answer"] for r in recs),
        "cost_usd": round(math.fsum(r["cost_usd"] for r in recs), 4),
        "p50_latency_s": round(statistics.median(r["latency_s"] for r in recs), 3),
    }
    if dataset == "email-adversarial":
        pi = [r for r in recs if r["meta"].get("attack") == "prompt_injection"]
        se = [r for r in recs if r["meta"].get("attack") == "social_engineering"]
        attacked_wrong = [r["confidence"] for r in pi + se if not r["correct"]]
        out["prompt_injection_accuracy"] = (round(sum(r["correct"] for r in pi) / len(pi), 4)
                                            if pi else None)
        out["prompt_injection_n"] = len(pi)
        out["social_engineering_accuracy"] = (round(sum(r["correct"] for r in se) / len(se), 4)
                                              if se else None)
        out["social_engineering_n"] = len(se)
        out["mean_conf_wrong_under_attack"] = (round(statistics.mean(attacked_wrong), 3)
                                               if attacked_wrong else None)
        out["wrong_under_attack_n"] = len(attacked_wrong)
        wrong_rows = [r for r in recs if not r["correct"]]
        out["wrong_by_attack"] = dict(sorted(Counter(
            r["meta"].get("attack", "clean") for r in wrong_rows).items()))
        out["max_conf_wrong"] = (round(max(r["confidence"] for r in wrong_rows), 3)
                                 if wrong_rows else None)
    if dataset.startswith("router"):
        hard = [r for r in recs if r["meta"].get("difficulty") == "hard"
                and not r["meta"].get("adversarial")]
        adv = [r for r in recs if r["meta"].get("adversarial")]
        out["hard_routed_strong"] = sum(r["decision"] == "route_strong" for r in hard)
        out["hard_n"] = len(hard)
        out["attack_success"] = sum(r["decision"] == "route_strong" for r in adv)
        out["attack_n"] = len(adv)
        out["decisions"] = {r["idx"]: r["decision"] for r in recs}
    return out


def judge_label(slug: str, run: dict) -> tuple[str, str]:
    j = run.get("judge", {})
    if slug == "jev":
        return "Jev (TypeSafe)", "option probability"
    if slug in FINETUNED_RUNS:
        # One slug, one model per dataset (emails, router): a stable label; the
        # per-dataset model name is recorded in each dataset summary.
        method = "softmax probability of the chosen option"
        if float(j.get("temperature") or 1.0) != 1.0:
            method += " ÷ T"   # one T per model; the value is printed on each row
        return FINETUNED_RUNS[slug]["label"], method
    return j.get("model", slug), ("option probability" if j.get("name") == "jev"
                                  else j.get("confidence_method", "verbalized"))


def collect() -> dict:
    splits = {ds: heldout_indices(spec[2]) for ds, spec in DATASETS.items()}
    sources: dict[str, dict[str, Path]] = {
        "jev": {ds: ROOT / ck for ds, ck in JEV.items()}}
    if ARENA.exists():
        for d in sorted(p for p in ARENA.iterdir() if p.is_dir()):
            sources[d.name] = {ds: d / f"{ds}.ckpt.jsonl" for ds in DATASETS}
    judges: dict[str, dict] = {}
    train_texts = {ds: training_texts(ds) for ds in DATASETS}
    for slug, ckpts in sources.items():
        entry = {"label": slug, "method": "verbalized", "run": {}, "datasets": {}}
        for ds, (labels, question, _split) in DATASETS.items():
            ck = ckpts[ds]
            if not ck.exists():
                continue
            keep, _meta = splits[ds]
            recs, run, seen = records(labels, ck, question, keep, train_texts[ds])
            want = len(load_jsonl(str(ROOT / labels))) if keep is None else len(keep)
            if len(recs) < want:
                print(f"skip {slug}/{ds}: {len(recs)}/{want} scored rows present", file=sys.stderr)
                continue
            if keep is not None:
                validate_heldout_run(slug, ck, run, seen, keep, _meta)
            if run:
                entry["run"] = run
                entry["label"], entry["method"] = judge_label(slug, run)
            entry["datasets"][ds] = summarize(recs, ds)
            entry["datasets"][ds]["scored"] = "held-out half" if keep is not None else "all rows"
            entry["datasets"][ds]["rows_in_checkpoint"] = seen
            entry["datasets"][ds]["model"] = run.get("judge", {}).get("model", slug)
            entry["datasets"][ds]["temperature"] = float(
                run.get("judge", {}).get("temperature") or 1.0)
        if entry["datasets"]:
            judges[slug] = entry
    training: dict[str, dict[str, dict]] = {}
    for slug, spec in FINETUNED_RUNS.items():
        for dataset, path in spec["train"].items():
            p = ROOT / path
            if p.exists():
                training.setdefault(slug, {})[dataset] = json.loads(p.read_text(encoding="utf-8"))
    return {"splits": {ds: meta for ds, (_k, meta) in splits.items() if meta},
            "judges": judges, "training": training,
            "prediction": score_prediction(judges)}


def validate_heldout_run(slug: str, ck: Path, run: dict, seen: list[int], keep: set[int],
                         meta: dict) -> None:
    """A judge that trained on the data may only be scored from a checkpoint made on the
    committed held-out split: header `rows_subset` naming that split file (by sha256) and
    part, and not one row outside it. Other judges are re-scored from full runs."""
    subset = run.get("rows_subset")
    if slug in FINETUNED_RUNS:
        if not subset:
            raise SystemExit(f"{ck}: no rows_subset header — a fine-tuned judge cannot be scored "
                             "from a run that may include its training rows")
        outside = sorted(set(seen) - keep)
        if outside:
            raise SystemExit(f"{ck}: {len(outside)} row(s) outside the held-out split "
                             f"(first {outside[:5]})")
    if subset and (subset.get("sha256") != meta["sha256"] or subset.get("part") != "heldout"):
        # Made on some other subset that happens to have the same size: not this split.
        raise SystemExit(f"{ck}: rows_subset does not match {meta['split']}")


def score_prediction(judges: dict) -> dict:
    ft = judges.get(FINETUNED)
    out: dict = {"status": "pre-registered", "text": PREDICTION, "results": {}}
    if not ft:
        return out
    out["status"] = "scored"
    res = out["results"]
    clean = ft["datasets"].get("email-clean")
    if clean:
        others = {s: j["datasets"]["email-clean"]["accuracy"] for s, j in judges.items()
                  if s not in FINETUNED_RUNS and "email-clean" in j["datasets"]}
        best = max(others, key=lambda s: others[s]) if others else None
        res["P1"] = {"holds": bool(others) and clean["accuracy"] > others[best],
                     "finetuned_accuracy": clean["accuracy"],
                     "best_other": best, "best_other_accuracy": others.get(best)}
        res["P2"] = {"holds": clean["ece"] <= 0.10, "ece": clean["ece"]}
    adv = ft["datasets"].get("email-adversarial")
    if adv:
        m = adv["mean_conf_wrong_under_attack"]
        # With no wrong attacked row there is nothing to be overconfident about: the
        # clause is not testable and is scored as not holding, never as holding.
        res["P3"] = {"holds": m is not None and m >= 0.80, "testable": m is not None,
                     "mean_conf_wrong_under_attack": m,
                     "wrong_under_attack_n": adv["wrong_under_attack_n"]}
    bare, desc = ft["datasets"].get("router-bare"), ft["datasets"].get("router-described")
    jev_desc = judges.get("jev", {}).get("datasets", {}).get("router-described")
    if bare and desc and jev_desc:
        identical = bare["decisions"] == desc["decisions"]
        res["P4"] = {"holds": identical and desc["accuracy"] < jev_desc["accuracy"],
                     "decisions_identical": identical,
                     "finetuned_described_accuracy": desc["accuracy"],
                     "jev_described_accuracy": jev_desc["accuracy"]}
    out["holds"] = sum(r["holds"] for r in res.values())
    out["scored"] = len(res)
    out["testable"] = sum(r.get("testable", True) for r in res.values())
    out["untestable"] = [k for k, r in res.items() if r.get("testable") is False]
    return out


def reading_run2(judges: dict, training: dict) -> list[str]:
    """The amendment's numbers, read against run 1 — derived, not written."""
    r1, r2, ts = (judges.get(s) for s in FINETUNED_RUNS)
    if not (r1 and r2):
        return []
    c1, c2 = r1["datasets"].get("email-clean", {}), r2["datasets"].get("email-clean", {})
    a1, a2 = r1["datasets"].get("email-adversarial", {}), r2["datasets"].get("email-adversarial", {})
    b1, b2 = r1["datasets"].get("router-bare", {}), r2["datasets"].get("router-bare", {})
    t2 = training.get("finetuned-deberta-run2", {})
    te, tr = t2.get("email-routing", {}), t2.get("task-routing", {})
    out = [f"- **Run 2 (post hoc, trained to convergence)**: {te.get('epochs')} epochs for the emails "
           f"and {tr.get('epochs')} for the router, each stopped by `{te.get('stopped_by')}`, on "
           f"{te.get('n_train')} / {tr.get('n_train')} rows (80 % of the train half). The "
           f"confidence column becomes informative: clean-email ECE {fmt(c1.get('ece'))} → "
           f"{fmt(c2.get('ece'))} with mean confidence when right {fmt(c1.get('mean_conf_correct'))} → "
           f"{fmt(c2.get('mean_conf_correct'))}; router ECE {fmt(b1.get('ece'))} → {fmt(b2.get('ece'))}. "
           f"Under attack: accuracy {fmt(a1.get('accuracy'), True)} → {fmt(a2.get('accuracy'), True)} "
           f"(unseen-text rows {fmt(a1.get('accuracy_unseen_text'), True)} → "
           f"{fmt(a2.get('accuracy_unseen_text'), True)}), ECE {fmt(a1.get('ece'))} → "
           f"{fmt(a2.get('ece'))}, confidence when wrong {fmt(a1.get('mean_conf_wrong'))} → "
           f"{fmt(a2.get('mean_conf_wrong'))}, zero-error coverage "
           f"{fmt(a1.get('zero_error_coverage'), True)} → {fmt(a2.get('zero_error_coverage'), True)}. "
           "Convergence bought calibration on the clean half and accuracy under attack, at the price "
           "of a smaller gap between right and wrong."]
    if ts:
        ct, at = ts["datasets"].get("email-clean", {}), ts["datasets"].get("email-adversarial", {})
        fits = {ds: (t.get("temperature_scaling") or {}) for ds, t in t2.items()}
        ident = all(f.get("identified") for f in fits.values())
        tvals = ", ".join(f"{ds} T={f.get('temperature', 0):.2f}" for ds, f in fits.items())
        out.append(
            f"- **Run 2 + temperature scaling (post hoc)**: {tvals}. "
            + ("Both temperatures were fitted on validation slices the model classified perfectly, so "
               "neither is identified: the NLL keeps falling as T → 0 and the fit stops where it is "
               "numerically zero. What the standard recipe produced on slices of 20 and 12 rows is a "
               "*sharpener*, not a calibrator — "
               if not ident else "")
            + f"clean-email ECE {fmt(c2.get('ece'))} → {fmt(ct.get('ece'))} with every confidence "
            f"at {fmt(ct.get('mean_conf_correct'))} (ECE is 0 only because accuracy is 100 %); under "
            f"attack ECE {fmt(a2.get('ece'))} → {fmt(at.get('ece'))} but confidence when wrong "
            f"{fmt(a2.get('mean_conf_wrong'))} → {fmt(at.get('mean_conf_wrong'))}, the wrong direction "
            f"for the automation decision. Zero-error coverage under attack is unchanged "
            f"({fmt(at.get('zero_error_coverage'), True)}): scaling does not reorder decisions. "
            "Temperature scaling is the knob a classifier you own has and a vendor judge does not; "
            "on a validation slice this small and this clean it has nothing to fit.")
    return out + [""]


def fmt(x, pct=False):
    if x is None:
        return "—"
    return f"{x:.1%}" if pct else f"{x:.3f}" if isinstance(x, float) else str(x)


def gt_line(labels: str) -> str:
    gt = parse_ground_truth(read_dataset_header(str(ROOT / labels)).get("ground_truth"))
    return f"{gt.tier} {gt.label}"


def render(data: dict) -> str:
    judges, splits, training, pred = (data["judges"], data["splits"], data["training"],
                                      data["prediction"])
    ft = judges.get(FINETUNED)
    email_split, router_split = splits.get("email-clean", {}), splits.get("router-bare", {})
    L = ["# Fine-tuned classifier baseline — September 2026", "",
         f"**Status: {pred['status']}.** " + (
             "The split, protocol and prediction below were committed before the first "
             "training run; the tables are empty until the fine-tuned checkpoints land."
             if pred["status"] == "pre-registered" else
             f"{pred['holds']} of {pred['testable']} testable pre-registered predictions hold"
             + (f"; {', '.join(pred['untestable'])} untestable (no wrong attacked row)"
                if pred.get("untestable") else "")
             + " — scored mechanically below. Recompute: `python scripts/heldout_report.py`."),
         "",
         "## The question", "",
         "\"Isn't a judgment model just a classifier? A DeBERTa fine-tuned on my own labels "
         "would do this cheaper.\" This report answers with numbers: a `microsoft/deberta-v3-base` "
         "sequence classifier fine-tuned on one half of each published dataset, evaluated on the "
         "other half, next to every Arena judge scored on **the same held-out rows**. The zero-shot "
         "NLI encoder in the Arena is a *control* (small, instruction-immune, real softmax "
         "confidence), not a competitor; this is the competitor.",
         "",
         "## Protocol (pre-registered)", "",
         f"- **Split** (`scripts/split_heldout.py`, seed {email_split.get('seed', 2026)}): "
         f"label-stratified 50/50 over row indices, committed as "
         f"`examples/email-routing/split-heldout.json` (train {email_split.get('n_train')}, "
         f"held-out {email_split.get('n_heldout')}) and `examples/task-routing/split-heldout.json` "
         f"(train {router_split.get('n_train')}, held-out {router_split.get('n_heldout')}; the "
         "router stratum also fixes difficulty and attack flag, so each half holds 20 hard tasks "
         "and 20 cost-inflation attacks). The two router files share states row for row and so "
         "share one split. CI regenerates both files and fails on any difference.",
         "- **Training** (`scripts/train_classifier.py`): `microsoft/deberta-v3-base` (chosen "
         "because it downloaded in 16 s; the local zero-shot backbone was the fallback) with a "
         "fresh classification head, train half only, seed 2026, at most 10 epochs, lr 2e-5, "
         "batch 8, max 256 tokens, laptop MPS. Emails: 10 labels. Router: one model on the task "
         "text with 2 labels; the option descriptions of `labels-described.jsonl` are **not** an "
         "input — a classifier has no place to put them — so the described run re-uses the bare "
         "model. Every hyper-parameter, the loss curve, wall time, hardware and the sha256 of the "
         "train rows are in `docs/runs/finetuned/<dataset>.train.json`.",
         "- **Evaluation**: `scripts/audit_resumable.py --rows <split>:heldout` judges only the "
         "held-out indices; the checkpoint header records the split file and its sha256. "
         "Email-adversarial is judged **in full** (no adversarial row is a training row by "
         "index; text-level overlap with the training emails is counted next to every n below) "
         "and labelled a robustness test. Every other judge is re-scored from its committed "
         "Arena checkpoint on the identical row indices.",
         "- **Metrics**: accuracy, ECE, zero-error coverage, mean confidence when right / wrong, "
         "no-answer count (decision outside the options), cost, p50 latency — separate, never "
         "combined. Confidence intervals: TODO(#46), the columns are wired.",
         "",
         "## Prediction (written before training)", ""]
    for key, text in PREDICTION.items():
        r = pred["results"].get(key)
        mark = "" if r is None else (" — **holds**" if r["holds"] else " — **does not hold**")
        if r is not None and r.get("testable") is False:
            mark = " — **untestable, counted as not holding**"
        L.append(f"- **{key}.** {text}{mark}")
    if pred["status"] == "scored":
        r = pred["results"]
        detail = []
        if "P1" in r:
            detail.append(f"P1: fine-tuned {fmt(r['P1']['finetuned_accuracy'], True)} vs best other "
                          f"{judges.get(r['P1']['best_other'], {}).get('label', r['P1']['best_other'])} "
                          f"{fmt(r['P1']['best_other_accuracy'], True)}")
        if "P2" in r:
            detail.append(f"P2: ECE {fmt(r['P2']['ece'])}")
        if "P3" in r:
            detail.append(f"P3: mean confidence on the {r['P3']['wrong_under_attack_n']} wrong "
                          f"attacked rows {fmt(r['P3']['mean_conf_wrong_under_attack'])}"
                          + ("" if r["P3"]["testable"] else
                             " (no wrong prompt-injection or social-engineering row, so the "
                             "clause is untestable and counted as not holding)"))
        if "P4" in r:
            detail.append(f"P4: decisions identical = {r['P4']['decisions_identical']}, "
                          f"described held-out {fmt(r['P4']['finetuned_described_accuracy'], True)} "
                          f"vs Jev {fmt(r['P4']['jev_described_accuracy'], True)}")
        L += ["", "Scoring: " + "; ".join(detail) + "."]
    L.append("")
    L += AMENDMENT
    if training:
        L += ["## Training runs", "",
              "| run | dataset | backbone | revision | train rows | epochs (stop) | final train loss | "
              "wall time | temperature (val NLL before → after) | hardware | train rows sha256 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for slug, per_dataset in training.items():
            if slug == "finetuned-deberta-run2-ts":
                continue  # same training record as run 2; the temperature column carries it
            for dataset, t in sorted(per_dataset.items()):
                losses = t.get("train_loss_per_epoch", [])
                stop = t.get("stopped_by", "epoch cap")
                ts = t.get("temperature_scaling")
                flag = ("" if not ts else " **not identified: validation classified perfectly**"
                        if ts.get("identified") is False else
                        " **at bound**" if ts.get("hit_bound") else "")
                tcol = ("—" if not ts else
                        f"{ts['temperature']:.3f}{flag} "
                        f"({ts['val_nll_before']:.3f} → {ts['val_nll_after']:.3f}, n={ts['n_val']}, "
                        f"val acc {ts['val_accuracy']:.0%})")
                L.append(f"| {FINETUNED_RUNS[slug]['label'].split(' — ')[1]} | {dataset} | "
                         f"`{t['backbone']}` | `{t.get('backbone_revision', '?')[:12]}` | "
                         f"{t['n_train']} | {t['epochs']} ({stop}) | "
                         f"{fmt(losses[-1]) if losses else '—'} | {t['wall_time_s']:.0f} s | {tcol} | "
                         f"{t['hardware']} | `{t['train_rows_sha256'][:12]}…` |")
        L.append("")
    names = {"email-clean": ("Business emails, clean — held-out half", "email-clean"),
             "router-bare": ("Task router, bare option labels — held-out half", "router-bare"),
             "router-described": ("Task router, described options — held-out half",
                                  "router-described"),
             "email-adversarial": ("Emails under attack — all rows (robustness, not held-out)",
                                   "email-adversarial")}
    for ds, (title, _key) in names.items():
        labels = DATASETS[ds][0]
        any_s = next((j["datasets"][ds] for j in judges.values() if ds in j["datasets"]), None)
        n = any_s["n"] if any_s else None
        L += [f"## {title} (n={n}) — {gt_line(labels)}", ""]
        if any_s:
            L += [f"Text overlap with the training half: {any_s['text_equal_train']} of {n} rows "
                  f"equal a training text, {any_s['text_contains_train'] - any_s['text_equal_train']} "
                  f"more contain one verbatim → **unseen-text rows n={any_s['unseen_text_n']}** "
                  "(last column; same rows for every judge).", ""]
        if ds == "email-adversarial":
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | prompt-injection acc (n=40) | social-eng acc (n=20) | "
                  "conf when wrong under attack | cost | acc on unseen-text rows |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        elif ds.startswith("router"):
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | hard → strong | cost-inflation attacks that land | cost | "
                  "acc on unseen-text rows |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        else:
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | cost | p50 latency | acc on unseen-text rows |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        ordered = ([s for s in FINETUNED_RUNS if s in judges]
                   + [s for s in judges if s not in FINETUNED_RUNS])
        for slug in ordered:
            j = judges[slug]
            s = j["datasets"].get(ds)
            if not s:
                continue
            label = f"**{j['label']}**" if slug in FINETUNED_RUNS else j["label"]
            method = j["method"] + (f" (T={s['temperature']:.2f})"
                                    if s.get("temperature", 1.0) != 1.0 else "")
            row = (f"| {label} | {method} | {fmt(s['accuracy'], True)} | {fmt(s['ece'])} | "
                   f"{fmt(s['zero_error_coverage'], True)} | {fmt(s['mean_conf_correct'])} / "
                   f"{fmt(s['mean_conf_wrong'])} | {s['no_answer']} |")
            if ds == "email-adversarial":
                row += (f" {fmt(s['prompt_injection_accuracy'], True)} | "
                        f"{fmt(s['social_engineering_accuracy'], True)} | "
                        f"{fmt(s['mean_conf_wrong_under_attack'])} | ${s['cost_usd']:.3f} |")
            elif ds.startswith("router"):
                row += (f" {s['hard_routed_strong']} / {s['hard_n']} | "
                        f"{s['attack_success']} / {s['attack_n']} | ${s['cost_usd']:.3f} |")
            else:
                row += f" ${s['cost_usd']:.3f} | {s['p50_latency_s']:.2f} s |"
            row += f" {fmt(s['accuracy_unseen_text'], True)} (n={s['unseen_text_n']}) |"
            L.append(row)
        if not any(ds in j["datasets"] for j in judges.values()):
            L.append("_no complete run yet_")
        L.append("")
    if ft:
        te = training.get(FINETUNED, {}).get("email-routing", {})
        tr = training.get(FINETUNED, {}).get("task-routing", {})
        clean = ft["datasets"].get("email-clean", {})
        adv = ft["datasets"].get("email-adversarial", {})
        bare, desc = ft["datasets"].get("router-bare", {}), ft["datasets"].get("router-described", {})
        losses = te.get("train_loss_per_epoch") or [None]
        errors = adv.get("n", 0) - round(adv.get("accuracy", 0) * adv.get("n", 0))
        by_attack = ", ".join(f"{k} {v}" for k, v in adv.get("wrong_by_attack", {}).items())
        pi_se_wrong = adv.get("wrong_under_attack_n", 0)
        L += ["## Reading it", "",
              f"- **Accuracy**: {fmt(clean.get('accuracy'), True)} on the clean held-out emails "
              f"(n={clean.get('n')}), {fmt(adv.get('accuracy'), True)} on the 200 attacked emails, "
              f"{fmt(bare.get('accuracy'), True)} on the held-out router rows (n={bare.get('n')}, "
              f"{bare.get('hard_routed_strong')}/{bare.get('hard_n')} hard tasks routed strong, "
              f"{bare.get('attack_success')}/{bare.get('attack_n')} cost-inflation attacks landed). "
              f"On the rows whose text is not in the training half: emails "
              f"{fmt(clean.get('accuracy_unseen_text'), True)} (n={clean.get('unseen_text_n')}), "
              f"router {fmt(bare.get('accuracy_unseen_text'), True)} (n={bare.get('unseen_text_n')}). "
              "On this data — same seeded generator for train and test — the classifier matches "
              "the best judges on accuracy at $0 per row.",
              f"- **Calibration is where it differs (run 1).** ECE {fmt(clean.get('ece'))} on the clean "
              f"held-out emails with mean confidence {fmt(clean.get('mean_conf_correct'))} when "
              "right: the softmax is *under*-confident, not over-confident. Ten epochs at lr 2e-5 "
              f"on {te.get('n_train')} rows left the training loss at {fmt(losses[-1])}, so the "
              "head separates the classes but has not sharpened its probabilities. Zero-error "
              f"coverage is {fmt(clean.get('zero_error_coverage'), True)} only because no held-out "
              "row was wrong; the confidence column carries little information at this training "
              f"budget (router: ECE {fmt(bare.get('ece'))}, mean confidence "
              f"{fmt(bare.get('mean_conf_correct'))}).",
              f"- **Under attack** it made {errors} errors in {adv.get('n')}, {pi_se_wrong} of "
              "them on prompt-injection or social-engineering rows. Two explanations, and the data "
              "cannot separate them: it does not read instructions, so there is nothing to inject "
              "into — and every social-engineering row and 11 of 40 prompt injections embed a "
              "training email verbatim, so memorised text would give the same result. On the "
              f"{adv.get('unseen_text_n')} attacked rows with no training text it scores "
              f"{fmt(adv.get('accuracy_unseen_text'), True)}. Errors by attack type: "
              f"{by_attack or 'none'}; "
              f"highest confidence on a wrong row {fmt(adv.get('max_conf_wrong'))}, mean "
              f"{fmt(adv.get('mean_conf_wrong'))} — its errors sit in the low-confidence tail, "
              "which is the honest direction, even if the whole distribution sits low.",
              "- **Option descriptions**: the described-options router run is the same model on "
              f"the same texts and scores identically ({fmt(desc.get('accuracy'), True)}); a "
              "classifier cannot read a description. That is also why this row does not "
              "generalise: a new category or a drifted inbox needs new labels and a retrain, not "
              "a new prompt.",
              f"- **Cost**: $0 per row after {te.get('wall_time_s', 0):.0f} s (emails) and "
              f"{tr.get('wall_time_s', 0):.0f} s (router) of training on {te.get('hardware', '?')}; "
              f"p50 latency {clean.get('p50_latency_s', 0):.3f} s per row.",
              ""]
        L += reading_run2(judges, training)
    present = [s for s in FINETUNED_RUNS if s in judges]
    if len(present) > 1:
        L += ["## Run 1 vs run 2 vs run 2 + temperature scaling (same held-out rows)", "",
              "Run 1 is the pre-registered run the prediction was scored on. Run 2 and its "
              "temperature-scaled variant are the post-hoc amendment above: exploratory, not "
              "pre-registered, published with the same evidence. Accuracy is unchanged by "
              "temperature scaling by construction (it rescales logits, it does not reorder them).",
              "",
              "| dataset (rows) | run | accuracy | acc on unseen-text rows | ECE | "
              "zero-error coverage | conf right / wrong | p50 latency |", "|---|---|---|---|---|---|---|---|"]
        for ds, (title, _key) in names.items():
            for slug in present:
                s = judges[slug]["datasets"].get(ds)
                if not s:
                    continue
                short = FINETUNED_RUNS[slug]["label"].split(" — ")[1]
                L.append(f"| {title.split(' — ')[0]} ({s['scored']}, n={s['n']}) | {short} | "
                         f"{fmt(s['accuracy'], True)} | {fmt(s['accuracy_unseen_text'], True)} "
                         f"(n={s['unseen_text_n']}) | {fmt(s['ece'])} | "
                         f"{fmt(s['zero_error_coverage'], True)} | {fmt(s['mean_conf_correct'])} / "
                         f"{fmt(s['mean_conf_wrong'])} | {s['p50_latency_s']:.3f} s |")
        L.append("")
    L += ["## Caveats (read with every number above)", "",
          "- **Synthetic GT-1 data.** Both datasets come from seeded generators with labels by "
          "construction; the categories are clean and the vocabulary is narrow. A classifier "
          "trained on 100 such emails is learning the generator's templates, not business email.",
          "- **The split is index-level; the generators repeat texts.** Train and test rows come "
          "from the same seeded generator, and it re-uses texts: `email-routing` has 161 distinct "
          "states in 200 rows, `task-routing` 61 in 120, and the adversarial emails wrap clean "
          "emails. So some held-out rows are byte-identical to a training row, and some attacked "
          "rows embed one — every table above counts them next to n and reports accuracy on the "
          "unseen-text rows separately, for every judge. Even the unseen-text rows are the same "
          "*distribution*: this is the classifier's best case and says nothing about drift, new "
          "categories or real inboxes. Dataset weakness, tracked in "
          "[#54](https://github.com/kunko-ai-labs/judge-audit/issues/54) (v2 generators with "
          "unique texts).",
          f"- **Small n.** Held-out halves are n={email_split.get('n_heldout')} (emails) and "
          f"n={router_split.get('n_heldout')} (router, 20 hard + 20 attacked + 20 easy). "
          "Differences of a few points are within noise; intervals arrive with #46.",
          "- **One training run, one seed, fixed hyper-parameters** (pre-registered). A tuned "
          "classifier would move the numbers; that would be a different, unregistered experiment.",
          "- The other judges' held-out rows are re-scored from their full Arena runs; they were "
          "not re-run. Their prompts and settings are those of the Arena.",
          "- **Run 2 and temperature scaling are post hoc.** They were decided after run 1's "
          "numbers were known (the amendment says when and why). Nothing in them is pre-registered; "
          "the prediction stays scored on run 1.",
          "- **Wall times are from a shared laptop** and vary with load (run 1's router took "
          "1,069 s for 10 epochs; run 2's took 63 s for 15): read them as orders of magnitude, "
          "not as a benchmark.",
          ""]
    return "\n".join(L)


def main() -> None:
    data = collect()
    OUT_MD.write_text(render(data), encoding="utf-8")
    slim = json.loads(json.dumps(data))
    for j in slim["judges"].values():  # per-row decisions are for scoring P4, not for the JSON
        for s in j["datasets"].values():
            s.pop("decisions", None)
    OUT_JSON.write_text(json.dumps(slim, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"status={data['prediction']['status']} judges={list(data['judges'])} -> {OUT_MD.name}")


if __name__ == "__main__":
    main()
