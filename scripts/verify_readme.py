"""Every number in the README tables must be the committed JSON it came from, rounded.

The README is written by hand; the JSON under docs/ is regenerated from the raw checkpoints
in CI. This check ties the two together: it reads the three results tables in README.md
(the Jev audits, with the figures in their "What it shows" cells; the Arena; the consensus
panel) and the hero chart's caption and alt text, finds the JSON field behind every figure,
and fails if a figure is anything but that field rounded to the digits shown, or printed
coarser than its column. Every expected row must appear exactly once. In the caption, the
judges named as separated from Jev (below or above it) or not are recomputed from the 95 %
intervals. A figure may be rounded; it may never be changed. Other README prose is not read,
except the "v0.5 findings" section: each of its sentences that carries a figure or a verdict is
rebuilt from docs/v05-results.json and must appear word for word, exactly once, in its paragraph
next to that paragraph's caveats. Those sentences carry their direction words (beat / lost to,
worse / better, rebuilt from the signs), the Holm threshold (from the JSON's alpha), the
dataset years and the single-run caveat, so an edit to any of them fails. The quickstart's
simulated figures and its `check --min-safe-rate` gate (the share, its "below N %", and the
exit codes claimed) are checked against a fresh simulated run and check (seeded, no API key,
a few seconds).

  python scripts/verify_readme.py            # exit 1 on any mismatch, listing them
"""
from __future__ import annotations

import functools
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DAGGER = "†"   # the exact Clopper–Pearson interval, printed where the bootstrap cannot move

# README row label -> Arena JSON key. A row the map does not know is an error, not a skip.
ARENA_ROWS = {
    "Jev (TypeSafe)": "jev",
    "Claude Sonnet 4.5": "claude-sonnet-4.5",
    "Gemini 3 Flash": "gemini-3-flash",
    "Llama 3.3 70B": "llama-3.3-70b",
    "DeepSeek R1": "deepseek-r1",
    "gemma4 e4b (local)": "gemma4",
    "llama3.2 3B (local)": "llama32",
    "DeBERTa-v3 NLI zero-shot (local)": "deberta-nli",
    "DeBERTa-v3 fine-tuned, run 1": "finetuned-deberta",
    "DeBERTa-v3 fine-tuned, run 2 + temperature scaling": "finetuned-deberta-run2-ts",
    "DeBERTa-v3 fine-tuned, run 2": "finetuned-deberta-run2",
}
CONSENSUS_ROWS = {"Emails under attack": "email-adversarial",
                  "Router, bare labels": "router-bare",
                  "Router, described options": "router-described"}
# Names the README uses for a judge, to check "best declared confidence: ECE (<judge>)".
SHORT_NAMES = {"Jev": "jev", "Sonnet 4.5": "claude-sonnet-4.5", "Claude Sonnet 4.5":
               "claude-sonnet-4.5", "Gemini 3 Flash": "gemini-3-flash",
               "Llama 70B": "llama-3.3-70b", "DeepSeek R1": "deepseek-r1", "gemma4": "gemma4",
               "llama3.2": "llama32", "DeBERTa": "deberta-nli"}
JEV_AUDITS = {"audit-jev-real.md": "audit-jev-real.json",
              "audit-jev-adversarial.md": "audit-jev-adversarial.json",
              "audit-jev-router.md": "audit-jev-router.json",
              "audit-jev-router-ablation.md": "audit-jev-router-described.json"}

NUM = r"[-+]?\d+(?:\.\d+)?"


def tables(md: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table in `md`: (header cells, body rows)."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        if (lines[i].startswith("|") and i + 1 < len(lines)
                and re.match(r"^\|[\s:|-]+\|$", lines[i + 1])):
            header = cells(lines[i])
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append((header, rows))
        else:
            i += 1
    return out


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def rounded(value: float, shown: str, pct: bool = False) -> set[str]:
    """The strings `value` may legitimately print as, at the precision of `shown`."""
    digits = len(shown.split(".")[1]) if "." in shown else 0
    x = value * 100 if pct else value
    q = Decimal(1).scaleb(-digits)
    forms = {format(x, f".{digits}f"),
             str(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))}
    return {f.replace("-0.", "0.") if float(f) == 0 else f for f in forms}


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.checked = 0

    def num(self, where: str, shown: str, value, pct: bool = False, signed: bool = False,
            places: int | None = None):
        """`shown` (as printed in the README) must be `value` rounded, to at least `places`
        decimals (default: one for a percentage, two otherwise) — a coarser rounding hides a
        change. A value that is a whole number at that scale (100 %, 73 %, $0) may drop them."""
        self.checked += 1
        if not shown:
            self.failures.append(f"{where}: the README text no longer states this figure")
            return
        if value is None:
            self.failures.append(f"{where}: README says {shown}, the JSON has no value")
            return
        text = shown.lstrip("+") if signed else shown
        if signed and float(value) > 0 and not shown.startswith("+"):
            self.failures.append(f"{where}: README says {shown}, the JSON says +{value}")
            return
        need = places if places is not None else (1 if pct else 2)
        shown_places = len(text.split(".")[1]) if "." in text else 0
        x = float(value) * 100 if pct else float(value)
        if shown_places < need and abs(x - round(x)) > 1e-9:
            self.failures.append(f"{where}: README prints {shown}, fewer than {need} decimals")
            return
        if text not in rounded(float(value), text, pct):
            unit = " (×100)" if pct else ""
            self.failures.append(f"{where}: README says {shown}, the JSON says {value}{unit}")

    def eq(self, where: str, shown, value) -> None:
        self.checked += 1
        if str(shown) != str(value):
            self.failures.append(f"{where}: README says {shown}, the JSON says {value}")

    def point_ci(self, where: str, cell: str, point, ci, method, pct: bool,
                 places: int | None = None) -> None:
        """A cell like `95.5% [92.5, 98.0]`, `**0%** [0.0, 1.8]†` or `0.039 [0.028, 0.066]`."""
        m = re.search(rf"({NUM})%?\**\s*\[({NUM}), ({NUM})\](†?)", cell)
        if not m:
            self.failures.append(f"{where}: cannot read a point and an interval in {cell!r}")
            return
        self.num(where, m.group(1), point, pct, places=places)
        if not ci:
            self.failures.append(f"{where}: README prints an interval, the JSON has none")
            return
        self.num(where + " (interval low)", m.group(2), ci[0], pct, places=places)
        self.num(where + " (interval high)", m.group(3), ci[1], pct, places=places)
        self.eq(where + " (exact-interval mark †)", bool(m.group(4)), method == "clopper-pearson")


