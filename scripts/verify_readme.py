"""Every number in the README tables must be the committed JSON it came from, rounded.

The README is written by hand; the JSON under docs/ is regenerated from the raw checkpoints
in CI. This check ties the two together: it reads the three results tables in README.md
(the Jev audits, the Arena and the consensus panel), finds the JSON field behind every
figure, and fails if a figure is anything but that field rounded to the digits shown.
A figure may be rounded; it may never be changed.

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

    def num(self, where: str, shown: str, value, pct: bool = False, signed: bool = False):
        """`shown` (as printed in the README) must be `value` rounded."""
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
        if text not in rounded(float(value), text, pct):
            unit = " (×100)" if pct else ""
            self.failures.append(f"{where}: README says {shown}, the JSON says {value}{unit}")

    def eq(self, where: str, shown, value) -> None:
        self.checked += 1
        if str(shown) != str(value):
            self.failures.append(f"{where}: README says {shown}, the JSON says {value}")

    def point_ci(self, where: str, cell: str, point, ci, method, pct: bool) -> None:
        """A cell like `95.5% [92.5, 98.0]`, `**0%** [0.0, 1.8]†` or `0.039 [0.028, 0.066]`."""
        m = re.search(rf"({NUM})%?\**\s*\[({NUM}), ({NUM})\](†?)", cell)
        if not m:
            self.failures.append(f"{where}: cannot read a point and an interval in {cell!r}")
            return
        self.num(where, m.group(1), point, pct)
        if not ci:
            self.failures.append(f"{where}: README prints an interval, the JSON has none")
            return
        self.num(where + " (interval low)", m.group(2), ci[0], pct)
        self.num(where + " (interval high)", m.group(3), ci[1], pct)
        self.eq(where + " (exact-interval mark †)", bool(m.group(4)), method == "clopper-pearson")


def load(name: str) -> dict:
    return json.loads((ROOT / "docs" / name).read_text(encoding="utf-8"))


def find_table(all_tables, first: str):
    for header, rows in all_tables:
        if header and header[0] == first:
            return header, rows
    raise SystemExit(f"README: no table whose first column is {first!r}")


def check_jev_audits(ck: Checker, all_tables) -> None:
    header, rows = find_table(all_tables, "Audit")
    for row in rows:
        report = re.search(r"\((docs/[^)]+)\)", row[-1])
        name = Path(report.group(1)).name if report else ""
        if name not in JEV_AUDITS:
            ck.failures.append(f"Jev audits: unknown report link in row {row[0]!r}")
            continue
        d = load(JEV_AUDITS[name])
        overall = d.get("overall", d)
        where = f"Jev audits / {name}"
        ck.eq(where + " / n", row[1], d["n"])
        ck.num(where + " / accuracy", row[2].replace(" %", "").replace("%", ""),
               overall["accuracy"], pct=True)
        ck.num(where + " / ECE", row[3], overall["ece"])
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
        ck.eq(where + " / social-engineering successes", 0, asr["social_engineering"]["success"])
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
    for row in rows:
        key = next((v for k, v in ARENA_ROWS.items() if row[0].startswith(k)), None)
        if key is None:
            ck.failures.append(f"Arena: unknown judge row {row[0]!r}")
            continue
        attack = arena[key]["datasets"]["email-adversarial"]
        where = f"Arena / {row[0]}"
        for name, field, pct in (("accuracy", "accuracy", True), ("ECE", "ece", False),
                                 ("zero-error coverage", "zero_error_coverage", True)):
            ck.point_ci(f"{where} / {name}", row[col[name]], attack[field],
                        attack.get(f"{field}_ci"), attack.get(f"{field}_ci_method"), pct)
        right, wrong = row[col["conf right / wrong"]].split(" / ")
        ck.num(where + " / confidence when right", right, attack["mean_conf_correct"])
        ck.num(where + " / confidence when wrong", wrong, attack["mean_conf_wrong"])
        ck.num(where + " / confidence drop under injection", row[col["conf drop under injection"]],
               attack["confidence_drop_under_injection"], signed=True)
        ck.num(where + " / cost", row[col["cost / 200"]].lstrip("$"), attack["cost_usd"])
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
    for row in rows:
        ds = CONSENSUS_ROWS.get(row[0])
        if ds is None:
            ck.failures.append(f"Consensus: unknown dataset row {row[0]!r}")
            continue
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
        ck.num(where + " / vote-share ECE", row[5], p["vote_share_ece"])
        declared = {j: d for j, d in consensus[ds]["declared_confidence"].items()
                    if d.get("juror", True) and d.get("ece") is not None}
        lowest = min(declared, key=lambda j: declared[j]["ece"])
        m2 = re.match(rf"({NUM}) \((.+)\)", row[6])
        ck.num(where + " / best declared-confidence ECE", m2.group(1), declared[lowest]["ece"])
        ck.eq(where + " / best declared-confidence judge", SHORT_NAMES.get(m2.group(2)), lowest)


HERO_SEPARATED = ("gemini-3-flash", "llama-3.3-70b", "deepseek-r1", "gemma4", "llama32")
HERO_OVERLAPS = "claude-sonnet-4.5"


def check_hero(ck: Checker, md: str) -> None:
    """The hero chart's caption: its figures, and which gaps the intervals separate."""
    m = re.search(r"\*\*Read this chart with its limits\.\*\*(.+)", md)
    alt = re.search(r'<img alt="(200 emails under attack[^"]+)" src="docs/assets/hero-arena', md)
    if not m or not alt:
        ck.failures.append("hero chart: caption or alt text not found")
        return
    text, alt_text = m.group(1), alt.group(1)
    arena = load("arena-2026-09.json")
    attack = {k: v["datasets"]["email-adversarial"] for k, v in arena.items()}
    jev = attack["jev"]
    rows = (ROOT / "examples/email-routing-adversarial/labels.jsonl").read_text().splitlines()
    states = [json.loads(r)["state"] for r in rows if r.strip() and '"state"' in r]
    n = re.search(r"\((\d+) emails, (\d+) distinct texts", text)
    ck.eq("hero caption / n", n and n.group(1), jev["n"])
    ck.eq("hero caption / distinct texts", n and n.group(2), len(set(states)))
    j = re.search(rf"Jev ({NUM}) % \[({NUM}), ({NUM})\]", alt_text)
    if not j:
        ck.failures.append("hero alt text: cannot read Jev's point and interval")
        return
    ck.num("hero alt / Jev", j.group(1), jev["zero_error_coverage"], pct=True)
    ck.num("hero alt / Jev low", j.group(2), jev["zero_error_coverage_ci"][0], pct=True)
    ck.num("hero alt / Jev high", j.group(3), jev["zero_error_coverage_ci"][1], pct=True)
    lo = jev["zero_error_coverage_ci"][0]
    for where in (text, alt_text):
        bound = re.search(rf"exact upper bound (?:is )?({NUM}) %", where)
        for slug in HERO_SEPARATED:
            d = attack[slug]
            ck.eq(f"hero / {slug} at 0 %", d["zero_error_coverage"], 0.0)
            ck.eq(f"hero / {slug} exact interval", d["zero_error_coverage_ci_method"],
                  "clopper-pearson")
            ck.num(f"hero / {slug} upper bound", bound and bound.group(1),
                   d["zero_error_coverage_ci"][1], pct=True)
            ck.eq(f"hero / Jev separated from {slug}", lo > d["zero_error_coverage_ci"][1], True)
        up = re.search(rf"interval up to ({NUM}) %", where)
        other = attack[HERO_OVERLAPS]
        ck.num(f"hero / {HERO_OVERLAPS} upper bound", up and up.group(1),
               other["zero_error_coverage_ci"][1], pct=True)
        ck.eq(f"hero / Jev not separated from {HERO_OVERLAPS}",
              lo <= other["zero_error_coverage_ci"][1], True)


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
