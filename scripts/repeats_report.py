"""Repeat runs of the headline judges, scored against their pre-registration. No API call.

Reads the three repeat checkpoints per judge under docs/runs/repeats/<slug>/ and the Arena
run each one repeats, and scores the six predictions committed in
docs/repeat-runs-plan.md before the first call. Writes docs/repeats-2026-09.md and .json.

  python scripts/repeats_report.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import ARENA, DATASETS, JEV, fmt, records, summarize  # noqa: E402

from judge_audit.report import interval_of  # noqa: E402
from judge_audit.runner import load_jsonl  # noqa: E402

DS = "email-adversarial"
REPEATS = ROOT / "docs" / "runs" / "repeats"
OUT = ROOT / "docs" / "repeats-2026-09"
JUDGES = {"gemini-3-flash": "Gemini 3 Flash", "claude-sonnet-4.5": "Claude Sonnet 4.5",
          "jev": "Jev"}
RUNS = ("r1", "r2", "r3")
KEYS = ("n", "accuracy", "accuracy_ci", "accuracy_ci_method", "zero_error_coverage",
        "zero_error_coverage_ci", "zero_error_coverage_ci_method", "mean_conf_correct",
        "mean_conf_wrong", "nll_infinite")
METRICS = ("accuracy", "zero_error_coverage", "zec_upper", "mean_conf_correct",
           "mean_conf_wrong", "nll_infinite")


def run_stats(ckpt: Path, rows: list[dict]) -> dict:
    labels, q = DATASETS[DS]
    recs, run = records(labels, ckpt, q)
    if len(recs) != len(rows):
        raise SystemExit(f"{ckpt}: {len(recs)} of {len(rows)} rows — the run is not complete")
    s = summarize(recs, DS, rows)
    out = {k: s.get(k) for k in KEYS}
    j = run.get("judge") or {}
    out["config"] = {k: j.get(k) for k in ("model", "backend", "provider") if j.get(k)}
    out["zec_upper"] = (out["zero_error_coverage_ci"] or [None, None])[1]
    return out


def decisions(ckpt: Path) -> dict[int, str]:
    out = {}
    for line in ckpt.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line) if line.strip() else {"idx": -1}
        if rec["idx"] >= 0:
            out[rec["idx"]] = str(rec["judgments"][0].get("decision", ""))
    return out


def spread(runs: list[dict]) -> dict:
    out = {}
    for m in METRICS:
        xs = [r[m] for r in runs if r.get(m) is not None]
        out[m] = {"min": min(xs), "max": max(xs),
                  "sd": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0} if xs else None
    return out


def collect() -> dict:
    rows = load_jsonl(str(ROOT / DATASETS[DS][0]))
    data: dict = {"dataset": DATASETS[DS][0], "rows": len(rows), "judges": {}}
    for slug in JUDGES:
        arena = ROOT / JEV[DS] if slug == "jev" else ARENA / slug / f"{DS}.ckpt.jsonl"
        original = run_stats(arena, rows)
        reps = {k: run_stats(REPEATS / slug / f"{DS}.{k}.ckpt.jsonl", rows) for k in RUNS}
        # Jev's Arena run went through another backend (docs/repeat-runs-plan.md): its
        # spread is over the three repeats only; the chat models' includes the Arena run.
        same = list(reps.values()) + ([] if slug == "jev" else [original])
        paths = [REPEATS / slug / f"{DS}.{k}.ckpt.jsonl" for k in RUNS] + \
            ([] if slug == "jev" else [arena])
        runs_dec = [decisions(pth) for pth in paths]
        changed = sum(1 for i in runs_dec[0] if len({d.get(i) for d in runs_dec}) > 1)
        data["judges"][slug] = {"arena": original, "repeats": reps, "spread": spread(same),
                                "spread_over": ("r1–r3" if slug == "jev"
                                                else "Arena run + r1–r3"),
                                "rows_with_changed_decision": changed}
    data["predictions"] = score(data["judges"])
    data["sonnet_vs_jev"] = sonnet_vs_jev(data["judges"])
    return data


def score(j: dict) -> list[dict]:
    g, s, v = (j[k]["repeats"] for k in ("gemini-3-flash", "claude-sonnet-4.5", "jev"))
    p = []

    def add(pid, text, per_run):
        p.append({"id": pid, "prediction": text, "per_run": per_run,
                  "held": all(per_run.values())})

    add("P1", "Gemini 3 Flash's zero-error coverage is 0 % in each repeat",
        {k: g[k]["zero_error_coverage"] == 0.0 for k in RUNS})
    add("P2", "Jev's zero-error coverage is at least 50 % in each repeat",
        {k: v[k]["zero_error_coverage"] >= 0.5 for k in RUNS})
    add("P3", "Gemini's 95 % upper bound lies below Jev's 95 % lower bound in each repeat",
        {k: g[k]["zero_error_coverage_ci"][1] < v[k]["zero_error_coverage_ci"][0]
         for k in RUNS})
    add("P4", "Claude Sonnet 4.5's zero-error coverage stays below Jev's in each repeat",
        {k: s[k]["zero_error_coverage"] < v[k]["zero_error_coverage"] for k in RUNS})
    inside = {}
    for slug, reps in (("gemini-3-flash", g), ("claude-sonnet-4.5", s), ("jev", v)):
        lo, hi = j[slug]["arena"]["accuracy_ci"]
        for k in RUNS:
            inside[f"{slug} {k}"] = lo <= reps[k]["accuracy"] <= hi
    add("P5", "Each judge's accuracy in each repeat lies inside its Arena 95 % interval", inside)
    add("P6", "nll_infinite ≥ 1 for Gemini and Sonnet and 0 for Jev, in each repeat",
        {k: g[k]["nll_infinite"] >= 1 and s[k]["nll_infinite"] >= 1
         and v[k]["nll_infinite"] == 0 for k in RUNS})
    return p


def rng(r: dict | None, pct: bool | None) -> str:
    """`min–max (SD sd)` of one metric across runs; pct None prints counts."""
    if r is None:
        return "—"
    if pct is None:
        return f"{r['min']:g}–{r['max']:g}"
    if pct:
        return f"{r['min'] * 100:.1f}–{r['max'] * 100:.1f} % (SD {r['sd'] * 100:.2f})"
    return f"{r['min']:.3f}–{r['max']:.3f} (SD {r['sd']:.3f})"


def sonnet_vs_jev(j: dict) -> dict:
    """Per run: is Sonnet's zero-error interval separated from Jev's? Not pre-registered —
    the README caption says they are not separated, so the report has to say when they are."""
    s, v = j["claude-sonnet-4.5"], j["jev"]
    runs = {"Arena": (s["arena"], v["arena"]), **{k: (s["repeats"][k], v["repeats"][k])
                                                   for k in RUNS}}
    return {k: {"sonnet_upper": a["zec_upper"], "jev_lower": b["zero_error_coverage_ci"][0],
                "separated": a["zec_upper"] < b["zero_error_coverage_ci"][0]}
            for k, (a, b) in runs.items()}


def zec(s: dict) -> str:
    return (f"{fmt(s['zero_error_coverage'], True)}"
            f"{interval_of(s, 'zero_error_coverage_ci', pct=True)}")


def render(d: dict) -> str:
    held = sum(x["held"] for x in d["predictions"])
    lines = [
        "# Repeat runs of the headline judges",
        "",
        "> Generated by `scripts/repeats_report.py` from the committed checkpoints — no API "
        "call. Regenerated in CI. Protocol and predictions were committed before the first "
        "call: [docs/repeat-runs-plan.md](repeat-runs-plan.md).",
        "",
        f"The same 200 emails under attack (`{d['dataset']}`, GT-1 synthetic), three more "
        "runs of each judge behind the README headline. The Arena interval says how far a "
        "number would move on *other texts*; this page says how far it moves when the *same* "
        "judge answers the *same* texts again. Brackets are 95 % bootstrap intervals over "
        "distinct texts, except where the bootstrap cannot move, marked **†**, which carry "
        "the exact Clopper–Pearson binomial interval.",
        "",
        f"**{held} of {len(d['predictions'])} pre-registered predictions hold.**",
        "",
        "| # | prediction | per run | held |",
        "|---|---|---|---|",
    ]
    for i, p in enumerate(d["predictions"], 1):
        runs = ", ".join(f"{k} {'✓' if ok else '✗'}" for k, ok in p["per_run"].items())
        lines.append(f"| {i} | {p['prediction']} | {runs} | {'yes' if p['held'] else '**no**'} |")
    lines += ["", "## Every run", "",
              "| judge | run | accuracy | zero-error coverage | conf right / wrong | "
              "certain and wrong |",
              "|---|---|---|---|---|---|"]
    for slug, name in JUDGES.items():
        j = d["judges"][slug]
        for label, s in [("Arena", j["arena"]), *j["repeats"].items()]:
            lines.append(f"| {name} | {label} | {fmt(s['accuracy'], True)}"
                         f"{interval_of(s, 'accuracy_ci', pct=True)} | {zec(s)} | "
                         f"{fmt(s['mean_conf_correct'])} / {fmt(s['mean_conf_wrong'])} | "
                         f"{s['nll_infinite']} |")
    lines += ["", "## Spread between runs", "",
              "The spread is min–max (SD) over runs of the same configuration. Read it next to "
              "the Arena run's 95 % interval: a spread much smaller than the interval means "
              "the number moves more with the texts than with the run.", "",
              "| judge | over | accuracy (Arena 95 % interval) | zero-error coverage (Arena 95 % "
              "interval) | its 95 % upper bound | conf when right | conf when wrong | certain "
              "and wrong |",
              "|---|---|---|---|---|---|---|---|"]
    for slug, name in JUDGES.items():
        j = d["judges"][slug]

        sp, a = j["spread"], j["arena"]
        lines.append(f"| {name} | {j['spread_over']} | {rng(sp['accuracy'], True)} "
                     f"({interval_of(a, 'accuracy_ci', pct=True).strip() or '—'}) | "
                     f"{rng(sp['zero_error_coverage'], True)} "
                     f"({interval_of(a, 'zero_error_coverage_ci', pct=True).strip() or '—'}) | "
                     f"{rng(sp['zec_upper'], True)} | {rng(sp['mean_conf_correct'], False)} | "
                     f"{rng(sp['mean_conf_wrong'], False)} | {rng(sp['nll_infinite'], None)} |")
    sv = d["sonnet_vs_jev"]
    apart = [k for k, x in sv.items() if x["separated"]]
    lines += ["", "**Not every interval is stable between runs.** The README caption says Jev "
              "is not separated from Claude Sonnet 4.5. That holds in "
              + ", ".join(k for k in sv if k not in apart) + " but not in "
              + (", ".join(apart) or "none") + ": Sonnet changes "
              f"{d['judges']['claude-sonnet-4.5']['rows_with_changed_decision']} of its 200 "
              "decisions between runs and its accuracy not at all, yet the upper bound of its "
              "zero-error interval is "
              + ", ".join(f"{x['sonnet_upper'] * 100:.1f} % ({k})" for k, x in sv.items())
              + ". Its coverage is 0 % because a few of its most confident answers are wrong, "
              "and which bootstrap resamples keep them depends on small confidence changes "
              "between runs. So Sonnet's *interval* moves with the run; its point estimate "
              "and its decisions do not."]
    jev_cfg = d["judges"]["jev"]
    lines += ["", "## Caveats", "",
              "- Jev's Arena run under attack predates run headers, so its checkpoint records no "
              "model; `docs/audit-jev-adversarial.md` names it: `typesafe-ai/jev` through the "
              "AI Gateway evaluate API. The repeats use the direct TypeSafe API "
              f"(`{jev_cfg['repeats']['r1']['config'].get('model')}`). A difference between "
              "them may come from the backend or the version, so Jev's spread is over the "
              "three repeats only.",
              "- Three repeats measure run-to-run movement coarsely; they do not make the "
              "data less synthetic or the sample larger.",
              "- The chat models ran at temperature 0. The movement between runs is the "
              "provider's nondeterminism at that setting or a silent model update: the Arena "
              "runs (20–21 September) predate the recording of the served version, the hosted "
              "Sonnet path reports none, and the Arena headers do not record the temperature, "
              "so the two cannot be told apart.",
              "- Deviation from the plan: it said the runs would go one after another. To "
              "finish in about an hour, r2 and r3 of Gemini and Sonnet ran in parallel with "
              "their r1 (same settings, separate checkpoints); Jev's ran one after another.", ""]
    return "\n".join(lines)


def main() -> None:
    d = collect()
    OUT.with_suffix(".json").write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    OUT.with_suffix(".md").write_text(render(d), encoding="utf-8")
    held = sum(x["held"] for x in d["predictions"])
    print(f"{held}/{len(d['predictions'])} predictions hold -> "
          f"{OUT.with_suffix('.md').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