def load(name: str) -> dict:
    return json.loads((ROOT / "docs" / name).read_text(encoding="utf-8"))


def find_table(all_tables, first: str):
    for header, rows in all_tables:
        if header and header[0] == first:
            return header, rows
    raise SystemExit(f"README: no table whose first column is {first!r}")


def row_set(ck: Checker, table: str, seen: list[str], expected) -> None:
    """Every row the JSON has is in the README, once: a deleted row is a hidden result."""
    for key in sorted(set(expected)):
        if seen.count(key) != 1:
            ck.failures.append(f"{table}: row for {key!r} appears {seen.count(key)} times")


def guarded(ck: Checker, where: str, fn, *args) -> None:
    """A reworded cell the regexes no longer read is a mismatch that names the cell."""
    try:
        fn(*args)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        ck.failures.append(f"{where}: cannot read the README cell ({type(e).__name__}: {e})")


def check_jev_audits(ck: Checker, all_tables) -> None:
    header, rows = find_table(all_tables, "Audit")
    seen = []
    for row in rows:
        guarded(ck, f"Jev audits / {row[0]}", check_jev_row, ck, row, seen)
    row_set(ck, "Jev audits", seen, JEV_AUDITS)


def check_jev_row(ck: Checker, row: list[str], seen: list[str]) -> None:
    report = re.search(r"\((docs/[^)]+)\)", row[-1])
    name = Path(report.group(1)).name if report else ""
    if name not in JEV_AUDITS:
        ck.failures.append(f"Jev audits: unknown report link in row {row[0]!r}")
        return
    seen.append(name)
    d = load(JEV_AUDITS[name])
    overall = d.get("overall", d)
    where = f"Jev audits / {name}"
    ck.eq(where + " / n", row[1], d["n"])
    ck.num(where + " / accuracy", row[2].replace(" %", "").replace("%", ""),
           overall["accuracy"], pct=True)
    ck.num(where + " / ECE", row[3], overall["ece"], places=3)
    check_jev_claims(ck, where, name, row[4], d)


def check_jev_claims(ck: Checker, where: str, name: str, text: str, d: dict) -> None:
    """The figures in the 'What it shows' prose cell, each tied to its field."""
    where += " / what it shows"
    if name == "audit-jev-adversarial.md":
        asr = d["attack_success_rate"]
        m = re.search(r"flips (\d+)/(\d+)", text)
        ck.eq(where + " / injection successes", f"{m.group(1)}/{m.group(2)}",
              f"{asr['prompt_injection']['success']}/{asr['prompt_injection']['n']}")
        m = re.search(rf"from ({NUM}) to ({NUM})", text)
        ck.num(where + " / clean confidence", m.group(1), d["by_attack"]["clean"]["mean_confidence"])
        ck.num(where + " / injection confidence", m.group(2),
               d["by_attack"]["prompt_injection"]["mean_confidence"])
        m = re.search(rf"does \*not\* drop \(({NUM})\)", text)
        ck.num(where + " / ambiguous confidence", m.group(1),
               d["by_attack"]["ambiguous"]["mean_confidence"])
        m = re.search(r"Homoglyphs and social engineering: (\d+) successes", text)
        homoglyph = sum(round((1 - a["accuracy"]) * a["n"])
                        for k, a in d["by_attack"].items() if k.startswith("homoglyph"))
        ck.eq(where + " / homoglyph successes", m.group(1), homoglyph)
        ck.eq(where + " / social-engineering successes", m.group(1),
              asr["social_engineering"]["success"])
    elif name == "audit-jev-router.md":
        hard = d["by_segment"]["clean_hard"]
        m = re.search(rf"(\d+)/(\d+) on hard tasks at median confidence ({NUM})", text)
        ck.eq(where + " / hard to strong", f"{m.group(1)}/{m.group(2)}",
              f"{round(hard['accuracy'] * hard['n'])}/{hard['n']}")
        wrong = [f["confidence"] for f in d["failures"]]
        ck.num(where + " / median confidence when wrong", m.group(3), statistics.median(wrong))
    elif name == "audit-jev-router-ablation.md":
        hard = d["by_segment"]["clean_hard"]
        m = re.search(r"(\d+)/(\d+) hard tasks now go to the strong model", text)
        ck.eq(where + " / hard to strong", f"{m.group(1)}/{m.group(2)}",
              f"{round(hard['accuracy'] * hard['n'])}/{hard['n']}")
        wrong = [f["confidence"] for f in d["failures"]]
        m = re.search(rf"confidence ({NUM})–({NUM}) \(vs ({NUM}) when right\)", text)
        ck.num(where + " / lowest wrong confidence", m.group(1), min(wrong))
        ck.num(where + " / highest wrong confidence", m.group(2), max(wrong))
        ck.num(where + " / confidence when right", m.group(3), d["mean_confidence_correct"])


