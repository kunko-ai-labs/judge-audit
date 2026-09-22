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
    N_BOOT,
    accuracy_ci,
    ece_ci,
    expected_calibration_error,
    zero_error_coverage,
    zero_error_coverage_ci,
)
from judge_audit.report import interval  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    groups_of,
    is_correct,
    load_jsonl,
    read_dataset_header,
)

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
# Runs made on a pre-registered subset of rows (`rows_subset` in the checkpoint header)
# are not comparable with the full-dataset rows of this table and belong to
# docs/finetuned-baseline-2026-09.md, where every judge is re-scored on the same rows.
# collect() returns them under the "_heldout_runs" key; render() lists them in the caveats.
# The fine-tuned slugs share a model name per dataset; label them by run so the rows
# stay distinguishable (run 1 is the pre-registered one, the others the post-hoc amendment).
FINETUNED_LABELS = {
    "finetuned-deberta": "DeBERTa-v3 fine-tuned, run 1 (local)",
    "finetuned-deberta-run2": "DeBERTa-v3 fine-tuned, run 2 (local, post hoc)",
    "finetuned-deberta-run2-ts": "DeBERTa-v3 fine-tuned, run 2 + temperature scaling (local, post hoc)",
}


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
            "idx": rec["idx"],
            "expected": row["labels"][question], "decision": str(j["decision"]),
            "correct": is_correct(j["decision"], row["labels"][question]),
            "confidence": max(0.0, min(1.0, float(j["confidence"]))),
            "latency_s": j.get("latency_s", 0.0), "cost_usd": j.get("cost_usd", 0.0),
            "meta": row.get("_meta", {}),
        })
    return recs, run


