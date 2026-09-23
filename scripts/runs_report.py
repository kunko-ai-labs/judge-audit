"""Every per-run report recomputes from its checkpoint: the audit_resumable.py outputs.

`scripts/audit_resumable.py` writes a `.json` and a `.md` next to each checkpoint when a
run ends. Those files are generated, so they are regenerated here with the same code
(`build_result`, `report_markdown`) from the committed checkpoint and labels — no key,
no judge, no API call — and CI diffs them like every other report:

  docs/runs/arena/<slug>/<dataset>.{json,md}        (labels: examples/<dataset>/…)
  docs/runs/jury/<dataset>/<slug>.r2.{json,md}      (labels: the sibling .r2.input.jsonl;
                                                     clusters: the original dataset's texts)
  docs/audit-jev-real.json                          (Jev, clean emails; its .md is prose)

  python scripts/runs_report.py               # rewrite them all
  python scripts/runs_report.py --check       # exit 1 naming the files that would change
  python scripts/runs_report.py --charts      # also docs/audit-jev-real.html and its
                                              # accuracy-coverage PNG (needs matplotlib;
                                              # PNG bytes vary by version, so CI skips it)
  python scripts/runs_report.py --moved REF   # what moved against the reports at git REF

A checkpoint written before run headers existed (only docs/runs/audit-jev-real.ckpt.jsonl)
keeps the provenance block its report was first published with: the run time and version
are not in the checkpoint, and a regeneration must not invent them.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_resumable import (  # noqa: E402
    build_result,
    load_checkpoint,
    report_markdown,
    rows_subset,
)
from verify_published import ARENA_DATASETS  # noqa: E402

from judge_audit.report import render_html  # noqa: E402
from judge_audit.runner import load_dataset  # noqa: E402

JEV_REAL = {"labels": "examples/email-routing/labels.jsonl",
            "ckpt": "docs/runs/audit-jev-real.ckpt.jsonl", "json": "docs/audit-jev-real.json",
            "md": None, "html": "docs/audit-jev-real.html",
            "png": "docs/assets/accuracy-coverage-jev-real.png"}


def targets() -> list[dict]:
    """Every generated per-run report, with the labels and checkpoint it comes from."""
    out = []
    for js in sorted((ROOT / "docs" / "runs" / "arena").glob("*/*.json")):
        out.append({"labels": ARENA_DATASETS[js.stem], "cluster_labels": None,
                    "family": "arena", **_siblings(js, js.stem)})
    for js in sorted((ROOT / "docs" / "runs" / "jury").glob("*/*.r2.json")):
        stem = js.name.removesuffix(".json")
        # Round 2 clusters on the original texts, not on the deliberation prompt around
        # them (jury_deliberate.py passes the same --cluster-labels; so does jury_report).
        out.append({"labels": str(js.with_name(stem + ".input.jsonl").relative_to(ROOT)),
                    "cluster_labels": ARENA_DATASETS[js.parent.name],
                    "family": "jury", **_siblings(js, stem)})
    out.append({**JEV_REAL, "cluster_labels": None, "family": "audit-jev-real"})
    return out


def _siblings(js: Path, stem: str) -> dict:
    rel = js.relative_to(ROOT)
    return {"ckpt": str(rel.with_name(stem + ".ckpt.jsonl")), "json": str(rel),
            "md": str(rel.with_name(stem + ".md")), "html": None, "png": None}


def regenerate(t: dict):
    """(AuditResult, judge name) for one target, exactly as audit_resumable.py builds it."""
    rows, dataset_meta = load_dataset(t["labels"])
    done = load_checkpoint(Path(t["ckpt"]))
    if -1 not in done:
        published = json.loads(Path(t["json"]).read_text(encoding="utf-8"))["run"]
        done[-1] = {"idx": -1, "run": {k: v for k, v in published.items()
                                       if k not in ("checkpoint", "dataset")}}
    header = done[-1]["run"]
    judge_name = str(header["judge"]["name"]).split(":")[0]
    subset = header.get("rows_subset")
    if subset:
        wanted, now = rows_subset(f"{subset['split']}:{subset['part']}", len(rows))
        if now["sha256"] != subset["sha256"]:
            raise SystemExit(f"{t['ckpt']}: split {subset['split']} changed since the run")
    else:
        wanted = list(range(len(rows)))
    missing = [i for i in wanted if i not in done]
    if missing:
        raise SystemExit(f"{t['ckpt']}: incomplete checkpoint, {len(missing)} rows missing")
    cluster_rows = load_dataset(t["cluster_labels"])[0] if t["cluster_labels"] else None
    result = build_result(judge_name, rows, dataset_meta, wanted, done, Path(t["ckpt"]),
                          header, subset, cluster_rows)
    return result, judge_name


def outputs(t: dict, result, judge_name: str) -> dict[str, str]:
    files = {t["json"]: json.dumps(result.to_dict(), indent=2)}
    if t["md"]:
        files[t["md"]] = report_markdown(result, judge_name)
    return files


def moved(ref: str, t: dict, result) -> dict:
    """Old vs new curve of one report: which old points were cuts inside a tie."""
    old = json.loads(subprocess.run(["git", "show", f"{ref}:{t['json']}"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout)
    new = result.to_dict()
    conf = sorted((r["confidence"], r["correct"]) for r in result.records)[::-1]
    mixed = defaultdict(set)
    for c, ok in conf:
        mixed[c].add(ok)
    gone, inside, dependent = [], 0, 0
    for p in old["accuracy_coverage"]:
        if p in new["accuracy_coverage"]:
            continue
        gone.append(p)
        k = p["n"]
        if k < len(conf) and conf[k - 1][0] == conf[k][0]:
            inside += 1  # the cut split a group of tied confidences
            dependent += len(mixed[conf[k][0]]) == 2  # ...one that mixes right and wrong
    headline = [f"{key} {old.get(key)} -> {new.get(key)}"
                for key in ("n", "accuracy", "ece", "zero_error_coverage", "total_cost_usd",
                            "p50_latency_s", "p99_latency_s", "reliability_bins")
                if old.get(key) != new.get(key)]
    return {"old": len(old["accuracy_coverage"]), "new": len(new["accuracy_coverage"]),
            "moved": gone, "inside_tie": inside, "order_dependent": dependent,
            "distinct": len(mixed), "headline": headline}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="write nothing; exit 1 on drift")
    ap.add_argument("--charts", action="store_true", help="also the HTML report and PNG")
    ap.add_argument("--moved", metavar="REF", help="compare every curve with git REF")
    ap.add_argument("-v", "--verbose", action="store_true", help="with --moved: every point")
    a = ap.parse_args()
    os.chdir(ROOT)  # provenance names paths relative to the repository, on every machine
    stale, totals = [], defaultdict(lambda: defaultdict(int))
    for t in targets():
        result, judge_name = regenerate(t)
        for path, text in outputs(t, result, judge_name).items():
            p = Path(path)
            if p.exists() and p.read_text(encoding="utf-8") == text:
                continue
            stale.append(path)
            if not a.check:
                p.write_text(text, encoding="utf-8")
        if a.charts and t["html"]:
            from judge_audit.charts import accuracy_coverage_png
            Path(t["html"]).write_text(render_html(result, tag=""), encoding="utf-8")
            accuracy_coverage_png(result, t["png"])
        if a.moved:
            m = moved(a.moved, t, result)
            fam = totals[t["family"]]
            fam["files"] += 1
            fam["curve_changed"] += bool(m["moved"]) or m["old"] != m["new"]
            fam["points_before"] += m["old"]
            fam["points_after"] += m["new"]
            fam["points_moved"] += len(m["moved"])
            fam["inside_tie"] += m["inside_tie"]
            fam["order_dependent"] += m["order_dependent"]
            fam["order_dependent_files"] += m["order_dependent"] > 0
            fam["headline_changed"] += bool(m["headline"])
            print(f"{t['json']}: {m['distinct']} distinct confidences; curve {m['old']} -> "
                  f"{m['new']} points; {len(m['moved'])} old points moved, {m['inside_tie']} "
                  f"of them cut inside a tie, {m['order_dependent']} with order-dependent "
                  f"accuracy")
            for h in m["headline"]:
                print(f"    {h}")
            if a.verbose:
                for p in m["moved"]:
                    print(f"    moved {p['coverage']:.1%} n={p['n']} acc={p['accuracy']:.1%} "
                          f"min_conf={p['min_confidence']}")
    for fam, c in totals.items():
        print(f"== {fam}: " + ", ".join(f"{k}={v}" for k, v in c.items()))
    for path in stale:
        print(f"{'stale' if a.check else 'wrote'} {path}")
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