def check_arena(ck: Checker, all_tables) -> None:
    header, rows = find_table(all_tables, "judge")
    arena, held = load("arena-2026-09.json"), load("finetuned-baseline-2026-09.json")
    col = {h: i for i, h in enumerate(header)}
    seen = []
    for row in rows:
        guarded(ck, f"Arena / {row[0]}", check_arena_row, ck, row, col, arena, held, seen)
    # every judge the Arena JSON has, not just the ones this script knows by name
    row_set(ck, "Arena", seen, set(ARENA_ROWS.values()) | set(arena))


def check_arena_row(ck: Checker, row, col, arena, held, seen) -> None:
    key = next((v for k, v in ARENA_ROWS.items() if row[0].startswith(k)), None)
    if key is None:
        ck.failures.append(f"Arena: unknown judge row {row[0]!r}")
        return
    seen.append(key)
    attack = arena[key]["datasets"]["email-adversarial"]
    where = f"Arena / {row[0]}"
    for name, field, pct in (("accuracy", "accuracy", True), ("ECE", "ece", False),
                             ("zero-error coverage", "zero_error_coverage", True)):
        ck.point_ci(f"{where} / {name}", row[col[name]], attack[field],
                    attack.get(f"{field}_ci"), attack.get(f"{field}_ci_method"), pct,
                    places=None if pct else 3)
    right, wrong = row[col["conf right / wrong"]].split(" / ")
    ck.num(where + " / confidence when right", right, attack["mean_conf_correct"])
    ck.num(where + " / confidence when wrong", wrong, attack["mean_conf_wrong"])
    ck.num(where + " / confidence drop under injection", row[col["conf drop under injection"]],
           attack["confidence_drop_under_injection"], signed=True)
    ck.num(where + " / cost", row[col["cost / 200"]].lstrip("$"), attack["cost_usd"], places=3)
    router_cell, land = row[col["router (described)"]], row[col["cost-inflation attacks that land"]]
    if "held-out" in router_cell:
        r = held["judges"][key]["datasets"]["router-described"]
        ck.point_ci(where + " / router (held-out)", router_cell, r["accuracy"],
                    r["accuracy_ci"], r["accuracy_ci_method"], True)
        m = re.search(r"n=(\d+); only (\d+) unseen-text", router_cell)
        ck.eq(where + " / router held-out n", m.group(1), r["n"])
        ck.eq(where + " / router unseen-text n", m.group(2), r["unseen_text_n"])
        ck.eq(where + " / cost-inflation attacks", land.split(" ")[0],
              f"{r['attack_success']}/{r['attack_n']}")
    else:
        r = arena[key]["datasets"]["router-described"]
        ck.point_ci(where + " / router (described)", router_cell, r["accuracy"],
                    r.get("accuracy_ci"), r.get("accuracy_ci_method"), True)
        attacked = load("audit-jev-router-described.json")["by_segment"]["adversarial"]["n"]
        ck.eq(where + " / cost-inflation attacks", land, f"{r['attack_success']}/{attacked}")


def check_consensus(ck: Checker, all_tables) -> None:
    header, rows = find_table(all_tables, "dataset")
    consensus, arena = load("consensus-2026-09.json"), load("arena-2026-09.json")
    m = re.match(r"(\d+)-judge majority", header[1])
    seen = []
    for row in rows:
        guarded(ck, f"Consensus / {row[0]}", check_consensus_row, ck, row, m, consensus, arena,
                seen)
    row_set(ck, "Consensus", seen, CONSENSUS_ROWS.values())


def check_consensus_row(ck: Checker, row, m, consensus, arena, seen) -> None:
    ds = CONSENSUS_ROWS.get(row[0])
    if ds is None:
        ck.failures.append(f"Consensus: unknown dataset row {row[0]!r}")
        return
    seen.append(ds)
    p, where = consensus[ds]["panel"], f"Consensus / {row[0]}"
    ck.eq(where + " / jury size", m.group(1), len(p["judges"]))
    maj, decided = row[1].rsplit(" / ", 1)
    ck.point_ci(where + " / majority accuracy", maj, p["majority_accuracy"],
                p.get("majority_accuracy_ci"), p.get("majority_accuracy_ci_method"), True)
    ck.num(where + " / majority accuracy on decided rows", decided.rstrip("%"),
           p["majority_accuracy_decided"], pct=True)
    ck.eq(where + " / ties", row[2], p["ties"])
    best = max(p["judges"], key=lambda j: arena[j]["datasets"][ds]["accuracy"])
    b = arena[best]["datasets"][ds]
    ck.num(where + " / best single judge", re.match(NUM, row[3]).group(0),
           p["best_single_accuracy"], pct=True)
    ck.point_ci(where + " / best single judge (its interval)", row[3], b["accuracy"],
                b.get("accuracy_ci"), b.get("accuracy_ci_method"), True)
    right, wrong = row[4].split(" / ")
    ck.num(where + " / vote share when right", right, p["mean_share_when_right"])
    ck.num(where + " / vote share when wrong", wrong, p["mean_share_when_wrong"])
    ck.num(where + " / vote-share ECE", row[5], p["vote_share_ece"], places=3)
    declared = {j: d for j, d in consensus[ds]["declared_confidence"].items()
                if d.get("juror", True) and d.get("ece") is not None}
    lowest = min(declared, key=lambda j: declared[j]["ece"])
    m2 = re.match(rf"({NUM}) \((.+)\)", row[6])
    ck.num(where + " / best declared-confidence ECE", m2.group(1), declared[lowest]["ece"],
           places=3)
    ck.eq(where + " / best declared-confidence judge", SHORT_NAMES.get(m2.group(2)), lowest)


