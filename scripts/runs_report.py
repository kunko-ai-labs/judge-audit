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

Provenance is never rewritten. A report's `run` block is what the run said — the checkpoint
header, plus the dataset's ground-truth tier, read from its labels file — or, for the one
checkpoint written before headers existed, docs/runs/audit-jev-real.ckpt.jsonl, the block
its report was first published with in v0.2.0, pinned below (not read back from the file it
is checked against). When a
committed report's `run` block differs from that evidence this script stops instead of
overwriting it. A regeneration is recorded beside the run, in a `regenerated` block with
the real UTC time, version and script, written only when the file's content changes, so
rerunning on an unchanged tree rewrites nothing and CI stays byte-identical.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_resumable import (  # noqa: E402
    build_result,
    load_checkpoint,
    recorded_judge,
    report_markdown,
    rows_subset,
)
from verify_published import ARENA_DATASETS  # noqa: E402

from judge_audit import __version__  # noqa: E402
from judge_audit.ground_truth import parse_ground_truth  # noqa: E402
from judge_audit.report import render_html  # noqa: E402
from judge_audit.runner import load_dataset  # noqa: E402

SCRIPT = "scripts/runs_report.py"
JEV_REAL = {"labels": "examples/email-routing/labels.jsonl",
            "ckpt": "docs/runs/audit-jev-real.ckpt.jsonl", "json": "docs/audit-jev-real.json",
            "md": None, "html": "docs/audit-jev-real.html",
            "png": "docs/assets/accuracy-coverage-jev-real.png"}
# The run block docs/audit-jev-real.json was published with in v0.2.0 (704534b), verbatim.
# Its checkpoint has no header, so this is the only record of the run; it is pinned here
# rather than copied from the file it would then be checked against.
JEV_REAL_RUN = {"judge": {"name": "jev", "model": "typesafe-ai/jev", "backend": "gateway"},
                "judge_audit_version": "0.2.0",
                "recomputed_utc": "2026-09-19T09:09:12+00:00",
                "note": "original run time not recorded in this checkpoint",
                "checkpoint": "docs/runs/audit-jev-real.ckpt.jsonl"}


def targets() -> list[dict]:
    """Every generated per-run report, with the labels and checkpoint it comes from."""
    # Found from the checkpoints, not from the reports: evidence decides what is published.
    out = []
    for ck in sorted((ROOT / "docs" / "runs" / "arena").glob("*/*.ckpt.jsonl")):
        js = ck.with_name(ck.name.removesuffix(".ckpt.jsonl") + ".json")
        out.append({"labels": ARENA_DATASETS[js.stem], "cluster_labels": None,
                    "family": "arena", **_siblings(js, js.stem)})
    for ck in sorted((ROOT / "docs" / "runs" / "jury").glob("*/*.r2.ckpt.jsonl")):
        js = ck.with_name(ck.name.removesuffix(".ckpt.jsonl") + ".json")
        stem = js.name.removesuffix(".json")
        # Round 2 clusters on the original texts, not on the deliberation prompt around
        # them (jury_deliberate.py passes the same --cluster-labels; so does jury_report).
        out.append({"labels": str(js.with_name(stem + ".input.jsonl").relative_to(ROOT)),
                    "cluster_labels": ARENA_DATASETS[js.parent.name],
                    "family": "jury", **_siblings(js, stem)})
    out.append({**JEV_REAL, "cluster_labels": None, "family": "audit-jev-real",
                "pinned_run": JEV_REAL_RUN})
    return out


def _siblings(js: Path, stem: str) -> dict:
    # A checkpoint is evidence of a published run: its report must be there too. A missing
    # sibling is a publishing error, not a file to create silently.
    for f in (js, js.with_name(stem + ".md")):
        if not f.exists():
            raise SystemExit(f"{f.parent.name}/{f.name}: missing; every checkpoint under "
                             "docs/runs has its .json and .md report beside it")
    rel = js.relative_to(ROOT)
    return {"ckpt": str(rel.with_name(stem + ".ckpt.jsonl")), "json": str(rel),
            "md": str(rel.with_name(stem + ".md")), "html": None, "png": None}


