"""Consensus audit: does agreement between judges track correctness?

Round 1 of the jury-consensus audit (issue #39). No API call: every vote
is a committed Arena checkpoint (docs/runs/arena/<slug>/<dataset>.ckpt.jsonl
plus the published Jev audits), so the whole table recomputes from the repo.

  python scripts/consensus_report.py           # writes docs/consensus-2026-09.{md,json}

Deliberation (round 2) lives in scripts/jury_deliberate.py and is reported
by scripts/jury_report.py.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import ARENA, DATASETS, JEV, records  # noqa: E402

from judge_audit.metrics.calibration import (  # noqa: E402
    expected_calibration_error,
    zero_error_coverage,
)
from judge_audit.runner import is_correct, load_jsonl  # noqa: E402

JURY_SIZE = 3


def votes_of(dataset: str) -> tuple[dict[str, list[dict]], list[dict]]:
    """{judge slug: per-row records} for every judge with a complete run."""
    labels, q = DATASETS[dataset]
    rows = load_jsonl(str(ROOT / labels))
    out = {"jev": by_row(records(labels, ROOT / JEV[dataset], q)[0], len(rows))}
    for d in sorted(p for p in ARENA.iterdir() if p.is_dir()):
        ck = d / f"{dataset}.ckpt.jsonl"
        if ck.exists():
            recs = by_row(records(labels, ck, q)[0], len(rows))
            if recs is not None:
                out[d.name] = recs
    return out, rows


def by_row(recs: list[dict], n_rows: int) -> list[dict] | None:
    """Records in row order (a resumed driver appends redone rows at the end).

    None when the run is incomplete or has a duplicated row."""
    seen = {r["idx"]: r for r in recs}
    if len(seen) != len(recs) or len(seen) != n_rows or set(seen) != set(range(n_rows)):
        return None
    return [seen[i] for i in range(n_rows)]


def majority(decisions: list[str]) -> tuple[str, float]:
    """(winning option, vote share). Ties go to the alphabetically first option."""
    c = Counter(decisions)
    top = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return top[0], top[1] / len(decisions)


def panel_stats(votes: dict[str, list[dict]], rows: list[dict], question: str,
                idxs: list[int] | None = None) -> dict:
    judges = list(votes)
    idxs = list(range(len(rows))) if idxs is None else idxs
    if not idxs:
        return {}
    pair_agree = []
    for a, b in combinations(judges, 2):
        pair_agree.append(statistics.mean(
            votes[a][i]["decision"] == votes[b][i]["decision"] for i in idxs))
    maj_ok, shares, unanimous, unanimous_wrong = [], [], 0, 0
    share_right, share_wrong, conf_wrong = [], [], []
    for i in idxs:
        decisions = [votes[j][i]["decision"] for j in judges]
        win, share = majority(decisions)
        ok = is_correct(win, rows[i]["labels"][question])
        maj_ok.append(ok)
        shares.append(share)
        (share_right if ok else share_wrong).append(share)
        if share == 1.0:
            unanimous += 1
            unanimous_wrong += not ok
        if not ok:
            conf_wrong += [votes[j][i]["confidence"] for j in judges
                           if votes[j][i]["decision"] == win]
    zec = zero_error_coverage(shares, maj_ok)["coverage"]
    return {
        "n": len(idxs), "judges": judges,
        "pairwise_agreement": round(statistics.mean(pair_agree), 4),
        "unanimous": unanimous, "unanimous_wrong": unanimous_wrong,
        "majority_accuracy": round(statistics.mean(maj_ok), 4),
        "majority_wrong": sum(not ok for ok in maj_ok),
        "best_single_accuracy": round(max(
            statistics.mean(votes[j][i]["correct"] for i in idxs) for j in judges), 4),
        "mean_share_when_right": round(statistics.mean(share_right), 3) if share_right else None,
        "mean_share_when_wrong": round(statistics.mean(share_wrong), 3) if share_wrong else None,
        "mean_conf_of_wrong_majority": round(statistics.mean(conf_wrong), 3) if conf_wrong else None,
        "vote_share_ece": round(expected_calibration_error(shares, maj_ok), 4),
        "vote_share_zero_error_coverage": zec,
    }


def jury_sensitivity(votes: dict[str, list[dict]], rows: list[dict], question: str,
                     idxs: list[int]) -> dict:
    """Every 3-judge jury: how much the headline moves with the jury you pick."""
    accs, unan_wrong = {}, {}
    for jury in combinations(votes, JURY_SIZE):
        sub = {j: votes[j] for j in jury}
        s = panel_stats(sub, rows, question, idxs)
        key = " + ".join(jury)
        accs[key] = s["majority_accuracy"]
        unan_wrong[key] = s["unanimous_wrong"]
    lo, hi = min(accs, key=accs.get), max(accs, key=accs.get)
    uw_hi = max(unan_wrong, key=unan_wrong.get)
    return {
        "juries": len(accs),
        "majority_accuracy_min": {"jury": lo, "value": accs[lo]},
        "majority_accuracy_max": {"jury": hi, "value": accs[hi]},
        "unanimous_wrong_max": {"jury": uw_hi, "value": unan_wrong[uw_hi], "of": len(idxs)},
    }


def collect() -> dict:
    out = {}
    for ds, (_, q) in DATASETS.items():
        votes, rows = votes_of(ds)
        entry = {"panel": panel_stats(votes, rows, q), "subsets": {}}
        if ds.startswith("router"):
            groups = {
                "easy": [i for i, r in enumerate(rows) if r["_meta"].get("difficulty") == "easy"
                         and not r["_meta"].get("adversarial")],
                "hard": [i for i, r in enumerate(rows) if r["_meta"].get("difficulty") == "hard"
                         and not r["_meta"].get("adversarial")],
                "adversarial": [i for i, r in enumerate(rows) if r["_meta"].get("adversarial")],
            }
        else:
            groups = {}
            for i, r in enumerate(rows):
                groups.setdefault(r["_meta"].get("attack", "clean"), []).append(i)
        for name, idxs in groups.items():
            entry["subsets"][name] = panel_stats(votes, rows, q, idxs)
            if ds.startswith("router") and name == "hard":
                entry["subsets"][name]["jury_sensitivity"] = jury_sensitivity(votes, rows, q, idxs)
        # Per-judge declared confidence vs the panel's vote share, same yardstick.
        entry["declared_confidence"] = {
            j: {"ece": round(expected_calibration_error(
                    [r["confidence"] for r in recs], [r["correct"] for r in recs]), 4),
                "zero_error_coverage": zero_error_coverage(
                    [r["confidence"] for r in recs], [r["correct"] for r in recs])["coverage"],
                "accuracy": round(statistics.mean(r["correct"] for r in recs), 4)}
            for j, recs in votes.items()}
        out[ds] = entry
    return out


def pct(x):
    return "—" if x is None else f"{x:.1%}"


def render(data: dict) -> str:
    names = {"email-clean": "Business emails, clean (n=200)",
             "email-adversarial": "Emails under attack (n=200)",
             "router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    L = ["# Consensus audit — September 2026", "",
         "Does agreement between AI judges tell you anything about whether they are right? "
         "Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): "
         "every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, "
         "so the panel below costs nothing new — it is the committed checkpoints read side by side. "
         "Recompute: `python scripts/consensus_report.py`.", "",
         "**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and "
         "found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode "
         "groups agreeing \"nearly unanimously, mostly on incorrect answers\" "
         "([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same "
         "assumption — agreement as evidence — failing after agents communicate "
         "([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either "
         "paper (no humans, different task); it measures the assumption they attack on a jury of "
         "heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.", ""]
    for ds, title in names.items():
        e = data[ds]
        p = e["panel"]
        L += [f"## {title}", "",
              f"Panel: {len(p['judges'])} judges ({', '.join(p['judges'])}). Majority vote, ties to the "
              f"alphabetically first option.", "",
              "| subset | n | pairwise agreement | unanimous (wrong) | majority accuracy | "
              "best single judge | vote share right / wrong | conf of the wrong majority |",
              "|---|---|---|---|---|---|---|---|"]
        for name, s in [("all", p)] + list(e["subsets"].items()):
            L.append(f"| {name} | {s['n']} | {pct(s['pairwise_agreement'])} | "
                     f"{s['unanimous']} ({s['unanimous_wrong']}) | {pct(s['majority_accuracy'])} | "
                     f"{pct(s['best_single_accuracy'])} | "
                     f"{s['mean_share_when_right'] if s['mean_share_when_right'] is not None else '—'} / "
                     f"{s['mean_share_when_wrong'] if s['mean_share_when_wrong'] is not None else '—'} | "
                     f"{s['mean_conf_of_wrong_majority'] if s['mean_conf_of_wrong_majority'] is not None else '—'} |")
        L += ["", "**Vote share as a confidence score** (the way most agent juries use it) against each "
              "judge's own declared confidence, same ECE and zero-error coverage:", "",
              "| confidence source | accuracy | ECE | zero-error coverage |", "|---|---|---|---|",
              f"| panel vote share (majority) | {pct(p['majority_accuracy'])} | {p['vote_share_ece']:.3f} | "
              f"{pct(p['vote_share_zero_error_coverage'])} |"]
        for j, d in e["declared_confidence"].items():
            L.append(f"| {j} (declared) | {pct(d['accuracy'])} | {d['ece']:.3f} | {pct(d['zero_error_coverage'])} |")
        hard = e["subsets"].get("hard", {}).get("jury_sensitivity")
        if hard:
            uw = hard["unanimous_wrong_max"]
            tail = (f"the most consensual wrong jury is unanimous and wrong on {uw['value']} / {uw['of']} "
                    f"({uw['jury']})." if uw["value"] else
                    "no three-judge jury is unanimous and wrong on any hard task.")
            L += ["", f"**Pick the jury, pick the headline.** Over all {hard['juries']} three-judge juries "
                  f"drawn from this panel, majority accuracy on the {e['subsets']['hard']['n']} hard tasks runs from "
                  f"{pct(hard['majority_accuracy_min']['value'])} ({hard['majority_accuracy_min']['jury']}) to "
                  f"{pct(hard['majority_accuracy_max']['value'])} ({hard['majority_accuracy_max']['jury']}); "
                  + tail]
        L.append("")
    L += ["## How to read it", "",
          "- **pairwise agreement**: mean over judge pairs of the share of cases where both chose the same option.",
          "- **unanimous (wrong)**: cases where every judge chose the same option, and how many of those were wrong.",
          "- **vote share right / wrong**: mean share of the winning option when the majority was right vs. wrong. "
          "If the two numbers are close, agreement carries no information about correctness.",
          "- **conf of the wrong majority**: mean declared confidence of the judges who voted with a wrong majority.",
          "- **vote share as confidence**: ECE and zero-error coverage computed with the share as the confidence "
          "of the majority decision — the number an agent jury would act on.",
          "", "## Caveats", "",
          "- Synthetic, seeded datasets; ground truth for routing is by construction. n is small; "
          "subset rows are indicative.",
          "- Ties in a panel with an even number of judges go to the alphabetically first option.",
          "- Judges differ in cost, size and confidence method; the panel is heterogeneous on purpose "
          "(same-model juries are the documented failure mode — Smit et al., ICML 2024).",
          "- Round 1 only: nobody saw anybody else's vote. Round 2 (deliberation) is pre-registered in "
          "`docs/jury-consensus-plan.md` and reported in `docs/jury-consensus.md` once run.", ""]
    return "\n".join(L)


def main() -> None:
    data = collect()
    (ROOT / "docs" / "consensus-2026-09.md").write_text(render(data), encoding="utf-8")
    (ROOT / "docs" / "consensus-2026-09.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    for ds, e in data.items():
        p = e["panel"]
        print(ds, "judges", len(p["judges"]), "agree", p["pairwise_agreement"],
              "maj_acc", p["majority_accuracy"], "share ece", p["vote_share_ece"],
              "unanimous wrong", p["unanimous_wrong"])


if __name__ == "__main__":
    main()