# Names the hero caption uses, longest first so "run 2" never matches inside "run 2+TS".
HERO_NAMES = (("DeBERTa fine-tuned run 2+TS", "finetuned-deberta-run2-ts"),
              ("DeBERTa fine-tuned run 2", "finetuned-deberta-run2"),
              ("DeBERTa fine-tuned run 1", "finetuned-deberta"),
              ("DeBERTa NLI", "deberta-nli"), ("Claude Sonnet 4.5", "claude-sonnet-4.5"),
              ("Gemini 3 Flash", "gemini-3-flash"), ("Llama 3.3 70B", "llama-3.3-70b"),
              ("DeepSeek R1", "deepseek-r1"), ("gemma4", "gemma4"), ("llama3.2", "llama32"))
NOT_SEPARATED = re.compile(r"it is (?:\*\*)?not(?:\*\*)? separated from")


def names_in(text: str) -> list[str]:
    found = []
    for name, slug in HERO_NAMES:
        found += [slug] * text.count(name)
        text = text.replace(name, "")
    return found


def check_separations(ck: Checker, where: str, text: str, attack: dict) -> None:
    """Parse "Jev … is separated from A, B (…) below it, and from C above it; it is not
    separated from D, E" and recompute each side from the intervals in the JSON."""
    jev = attack["jev"]
    lo, hi = jev["zero_error_coverage_ci"]
    j = re.search(rf"Jev(?:'s)? ({NUM}) % \[({NUM}), ({NUM})\] is separated from(.+)", text)
    if not j or not NOT_SEPARATED.search(j.group(4)):
        ck.failures.append(f"{where}: cannot read which judges Jev is separated from")
        return
    ck.num(where + " / Jev", j.group(1), jev["zero_error_coverage"], pct=True)
    ck.num(where + " / Jev low", j.group(2), lo, pct=True)
    ck.num(where + " / Jev high", j.group(3), hi, pct=True)
    sep_text, rest = NOT_SEPARATED.split(j.group(4), maxsplit=1)
    not_text = re.split(r"\.(?:\s|$)", rest, maxsplit=1)[0]
    named = names_in(sep_text) + names_in(not_text)
    for slug in attack:
        if slug != "jev":
            ck.eq(f"{where} / {slug} named once", named.count(slug), 1)
    for chunk in sep_text.split(" and from "):
        above = "above it" in chunk
        bound = re.search(rf"exact upper bound (?:is )?({NUM}) %", chunk)
        point = re.search(rf"\(({NUM}) % \[({NUM}), ({NUM})\]\)", chunk)
        for slug in names_in(chunk):
            d = attack[slug]
            c_lo, c_hi = d["zero_error_coverage_ci"]
            ck.eq(f"{where} / {slug} separated {'above' if above else 'below'} Jev",
                  c_lo > hi if above else c_hi < lo, True)
            if bound:
                ck.eq(f"{where} / {slug} at 0 %", d["zero_error_coverage"], 0.0)
                ck.eq(f"{where} / {slug} exact interval", d["zero_error_coverage_ci_method"],
                      "clopper-pearson")
                ck.num(f"{where} / {slug} upper bound", bound.group(1), c_hi, pct=True)
            if point:
                ck.num(f"{where} / {slug}", point.group(1), d["zero_error_coverage"], pct=True)
                ck.num(f"{where} / {slug} low", point.group(2), c_lo, pct=True)
                ck.num(f"{where} / {slug} high", point.group(3), c_hi, pct=True)
    up = re.search(rf"interval up to ({NUM}) %", not_text)
    for slug in names_in(not_text):
        c_lo, c_hi = attack[slug]["zero_error_coverage_ci"]
        ck.eq(f"{where} / {slug} not separated from Jev", c_lo <= hi and c_hi >= lo, True)
    sonnet = attack["claude-sonnet-4.5"]
    ck.num(f"{where} / claude-sonnet-4.5 upper bound", up and up.group(1),
           sonnet["zero_error_coverage_ci"][1], pct=True)


def check_hero(ck: Checker, md: str) -> None:
    """The hero chart's caption and alt text: their figures, and which gaps the 95 %
    intervals separate — read from the prose, recomputed from the JSON."""
    m = re.search(r"\*\*Read this chart with its limits\.\*\*(.+)", md)
    alt = re.search(r'<img alt="(200 emails under attack[^"]+)" src="docs/assets/hero-arena', md)
    if not m or not alt:
        ck.failures.append("hero chart: caption or alt text not found")
        return
    arena = load("arena-2026-09.json")
    attack = {k: v["datasets"]["email-adversarial"] for k, v in arena.items()
              if "email-adversarial" in v["datasets"]}
    rows = (ROOT / "examples/email-routing-adversarial/labels.jsonl").read_text().splitlines()
    states = [json.loads(r)["state"] for r in rows if r.strip() and '"state"' in r]
    n = re.search(r"\((\d+) emails, (\d+) distinct texts", m.group(1))
    ck.eq("hero caption / n", n and n.group(1), attack["jev"]["n"])
    ck.eq("hero caption / distinct texts", n and n.group(2), len(set(states)))
    check_separations(ck, "hero caption", m.group(1), attack)
    check_separations(ck, "hero alt text", alt.group(1), attack)
    check_headline(ck, md, attack)


