"""Markdown audit report + CI drift gate."""
from __future__ import annotations

import json

from .runner import AuditResult


def provenance_lines(run: dict) -> list[str]:
    """Who, what, when — so a reader can tell a real vendor run from a demo."""
    if not run:
        return []
    j = run.get("judge", {})
    ds = run.get("dataset", {})
    parts = [f"judge `{j.get('name', '?')}`"]
    if j.get("model"):
        parts.append(f"model `{j['model']}`")
    if j.get("backend"):
        parts.append(f"backend `{j['backend']}`")
    if j.get("seed") is not None:
        parts.append(f"seed {j['seed']}")
    if run.get("timestamp_utc"):
        parts.append(f"run {run['timestamp_utc']}")
    elif run.get("recomputed_utc"):
        parts.append(f"recomputed {run['recomputed_utc']} (original run time not recorded)")
    if run.get("judge_audit_version"):
        parts.append(f"judge-audit {run['judge_audit_version']}")
    lines = ["_" + " · ".join(parts) + "_"]
    if ds:
        lines.append(f"_dataset `{ds.get('path')}` · {ds.get('rows')} rows · "
                     f"sha256 `{str(ds.get('sha256', ''))[:12]}…`_")
    return lines


def render_markdown(result: AuditResult) -> str:
    d = result.to_dict()
    lines = [
        f"# Audit report — {d['judge']}",
        "",
        f"**n={d['n']}** · accuracy **{d['accuracy']:.1%}** · ECE **{d['ece']:.4f}**",
        f"· cost **${d['total_cost_usd']:.4f}** · p50 **{d['p50_latency_s']}s** · p99 **{d['p99_latency_s']}s**",
        "",
        *provenance_lines(d.get("run", {})),
        "",
        "## Can I automate this?",
        "",
        f"Zero observed errors through the most confident **{d['zero_error_coverage']['coverage']:.1%}** "
        f"({d['zero_error_coverage']['n']} decisions, confidence ≥ {d['zero_error_coverage']['threshold']}).",
        "Retrospective on this dataset — not a production guarantee.",
        "",
        "## Accuracy vs coverage",
        "",
        "| coverage | accuracy | min confidence | n |",
        "|---|---|---|---|",
    ]
    for row in d["accuracy_coverage"][::4]:  # every 5%
        lines.append(f"| {row['coverage']:.0%} | {row['accuracy']:.1%} | "
                     f"{row['min_confidence']:.2f} | {row['n']} |")
    lines += ["", "## Calibration (reliability bins)", "",
              "| confidence bin | avg confidence | accuracy | n |",
              "|---|---|---|---|"]
    for b in d["reliability_bins"]:
        if b["n"]:
            lines.append(f"| {b['bin']} | {b['avg_confidence']:.3f} | "
                         f"{b['accuracy']:.1%} | {b['n']} |")
    lines += ["", "_A perfectly honest judge sits on the diagonal: "
                  "avg confidence == accuracy in every bin._"]
    return "\n".join(lines) + "\n"


def render_html(result: AuditResult, tag: str = "") -> str:
    """Self-contained HTML report with base64-embedded charts. No network needed."""
    from .charts import accuracy_coverage_png, png_to_data_uri, reliability_diagram_png
    d = result.to_dict()
    rel = png_to_data_uri(reliability_diagram_png(result))
    acc = png_to_data_uri(accuracy_coverage_png(result))
    banner = f'<div class="banner">⚠️ {tag}</div>' if tag else ""
    prov = "<br>".join(line.strip("_") for line in provenance_lines(d.get("run", {})))
    curve_rows = "".join(
        f"<tr><td>{r['coverage']:.0%}</td><td>{r['accuracy']:.1%}</td>"
        f"<td>{r['min_confidence']:.2f}</td><td>{r['n']}</td></tr>"
        for r in d["accuracy_coverage"][::2])
    bin_rows = "".join(
        f"<tr><td>{b['bin']}</td><td>{b['avg_confidence']:.3f}</td>"
        f"<td>{b['accuracy']:.1%}</td><td>{b['n']}</td></tr>"
        for b in d["reliability_bins"] if b["n"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Audit report — {d['judge']}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
.banner{{background:#fff3cd;border:1px solid #e6a800;padding:.75rem;border-radius:8px;font-weight:600}}
.metric{{font-size:1.1rem}}.metric b{{font-size:1.6rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}td,th{{border:1px solid #ddd;padding:.4rem .6rem;text-align:right}}
th{{background:#f5f5f5}}img{{max-width:100%;border:1px solid #eee;border-radius:8px;margin:1rem 0}}
h2{{margin-top:2.5rem}}.prov{{color:#666;font-size:.9rem}}</style></head><body>
{banner}
<h1>Audit report — {d['judge']}</h1>
<p class="metric"><b>{d['n']}</b> decisions · accuracy <b>{d['accuracy']:.1%}</b> · ECE <b>{d['ece']:.4f}</b><br>
cost <b>${d['total_cost_usd']:.4f}</b> · p50 <b>{d['p50_latency_s']}s</b> · p99 <b>{d['p99_latency_s']}s</b></p>
<p class="prov">{prov}</p>
<h2>Can I automate this?</h2>
<p>Zero observed errors through the most confident <b>{d['zero_error_coverage']['coverage']:.1%}</b>
({d['zero_error_coverage']['n']} decisions, confidence ≥ {d['zero_error_coverage']['threshold']}).<br>
<em>Retrospective on this dataset — not a production guarantee.</em></p>
<h2>Reliability diagram</h2>
<img src="{rel}" alt="reliability diagram">
<h2>Accuracy vs coverage</h2>
<img src="{acc}" alt="accuracy coverage curve">
<table><tr><th>coverage</th><th>accuracy</th><th>min confidence</th><th>n</th></tr>{curve_rows}</table>
<h2>Calibration bins</h2>
<table><tr><th>bin</th><th>avg confidence</th><th>accuracy</th><th>n</th></tr>{bin_rows}</table>
<p><em>A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin.</em></p>
</body></html>
"""


def check_drift(current: AuditResult, baseline_path: str,
                max_ece_drift: float = 0.02, max_acc_drop: float = 0.01) -> list[str]:
    """CI gate: fail the build when the judge degrades vs baseline."""
    with open(baseline_path, encoding="utf-8") as f:
        base = json.load(f)
    failures = []
    ece_drift = current.ece - base.get("ece", current.ece)
    if ece_drift > max_ece_drift:
        failures.append(f"ECE drifted +{ece_drift:.4f} (>{max_ece_drift}): "
                        "the judge is less honest than baseline.")
    acc_drop = base.get("accuracy", current.accuracy) - current.accuracy
    if acc_drop > max_acc_drop:
        failures.append(f"Accuracy dropped {acc_drop:.2%} (>{max_acc_drop:.0%}).")
    return failures
