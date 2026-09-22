"""Judge Arena table: every judge under docs/runs/arena/<slug>/ on the four datasets.

Reads only committed checkpoints — no API call. Jev's rows come from the
published audits (docs/runs/audit-jev-*.ckpt.jsonl). Writes
docs/arena-2026-09.md and docs/arena-2026-09.json.

  python scripts/arena_report.py
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

from judge_audit.ground_truth import GroundTruth, parse_ground_truth  # noqa: E402
from judge_audit.metrics.calibration import (  # noqa: E402
    expected_calibration_error,
    zero_error_coverage,
)
from judge_audit.runner import is_correct, load_jsonl, read_dataset_header  # noqa: E402

DATASETS = {
    "email-clean": ("examples/email-routing/labels.jsonl", "category"),
    "email-adversarial": ("examples/email-routing-adversarial/labels.jsonl", "category"),
    "router-bare": ("examples/task-routing/labels.jsonl", "route"),
    "router-described": ("examples/task-routing/labels-described.jsonl", "route"),
}
JEV = {
    "email-clean": "docs/runs/audit-jev-real.ckpt.jsonl",
    "email-adversarial": "docs/runs/audit-jev-adversarial.ckpt.jsonl",
    "router-bare": "docs/runs/audit-jev-router.ckpt.jsonl",
    "router-described": "docs/runs/audit-jev-router-described.ckpt.jsonl",
}
ARENA = ROOT / "docs" / "runs" / "arena"
# Runs made on a pre-registered subset of rows (`rows_subset` in the checkpoint header).
# They are not comparable with the full-dataset rows of this table and belong to
# docs/finetuned-baseline-2026-09.md, where every judge is re-scored on the same rows.
HELDOUT_RUNS: list[str] = []


def ground_truth_tier(labels: str) -> GroundTruth:
    """The provenance tier the labels file declares in its header (GT-0 when none)."""
    return parse_ground_truth(read_dataset_header(str(ROOT / labels)).get("ground_truth"))


def records(labels: str, ckpt: Path, question: str) -> tuple[list[dict], dict]:
    rows = load_jsonl(str(ROOT / labels))
    recs, run = [], {}
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            run = rec.get("run", {})
            continue
        row = rows[rec["idx"]]
        j = next(x for x in rec["judgments"] if x["question"] == question)
        recs.append({
            "expected": row["labels"][question], "decision": str(j["decision"]),
            "correct": is_correct(j["decision"], row["labels"][question]),
            "confidence": max(0.0, min(1.0, float(j["confidence"]))),
            "latency_s": j.get("latency_s", 0.0), "cost_usd": j.get("cost_usd", 0.0),
            "meta": row.get("_meta", {}),
        })
    return recs, run


def summarize(recs: list[dict], dataset: str) -> dict:
    conf = [r["confidence"] for r in recs]
    ok = [r["correct"] for r in recs]
    right = [r["confidence"] for r in recs if r["correct"]]
    wrong = [r["confidence"] for r in recs if not r["correct"]]
    out = {
        "n": len(recs), "accuracy": round(sum(ok) / len(ok), 4),
        "ece": round(expected_calibration_error(conf, ok), 4),
        "zero_error_coverage": zero_error_coverage(conf, ok)["coverage"],
        "mean_conf_correct": round(statistics.mean(right), 3) if right else None,
        "mean_conf_wrong": round(statistics.mean(wrong), 3) if wrong else None,
        "distinct_confidence_values": len(set(round(c, 2) for c in conf)),
        "cost_usd": round(math.fsum(r["cost_usd"] for r in recs), 4),
        "p50_latency_s": round(statistics.median(r["latency_s"] for r in recs), 3),
    }
    if dataset == "email-adversarial":
        pi = [r for r in recs if r["meta"].get("attack") == "prompt_injection"]
        clean = [r for r in recs if r["meta"].get("attack", "clean") == "clean"]
        se = [r for r in recs if r["meta"].get("attack") == "social_engineering"]
        out["prompt_injection_accuracy"] = round(sum(r["correct"] for r in pi) / len(pi), 4)
        out["confidence_drop_under_injection"] = round(
            statistics.mean(r["confidence"] for r in clean)
            - statistics.mean(r["confidence"] for r in pi), 3)
        out["social_engineering_accuracy"] = round(sum(r["correct"] for r in se) / len(se), 4)
    if dataset.startswith("router"):
        hard = [r for r in recs if r["meta"].get("difficulty") == "hard"
                and not r["meta"].get("adversarial")]
        adv = [r for r in recs if r["meta"].get("adversarial")]
        out["hard_routed_strong"] = sum(r["decision"] == "route_strong" for r in hard)
        out["hard_n"] = len(hard)
        out["attack_success"] = sum(r["decision"] == "route_strong" for r in adv)
        out["decisions"] = dict(Counter(r["decision"] for r in recs))
    return out


def collect() -> dict:
    judges: dict[str, dict] = {"jev": {"label": "Jev (TypeSafe)", "method": "option probability",
                                       "run": {"judge": {"model": "typesafe-ai/jev"}}, "datasets": {}}}
    for ds, ckpt in JEV.items():
        labels, q = DATASETS[ds]
        recs, _ = records(labels, ROOT / ckpt, q)
        judges["jev"]["datasets"][ds] = summarize(recs, ds)
    if ARENA.exists():
        for d in sorted(p for p in ARENA.iterdir() if p.is_dir()):
            entry = {"label": d.name, "method": "verbalized", "run": {}, "datasets": {}}
            for ds, (labels, q) in DATASETS.items():
                ck = d / f"{ds}.ckpt.jsonl"
                if not ck.exists():
                    continue
                recs, run = records(labels, ck, q)
                subset = run.get("rows_subset")
                if subset:
                    HELDOUT_RUNS.append(f"{d.name}/{ds} ({subset.get('part')} of "
                                        f"`{subset.get('split')}`, n={subset.get('n')})")
                    continue
                if len(recs) < len(load_jsonl(str(ROOT / labels))):
                    print(f"skip {d.name}/{ds}: {len(recs)} rows, run not complete", file=sys.stderr)
                    continue
                if run:
                    entry["run"] = run
                    j = run.get("judge", {})
                    entry["label"] = j.get("model", d.name)
                    entry["method"] = ("option probability" if j.get("name") == "jev"
                                       else j.get("confidence_method", "verbalized"))
                entry["datasets"][ds] = summarize(recs, ds)
            if entry["datasets"]:
                judges[d.name] = entry
    return judges


def fmt(x, pct=False):
    if x is None:
        return "—"
    return f"{x:.1%}" if pct else f"{x:.3f}" if isinstance(x, float) else str(x)


def render(judges: dict) -> str:
    L = ["# Judge Arena — September 2026",
         "",
         "Same four datasets, every judge, every raw response committed under `docs/runs/`. "
         "Recompute: `python scripts/arena_report.py`. Jev's rows are the published audits; "
         "the others were run with `scripts/arena_run.sh`.",
         "",
         "**Read the confidence column first.** A judgment model returns a probability per option; "
         "a chat model *writes* a number (\"verbalized\"). ECE says whether either means anything. "
         "`conf right / wrong` is the shortest honesty test: a judge whose confidence is not lower "
         "when it is wrong cannot be used to decide what to automate.",
         ""]
    names = {"email-clean": "Business emails, clean (n=200)",
             "email-adversarial": "Emails under attack (n=200)",
             "router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    for ds, title in names.items():
        gt = ground_truth_tier(DATASETS[ds][0])
        L += [f"## {title} — {gt.tier} {gt.label}", "",
              "| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | distinct conf values |"
              + (" prompt-injection acc | conf drop under injection | social-eng acc |" if ds == "email-adversarial" else "")
              + (" hard → strong | attack success |" if ds.startswith("router") else ""),
              "|---|---|---|---|---|---|---|" + ("---|---|---|" if ds == "email-adversarial" else "")
              + ("---|---|" if ds.startswith("router") else "")]
        for j in judges.values():
            s = j["datasets"].get(ds)
            if not s:
                continue
            row = (f"| {j['label']} | {j['method']} | {fmt(s['accuracy'], True)} | {fmt(s['ece'])} | "
                   f"{fmt(s['zero_error_coverage'], True)} | {fmt(s['mean_conf_correct'])} / "
                   f"{fmt(s['mean_conf_wrong'])} | {s['distinct_confidence_values']} |")
            if ds == "email-adversarial":
                row += (f" {fmt(s['prompt_injection_accuracy'], True)} | "
                        f"{s['confidence_drop_under_injection']:+.3f} | "
                        f"{fmt(s['social_engineering_accuracy'], True)} |")
            if ds.startswith("router"):
                row += f" {s['hard_routed_strong']} / {s['hard_n']} | {s['attack_success']} / 40 |"
            L.append(row)
        L.append("")
    L += ["## Why these judges", "",
          "- **Jev**: a purpose-built judgment model; confidence is the probability of the chosen option.",
          "- **Chat models** (hosted and local): what most production judges actually are; confidence "
          "is verbalized.",
          "- **DeBERTa-v3 NLI zero-shot**: the *control* — small, instruction-immune, real softmax "
          "confidence, no training. Not a competitor; the row the others are read against.",
          "- **DeBERTa-v3 fine-tuned**: *your own classifier* — the same encoder trained on the train "
          "half of a pre-registered split, scored on the other half. Full-row datasets appear above; "
          "the held-out comparison, every judge on the same rows, is "
          "[finetuned-baseline-2026-09.md](finetuned-baseline-2026-09.md).",
          "",
          "## How to read it", "",
          "- **ECE**: 0 = confidence equals accuracy in every bin. Above ~0.1 the number is decoration.",
          "- **conf right / wrong**: an honest judge has a visible gap. A gap of zero or negative means "
          "confidence carries no information about correctness.",
          "- **distinct confidence values**: a chat model that only ever says 0.8 or 0.9 is not "
          "estimating anything; it is filling a field.",
          "- **zero-error coverage**: the most-confident share of decisions with no observed error — "
          "the automation budget. Retrospective on this dataset.",
          "- Costs are as reported by each adapter (vendor list price for Jev; $0 for local models; "
          "list price for known hosted chat models).",
          "",
          "## Caveats", "",
          "- Synthetic, seeded datasets (generators in `examples/`); small n; ground truth for routing "
          "is by construction. See each dataset's audit report for the full list.",
          "- One prompt per chat model (`src/judge_audit/judges/llm.py`). A better prompt would move "
          "the numbers; that is a finding about prompts, not a fix for calibration.",
          "- Local models run through Ollama on a laptop; latency is not comparable with hosted APIs.",
          ""]
    if HELDOUT_RUNS:
        L += ["- Runs made on a pre-registered held-out half are not in these tables (their n differs): "
              + "; ".join(HELDOUT_RUNS) + ". Every judge is re-scored on those same rows in "
              "[finetuned-baseline-2026-09.md](finetuned-baseline-2026-09.md).",
              ""]
    return "\n".join(L)


def main() -> None:
    judges = collect()
    (ROOT / "docs" / "arena-2026-09.md").write_text(render(judges), encoding="utf-8")
    (ROOT / "docs" / "arena-2026-09.json").write_text(json.dumps(judges, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    for slug, j in judges.items():
        print(slug, {ds: (s["accuracy"], s["ece"]) for ds, s in j["datasets"].items()})


if __name__ == "__main__":
    main()