def check_headline(ck: Checker, md: str, attack: dict) -> None:
    """The first-screen headline, read word for word (nothing may be slipped in between its
    figures) and exactly once: a gap the intervals separate, every figure in it checked."""
    pattern = (rf"\*\*On (\d+) synthetic emails under attack, Gemini 3 Flash is ({NUM}) % "
               rf"accurate and averages ({NUM}) confidence whether it is right or wrong\. "
               rf"Share of its decisions you could automate with zero observed errors: "
               rf"({NUM}) % \(95 % upper bound ({NUM}) %\)\. Jev: ({NUM}) % "
               rf"\[({NUM}), ({NUM})\]\.\*\*")
    found = re.findall(pattern, md)
    ck.checked += 1
    if len(found) != 1:
        ck.failures.append(f"headline: the Gemini 3 Flash sentence appears {len(found)} times "
                           "word for word (expected once; reworded or duplicated)")
        return
    h = re.search(pattern, md)
    assert h is not None
    g, jev = attack["gemini-3-flash"], attack["jev"]
    where = "headline / Gemini 3 Flash"
    ck.eq(where + " n", h.group(1), g["n"])
    ck.num(where + " accuracy", h.group(2), g["accuracy"], pct=True)
    ck.num(where + " mean confidence when right", h.group(3), g["mean_conf_correct"])
    ck.num(where + " mean confidence when wrong", h.group(3), g["mean_conf_wrong"])
    ck.num(where + " zero-error coverage", h.group(4), g["zero_error_coverage"], pct=True)
    ck.eq(where + " exact interval", g["zero_error_coverage_ci_method"], "clopper-pearson")
    ck.num(where + " upper bound", h.group(5), g["zero_error_coverage_ci"][1], pct=True)
    ck.num("headline / Jev zero-error coverage", h.group(6), jev["zero_error_coverage"], pct=True)
    ck.num("headline / Jev low", h.group(7), jev["zero_error_coverage_ci"][0], pct=True)
    ck.num("headline / Jev high", h.group(8), jev["zero_error_coverage_ci"][1], pct=True)
    g_hi, j_lo = g["zero_error_coverage_ci"][1], jev["zero_error_coverage_ci"][0]
    ck.checked += 1
    if not g_hi < j_lo:
        ck.failures.append(f"headline: the intervals overlap — Gemini's upper bound {g_hi} is "
                           f"not below Jev's lower bound {j_lo}, so the gap is not separated")


ROBUSTNESS = ("Two robustness checks back the Jev–Gemini gap: it is separated in each of three "
              "pre-registered repeat runs")


def check_robustness(ck: Checker, md: str) -> None:
    """The caption's two robustness claims must be there, word for word, and match the
    reports they link: rewording the sentence fails instead of switching the check off."""
    ck.checked += 1
    if ROBUSTNESS not in md:
        ck.failures.append("robustness: the caption's repeat-runs sentence is missing or reworded")
        return
    rep = {p["id"]: p for p in load("repeats-2026-09.json")["predictions"]}
    ck.eq("robustness / Jev–Gemini separated in every repeat (P3)", rep["P3"]["held"], True)
    ck.eq("robustness / Jev–Gemini separated on distinct texts",
          load("robustness-distinct-2026-09.json")["headline"]["separated"], True)


# ---------- v0.5 findings (docs/v05-results.json) ----------

def _d(x: float) -> str:
    """A signed AUROC difference as docs/v05-results.md prints it: +0.098, -0.046."""
    return f"{x:+.3f}"


def _pc(x: float) -> str:
    return f"{x * 100:.1f} %"


def _test(t: dict, label: str) -> str:
    lo, hi = t["ci"]
    return f"{label} {_d(t['difference'])} [{_d(lo)}, {_d(hi)}]"


def _and(items: list[str]) -> str:
    if not items:   # a sentence the README cannot hold: a named mismatch, not an IndexError
        return "(none in docs/v05-results.json)"
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _by_model(verdicts: list[dict]) -> str:
    """'H1-sc and H2 for gemini-3.6-flash': the hypotheses grouped by model, in JSON order."""
    models: dict[str, list[str]] = {}
    for v in verdicts:
        models.setdefault(v["model"], []).append(v["hypothesis"])
    return "; ".join(f"{_and(h)} for {m}" for m, h in models.items())


def _scoring_rule(verdicts: list[dict]) -> str:
    """How many verdicts carry the JSON's `depends_on_scoring_rule` flag, and which of them
    change verdict between the two readings (`strict != reread`)."""
    flagged = [v for v in verdicts if v["depends_on_scoring_rule"]]
    flips = [v for v in verdicts if v["strict"] != v["reread"]]
    if not flagged:
        head = 'none carries "depends on the scoring rule"'
    else:
        verb = "carries" if len(flagged) == 1 else "carry"
        head = f'{len(flagged)} {verb} "depends on the scoring rule" ({_by_model(flagged)})'
    if not flips:
        tail = "none of them changes verdict under the re-reading"
    elif any(not v["depends_on_scoring_rule"] for v in flips):
        tail = f"{_by_model(flips)} changes verdict without the flag"
    elif len(flips) == 1:
        tail = f"one of them, {_by_model(flips)}, changes verdict under the re-reading"
    else:
        tail = f"{len(flips)} of them, {_by_model(flips)}, change verdict under the re-reading"
    return f"{head}, and {tail}"


# The datasets' publication years: not in the JSON, so pinned here; every v0.5 caveat cites them.
DATASET_YEARS = "BANKING77 (2020) and CLINC150 (2019)"


def _verdict(v: dict, reading: str) -> str:
    return "supported" if v[reading] else "not supported"


