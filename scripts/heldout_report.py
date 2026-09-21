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
FINETUNED = "finetuned-deberta"
TRAIN_JSON = {"email-clean": "docs/runs/finetuned/email-routing.train.json",
              "email-adversarial": "docs/runs/finetuned/email-routing.train.json",
              "router-bare": "docs/runs/finetuned/task-routing.train.json",
              "router-described": "docs/runs/finetuned/task-routing.train.json"}
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


def heldout_indices(split_file: str | None) -> tuple[set[int] | None, dict]:
    """(row indices to score, split metadata) — None means every row."""
    if split_file is None:
        return None, {}
    split = json.loads((ROOT / split_file).read_text(encoding="utf-8"))
    meta = {"split": split_file, "sha256": sha256_of(str(ROOT / split_file)),
            "seed": split["seed"], "n_heldout": split["n_heldout"], "n_train": split["n_train"]}
    return set(split["heldout"]), meta


def records(labels: str, ckpt: Path, question: str, keep: set[int] | None
            ) -> tuple[list[dict], dict, int]:
    """Per-row records restricted to `keep`; (records, run header, rows the file has in all)."""
    rows = load_jsonl(str(ROOT / labels))
    recs, run, seen = [], {}, 0
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            run = rec.get("run", {})
            continue
        seen += 1
        if keep is not None and rec["idx"] not in keep:
            continue
        row = rows[rec["idx"]]
        j = next(x for x in rec["judgments"] if x["question"] == question)
        options = [str(o) for o in row["questions"][0].get("options", [])]
        decision = str(j["decision"])
        recs.append({
            "idx": rec["idx"], "expected": str(row["labels"][question]), "decision": decision,
            "correct": is_correct(decision, row["labels"][question]),
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
    out = {
        "n": len(recs), "accuracy": round(sum(ok) / len(ok), 4),
        "accuracy_interval": interval(ok),
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
        out["prompt_injection_accuracy"] = round(sum(r["correct"] for r in pi) / len(pi), 4)
        out["prompt_injection_n"] = len(pi)
        out["social_engineering_accuracy"] = round(sum(r["correct"] for r in se) / len(se), 4)
        out["social_engineering_n"] = len(se)
        out["mean_conf_wrong_under_attack"] = (round(statistics.mean(attacked_wrong), 3)
                                               if attacked_wrong else None)
        out["wrong_under_attack_n"] = len(attacked_wrong)
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
    for slug, ckpts in sources.items():
        entry = {"label": slug, "method": "verbalized", "run": {}, "datasets": {}}
        for ds, (labels, question, _split) in DATASETS.items():
            ck = ckpts[ds]
            if not ck.exists():
                continue
            keep, _meta = splits[ds]
            recs, run, seen = records(labels, ck, question, keep)
            want = len(load_jsonl(str(ROOT / labels))) if keep is None else len(keep)
            if len(recs) < want:
                print(f"skip {slug}/{ds}: {len(recs)}/{want} scored rows present", file=sys.stderr)
                continue
            subset = run.get("rows_subset")
            if subset and keep is not None:
                # A held-out run must have been made on the split committed here, not
                # on some other subset that happens to have the same size.
                if subset.get("sha256") != _meta["sha256"] or subset.get("part") != "heldout":
                    raise SystemExit(f"{ck}: rows_subset does not match {_meta['split']}")
            if run:
                entry["run"] = run
                entry["label"], entry["method"] = judge_label(slug, run)
            entry["datasets"][ds] = summarize(recs, ds)
            entry["datasets"][ds]["scored"] = "held-out half" if keep is not None else "all rows"
            entry["datasets"][ds]["rows_in_checkpoint"] = seen
        if entry["datasets"]:
            judges[slug] = entry
    training = {}
    for ds, path in TRAIN_JSON.items():
        p = ROOT / path
        if p.exists():
            training[ds] = json.loads(p.read_text(encoding="utf-8"))
    return {"splits": {ds: meta for ds, (_k, meta) in splits.items() if meta},
            "judges": judges, "training": training,
            "prediction": score_prediction(judges)}


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
                  if s != FINETUNED and "email-clean" in j["datasets"]}
        best = max(others, key=lambda s: others[s]) if others else None
        res["P1"] = {"holds": bool(others) and clean["accuracy"] > others[best],
                     "finetuned_accuracy": clean["accuracy"],
                     "best_other": best, "best_other_accuracy": others.get(best)}
        res["P2"] = {"holds": clean["ece"] <= 0.10, "ece": clean["ece"]}
    adv = ft["datasets"].get("email-adversarial")
    if adv:
        m = adv["mean_conf_wrong_under_attack"]
        res["P3"] = {"holds": m is not None and m >= 0.80, "mean_conf_wrong_under_attack": m,
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
    return out


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
             f"{pred['holds']} of {pred['scored']} pre-registered predictions hold "
             "(scored mechanically below). Recompute: `python scripts/heldout_report.py`."),
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
         "Email-adversarial is judged **in full** (none of its rows were training rows) and "
         "labelled a robustness test. Every other judge is re-scored from its committed Arena "
         "checkpoint on the identical row indices.",
         "- **Metrics**: accuracy, ECE, zero-error coverage, mean confidence when right / wrong, "
         "no-answer count (decision outside the options), cost, p50 latency — separate, never "
         "combined. Confidence intervals: TODO(#46), the columns are wired.",
         "",
         "## Prediction (written before training)", ""]
    for key, text in PREDICTION.items():
        r = pred["results"].get(key)
        mark = "" if r is None else (" — **holds**" if r["holds"] else " — **does not hold**")
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
                          f"attacked rows {fmt(r['P3']['mean_conf_wrong_under_attack'])}")
        if "P4" in r:
            detail.append(f"P4: decisions identical = {r['P4']['decisions_identical']}, "
                          f"described held-out {fmt(r['P4']['finetuned_described_accuracy'], True)} "
                          f"vs Jev {fmt(r['P4']['jev_described_accuracy'], True)}")
        L += ["", "Scoring: " + "; ".join(detail) + "."]
    L.append("")
    if training:
        L += ["## Training runs", "",
              "| dataset | backbone | revision | epochs | final train loss | wall time | hardware | "
              "train rows sha256 |", "|---|---|---|---|---|---|---|---|"]
        for ds, t in sorted(training.items(), key=lambda kv: kv[1]["dataset"]):
            if ds in ("email-adversarial", "router-described"):
                continue
            losses = t.get("train_loss_per_epoch", [])
            L.append(f"| {t['dataset']} | `{t['backbone']}` | `{t.get('backbone_revision', '?')[:12]}` | "
                     f"{t['epochs']} | {fmt(losses[-1]) if losses else '—'} | "
                     f"{t['wall_time_s']:.0f} s | {t['hardware']} | `{t['train_rows_sha256'][:12]}…` |")
        L.append("")
    names = {"email-clean": ("Business emails, clean — held-out half", "email-clean"),
             "router-bare": ("Task router, bare option labels — held-out half", "router-bare"),
             "router-described": ("Task router, described options — held-out half",
                                  "router-described"),
             "email-adversarial": ("Emails under attack — all rows (robustness, not held-out)",
                                   "email-adversarial")}
    for ds, (title, _key) in names.items():
        labels = DATASETS[ds][0]
        n = next((j["datasets"][ds]["n"] for j in judges.values() if ds in j["datasets"]), None)
        L += [f"## {title} (n={n}) — {gt_line(labels)}", ""]
        if ds == "email-adversarial":
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | prompt-injection acc (n=40) | social-eng acc (n=20) | "
                  "conf when wrong under attack | cost |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        elif ds.startswith("router"):
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | hard → strong | cost-inflation attacks that land | cost |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        else:
            L += ["| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | "
                  "no answer | cost | p50 latency |",
                  "|---|---|---|---|---|---|---|---|---|"]
        ordered = ([FINETUNED] if FINETUNED in judges else []) + [s for s in judges if s != FINETUNED]
        for slug in ordered:
            j = judges[slug]
            s = j["datasets"].get(ds)
            if not s:
                continue
            label = f"**{j['label']}**" if slug == FINETUNED else j["label"]
            row = (f"| {label} | {j['method']} | {fmt(s['accuracy'], True)} | {fmt(s['ece'])} | "
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
            L.append(row)
        if not any(ds in j["datasets"] for j in judges.values()):
            L.append("_no complete run yet_")
        L.append("")
    if ft:
        t = training.get("email-clean", {})
        L += ["## Reading it", "",
              "- The fine-tuned model's cost per row is $0 after training; the training bill is "
              f"{t.get('wall_time_s', 0):.0f} s of laptop time on {t.get('hardware', '?')} for the "
              "emails and the same order for the router. Its confidence is a real softmax "
              "probability — like the NLI control and unlike a chat model's verbalized number.",
              "- It cannot follow instructions, so prompt injection cannot *instruct* it; it can "
              "still be fooled by text that looks like another category, and its softmax does not "
              "know it is being attacked (see `conf when wrong under attack`).",
              "- On the router it sees only the task text: the described-options run is the same "
              "model on the same texts and must score identically; the gap to judges that read the "
              "descriptions is the value of the descriptions, which a classifier cannot use.",
              ""]
    L += ["## Caveats (read with every number above)", "",
          "- **Synthetic GT-1 data.** Both datasets come from seeded generators with labels by "
          "construction; the categories are clean and the vocabulary is narrow. A classifier "
          "trained on 100 such emails is learning the generator's templates, not business email.",
          "- **Train and test rows come from the same generator.** The held-out half is unseen "
          "*rows*, not an unseen *distribution*: this shows what a classifier does when the labels "
          "you train on look exactly like the traffic you score, which is the best case for the "
          "classifier. It does not show robustness to drift, new categories, or real inboxes.",
          f"- **Small n.** Held-out halves are n={email_split.get('n_heldout')} (emails) and "
          f"n={router_split.get('n_heldout')} (router, 20 hard + 20 attacked + 20 easy). "
          "Differences of a few points are within noise; intervals arrive with #46.",
          "- **One training run, one seed, fixed hyper-parameters** (pre-registered). A tuned "
          "classifier would move the numbers; that would be a different, unregistered experiment.",
          "- The other judges' held-out rows are re-scored from their full Arena runs; they were "
          "not re-run. Their prompts and settings are those of the Arena.",
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