def regenerate(t: dict):
    """(AuditResult, judge name) for one target, exactly as audit_resumable.py builds it."""
    rows, dataset_meta = load_dataset(t["labels"])
    done = load_checkpoint(Path(t["ckpt"]))
    pinned = t.get("pinned_run")
    if -1 not in done:
        if not pinned:
            raise SystemExit(f"{t['ckpt']}: no run header and no pinned provenance; "
                             "a regeneration will not invent one")
        done[-1] = {"idx": -1, "run": dict(pinned)}
    header = done[-1]["run"]
    judge_name = recorded_judge(done)
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
    if pinned:
        result.run = dict(pinned)  # verbatim: nothing added to what the run said
    return result, judge_name


def outputs(t: dict, result, judge_name: str) -> dict[str, str]:
    files = {t["json"]: json.dumps(result.to_dict(), indent=2)}
    if t["md"]:
        files[t["md"]] = report_markdown(result, judge_name)
    return files


def stamp(t: dict, result, now: str) -> dict:
    """The regeneration's own provenance: when, by which version and script, from what."""
    g = {"utc": now, "judge_audit_version": __version__, "script": SCRIPT,
         "checkpoint": t["ckpt"], "labels": t["labels"]}
    if not (result.run.get("dataset") or {}).get("ground_truth"):
        # A run older than tier headers: the tier is the labels file's, read today.
        meta = load_dataset(t["labels"])[1]
        g["ground_truth"] = parse_ground_truth(meta.get("ground_truth")).to_dict()
    return g


def _without_tier(run: dict) -> dict:
    """The run block minus the tier read from the labels file (not from the checkpoint)."""
    ds = {k: v for k, v in (run.get("dataset") or {}).items() if k != "ground_truth"}
    return {**run, "dataset": ds}


def plan(t: dict, result, judge_name: str, on_disk: dict[str, str | None],
         now: str) -> dict[str, str]:
    """The files to write for one target ({} when the committed ones are current).

    Never rewrites provenance: a committed `run` block that differs from the evidence
    stops the script. The `regenerated` block is kept while nothing else changes and
    replaced by one stamped `now` when something does.
    """
    committed = on_disk.get(t["json"])
    result.regenerated = {}
    if committed is not None:
        old = json.loads(committed)
        if old.get("run") != result.run:
            if _without_tier(old.get("run") or {}) == _without_tier(result.run):
                raise SystemExit(f"{t['json']}: the ground-truth tier declared by "
                                 f"{t['labels']} changed since this report was written; "
                                 "runs_report.py never rewrites provenance — review the "
                                 "labels file, then update the report by hand")
            raise SystemExit(f"{t['json']}: its run block differs from the one its checkpoint "
                             "(or pinned provenance) records; runs_report.py never rewrites "
                             "provenance — fix the evidence or the file by hand, with review")
        result.regenerated = old.get("regenerated") or {}
    files = outputs(t, result, judge_name)
    if all(on_disk.get(path) == text for path, text in files.items()):
        return {}
    result.regenerated = stamp(t, result, now)
    return outputs(t, result, judge_name)


def moved(ref: str, t: dict, result) -> dict:
    """Old vs new curve of one report: which old points were cuts inside a tie."""
    old = json.loads(subprocess.run(["git", "show", f"{ref}:{t['json']}"], cwd=ROOT,
                                    capture_output=True, text=True, check=True).stdout)
    new = result.to_dict()
    conf = sorted((r["confidence"], r["correct"]) for r in result.records
                  if r["confidence"] is not None)[::-1]
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
                for key in ("n", "accuracy", "confidence", "ece", "zero_error_coverage",
                            "total_cost_usd", "p50_latency_s", "p99_latency_s",
                            "reliability_bins")
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
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for t in targets():
        result, judge_name = regenerate(t)
        on_disk = {p: (Path(p).read_text(encoding="utf-8") if Path(p).exists() else None)
                   for p in (t["json"], t["md"]) if p}
        for path, text in plan(t, result, judge_name, on_disk, now).items():
            stale.append(path)
            if not a.check:
                Path(path).write_text(text, encoding="utf-8")
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
