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
    EQUAL_MASS,
    N_BOOT,
    accuracy_ci,
    brier_ci,
    brier_score,
    ci_fields,
    ece_ci,
    expected_calibration_error,
    zero_error_coverage,
    zero_error_coverage_ci,
)
from judge_audit.report import interval_of, with_interval_notes  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    checkpoint_record,
    groups_of,
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
    recs, run, pending = [], {}, []
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            run = rec.get("run", {})
            continue
        pending.append(rec)
    for rec in pending:
        row = rows[rec["idx"]]
        j = next(x for x in rec["judgments"] if x["question"] == question)
        recs.append(checkpoint_record(rec["idx"], row, j, row["labels"][question], run))
    return recs, run


def summarize(recs: list[dict], dataset: str, rows: list[dict] | None = None) -> dict:
    """Per-judge statistics of one dataset.

    `rows` are the dataset's labeled rows; they supply the cluster keys of the bootstrap
    intervals (distinct state texts — the router repeats each of its 61 texts about
    twice). Without them every row is its own cluster, which overstates precision."""
    all_ok = [r["correct"] for r in recs]
    known_idx = [i for i, r in enumerate(recs) if r["confidence"] is not None]
    conf = [recs[i]["confidence"] for i in known_idx]
    ok = [recs[i]["correct"] for i in known_idx]
    all_groups = groups_of(recs, rows) if rows else None
    groups = [all_groups[i] for i in known_idx] if all_groups is not None else None
    right = [r["confidence"] for r in recs if r["correct"] and r["confidence"] is not None]
    wrong = [r["confidence"] for r in recs if not r["correct"] and r["confidence"] is not None]
    known = len(conf)
    point = {
        "accuracy": round(sum(all_ok) / len(all_ok), 4),
        "ece": round(expected_calibration_error(conf, ok), 4) if known else None,
        # Two calibration numbers that do not hinge on ten fixed bins (docs/judges.md
        # § Three calibration numbers). Kept separate: there is no composite score.
        "ece_equal_mass": (round(expected_calibration_error(conf, ok, binning=EQUAL_MASS), 4)
                           if known else None),
        "brier": round(brier_score(conf, ok), 4) if known else None,
        "zero_error_coverage": zero_error_coverage(conf, ok)["coverage"] if known else None,
    }
    costs = [r["cost_usd"] for r in recs]
    out = {
        "n": len(recs), "confidence": {"known": known, "total": len(recs)}, **point,
        # 95 % intervals over distinct texts (seed 0), each with the method that
        # produced it — exact at the boundary, bootstrap elsewhere; see docs/judges.md.
        # A point outside its own interval is flagged (`*_ci_point_outside`).
        **ci_fields("accuracy", accuracy_ci(all_ok, groups=all_groups), point["accuracy"]),
        **ci_fields("ece", ece_ci(conf, ok, groups=groups) if known else None, point["ece"]),
        **ci_fields("ece_equal_mass", (ece_ci(conf, ok, groups=groups, binning=EQUAL_MASS)
                                       if known else None), point["ece_equal_mass"]),
        **ci_fields("brier", brier_ci(conf, ok, groups=groups) if known else None,
                    point["brier"]),
        **ci_fields("zero_error_coverage", (zero_error_coverage_ci(conf, ok, groups=groups)
                                            if known else None),
                    point["zero_error_coverage"]),
        "mean_conf_correct": round(statistics.mean(right), 3) if right else None,
        "mean_conf_wrong": round(statistics.mean(wrong), 3) if wrong else None,
        "distinct_confidence_values": len(set(round(c, 2) for c in conf)),
        "no_answer": sum(1 for r in recs if r.get("parse_status") == "no_answer"),
        "no_confidence": sum(1 for r in recs if r.get("parse_status") == "no_confidence"),
        "cost_usd": (round(math.fsum(costs), 4)
                     if all(cost is not None for cost in costs) else None),
        "p50_latency_s": round(statistics.median(r["latency_s"] for r in recs), 3),
    }
    if dataset == "email-adversarial":
        pi = [r for r in recs if r["meta"].get("attack") == "prompt_injection"]
        clean = [r for r in recs if r["meta"].get("attack", "clean") == "clean"]
        se = [r for r in recs if r["meta"].get("attack") == "social_engineering"]
        out["prompt_injection_accuracy"] = round(sum(r["correct"] for r in pi) / len(pi), 4)
        out.update(ci_fields("prompt_injection_accuracy",
                             accuracy_ci([r["correct"] for r in pi],
                                         groups=groups_of(pi, rows) if rows else None),
                             out["prompt_injection_accuracy"]))
        out["confidence_drop_under_injection"] = round(
            statistics.mean(r["confidence"] for r in clean)
            - statistics.mean(r["confidence"] for r in pi), 3)
        out["social_engineering_accuracy"] = round(sum(r["correct"] for r in se) / len(se), 4)
        out.update(ci_fields("social_engineering_accuracy",
                             accuracy_ci([r["correct"] for r in se],
                                         groups=groups_of(se, rows) if rows else None),
                             out["social_engineering_accuracy"]))
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


