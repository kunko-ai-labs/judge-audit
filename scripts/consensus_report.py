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
import math
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
PANEL = ROOT / "docs" / "runs" / "jury" / "panel.json"        # frozen panel, judge order
ARENA_JSON = ROOT / "docs" / "arena-2026-09.json"             # cost and latency per judge


def frozen_panel(votes: dict[str, list[dict]]) -> list[str]:
    """Judges of the frozen panel (docs/runs/jury/panel.json) that have a complete run,
    in the panel's order; every judge with a run when no panel file exists."""
    if PANEL.exists():
        return [j for j in json.loads(PANEL.read_text(encoding="utf-8"))["panel"] if j in votes]
    return list(votes)


def arena_costs(dataset: str) -> dict[str, dict]:
    """{judge slug: Arena summary of this dataset} — cost_usd and p50_latency_s per judge."""
    if not ARENA_JSON.exists():
        return {}
    arena = json.loads(ARENA_JSON.read_text(encoding="utf-8"))
    return {slug: j["datasets"][dataset] for slug, j in arena.items() if dataset in j["datasets"]}


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


def majority(decisions: list[str]) -> tuple[str | None, float, bool]:
    """(winning option, vote share among those who voted, tie?).

    A blank decision (unparseable answer) is an abstention, not a vote.
    A tie is no decision: option None, share 0.5, tie True. No votes: (None, 0.0, False)."""
    voted = [d.strip().lower() for d in decisions if d.strip()]
    if not voted:
        return None, 0.0, False
    c = Counter(voted)
    ranked = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None, ranked[0][1] / len(voted), True
    return ranked[0][0], ranked[0][1] / len(voted), False


def panel_stats(votes: dict[str, list[dict]], rows: list[dict], question: str,
                idxs: list[int] | None = None) -> dict:
    """Majority-vote statistics of a panel on the given rows.

    Abstentions (blank answers) are not votes; a tie is no decision and counts as
    not correct in majority accuracy; share statistics, vote-share ECE and
    zero-error coverage are computed over decided rows only."""
    judges = list(votes)
    idxs = list(range(len(rows))) if idxs is None else idxs
    if not idxs:
        return {}

    def vote(j: str, i: int) -> str:
        return votes[j][i]["decision"].strip().lower()

    pair_agree = []
    for a, b in combinations(judges, 2):
        both = [i for i in idxs if vote(a, i) and vote(b, i)]
        if both:
            pair_agree.append(statistics.mean(vote(a, i) == vote(b, i) for i in both))
    maj_ok, ties, abstentions, unanimous, unanimous_wrong = [], 0, 0, 0, 0
    shares, decided_ok, share_right, share_wrong, conf_wrong = [], [], [], [], []
    for i in idxs:
        decisions = [vote(j, i) for j in judges]
        abstentions += sum(1 for d in decisions if not d)
        win, share, tie = majority(decisions)
        ok = win is not None and is_correct(win, rows[i]["labels"][question])
        maj_ok.append(ok)
        if tie:
            ties += 1
        if win is None:
            continue
        shares.append(share)
        decided_ok.append(ok)
        (share_right if ok else share_wrong).append(share)
        if share == 1.0 and sum(1 for d in decisions if d) >= 2:
            unanimous += 1
            unanimous_wrong += not ok
        if not ok:
            conf_wrong += [votes[j][i]["confidence"] for j in judges if vote(j, i) == win]
    return {
        "n": len(idxs), "judges": judges,
        "pairwise_agreement": round(statistics.mean(pair_agree), 4) if pair_agree else None,
        "unanimous": unanimous, "unanimous_wrong": unanimous_wrong,
        "ties": ties, "abstentions": abstentions,
        "majority_accuracy": round(statistics.mean(maj_ok), 4),
        "majority_accuracy_decided": round(statistics.mean(decided_ok), 4) if decided_ok else None,
        "majority_wrong": sum(not ok for ok in maj_ok),
        "best_single_accuracy": round(max(
            statistics.mean(votes[j][i]["correct"] for i in idxs) for j in judges), 4),
        "mean_share_when_right": round(statistics.mean(share_right), 3) if share_right else None,
        "mean_share_when_wrong": round(statistics.mean(share_wrong), 3) if share_wrong else None,
        "mean_conf_of_wrong_majority": round(statistics.mean(conf_wrong), 3) if conf_wrong else None,
        "vote_share_ece": round(expected_calibration_error(shares, decided_ok), 4) if shares else None,
        "vote_share_zero_error_coverage": (zero_error_coverage(shares, decided_ok)["coverage"]
                                          if shares else None),
    }


