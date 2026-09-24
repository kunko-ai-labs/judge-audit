"""Every number in the README tables must be the committed JSON it came from, rounded.

The README is written by hand; the JSON under docs/ is regenerated from the raw checkpoints
in CI. This check ties the two together: it reads the three results tables in README.md
(the Jev audits, with the figures in their "What it shows" cells; the Arena; the consensus
panel) and the hero chart's caption and alt text, finds the JSON field behind every figure,
and fails if a figure is anything but that field rounded to the digits shown, or printed
coarser than its column. Every expected row must appear exactly once. In the caption, the
judges named as separated from Jev (below or above it) or not are recomputed from the 95 %
intervals. A figure may be rounded; it may never be changed. Other README prose is not read.

  python scripts/verify_readme.py            # exit 1 on any mismatch, listing them
"""
from __future__ import annotations

import json
import re
import statistics
import sys
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
    """The first-screen headline: a gap the intervals separate, every figure in it checked."""
    h = re.search(rf"\*\*Gemini 3 Flash is ({NUM}) % accurate on (\d+) emails under attack and "
                  rf"says ({NUM}) whether it is right or wrong\. .*?zero observed errors: ({NUM}) % "
                  rf"\(exact upper bound ({NUM}) %\)\. Jev: ({NUM}) %\.\*\*", md)
    if not h:
        ck.failures.append("headline: the Gemini 3 Flash sentence is missing or reworded")
        return
    g, jev = attack["gemini-3-flash"], attack["jev"]
    where = "headline / Gemini 3 Flash"
    ck.num(where + " accuracy", h.group(1), g["accuracy"], pct=True)
    ck.eq(where + " n", h.group(2), g["n"])
    ck.num(where + " confidence when right", h.group(3), g["mean_conf_correct"])
    ck.num(where + " confidence when wrong", h.group(3), g["mean_conf_wrong"])
    ck.num(where + " zero-error coverage", h.group(4), g["zero_error_coverage"], pct=True)
    ck.eq(where + " exact interval", g["zero_error_coverage_ci_method"], "clopper-pearson")
    ck.num(where + " upper bound", h.group(5), g["zero_error_coverage_ci"][1], pct=True)
    ck.num("headline / Jev zero-error coverage", h.group(6), jev["zero_error_coverage"], pct=True)
    ck.eq("headline / the gap is separated", g["zero_error_coverage_ci"][1]
          < jev["zero_error_coverage_ci"][0], True)


def check(md: str) -> Checker:
    ck, all_tables = Checker(), tables(md)
    check_hero(ck, md)
    check_jev_audits(ck, all_tables)
    check_arena(ck, all_tables)
    check_consensus(ck, all_tables)
    return ck


def main() -> None:
    ck = check((ROOT / "README.md").read_text(encoding="utf-8"))
    for f in ck.failures:
        print(f"MISMATCH {f}")
    print(f"{ck.checked} README figures checked, {len(ck.failures)} mismatch(es)")
    sys.exit(1 if ck.failures else 0)


if __name__ == "__main__":
    main()