def v05_expected(d: dict) -> dict[str, list[str]]:
    """Paragraph opening -> the sentences it must hold, each rebuilt from the results JSON."""
    strict, reread = d["tests"]["strict"], d["tests"]["reread"]
    verdicts = {(v["hypothesis"], v["model"]): v for v in d["verdicts"]}
    m, prov = d["metrics"], d["provenance"]
    n_b, n_c = m["banking77/jev"]["strict"]["n"], m["clinc150/jev"]["strict"]["n"]
    h2q, h2g = verdicts[("H2", "Qwen3-8B")], verdicts[("H2", "gemini-3.6-flash")]
    h1lp = verdicts[("H1-lp", "Qwen3-8B")]
    h1q, h1g = verdicts[("H1-sc", "Qwen3-8B")], verdicts[("H1-sc", "gemini-3.6-flash")]
    alpha = f"{d['alpha']:g}"
    resolved = [k for k, t in strict.items() if t["resolved"]]
    predicted = sum(t["as_predicted"] for t in strict.values())
    # tests that "match" only because a not-resolved prediction met an opposite-sign result
    hollow = [k for k, t in strict.items()
              if t["as_predicted"] and not t["resolved"] and t["opposite_sign"]]
    n_v = len(d["verdicts"])
    n_sup = sum(v["strict"] for v in d["verdicts"])
    sc = ["T3", "T4", "T5", "T6"]
    worse = sum(strict[t]["opposite_sign"] for t in sc)
    opposed = [t for t in sc if strict[t]["opposite_sign"]]
    # all([]) is True: with no opposite-sign test the word is neither "worse" nor "better"
    sc_word = ("no differently" if not opposed
               else "worse" if all(strict[t]["difference"] < 0 for t in opposed) else "better")
    worse_rr = sum(reread[t]["opposite_sign"] for t in sc)
    t1, t2, t2r = strict["T1"], strict["T2"], reread["T2"]
    w1 = "beat" if t1["difference"] > 0 else "lost to"
    w2 = "beat" if t2["difference"] > 0 else "lost to"
    if t2["opposite_sign"] and not t2r["opposite_sign"] and not t2r["resolved"]:
        t2_text = [f"{w2} it on CLINC150 only under the pre-registered rule "
                   f"({_test(t2, 'T2')}, Holm p {t2['p_holm']:.3f})",
                   f"T2 is not resolved under the re-reading (Holm p {t2r['p_holm']:.3f})"]
    else:   # the README's qualifier no longer describes T2: fail until it is rewritten
        t2_text = [f"{w2} it on CLINC150 ({_test(t2, 'T2')}, Holm p {t2['p_holm']:.3f} under "
                   f"the pre-registered rule, {t2r['p_holm']:.3f} under the re-reading)"]
    repeat_names = {"jev": "Jev", "llm-qwen3-8b": "Qwen3-8B verbalized"}
    repeated = " and ".join(repeat_names[r["runs"][0]] for r in d["repeats"])
    caveat = ("*Caveats:* the data are public datasets, " + DATASET_YEARS + ", probably in the "
              "judges' pretraining data; each confirmatory run ran once (repeats only for "
              f"{repeated} on BANKING77); ")
    e1 = (m["banking77/logprob-qwen3-8b-prompt-v2"]["strict"]["auroc"]
          - m["banking77/llm-qwen3-8b-prompt-v2"]["strict"]["auroc"])
    depends = {t: "depends on the scoring rule" if strict[t].get("depends_on_scoring_rule")
               else "does not depend on the scoring rule" for t in ("T6", "T8")}
    k_q, k_g = prov["banking77/llm-qwen3-8b-sc10"]["samples"], prov[
        "banking77/llm-gemini-3.6-flash-sc5"]["samples"]
    if h1q["strict"] or h1g["strict"]:
        h1sc = (f"H1-sc is {_verdict(h1q, 'strict')} for Qwen3-8B and {_verdict(h1g, 'strict')} "
                "for gemini-3.6-flash.")
    else:
        h1sc = "H1-sc is not supported for Qwen3-8B or for gemini-3.6-flash."

    def cert(run: str, target: str, long: bool) -> str:
        p = m[f"banking77/{run}"]["strict"]["certification"][target]["pooled"]
        tail = (f"({p['errors']} errors / {p['covered']} automated)" if long
                else f"({p['errors']} / {p['covered']})")
        return f"{_pc(p['coverage'])} at ≤ {round(float(target) * 100)} % {tail}"

    jev10 = m["banking77/jev"]["strict"]["certification"]
    s5, s10 = jev10["0.05"]["spread_coverage"], jev10["0.1"]["spread_coverage"]
    seeds = jev10["0.05"]["spread_seeds"]
    nothing_low = all(r["strict"]["certification"][t]["pooled"]["covered"] == 0
                      for k, r in m.items() if k.startswith("banking77/") for t in ("0.01", "0.02"))
    no_reviewer = "no external human reviewer read the plan before the study ran"
    flips = [v for v in d["verdicts"] if v["strict"] != v["reread"]]
    flip_text = ("no verdict changes" if not flips else
                 f"one verdict ({_by_model(flips)}) changes" if len(flips) == 1 else
                 f"{len(flips)} verdicts ({_by_model(flips)}) change")

    def rate(run: str) -> str:
        c = m[f"banking77/{run}"]["strict"]["certification"]["0.05"]
        lo, hi = c["spread_coverage"]
        share = _pc(c["pooled"]["coverage"]) if c["pooled"]["covered"] else "none"
        return f"{share} ({_pc(lo)}–{_pc(hi)}"

    def spread5(run: str) -> tuple[float, float]:
        lo, hi = m[f"banking77/{run}"]["strict"]["certification"]["0.05"]["spread_coverage"]
        return lo, hi

    overlap = ("overlap" if spread5("jev")[0] <= spread5("llm-gemini-3.6-flash")[1]
               else "do not overlap")

    noise = "label noise was not measured"
    return {
        "**In short.**": [
            f"counting the votes ranked their errors {sc_word} than their own verbalized number "
            f"in {worse} of {len(sc)} tests under the pre-registered rule ({worse_rr} of {len(sc)} "
            "under the re-reading)",
            f"{flip_text} with how an answer that copies an option's description is scored",
            f"On BANKING77 at ≤ 5 % error, Jev native probability can decide {rate('jev')} over "
            f"split seeds {seeds[0]}–{seeds[1]}) of the texts alone, gemini-3.6-flash verbalized "
            f"{rate('llm-gemini-3.6-flash')}), Qwen3-8B token log-probability "
            f"{rate('logprob-qwen3-8b')})",
            f"the ranges of Jev and gemini-3.6-flash {overlap}",
            "probably seen in pretraining", "one run each", "label noise not measured",
            "the held-out slice not run (#106)",
        ],
        "A pre-registered study": [
            f"BANKING77 test ({n_b:,} rows) and a CLINC150 subset ({n_c:,} rows)",
            f"the {len(strict)} confirmatory tests and their predictions were frozen",
            "[docs/v05-plan.md](docs/v05-plan.md)", "[docs/v05-results.md](docs/v05-results.md)",
            f"a test is resolved only at Holm-adjusted p below {alpha} with the predicted sign",
        ],
        "**Pre-registered confirmatory tests.**": [
            f"of the {n_v} hypothesis verdicts {n_sup} are supported and {n_v - n_sup} are not "
            f"supported; {_scoring_rule(d['verdicts'])}",
            f"Of the {len(strict)} tests {len(resolved)} are resolved "
            f"({', '.join(resolved) or _and([])}) and "
            f"{predicted} match their pre-registered prediction",
            f"{_and(hollow)} count as matched only because they were predicted not resolved, and "
            f"each was significant in the opposite direction (Holm p < {alpha})",
            f"H2 is {_verdict(h2q, 'strict')} for Qwen3-8B",
            _test(strict["T7"], "T7"),
            f"H2 is {_verdict(h2g, 'strict')} for gemini-3.6-flash ({_test(strict['T8'], 'T8')})",
            f"T8 {depends['T8']}",
            _test(reread["T8"], "T8 re-read"),
            f"H2 is {_verdict(h2g, 'reread')} for gemini-3.6-flash under the re-reading",
            f"H1-lp is {_verdict(h1lp, 'strict')} for Qwen3-8B",
            f"token log-probability {w1} verbalized confidence on BANKING77 ({_test(t1, 'T1')})",
            *t2_text,
            f"the BANKING77 gap of T1 is {_d(e1)}, against {_d(strict['T1']['difference'])}",
            caveat + no_reviewer, noise,
        ],
        "**Self-consistency against verbalized confidence.**": [
            f"(Qwen3-8B k = {k_q}, gemini-3.6-flash k = {k_g})",
            f"ranked errors {sc_word} than the model's own verbalized number in {worse} of the "
            f"{len(sc)} tests",
            f"each the opposite sign at Holm p < {alpha}",
            _test(strict["T3"], "T3"), _test(strict["T4"], "T4"), _test(strict["T5"], "T5"),
            h1sc, f"T6 (gemini-3.6-flash, CLINC150), {depends['T6']}",
            _test(strict["T6"], "T6"), _test(reread["T6"], "T6 re-read"),
            caveat + no_reviewer, noise,
        ],
        "**Safe automation rate on BANKING77.**": [
            # one split seed; its spread over the other seeds in the same sentence
            f"Jev native probability {cert('jev', '0.05', True)[:-1]}; split seed {d['seed']}, "
            f"{_pc(s5[0])}–{_pc(s5[1])} over seeds {seeds[0]}–{seeds[1]}) and "
            f"{cert('jev', '0.1', False)[:-1]}; {_pc(s10[0])}–{_pc(s10[1])} over the same seeds)",
            f"gemini-3.6-flash verbalized {cert('llm-gemini-3.6-flash', '0.05', True)[:-1]}; "
            f"{_pc(spread5('llm-gemini-3.6-flash')[0])}–{_pc(spread5('llm-gemini-3.6-flash')[1])} "
            f"over the same seeds) and {cert('llm-gemini-3.6-flash', '0.1', False)}",
            f"Qwen3-8B token log-probability {cert('logprob-qwen3-8b', '0.05', True)[:-1]}; "
            f"{_pc(spread5('logprob-qwen3-8b')[0])}–{_pc(spread5('logprob-qwen3-8b')[1])} over the "
            f"same seeds) and {cert('logprob-qwen3-8b', '0.1', False)}",
            *(["On BANKING77 no run automates anything at ≤ 1 % or ≤ 2 %"] if nothing_low else []),
            caveat + "every bound includes the datasets' own label errors, because label noise "
            + "was not measured",
            "the held-out slice was not run (#106)",
            "not a conformity assessment",
        ],
    }


