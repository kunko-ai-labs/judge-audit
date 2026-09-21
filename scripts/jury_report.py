"""Jury-consensus audit, round 1 vs round 2: did deliberation raise agreement, or accuracy?

Reads the Arena checkpoints (round 1, independent votes) and
docs/runs/jury/<dataset>/<slug>.r2.ckpt.jsonl (round 2, after seeing the
panel). Judges without a complete round-2 run keep their round-1 vote in
the round-2 panel, as pre-registered. No API call.

  python scripts/jury_report.py     # writes docs/jury-consensus.{md,json}
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import DATASETS, records  # noqa: E402
from consensus_report import by_row, majority, panel_stats, votes_of  # noqa: E402

from judge_audit.metrics.calibration import expected_calibration_error  # noqa: E402

JURY = ROOT / "docs" / "runs" / "jury"
ROUND2_DATASETS = ("router-bare", "router-described")


def judge_stats(recs: list[dict]) -> dict:
    wrong = [r["confidence"] for r in recs if not r["correct"]]
    return {"accuracy": round(statistics.mean(r["correct"] for r in recs), 4),
            "ece": round(expected_calibration_error([r["confidence"] for r in recs],
                                                    [r["correct"] for r in recs]), 4),
            "mean_conf_wrong": round(statistics.mean(wrong), 3) if wrong else None}


def collect() -> dict:
    out = {}
    for ds in ROUND2_DATASETS:
        labels, q = DATASETS[ds]
        r1, rows = votes_of(ds)
        hard = [i for i, r in enumerate(rows) if r["_meta"].get("difficulty") == "hard"
                and not r["_meta"].get("adversarial")]
        r2 = dict(r1)
        judges, rerun = {}, []
        for slug in r1:
            ck = JURY / ds / f"{slug}.r2.ckpt.jsonl"
            if not ck.exists():
                continue
            raw, run = records(str(ROOT / labels), ck, q)
            recs = by_row(raw, len(rows))
            if recs is None:
                print(f"skip {ds}/{slug}: {len(raw)} rows, round 2 not complete", file=sys.stderr)
                continue
            rerun.append(slug)
            r2[slug] = recs
            a, b = r1[slug], recs
            switched = [i for i in range(len(rows)) if a[i]["decision"] != b[i]["decision"]]
            others = [j for j in r1 if j != slug]
            toward_majority = sum(
                b[i]["decision"] == majority([r1[j][i]["decision"] for j in others])[0]
                for i in switched)
            judges[slug] = {
                "round1": judge_stats(a), "round2": judge_stats(b),
                "hard_round1": judge_stats([a[i] for i in hard]),
                "hard_round2": judge_stats([b[i] for i in hard]),
                "switched": len(switched),
                "switched_to_correct": sum(b[i]["correct"] for i in switched),
                "switched_to_wrong": sum(not b[i]["correct"] for i in switched),
                "switched_toward_panel_majority": toward_majority,
                "run": run.get("judge", {}),
            }
        out[ds] = {
            "rerun": rerun, "kept_round1": [j for j in r1 if j not in rerun],
            "judges": judges,
            "panel_round1": panel_stats(r1, rows, q),
            "panel_round2": panel_stats(r2, rows, q) if rerun else {},
            "hard_round1": panel_stats(r1, rows, q, hard),
            "hard_round2": panel_stats(r2, rows, q, hard) if rerun else {},
        }
    return out


def pct(x):
    return "—" if x is None else f"{x:.1%}"


def num(x):
    return "—" if x is None else f"{x:.3f}"


def render(data: dict) -> str:
    names = {"router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    L = ["# Jury consensus audit — deliberation (round 2)", "",
         "Round 1 (independent votes, every judge, no new API call) is in "
         "[consensus-2026-09.md](consensus-2026-09.md). Here each judge votes again after "
         "seeing the other judges' round-1 decisions and confidences, anonymised and shuffled "
         "(protocol pre-registered in [jury-consensus-plan.md](jury-consensus-plan.md); inputs and "
         "raw answers under `docs/runs/jury/`). Recompute: `python scripts/jury_report.py`.", "",
         "The question is the one Shao (2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) "
         "and Huang et al. (2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) raise: "
         "after communication, does agreement go up because the panel got closer to the truth, "
         "or just closer to each other?", ""]
    for ds, title in names.items():
        e = data[ds]
        L += [f"## {title}", ""]
        if not e["rerun"]:
            L += ["_Round 2 not run yet._", ""]
            continue
        L += [f"Re-voted after seeing the panel: {', '.join(e['rerun'])}. Kept their round-1 vote "
              f"(cannot read a deliberation prompt): {', '.join(e['kept_round1']) or 'none'}.", "",
              "| panel | pairwise agreement | unanimous (wrong) | majority accuracy | "
              "vote share right / wrong | vote-share ECE | zero-error coverage |",
              "|---|---|---|---|---|---|---|"]
        for label, key in [("all, round 1", "panel_round1"), ("all, round 2", "panel_round2"),
                           ("hard, round 1", "hard_round1"), ("hard, round 2", "hard_round2")]:
            s = e[key]
            L.append(f"| {label} | {pct(s['pairwise_agreement'])} | {s['unanimous']} ({s['unanimous_wrong']}) | "
                     f"{pct(s['majority_accuracy'])} | {num(s['mean_share_when_right'])} / "
                     f"{num(s['mean_share_when_wrong'])} | {num(s['vote_share_ece'])} | "
                     f"{pct(s['vote_share_zero_error_coverage'])} |")
        L += ["", "| judge | accuracy r1 → r2 | hard accuracy r1 → r2 | ECE r1 → r2 | "
              "conf when wrong r1 → r2 | switched | → correct / → wrong | followed the panel majority |",
              "|---|---|---|---|---|---|---|---|"]
        for slug, j in e["judges"].items():
            L.append(f"| {slug} | {pct(j['round1']['accuracy'])} → {pct(j['round2']['accuracy'])} | "
                     f"{pct(j['hard_round1']['accuracy'])} → {pct(j['hard_round2']['accuracy'])} | "
                     f"{num(j['round1']['ece'])} → {num(j['round2']['ece'])} | "
                     f"{num(j['round1']['mean_conf_wrong'])} → {num(j['round2']['mean_conf_wrong'])} | "
                     f"{j['switched']} | {j['switched_to_correct']} / {j['switched_to_wrong']} | "
                     f"{j['switched_toward_panel_majority']} / {j['switched']} |")
        L.append("")
    L += predictions(data)
    L += ["## How to read it", "",
          "- A jury that deliberates well moves **majority accuracy** up and keeps **conf when wrong** low.",
          "- A jury that merely converges moves **pairwise agreement** and **unanimous** up while accuracy "
          "stays put — Shao's \"nearly unanimous, mostly incorrect\" in miniature.",
          "- **followed the panel majority** counts switches that landed on the other judges' round-1 "
          "majority: conformity, whether or not it was right.",
          "", "## Caveats", "",
          "- Illustration, not replication: no human groups, a routing task instead of Wason, n=120 "
          "(40 hard). Ground truth for routing is by construction.",
          "- One deliberation prompt, one round; the panel seen is round-1 votes, so judges do not see "
          "each other's revisions.",
          "- Judges without a text prompt (zero-shot NLI) keep their round-1 vote in the round-2 panel; "
          "this is stated per dataset above.", ""]
    return "\n".join(L)


def _delta(a: float | None, b: float | None, pct_: bool = True) -> str:
    if a is None or b is None:
        return "—"
    return f"{pct(a)} → {pct(b)}" if pct_ else f"{num(a)} → {num(b)}"


def predictions(data: dict) -> list[str]:
    """The four pre-registered predictions (docs/jury-consensus-plan.md), scored from the data."""
    if not all(data[ds]["rerun"] for ds in ROUND2_DATASETS):
        return []
    bare, desc = data["router-bare"], data["router-described"]
    L = ["## Results vs the pre-registered predictions", "",
         "Scored mechanically from the tables above; the thresholds are stated with each verdict.", ""]
    # 1. agreement and unanimity rise on both datasets
    rows = []
    ok1 = True
    for ds, e in (("router-bare", bare), ("router-described", desc)):
        a, b = e["panel_round1"], e["panel_round2"]
        up = b["pairwise_agreement"] > a["pairwise_agreement"] and b["unanimous"] >= a["unanimous"]
        ok1 &= up
        rows.append(f"{ds}: agreement {_delta(a['pairwise_agreement'], b['pairwise_agreement'])}, "
                    f"unanimous {a['unanimous']} → {b['unanimous']}")
    L.append(f"1. **Agreement and unanimity rise on both datasets** — {'held' if ok1 else 'not held'}. "
             + "; ".join(rows) + ".")
    # 2. bare: hard majority accuracy does not rise materially (< 10 points); llama32 follows the panel
    h1, h2 = bare["hard_round1"]["majority_accuracy"], bare["hard_round2"]["majority_accuracy"]
    small = (h2 - h1) < 0.10
    j = bare["judges"].get("llama32")
    follows = bool(j) and j["switched"] > 0 and j["switched_toward_panel_majority"] / j["switched"] >= 0.5
    verdict = "held" if small and follows else ("partly held" if small or follows else "not held")
    L.append(f"2. **Bare labels: hard-task majority accuracy does not rise materially (< 10 points) and the "
             f"3B model follows the panel** — {verdict}. Hard-task majority accuracy {_delta(h1, h2)}; "
             + (f"llama3.2 switched {j['switched']} votes, {j['switched_toward_panel_majority']} of them "
                f"onto the panel majority." if j else "llama3.2 did not re-vote."))
    # 3. described: right judges keep their vote (switches to wrong <= 5 % of votes), majority accuracy rises (>= 0)
    to_wrong = sum(x["switched_to_wrong"] for x in desc["judges"].values())
    votes = sum(desc["panel_round1"]["n"] for _ in desc["judges"])
    keep = to_wrong <= 0.05 * votes
    m1, m2 = desc["panel_round1"]["majority_accuracy"], desc["panel_round2"]["majority_accuracy"]
    rises = m2 >= m1
    verdict = "held" if keep and rises else ("partly held" if keep or rises else "not held")
    L.append(f"3. **Described options: judges that were right keep their vote (switches to wrong ≤ 5 % of "
             f"votes) and majority accuracy does not fall** — {verdict}. Switches to wrong: {to_wrong} of "
             f"{votes} re-votes; majority accuracy {_delta(m1, m2)}.")
    # 4. chat models' confidence when wrong goes up
    ups, tot, cells = 0, 0, []
    for ds, e in (("router-bare", bare), ("router-described", desc)):
        for slug, x in e["judges"].items():
            if slug == "jev":
                continue
            a, b = x["round1"]["mean_conf_wrong"], x["round2"]["mean_conf_wrong"]
            if a is None or b is None:
                continue
            tot += 1
            ups += b > a
            cells.append(f"{slug}/{ds.split('-')[1]} {num(a)}→{num(b)}")
    verdict = "held" if tot and ups > tot / 2 else "not held"
    L.append(f"4. **Chat models are more confident when wrong after deliberation** — {verdict} "
             f"({ups} of {tot} judge×dataset cells went up). " + "; ".join(cells) + ".")
    L.append("")
    return L


def main() -> None:
    data = collect()
    (ROOT / "docs" / "jury-consensus.md").write_text(render(data), encoding="utf-8")
    (ROOT / "docs" / "jury-consensus.json").write_text(json.dumps(data, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    for ds, e in data.items():
        print(ds, "rerun", e["rerun"],
              {k: (e[k].get("pairwise_agreement"), e[k].get("majority_accuracy"))
               for k in ("panel_round1", "panel_round2") if e[k]})


if __name__ == "__main__":
    main()