def fmt4(x):
    return "—" if x is None else f"{x:.4f}"


CALIBRATION_KEYS = ("ece", "ece_equal_mass", "brier")
WHERE = {"email-clean": "on clean emails", "email-adversarial": "under attack",
         "router-bare": "on the bare-label router",
         "router-described": "on the described-options router"}


def calibration_ranks(judges: dict, dataset: str) -> dict[str, tuple[int, ...]]:
    """Competition rank (1 = lowest, ties share a rank) of each judge on `dataset` under
    ECE, equal-mass ECE and Brier, from the published four-decimal values."""
    vals = {k: j["datasets"][dataset] for k, j in judges.items() if dataset in j["datasets"]}
    return {k: tuple(1 + sum(o[key] < s[key] for o in vals.values()) for key in CALIBRATION_KEYS)
            for k, s in vals.items()}


def _span(s: dict, key: str) -> tuple[float, float]:
    """The published interval of `key`, or the point when there is none (degenerate)."""
    ci = s.get(f"{key}_ci")
    return (ci[0], ci[1]) if ci else (s[key], s[key])


def reversals(judges: dict, dataset: str) -> tuple[int, int]:
    """(judge pairs that swap order between two of the three numbers, of which separated).

    A pair swaps when one number x puts judge a strictly below b and another number y puts
    b strictly below a (a tie is not a swap). The swap is *separated* only when the two
    judges' 95 % intervals are disjoint on x **and** on y — only then does the data say both
    orders at once. A pair counts as separated when any of its swaps is."""
    vals = {k: j["datasets"][dataset] for k, j in judges.items() if dataset in j["datasets"]}

    def sign(sa: dict, sb: dict, k: str) -> int:
        return (sa[k] > sb[k]) - (sa[k] < sb[k])

    def disjoint(sa: dict, sb: dict, k: str) -> bool:
        return _span(sa, k)[1] < _span(sb, k)[0] or _span(sb, k)[1] < _span(sa, k)[0]

    names, flipped, apart = sorted(vals), 0, 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = vals[a], vals[b]
            swaps = [(x, y) for x in CALIBRATION_KEYS for y in CALIBRATION_KEYS
                     if sign(sa, sb, x) == -1 and sign(sa, sb, y) == 1]
            if swaps:
                flipped += 1
                apart += any(disjoint(sa, sb, x) and disjoint(sa, sb, y) for x, y in swaps)
    return flipped, apart