def _ratio(num: float, den: float, digits: int = 4) -> float | None:
    return round(num / den, digits) if den else None


def pairwise_error_stats(votes: dict[str, list[dict]], rows: list[dict], question: str,
                         idxs: list[int] | None = None) -> list[dict]:
    """Are two judges' errors independent evidence or one blind spot voting twice?

    For every judge pair, over the rows where both answered (a blank is an abstention and
    the row is excluded — n is stated per pair): agreement, joint error rate,
    P(A wrong | B wrong), P(B wrong | A wrong), Jaccard of the two error sets and the phi
    coefficient between the two error indicators. Phi is None when a judge has no error
    (or no correct answer) on the compared rows; the conditionals are None when the
    conditioning judge has no error; Jaccard is None when neither judge erred."""
    idxs = list(range(len(rows))) if idxs is None else idxs
    out = []
    for a, b in combinations(votes, 2):
        both = [i for i in idxs
                if votes[a][i]["decision"].strip() and votes[b][i]["decision"].strip()]
        n = len(both)
        wrong_a = {i for i in both if not votes[a][i]["correct"]}
        wrong_b = {i for i in both if not votes[b][i]["correct"]}
        n11 = len(wrong_a & wrong_b)                   # both wrong
        n10, n01 = len(wrong_a) - n11, len(wrong_b) - n11
        n00 = n - n11 - n10 - n01                      # both right
        den = math.sqrt(len(wrong_a) * (n - len(wrong_a)) * len(wrong_b) * (n - len(wrong_b)))
        out.append({
            "a": a, "b": b, "n": n,
            "agreement": _ratio(sum(votes[a][i]["decision"].strip() == votes[b][i]["decision"].strip()
                                    for i in both), n),
            "errors_a": len(wrong_a), "errors_b": len(wrong_b), "shared_wrong": n11,
            "joint_error": _ratio(n11, n),
            "p_a_wrong_given_b_wrong": _ratio(n11, len(wrong_b)),
            "p_b_wrong_given_a_wrong": _ratio(n11, len(wrong_a)),
            "error_jaccard": _ratio(n11, len(wrong_a | wrong_b)),
            "phi": round((n11 * n00 - n10 * n01) / den, 4) if den else None,
        })
    return out