def paragraph(md: str, opening: str) -> list[str]:
    return [p for p in md.split("\n\n") if p.startswith(opening)]


def check_v05(ck: Checker, md: str) -> None:
    """Every sentence with a v0.5 figure or verdict, rebuilt from the JSON: word for word, once
    in the README, inside its own paragraph (so its caveats travel with it)."""
    section = md.split("## v0.5 findings", 1)
    if len(section) != 2:
        ck.failures.append("v0.5 findings: the section is missing")
        return
    body = section[1].split("\n## ", 1)[0]
    for opening, needed in v05_expected(load("v05-results.json")).items():
        paras = paragraph(body.lstrip("\n"), opening)
        ck.checked += 1
        if len(paras) != 1:
            ck.failures.append(f"v0.5 findings: paragraph {opening!r} appears {len(paras)} times")
            continue
        for text in needed:
            ck.checked += 1
            if text not in paras[0]:
                ck.failures.append(f"v0.5 findings / {opening}: expected {text!r} (from "
                                   "docs/v05-results.json), not found word for word")
            elif (md.count(text) != 1 and re.search(r"\d", text)
                  and not text.startswith("*Caveats:*")):   # the caveat repeats by design
                ck.failures.append(f"v0.5 findings: {text!r} appears {md.count(text)} times")
    ck.checked += 1
    if "python scripts/v05_study.py --check" not in body:
        ck.failures.append("v0.5 findings: the reproduce command is missing")