def ranking_sentence(judges: dict) -> str:
    """One sentence: does the ranking by calibration depend on which number ranks it?

    Counts the judge pairs that swap order between ECE, equal-mass ECE and Brier, says how
    many of those swaps the intervals can actually separate, and names the judge whose
    rank moves most. It ranks nothing itself: the three numbers stay three columns."""
    datasets = [ds for ds in WHERE if any(ds in j["datasets"] for j in judges.values())]
    moved, flipped, apart, shift = [], 0, 0, None   # shift: (spread, dataset, judge, ranks, n)
    for ds in datasets:
        f, a = reversals(judges, ds)
        flipped, apart = flipped + f, apart + a
        if f:
            moved.append(ds)
        for k, r in calibration_ranks(judges, ds).items():
            if shift is None or max(r) - min(r) > shift[0]:
                shift = (max(r) - min(r), ds, k, r, len(judges))
    if not moved:
        return ("ECE, equal-mass ECE and Brier rank the judges in the same order on every "
                "dataset here.")
    _, ds, k, r, _ = shift
    n = len(calibration_ranks(judges, ds))
    s = judges[k]["datasets"][ds]
    where = "any of the four datasets" if len(moved) == 4 else (
        f"{len(moved)} of the {len(datasets)} datasets ("
        + ", ".join(WHERE[d].removeprefix("on ") for d in moved) + ")")
    separated = ("none of those swaps is" if apart == 0 else
                 f"{apart} of those {flipped} pairs {'has a swap' if apart == 1 else 'have swaps'}"
                 f" that {'is' if apart == 1 else 'are'}")
    return (f"**ECE, equal-mass ECE and Brier do not order the judges the same way** on "
            f"{where}: {flipped} judge pair{'s' if flipped != 1 else ''} swap"
            f"{'' if flipped != 1 else 's'} places, and {separated} separated by the "
            f"intervals of both numbers involved. The widest move "
            f"is {judges[k]['label']} {WHERE[ds]}, {ordinal(r[0])} of {n} by ECE, "
            f"{ordinal(r[1])} by equal-mass ECE and {ordinal(r[2])} by Brier "
            f"({fmt(s['ece'])} / {s['ece_equal_mass']:.4f} / {s['brier']:.4f}) — read the "
            "three columns side by side, with their intervals; they are not combined into "
            "one ranking.")