def error_correlation(votes: dict[str, list[dict]], rows: list[dict], question: str,
                      idxs: list[int] | None = None) -> dict:
    """Pairwise error statistics plus the most and least correlated pairs (by phi)."""
    pairs = pairwise_error_stats(votes, rows, question, idxs)
    idxs = list(range(len(rows))) if idxs is None else idxs
    defined = [p for p in pairs if p["phi"] is not None]

    def pick(p: dict) -> dict:
        return {"pair": f"{p['a']} + {p['b']}", "phi": p["phi"], "shared_wrong": p["shared_wrong"],
                "n": p["n"]}

    return {
        "n_rows": len(idxs), "judges": list(votes),
        "errors": {j: sum(1 for i in idxs if votes[j][i]["decision"].strip()
                          and not votes[j][i]["correct"]) for j in votes},
        "pairs": pairs, "pairs_with_phi": len(defined),
        "most_correlated": pick(max(defined, key=lambda p: p["phi"])) if defined else None,
        "least_correlated": pick(min(defined, key=lambda p: p["phi"])) if defined else None,
    }


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation (average ranks on ties); None below three points or
    when either side has no variance."""
    if len(xs) < 3:
        return None

    def ranks(vs: list[float]) -> list[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        r = [0.0] * len(vs)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    var = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(cov / var, 4) if var else None


def jury_composition(votes: dict[str, list[dict]], rows: list[dict], question: str,
                     idxs: list[int], panel: list[str], costs: dict[str, dict]) -> dict:
    """Every 3-judge jury from the frozen panel, one row each: majority accuracy (a tie is
    no decision), decided-rows accuracy, ties, vote-share ECE, mean pairwise error phi,
    shared-wrong cases (all three answered and all three wrong), cost and p50 latency
    (sum / mean of the members' Arena figures). Sorted by majority accuracy; no composite.

    Mean phi averages the pairs whose phi is defined (`pairs_with_phi` says how many); it is
    given on the scored rows (`mean_phi`) and on every row of the dataset (`mean_phi_all`),
    because a judge wrong on all — or none — of the scored rows has no phi there.
    `diversity_vs_accuracy` is the Spearman correlation between each mean phi and majority
    accuracy over the juries where it is defined — a number, not a verdict."""
    all_idxs = list(range(len(rows)))

    def mean_phi(sub: dict[str, list[dict]], on: list[int]) -> tuple[float | None, int]:
        phis = [p["phi"] for p in pairwise_error_stats(sub, rows, question, on)
                if p["phi"] is not None]
        return (round(statistics.mean(phis), 4) if phis else None), len(phis)

    juries = []
    for jury in combinations([j for j in panel if j in votes], JURY_SIZE):
        sub = {j: votes[j] for j in jury}
        s = panel_stats(sub, rows, question, idxs)
        phi, k = mean_phi(sub, idxs)
        phi_all, k_all = mean_phi(sub, all_idxs)
        members = [costs.get(j) for j in jury]
        juries.append({
            "jury": " + ".join(jury), "members": list(jury), "n": len(idxs),
            "majority_accuracy": s["majority_accuracy"],
            "majority_accuracy_decided": s["majority_accuracy_decided"],
            "ties": s["ties"], "vote_share_ece": s["vote_share_ece"],
            "mean_phi": phi, "pairs_with_phi": k,
            "mean_phi_all": phi_all, "pairs_with_phi_all": k_all, "n_all": len(all_idxs),
            "shared_wrong": sum(1 for i in idxs
                                if all(votes[j][i]["decision"].strip() and not votes[j][i]["correct"]
                                       for j in jury)),
            "cost_usd": (round(math.fsum(m["cost_usd"] for m in members), 4)
                         if all(members) else None),
            "p50_latency_s": (round(statistics.mean(m["p50_latency_s"] for m in members), 3)
                              if all(members) else None),
        })
    juries.sort(key=lambda j: (-j["majority_accuracy"], -(j["majority_accuracy_decided"] or 0),
                               j["jury"]))

    def diversity(key: str) -> dict:
        with_phi = [j for j in juries if j[key] is not None]
        return {"spearman": spearman([j[key] for j in with_phi],
                                     [j["majority_accuracy"] for j in with_phi]),
                "juries": len(with_phi)}

    return {
        "panel": [j for j in panel if j in votes], "size": JURY_SIZE, "juries": juries,
        "diversity_vs_accuracy": diversity("mean_phi"),
        "diversity_vs_accuracy_all_rows": diversity("mean_phi_all"),
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
                entry["subsets"][name]["jury_composition"] = jury_composition(
                    votes, rows, q, idxs, frozen_panel(votes), arena_costs(ds))
        entry["error_correlation"] = error_correlation(votes, rows, q)
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


def num(x):
    return "—" if x is None else f"{x:.3f}"


def money(x):
    return "—" if x is None else f"${x:.4f}"


def secs(x):
    return "—" if x is None else f"{x:.2f} s"


def render_error_correlation(ec: dict) -> list[str]:
    """Phi matrix (upper triangle) with each judge's error count, the full pair table
    folded away, and one reading line."""
    judges = ec["judges"]
    phi = {(p["a"], p["b"]): p for p in ec["pairs"]}
    L = [f"### Error correlation (n={ec['n_rows']})", "",
         "Phi between the two judges' error indicators, over the rows where both answered. " +
         "\"—\": undefined because one judge has no error on those rows. `errors` is the judge's " +
         "own count; the full pair table (agreement, joint error, conditional error rates, " +
         "error-set Jaccard, n) is folded below.", "",
         "| judge (errors) | " + " | ".join(judges) + " |", "|---|" + "---|" * len(judges)]
    for a in judges:
        cells = []
        for b in judges:
            p = phi.get((a, b))
            cells.append(num(p["phi"]) if p else "")
        L.append(f"| {a} ({ec['errors'][a]}) | " + " | ".join(cells) + " |")
    L += ["", "<details><summary>Every pair</summary>", "",
          "| A | B | n | agreement | joint error | P(A wrong \\| B wrong) | P(B wrong \\| A wrong) | " +
          "error-set Jaccard | phi |", "|---|---|---|---|---|---|---|---|---|"]
    for p in ec["pairs"]:
        L.append(f"| {p['a']} | {p['b']} | {p['n']} | {pct(p['agreement'])} | {pct(p['joint_error'])} | " +
                 f"{pct(p['p_a_wrong_given_b_wrong'])} | {pct(p['p_b_wrong_given_a_wrong'])} | " +
                 f"{num(p['error_jaccard'])} | {num(p['phi'])} |")
    L += ["", "</details>", ""]
    hi, lo = ec["most_correlated"], ec["least_correlated"]
    if hi is None:
        L.append("**Reading.** Phi is undefined for every pair: no two judges both err on this dataset.")
    elif ec["pairs_with_phi"] == 1:
        L.append(f"**Reading.** Only one pair has a defined phi: {hi['pair']} at {num(hi['phi'])} " +
                 f"({hi['shared_wrong']} shared wrong cases of {hi['n']}).")
    else:
        L.append(f"**Reading.** Of {ec['pairs_with_phi']} pairs with a defined phi, the most correlated " +
                 f"errors are {hi['pair']} (phi {num(hi['phi'])}, {hi['shared_wrong']} shared wrong " +
                 f"cases of {hi['n']}) and the least correlated are {lo['pair']} (phi {num(lo['phi'])}, " +
                 f"{lo['shared_wrong']} shared wrong cases of {lo['n']}).")
    return L


def render_jury_composition(comp: dict, n: int) -> list[str]:
    """One row per 3-judge jury of the frozen panel on the hard tasks, sorted by majority
    accuracy; every column stays separate."""
    n_all = comp["juries"][0]["n_all"] if comp["juries"] else 0
    pairs = comp["size"] * (comp["size"] - 1) // 2

    def phi_cell(value, k) -> str:
        return num(value) + (f" ({k}/{pairs})" if value is not None and k < pairs else "")

    L = ["", f"### Jury composition — hard tasks (n={n})", "",
         f"Every {comp['size']}-judge jury from the frozen panel ({', '.join(comp['panel'])}; " +
         f"`docs/runs/jury/panel.json`), {len(comp['juries'])} juries. Mean pairwise error phi is " +
         f"given on the {n} hard rows and on all {n_all} rows of the dataset — a judge wrong on " +
         "every hard row (or on none) has no phi there; \"(k/3)\" says how many of the three pairs " +
         f"had one. Cost is the sum of the members' cost on the {n_all} rows; p50 latency the mean " +
         "of the members' medians (`docs/arena-2026-09.json`). Sorted by majority accuracy; no " +
         "composite score.", "",
         "| jury | majority accuracy (all / decided) | ties | vote-share ECE | " +
         f"mean pairwise error phi (hard / all {n_all}) | shared wrong | cost / {n_all} rows | " +
         "p50 latency |", "|---|---|---|---|---|---|---|---|"]
    for j in comp["juries"]:
        L.append(f"| {j['jury']} | {pct(j['majority_accuracy'])} / " +
                 f"{pct(j['majority_accuracy_decided'])} | {j['ties']} | {num(j['vote_share_ece'])} | " +
                 f"{phi_cell(j['mean_phi'], j['pairs_with_phi'])} / " +
                 f"{phi_cell(j['mean_phi_all'], j['pairs_with_phi_all'])} | {j['shared_wrong']} | " +
                 f"{money(j['cost_usd'])} | {secs(j['p50_latency_s'])} |")
    parts = []
    for key, k_key, d, label in [
            ("mean_phi", "pairs_with_phi", comp["diversity_vs_accuracy"], f"the {n} hard rows"),
            ("mean_phi_all", "pairs_with_phi_all", comp["diversity_vs_accuracy_all_rows"],
             f"all {n_all} rows")]:
        phis = [j[key] for j in comp["juries"] if j[key] is not None]
        one_pair = sum(1 for j in comp["juries"] if j[key] is not None and j[k_key] == 1)
        count = f"{d['juries']} juries" + (f", {one_pair} of them with only one defined pair"
                                           if one_pair else "")
        if d["spearman"] is None:
            parts.append(f"on {label}, Spearman is undefined ({count} with a defined mean phi)")
        else:
            parts.append(f"on {label}, mean phi runs from {num(min(phis))} to {num(max(phis))} " +
                         "and its Spearman correlation with majority accuracy is " +
                         f"{d['spearman']:+.2f} ({count})")
    text = "; ".join(parts)
    L += ["", "**Diversity vs accuracy.** " + text[0].upper() + text[1:] + "."]
    return L


def render(data: dict) -> str:
    names = {"email-clean": "Business emails, clean (n=200)",
             "email-adversarial": "Emails under attack (n=200)",
             "router-bare": "Task router, bare option labels (n=120)",
             "router-described": "Task router, described options (n=120)"}
    L = ["# Consensus audit — September 2026", "",
         "Does agreement between AI judges tell you anything about whether they are right? " +
         "Round 1 of the jury-consensus audit ([#39](https://github.com/kunko-ai-labs/judge-audit/issues/39)): " +
         "every judge in the [Arena](arena-2026-09.md) voted independently on the same four datasets, " +
         "so the panel below costs nothing new — it is the committed checkpoints read side by side. " +
         "Recompute: `python scripts/consensus_report.py`.", "",
         "**Why it matters.** Shao (2026) replayed 100 human deliberation groups with LLM agents and " +
         "found the agent groups overstated consensus by 34–44 percentage points, with reasoning-mode " +
         "groups agreeing \"nearly unanimously, mostly on incorrect answers\" " +
         "([arXiv:2609.20543](https://arxiv.org/abs/2609.20543)). Huang et al. (2026) show the same " +
         "assumption — agreement as evidence — failing after agents communicate " +
         "([arXiv:2605.30653](https://arxiv.org/abs/2605.30653)). This audit does not replicate either " +
         "paper (no humans, different task); it measures the assumption they attack on a jury of " +
         "heterogeneous judges: **vote share vs. calibrated confidence, same yardstick**.", ""]
    for ds, title in names.items():
        e = data[ds]
        p = e["panel"]
        L += [f"## {title}", "",
              f"Panel: {len(p['judges'])} judges ({', '.join(p['judges'])}). Majority vote among " +
              "those who answered; a tie is no decision.", "",
              "| subset | n | pairwise agreement | unanimous (wrong) | ties | abstentions | " +
              "majority accuracy (all / decided) | best single judge | vote share right / wrong | " +
              "conf of the wrong majority |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for name, s in [("all", p)] + list(e["subsets"].items()):
            L.append(f"| {name} | {s['n']} | {pct(s['pairwise_agreement'])} | " +
                     f"{s['unanimous']} ({s['unanimous_wrong']}) | {s['ties']} | {s['abstentions']} | " +
                     f"{pct(s['majority_accuracy'])} / {pct(s['majority_accuracy_decided'])} | " +
                     f"{pct(s['best_single_accuracy'])} | " +
                     f"{s['mean_share_when_right'] if s['mean_share_when_right'] is not None else '—'} / " +
                     f"{s['mean_share_when_wrong'] if s['mean_share_when_wrong'] is not None else '—'} | " +
                     f"{s['mean_conf_of_wrong_majority'] if s['mean_conf_of_wrong_majority'] is not None else '—'} |")
        L += ["", "**Vote share as a confidence score** (the way most agent juries use it) against each " +
              "judge's own declared confidence, same ECE and zero-error coverage:", "",
              "| confidence source | accuracy | ECE | zero-error coverage |", "|---|---|---|---|",
              f"| panel vote share (majority) | {pct(p['majority_accuracy'])} | {num(p['vote_share_ece'])} | " +
              f"{pct(p['vote_share_zero_error_coverage'])} |"]
        for j, d in e["declared_confidence"].items():
            L.append(f"| {j} (declared) | {pct(d['accuracy'])} | {d['ece']:.3f} | {pct(d['zero_error_coverage'])} |")
        hard = e["subsets"].get("hard", {}).get("jury_sensitivity")
        if hard:
            uw = hard["unanimous_wrong_max"]
            tail = (f"the most consensual wrong jury is unanimous and wrong on {uw['value']} / {uw['of']} " +
                    f"({uw['jury']})." if uw["value"] else
                    "no three-judge jury is unanimous and wrong on any hard task.")
            L += ["", f"**Pick the jury, pick the headline.** Over all {hard['juries']} three-judge juries " +
                  f"drawn from this panel, majority accuracy on the {e['subsets']['hard']['n']} hard tasks runs from " +
                  f"{pct(hard['majority_accuracy_min']['value'])} ({hard['majority_accuracy_min']['jury']}) to " +
                  f"{pct(hard['majority_accuracy_max']['value'])} ({hard['majority_accuracy_max']['jury']}); "
                  + tail]
        L += [""] + render_error_correlation(e["error_correlation"])
        comp = e["subsets"].get("hard", {}).get("jury_composition")
        if comp:
            L += render_jury_composition(comp, e["subsets"]["hard"]["n"])
        L.append("")
    L += ["## How to read it", "",
          "- **pairwise agreement**: mean over judge pairs of the share of cases where both chose the same option.",
          "- **unanimous (wrong)**: cases where every judge who answered chose the same option (at least two " +
          "answered), and how many of those were wrong.",
          "- **ties**: an even split among those who answered — no decision. *majority accuracy (all)* counts " +
          "a tie as not correct (the jury could not act); *(decided)* is accuracy over the rows with a " +
          "majority. Ties are excluded from the share statistics.",
          "- **abstentions**: blank (unparseable) answers across the panel; an abstention is not a vote.",
          "- **vote share right / wrong**: mean share of the winning option when the majority was right vs. wrong. " +
          "If the two numbers are close, agreement carries no information about correctness.",
          "- **conf of the wrong majority**: mean declared confidence of the judges who voted with a wrong majority.",
          "- **vote share as confidence**: ECE and zero-error coverage computed with the share as the confidence " +
          "of the majority decision — the number an agent jury would act on.",
          "- **error correlation** (per judge pair, over the rows where both answered; n stated per " +
          "pair): *joint error* is the share of rows where both were wrong; *P(A wrong | B wrong)* is " +
          "the joint errors over B's errors; *error-set Jaccard* is shared errors over the union of the " +
          "two error sets; *phi* is the correlation between the two 0/1 error indicators (+1: identical " +
          "errors, 0: independent, −1: never wrong together). Phi is undefined when a judge has no " +
          "error (or no correct answer) on the compared rows, the conditional when the conditioning " +
          "judge has none, Jaccard when neither erred. Three judges with phi near 1 are one opinion " +
          "voting three times.",
          "- **jury composition**: *mean pairwise error phi* averages the three pairs' phi (pairs with " +
          "an undefined phi are left out and the count is shown; \"—\" when all three are), on the " +
          "hard rows and on every row of the dataset; *shared wrong* counts the hard rows where all " +
          "three answered and all three were wrong; *diversity vs accuracy* is the Spearman rank " +
          "correlation between mean phi and majority accuracy across the juries — reported as " +
          "computed, on 40 scored rows.",
          "", "## Caveats", "",
          "- Synthetic, seeded datasets; ground truth for routing is by construction. n is small; " +
          "subset rows are indicative.",
          "- Ties are no decision (see above). An earlier version broke ties alphabetically, which on the " +
          "router always favoured `route_easy`; changed and disclosed in `jury-consensus-plan.md`.",
          "- Judges differ in cost, size and confidence method; the panel is heterogeneous on purpose " +
          "(same-model juries are the documented failure mode — Smit et al., ICML 2024).",
          "- Round 1 only: nobody saw anybody else's vote. Round 2 (deliberation) is pre-registered in " +
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