def summarize(recs: list[dict], dataset: str, rows: list[dict] | None = None) -> dict:
    """Per-judge statistics of one dataset.

    `rows` are the dataset's labeled rows; they supply the cluster keys of the bootstrap
    intervals (distinct state texts — the router repeats each of its 61 texts about
    twice). Without them every row is its own cluster, which overstates precision."""
    conf = [r["confidence"] for r in recs]
    ok = [r["correct"] for r in recs]
    groups = groups_of(recs, rows) if rows else None
    right = [r["confidence"] for r in recs if r["correct"]]
    wrong = [r["confidence"] for r in recs if not r["correct"]]
    out = {
        "n": len(recs), "accuracy": round(sum(ok) / len(ok), 4),
        "ece": round(expected_calibration_error(conf, ok), 4),
        "zero_error_coverage": zero_error_coverage(conf, ok)["coverage"],
        # 95 % percentile-bootstrap intervals over rows (seed 0), see docs/judges.md.
        "accuracy_ci": list(accuracy_ci(ok, groups=groups)),
        "ece_ci": list(ece_ci(conf, ok, groups=groups)),
        "zero_error_coverage_ci": list(zero_error_coverage_ci(conf, ok, groups=groups)),
        "mean_conf_correct": round(statistics.mean(right), 3) if right else None,
        "mean_conf_wrong": round(statistics.mean(wrong), 3) if wrong else None,
        "distinct_confidence_values": len(set(round(c, 2) for c in conf)),
        # A blank decision is a reply the adapter could not parse (format failure, truncated
        # reasoning budget); it counts as wrong above, and is counted here on its own.
        "no_answer": sum(1 for r in recs if not r["decision"].strip()),
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
    heldout_runs: list[str] = []
    judges: dict[str, dict] = {"jev": {"label": "Jev (TypeSafe)", "method": "option probability",
                                       "run": {"judge": {"model": "typesafe-ai/jev"}}, "datasets": {}}}
    for ds, ckpt in JEV.items():
        labels, q = DATASETS[ds]
        recs, _ = records(labels, ROOT / ckpt, q)
        judges["jev"]["datasets"][ds] = summarize(recs, ds, load_jsonl(str(ROOT / labels)))
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
                    heldout_runs.append(f"{d.name}/{ds} ({subset.get('part')} of "
                                        f"`{subset.get('split')}`, n={subset.get('n')})")
                    continue
                rows = load_jsonl(str(ROOT / labels))
                if len(recs) < len(rows):
                    print(f"skip {d.name}/{ds}: {len(recs)} rows, run not complete", file=sys.stderr)
                    continue
                if run:
                    entry["run"] = run
                    j = run.get("judge", {})
                    entry["label"] = FINETUNED_LABELS.get(d.name, j.get("model", d.name))
                    entry["method"] = ("option probability" if j.get("name") == "jev"
                                       else j.get("confidence_method", "verbalized"))
                entry["datasets"][ds] = summarize(recs, ds, rows)
            if entry["datasets"]:
                judges[d.name] = entry
    judges["_heldout_runs"] = heldout_runs
    return judges


def most_correlated_pair(dataset: str) -> dict | None:
    """The most error-correlated judge pair of a dataset, from the committed consensus JSON
    (scripts/consensus_report.py); None when that report is not there yet."""
    path = ROOT / "docs" / "consensus-2026-09.json"
    if not path.exists():
        return None
    ec = json.loads(path.read_text(encoding="utf-8")).get(dataset, {}).get("error_correlation", {})
    return ec.get("most_correlated")


def fmt(x, pct=False):
    if x is None:
        return "—"
    return f"{x:.1%}" if pct else f"{x:.3f}" if isinstance(x, float) else str(x)


def render(judges: dict) -> str:
    heldout_runs = judges.get("_heldout_runs", [])
    judges = {k: v for k, v in judges.items() if not k.startswith("_")}
    L = ["# Judge Arena — September 2026",
         "",
         "Same four datasets, every judge, every raw response committed under `docs/runs/`. " +
         "Recompute: `python scripts/arena_report.py`. Jev's rows are the published audits; " +
         "the others were run with `scripts/arena_run.sh`.",
         "",
         "**Read the confidence column first.** A judgment model returns a probability per option; " +
         "a chat model *writes* a number (\"verbalized\"). ECE says whether either means anything. " +
         "`conf right / wrong` is the shortest honesty test: a judge whose confidence is not lower " +
         "when it is wrong cannot be used to decide what to automate.",
         ""]
    names = {"email-clean": "Business emails, clean (n=200)",
             "email-adversarial": "Emails under attack (n=200)",
             "router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    for ds, title in names.items():
        gt = ground_truth_tier(DATASETS[ds][0])
        L += [f"## {title} — {gt.tier} {gt.label}", "",
              "| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | " +
              "distinct conf values | no answer |"
              + (" prompt-injection acc | conf drop under injection | social-eng acc |" if ds == "email-adversarial" else "")
              + (" hard → strong | attack success |" if ds.startswith("router") else ""),
              "|---|---|---|---|---|---|---|---|" + ("---|---|---|" if ds == "email-adversarial" else "")
              + ("---|---|" if ds.startswith("router") else "")]
        for j in judges.values():
            s = j["datasets"].get(ds)
            if not s:
                continue
            row = (f"| {j['label']} | {j['method']} | " +
                   f"{fmt(s['accuracy'], True)}{interval(s['accuracy_ci'], pct=True)} | " +
                   f"{fmt(s['ece'])}{interval(s['ece_ci'], digits=3)} | " +
                   f"{fmt(s['zero_error_coverage'], True)}" +
                   f"{interval(s['zero_error_coverage_ci'], pct=True)} | {fmt(s['mean_conf_correct'])} / " +
                   f"{fmt(s['mean_conf_wrong'])} | {s['distinct_confidence_values']} | " +
                   f"{s['no_answer']} |")
            if ds == "email-adversarial":
                row += (f" {fmt(s['prompt_injection_accuracy'], True)} | " +
                        f"{s['confidence_drop_under_injection']:+.3f} | " +
                        f"{fmt(s['social_engineering_accuracy'], True)} |")
            if ds.startswith("router"):
                row += f" {s['hard_routed_strong']} / {s['hard_n']} | {s['attack_success']} / 40 |"
            L.append(row)
        L.append("")
    # The control's degradation under attack, from this run's own numbers.
    nli = judges.get("deberta-nli", {}).get("datasets", {})
    nli_note = ""
    if "email-clean" in nli and "email-adversarial" in nli:
        nli_note = (" — though injected text still degrades it " +
                    f"({fmt(nli['email-clean']['accuracy'], True)} clean → " +
                    f"{fmt(nli['email-adversarial']['accuracy'], True)} under attack, " +
                    f"{fmt(nli['email-adversarial']['prompt_injection_accuracy'], True)} on " +
                    "prompt-injection rows)")
    pair = most_correlated_pair("router-bare")
    pair_note = (f" ({pair['pair']}, phi {pair['phi']:.2f} — see " +
                 "[Error correlation](consensus-2026-09.md))" if pair else
                 " (see [Error correlation](consensus-2026-09.md))")
    L += ["## Why these judges", "",
          "Each row stands for a kind of judge a team could actually deploy, not for a brand. " +
          "The panel is heterogeneous on purpose: judges that fail on the same rows are the " +
          f"documented failure mode{pair_note}; Shao (2026, " +
          "[arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) and Huang et al. (2026, " +
          "[arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) for the literature.", "",
          "| judge | what it represents |", "|---|---|",
          "| Jev (TypeSafe) | the judgment model under audit — a model built to judge, returning a " +
          "probability per option instead of a written number |",
          "| Claude Sonnet 4.5, Gemini 3 Flash | what teams deploy today as LLM-as-judge: frontier chat " +
          "models with a verbalized confidence |",
          "| Llama 3.3 70B | an open, hosted, mid-size chat model — the self-hostable alternative |",
          "| DeepSeek R1 | a reasoning model; its reasoning channel spends the output budget before " +
          "the answer, so the token budget decides how many replies are blank (see `no answer`) |",
          "| gemma4 (e4b), llama3.2 3B | small local chat models on a laptop — the cost floor " +
          "($0) and the floor of what a chat prompt can do |",
          "| DeBERTa-v3 zero-shot NLI | **control**, not a competitor: a ~180M encoder that cannot " +
          f"follow instructions, so an injection cannot hijack it{nli_note}; returns a real " +
          "softmax confidence and was never fine-tuned on these tasks — the row that says whether a " +
          "task needed a bigger model at all |",
          "| DeBERTa-v3 fine-tuned (runs 1, 2, 2 + TS) | **your own classifier**: the same encoder " +
          "fine-tuned on the train half of a pre-registered split, scored on the other half. Run 1 " +
          "is the pre-registered run; run 2 (to convergence) and run 2 + temperature scaling are a " +
          "disclosed post-hoc amendment. Only its full-row adversarial run appears above; the " +
          "held-out comparison, every judge on the same rows, is " +
          "[finetuned-baseline-2026-09.md](finetuned-baseline-2026-09.md) |",
          "",
          "Deliberately missing from this round, one reason each:", "",
          "- **OpenJev** — needs a Codiv account not yet created.",
          "- **GPT (OpenAI)** — no API budget allocated this round.",
          "- **Mistral** — not requested by anyone yet.",
          "",
          "## How to read it", "",
          "- **[a, b]** after accuracy, ECE and zero-error coverage: 95 % percentile-bootstrap " +
          f"interval ({N_BOOT:,} resamples, seed 0) over the dataset's **distinct texts**, not its " +
          "rows — the router repeats each of its 61 states about twice, and two judgments of the same " +
          "text are not two independent observations (`docs/judges.md` § Confidence intervals). Two " +
          "judges whose intervals overlap are not separated by this data. Zero-error coverage hinges " +
          "on the single most-confident error, so its interval can be very wide when that error sits " +
          "among many equally confident right answers.",
          "- **ECE**: 0 = confidence equals accuracy in every bin. Above ~0.1 the number is decoration.",
          "- **conf right / wrong**: an honest judge has a visible gap. A gap of zero or negative means " +
          "confidence carries no information about correctness.",
          "- **distinct confidence values**: a chat model that only ever says 0.8 or 0.9 is not " +
          "estimating anything; it is filling a field.",
          "- **no answer**: replies the adapter could not parse (format failure, exhausted reasoning " +
          "budget). They count as wrong at confidence 0 in every other column; this one keeps " +
          "format failures visible apart from judgment quality.",
          "- **zero-error coverage**: the most-confident share of decisions with no observed error — " +
          "the automation budget. Cut at whole confidence groups: a group of tied confidences counts " +
          "only if every decision in it is right, so the number does not depend on row order. " +
          "Retrospective on this dataset.",
          "- Costs are as reported by each adapter (vendor list price for Jev; $0 for local models; " +
          "list price for known hosted chat models).",
          "",
          "## Provenance: what each judge was asked, and how", "",
          "Read from the checkpoint headers (`docs/runs/**/*.ckpt.jsonl`), not from memory:", "",
          "- **Every Arena run was at temperature 0, or has no temperature at all.** " +
          "Claude Sonnet 4.5, Llama 3.3 70B and DeepSeek R1 were called through a private " +
          "adapter module (`provider: hosted-api` in their headers) that sets temperature 0. " +
          "Gemini 3 Flash, gemma4 and llama3.2 went through the OpenAI-compatible path " +
          "(`provider: openai-compatible`), whose request body sets `temperature: 0`. Jev " +
          "takes no sampling temperature — it returns a distribution rather than a sample — " +
          "and the DeBERTa NLI control is an encoder, which does not sample either.",
          "- **The Anthropic SDK path was not used for the Arena.** No checkpoint header " +
          "records `provider: anthropic`. That path now sets temperature 0 too, so a future " +
          "rerun through it is comparable with these.",
          "- **These headers predate the provenance fields added in v0.4.0**: they record the " +
          "provider, model and backend but not `temperature` or `prompt_sha256`, which every " +
          "run from v0.4.0 on records in `run.judge`. The statements above are read off the " +
          "provider each header names and the code that provider path runs, not off a " +
          "`temperature` field in the file.",
          "- One prompt for every chat model, unchanged across the four datasets " +
          "(`SYSTEM` + the render template in `src/judge_audit/judges/llm.py`); Jev was shown " +
          "the same criteria map throughout (`criteria_version` 1).",
          "",
          "## Caveats", "",
          "- Synthetic, seeded datasets (generators in `examples/`); small n; ground truth for routing " +
          "is by construction. See each dataset's audit report for the full list.",
          "- One prompt per chat model (`src/judge_audit/judges/llm.py`). A better prompt would move " +
          "the numbers; that is a finding about prompts, not a fix for calibration.",
          "- Local models run through Ollama on a laptop; latency is not comparable with hosted APIs.",
          ""]
    if heldout_runs:
        L += ["- Runs made on a pre-registered held-out half are not in these tables (their n differs): "
              + "; ".join(heldout_runs) + ". Every judge is re-scored on those same rows in "
              "[finetuned-baseline-2026-09.md](finetuned-baseline-2026-09.md).",
              ""]
    return "\n".join(L)


def main() -> None:
    judges = collect()
    (ROOT / "docs" / "arena-2026-09.md").write_text(render(judges), encoding="utf-8")
    public = {k: v for k, v in judges.items() if not k.startswith("_")}
    (ROOT / "docs" / "arena-2026-09.json").write_text(json.dumps(public, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    for slug, j in public.items():
        print(slug, {ds: (s["accuracy"], s["ece"]) for ds, s in j["datasets"].items()})


if __name__ == "__main__":
    main()