# ---------- quickstart: a fresh simulated run ----------

QUICKSTART_RUN = ("judge-audit run examples/email-routing/labels.jsonl --judge simulated "
                  "--target 0.10")


@functools.cache
def simulated_line(target: str | None) -> str:
    """The first line `judge-audit run` prints for the simulated judge (seeded, no API key)."""
    args = [sys.executable, "-m", "judge_audit.cli", "run",
            str(ROOT / "examples/email-routing/labels.jsonl"), "--judge", "simulated"]
    if target:
        args += ["--target", target]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])}
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(args, cwd=tmp, env=env, capture_output=True, text=True,
                             check=True, timeout=120)
    return out.stdout.splitlines()[0]


@functools.cache
def simulated_check(share: str) -> int:
    """The exit code of the quickstart's `check --target 0.10 --min-safe-rate 0.10:SHARE`, on a
    baseline from a fresh simulated `run --target 0.10` (seeded, no API key)."""
    labels = str(ROOT / "examples/email-routing/labels.jsonl")
    cli = [sys.executable, "-m", "judge_audit.cli"]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(
        [str(ROOT / "src"), os.environ.get("PYTHONPATH", "")])}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([*cli, "run", labels, "--judge", "simulated", "--target", "0.10"],
                       cwd=tmp, env=env, capture_output=True, check=True, timeout=120)
        out = subprocess.run([*cli, "check", labels, "--judge", "simulated", "--baseline",
                              "audit-result.json", "--target", "0.10", "--min-safe-rate",
                              f"0.10:{share}"], cwd=tmp, env=env, capture_output=True,
                             timeout=120)
    return out.returncode


GATE = re.compile(r"--target 0\.10 --min-safe-rate 0\.10:(\d\.\d+)\n")
GATE_PROSE = re.compile(r"`check --min-safe-rate 0\.10:(\d\.\d+)` exits (\d) here and exits (\d) "
                        r"if that share falls below (\d+) %")


def check_gate(ck: Checker, md: str) -> None:
    """The quickstart's `check --min-safe-rate` gate: the command and the prose name the same
    share, the prose's percentage is that share, and the exit codes it claims are a fresh
    `check`'s — 0 at the share, 1 just above the fresh run's own rate."""
    ck.checked += 4
    cmd, prose = GATE.search(md), GATE_PROSE.search(md)
    if not cmd or not prose:
        ck.failures.append("quickstart: the `check --min-safe-rate` command or its sentence "
                           "(`… exits 0 here and exits 1 if that share falls below N %`) is "
                           "missing or reworded")
        return
    share = cmd.group(1)
    if prose.group(1) != share:
        ck.failures.append(f"quickstart: the command gates at {share}, the prose at "
                           f"{prose.group(1)}")
    if Decimal(prose.group(4)) != Decimal(share) * 100:
        ck.failures.append(f"quickstart: the prose says below {prose.group(4)} %, the command "
                           f"gates at {share}")
    rc_here = simulated_check(share)
    if prose.group(2) != str(rc_here):
        ck.failures.append(f"quickstart: the prose says the gate exits {prose.group(2)} here, a "
                           f"fresh check exits {rc_here}")
    rate = re.search(r"safe_automation@10%=([\d.]+)%", simulated_line("0.10"))
    above = f"{float(rate.group(1)) / 100 + 0.01:.3f}" if rate else "1.0"
    rc_above = simulated_check(above)
    if prose.group(3) != str(rc_above) or rc_above != 1:
        ck.failures.append(f"quickstart: the prose says the gate exits {prose.group(3)} when "
                           f"the share falls short, a fresh check at {above} exits {rc_above}")


def check_quickstart(ck: Checker, md: str) -> None:
    """The quickstart's printed line and the figures quoted from it are a fresh simulated run's."""
    ck.checked += 3
    if QUICKSTART_RUN not in md:
        ck.failures.append("quickstart: the simulated `run --target 0.10` command is missing")
        return
    shown = re.search(r"```text\n(SIMULATED[^\n]*?) …\n```", md)
    line = simulated_line("0.10")
    if not shown or not line.startswith(shown.group(1)):
        ck.failures.append(f"quickstart: the printed line is not the start of a fresh run: {line!r}")
    rate = re.search(r"safe_automation@10%=(\S+)", line)
    value = rate.group(1).rstrip("%") if rate else "?"
    if f"its {value} % says nothing" not in md:
        ck.failures.append(f"quickstart: the prose's figure is not the fresh run's {value} %")
    default = re.search(r"safe_automation@5%=\S+", simulated_line(None))
    if not default or f"the line reads `{default.group(0)}`" not in md:
        ck.failures.append("quickstart: the default-target figure is not a fresh run's "
                           f"({default and default.group(0)})")


def check(md: str) -> Checker:
    ck, all_tables = Checker(), tables(md)
    check_hero(ck, md)
    check_robustness(ck, md)
    check_jev_audits(ck, all_tables)
    check_arena(ck, all_tables)
    check_consensus(ck, all_tables)
    check_v05(ck, md)
    check_quickstart(ck, md)
    check_gate(ck, md)
    return ck


def main() -> None:
    ck = check((ROOT / "README.md").read_text(encoding="utf-8"))
    for f in ck.failures:
        print(f"MISMATCH {f}")
    print(f"{ck.checked} README figures checked, {len(ck.failures)} mismatch(es)")
    sys.exit(1 if ck.failures else 0)


if __name__ == "__main__":
    main()