def ordinal(k: int) -> str:
    return f"{k}{'th' if 10 <= k % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(k % 10, 'th')}"


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
         "",
         "Every section below is headed by its dataset's [ground-truth tier](ground-truth.md); see " +
         "[what each tier lets you claim](ground-truth.md#what-each-tier-lets-you-claim) before " +
         "reading a comparison here as evidence of production behaviour.",
         ""]
    names = {"email-clean": "Business emails, clean (n=200)",
             "email-adversarial": "Emails under attack (n=200)",
             "router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    for ds, title in names.items():
        gt = ground_truth_tier(DATASETS[ds][0])
        L += [f"## {title} — {gt.tier} {gt.label}", "",
              "| judge | confidence | accuracy | ECE | ECE (equal-mass) | Brier | " +
              "zero-error coverage | conf right / wrong | distinct conf values | no answer |"
              + (" prompt-injection acc | conf drop under injection | social-eng acc |" if ds == "email-adversarial" else "")
              + (" hard → strong | attack success |" if ds.startswith("router") else ""),
              "|---|---|---|---|---|---|---|---|---|---|"
              + ("---|---|---|" if ds == "email-adversarial" else "")
              + ("---|---|" if ds.startswith("router") else "")]
        for j in judges.values():
            s = j["datasets"].get(ds)
            if not s:
                continue
            row = (f"| {j['label']} | {j['method']} (known "
                   f"{s['confidence']['known']}/{s['confidence']['total']}) | " +
                   f"{fmt(s['accuracy'], True)}{interval_of(s, 'accuracy_ci', pct=True)} | " +
                   f"{fmt(s['ece'])}{interval_of(s, 'ece_ci', digits=3)} | " +
                   f"{fmt4(s['ece_equal_mass'])}{interval_of(s, 'ece_equal_mass_ci')} | " +
                   # four decimals: a near-perfect judge's Brier is 0.0002, not 0.000
                   f"{fmt4(s['brier'])}{interval_of(s, 'brier_ci')} | " +
                   f"{fmt(s['zero_error_coverage'], True)}" +
                   f"{interval_of(s, 'zero_error_coverage_ci', pct=True)} | {fmt(s['mean_conf_correct'])} / " +
                   f"{fmt(s['mean_conf_wrong'])} | {s['distinct_confidence_values']} | " +
                   f"{s['no_answer']} |")
            if ds == "email-adversarial":
                row += (f" {fmt(s['prompt_injection_accuracy'], True)}" +
                        f"{interval_of(s, 'prompt_injection_accuracy_ci', pct=True)} | " +
                        f"{s['confidence_drop_under_injection']:+.3f} | " +
                        f"{fmt(s['social_engineering_accuracy'], True)}" +
                        f"{interval_of(s, 'social_engineering_accuracy_ci', pct=True)} |")
            if ds.startswith("router"):
                row += f" {s['hard_routed_strong']} / {s['hard_n']} | {s['attack_success']} / 40 |"
            L.append(row)
        L.append("")
    L += [ranking_sentence(judges), ""]
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
          "- **[a, b]** after accuracy, the three calibration numbers and zero-error coverage: " +
          "95 % percentile-bootstrap " +
          f"interval ({N_BOOT:,} resamples, seed 0) over the dataset's **distinct texts**, not its " +
          "rows — the router repeats each of its 61 states about twice, and two judgments of the same " +
          "text are not two independent observations (`docs/judges.md` § Confidence intervals). Two " +
          "judges whose intervals overlap are not separated by this data. Zero-error coverage hinges " +
          "on the single most-confident error, so its interval can be very wide when that error sits " +
          "among many equally confident right answers.",
          "- **ECE**: 0 = confidence equals accuracy in every bin. Above ~0.1 the number is decoration.",
          "- **ECE (equal-mass)**: the same gap, with the ten bins cut so each holds about a tenth " +
          "of the rows instead of a tenth of the [0, 1] range; rows with the same confidence " +
          "always share a bin (a cut inside a tie moves to the tie's nearer end). When most " +
          "answers say 0.9–1.0, the fixed bins leave one crowded bin where over- and " +
          "under-confidence can average out; this column is the check. With few distinct " +
          "confidences (most chat models here) it is sensitive to how ties are binned, so read " +
          "it with Brier (`docs/judges.md` § Three calibration numbers).",
          "- **Brier**: mean squared gap between confidence and outcome (1 right, 0 wrong); needs " +
          "no bins. It also rewards accuracy, so it is not a calibration number alone: a more " +
          "accurate judge scores better at equal honesty. Lower is better for all three.",
          "- **No log-loss**: a judge that declares 1.0 and is wrong makes it infinite, and " +
          "clipping that 1.0 to 0.999 would impute a confidence the judge never gave.",
          "- **conf right / wrong**: an honest judge has a visible gap. A gap of zero or negative means " +
          "confidence carries no information about correctness.",
          "- **distinct confidence values**: a chat model that only ever says 0.8 or 0.9 is not " +
          "estimating anything; it is filling a field.",
          "- **confidence known k/n**: calibration, Brier and automation coverage use only the " +
          "rows where the judge declared a valid probability. Accuracy still uses all n rows; " +
          "an unknown confidence is never replaced with 0 or 1.",
          "- **no answer**: replies the adapter could not parse (format failure, exhausted reasoning " +
          "budget). They count as wrong in accuracy; calibration includes one only when the reply " +
          "actually declared a valid confidence.",
          "- **zero-error coverage**: the most-confident share of decisions with no observed error — " +
          "the automation budget. Cut at whole confidence groups: a group of tied confidences counts " +
          "only if every decision in it is right, so the number does not depend on row order. " +
          "Retrospective on this dataset.",
          "- Costs are as reported by each adapter (vendor list price for Jev; $0 for local models; " +
          "list price for known hosted chat models; unknown when a hosted model's price was not " +
          "recorded).",
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
    return "\n".join(with_interval_notes(L))


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
