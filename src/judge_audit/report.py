"""Markdown audit report + CI drift gate."""
from __future__ import annotations

import html
import json
import math
import warnings

from .ground_truth import ground_truth_of
from .metrics.calibration import EXACT as EXACT_METHOD
from .runner import AuditResult

EXACT_MARK = "†"
DEGENERATE_MARK = "‡"
EXACT_NOTE = ("**†** exact 95 % Clopper–Pearson (binomial) interval, published where the "
              "estimate is 0 % or 100 % and the bootstrap collapses to a point. It assumes "
              "independent rows, so where the dataset repeats texts it is a *lower bound* "
              "on the width the clustered interval would have had.")
DEGENERATE_NOTE = ("**‡** degenerate: every clustered-bootstrap resample returned the same "
                   "value, so no interval width is published for that number.")


def interval(ci, pct: bool = False, digits: int = 4, method: str | None = None) -> str:
    """` [52.5, 80.3]` for a (lo, hi) pair — the compact form every report uses next to
    its point estimate; '' when the interval was not computed.

    `method` (or `ci.method`) says which machinery produced it: an exact Clopper–Pearson
    interval is marked `†`, and a bootstrap that came back with zero width is marked `‡`
    instead of printing `[x, x]`. `interval_notes` turns the marks into a legend.
    """
    method = method or getattr(ci, "method", None)
    if ci is None:
        # A degenerate interval is published as no interval plus its method.
        return f" {DEGENERATE_MARK}" if (method or "").startswith("degenerate-") else ""
    lo, hi = ci
    if lo == hi:
        return f" {DEGENERATE_MARK}"
    mark = EXACT_MARK if method == EXACT_METHOD else ""
    if pct:
        return f" [{lo * 100:.1f}, {hi * 100:.1f}]{mark}"
    return f" [{lo:.{digits}f}, {hi:.{digits}f}]{mark}"


def interval_of(d: dict, key: str, pct: bool = False, digits: int = 4) -> str:
    """`interval(d[key])` with the method stored next to it (`<key>_method`)."""
    return interval(d.get(key), pct=pct, digits=digits, method=d.get(f"{key}_method"))


def interval_notes(*texts: str) -> list[str]:
    """The legend lines for the interval marks that actually appear in `texts`."""
    blob = "\n".join(texts)
    return [note for mark, note in ((EXACT_MARK, EXACT_NOTE),
                                    (DEGENERATE_MARK, DEGENERATE_NOTE)) if mark in blob]


def with_interval_notes(lines: list[str]) -> list[str]:
    """The rendered lines plus the legend of the interval marks they actually use.

    The note goes right after the bullet that explains the brackets, so a reader who
    meets a `†` in a table finds what it means in the same list."""
    notes = interval_notes(*lines)
    if not notes:
        return lines
    out = list(lines)
    where = next((i for i, ln in enumerate(out) if ln.startswith("- **[a, b]**")),
                 len(out) - 1)
    for k, note in enumerate(notes):
        out.insert(where + 1 + k, f"- {note}")
    return out


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
    if ds.get("path"):
        lines.append(f"_dataset `{ds.get('path')}` · {ds.get('rows')} rows · "
                     f"sha256 `{str(ds.get('sha256', ''))[:12]}…`_")
    return lines


def ground_truth_line(run: dict) -> str:
    """`Ground truth: GT-1 constructed — …` from `run.dataset.ground_truth`; GT-0 when absent.

    Never silent: a report without a declared tier says so and how to declare one.
    """
    return ground_truth_of(run).report_line()


def render_markdown(result: AuditResult) -> str:
    d = result.to_dict()
    acc_ci = interval_of(d, "accuracy_ci", pct=True)
    ece_ci = interval_of(d, "ece_ci")
    zec_ci = interval_of(d, "zero_error_coverage_ci", pct=True)
    lines = [
        f"# Audit report — {d['judge']}",
        "",
        f"**n={d['n']}** · accuracy **{d['accuracy']:.1%}**{acc_ci} · ECE **{d['ece']:.4f}**{ece_ci}",
        f"· cost **${d['total_cost_usd']:.4f}** · p50 **{d['p50_latency_s']}s** · p99 **{d['p99_latency_s']}s**",
        "",
        *provenance_lines(d.get("run", {})),
        "",
        f"**{ground_truth_line(d.get('run', {}))}**",
        *ci_lines(d),
        "",
        "## Can I automate this?",
        "",
        f"Zero observed errors through the most confident **{d['zero_error_coverage']['coverage']:.1%}**"
        f"{zec_ci} ({d['zero_error_coverage']['n']} decisions, "
        f"confidence ≥ {d['zero_error_coverage']['threshold']}).",
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


def ci_lines(d: dict) -> list[str]:
    """What the brackets are — and, when one appears, what a † or a ‡ means."""
    b = d.get("bootstrap")
    if not b:
        return []
    marks = "".join(interval_of(d, k) for k in ("accuracy_ci", "ece_ci",
                                                "zero_error_coverage_ci"))
    return ["", f"_Brackets are {b['level']:.0%} percentile-bootstrap intervals over the dataset's "
                f"distinct texts ({b['n_boot']:,} resamples, seed {b['seed']}): how far the number "
                f"would move on another sample of n={d['n']} drawn the same way._",
            *[f"_{note}_" for note in interval_notes(marks)]]


def render_html(result: AuditResult, tag: str = "") -> str:
    """Self-contained HTML report with base64-embedded charts. No network needed."""
    from .charts import accuracy_coverage_png, png_to_data_uri, reliability_diagram_png
    d = result.to_dict()
    acc_ci = interval_of(d, "accuracy_ci", pct=True)
    ece_ci = interval_of(d, "ece_ci")
    zec_ci = interval_of(d, "zero_error_coverage_ci", pct=True)
    ci_note = "".join(f"<p class=\"prov\">{html.escape(line.strip('_'))}</p>"
                      for line in ci_lines(d) if line)
    rel = png_to_data_uri(reliability_diagram_png(result))
    acc = png_to_data_uri(accuracy_coverage_png(result))
    # Everything below is provenance a caller controls — model names, dataset paths, a
    # judge's tag — so it is escaped before it reaches the page, not trusted as markup.
    banner = f'<div class="banner">⚠️ {html.escape(tag)}</div>' if tag else ""
    prov = "<br>".join(html.escape(line.strip("_"))
                       for line in provenance_lines(d.get("run", {})))
    gt = html.escape(ground_truth_line(d.get("run", {})))
    judge = html.escape(str(d["judge"]))
    curve_rows = "".join(
        f"<tr><td>{r['coverage']:.0%}</td><td>{r['accuracy']:.1%}</td>"
        f"<td>{r['min_confidence']:.2f}</td><td>{r['n']}</td></tr>"
        for r in d["accuracy_coverage"][::2])
    bin_rows = "".join(
        f"<tr><td>{b['bin']}</td><td>{b['avg_confidence']:.3f}</td>"
        f"<td>{b['accuracy']:.1%}</td><td>{b['n']}</td></tr>"
        for b in d["reliability_bins"] if b["n"])
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Audit report — {judge}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}}
.banner{{background:#fff3cd;border:1px solid #e6a800;padding:.75rem;border-radius:8px;font-weight:600}}
.metric{{font-size:1.1rem}}.metric b{{font-size:1.6rem}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}td,th{{border:1px solid #ddd;padding:.4rem .6rem;text-align:right}}
th{{background:#f5f5f5}}img{{max-width:100%;border:1px solid #eee;border-radius:8px;margin:1rem 0}}
h2{{margin-top:2.5rem}}.prov{{color:#666;font-size:.9rem}}</style></head><body>
{banner}
<h1>Audit report — {judge}</h1>
<p class="metric"><b>{d['n']}</b> decisions · accuracy <b>{d['accuracy']:.1%}</b>{acc_ci} · ECE <b>{d['ece']:.4f}</b>{ece_ci}<br>
cost <b>${d['total_cost_usd']:.4f}</b> · p50 <b>{d['p50_latency_s']}s</b> · p99 <b>{d['p99_latency_s']}s</b></p>
<p class="prov">{prov}</p>
<p class="gt"><b>{gt}</b></p>
{ci_note}
<h2>Can I automate this?</h2>
<p>Zero observed errors through the most confident <b>{d['zero_error_coverage']['coverage']:.1%}</b>{zec_ci}
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


class IncompatibleBaseline(ValueError):
    """The baseline measured something else: other dataset, other judge, other n."""


def _comparable(current: dict, base: dict) -> list[str]:
    """What makes the two runs different measurements rather than two measurements.

    Only fields both sides declare are compared: a baseline that records nothing (a
    hand-written threshold file) has nothing to disagree about, and the gate still gates.
    """
    cj, bj = current.get("judge", {}), base.get("judge", {})
    cd, bd = current.get("dataset", {}), base.get("dataset", {})
    pairs = [
        ("judge name", cj.get("name"), bj.get("name")),
        ("judge model", cj.get("model"), bj.get("model")),
    ]
    out = [f"{what}: {b!r} in the baseline, {c!r} now"
           for what, c, b in pairs if c is not None and b is not None and c != b]
    # The dataset matches when any recorded digest matches any other: a run made before
    # the ground-truth header line recorded the whole file, which is today's rows digest.
    cur = {cd.get("sha256"), cd.get("sha256_rows")} - {None}
    old = {bd.get("sha256"), bd.get("sha256_rows")} - {None}
    if cur and old and not (cur & old):
        out.append(f"dataset sha256: {sorted(old)[0]!r} in the baseline, {sorted(cur)[0]!r} now")
    return out


def _finite(value: object, what: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise KeyError(f"{what} is not numeric (is it an audit-result.json?)")
    if not math.isfinite(value):
        raise ValueError(f"{what} is not finite ({value!r}); refusing to compare")
    return float(value)


def check_drift(current: AuditResult, baseline_path: str,
                max_ece_drift: float = 0.02, max_acc_drop: float = 0.01,
                allow_incompatible: bool = False) -> list[str]:
    """CI gate: fail the build when the judge degrades vs baseline.

    Refuses (`IncompatibleBaseline`) when the two runs are not the same measurement —
    other dataset, other judge or model, other n — because an ECE that moved between
    two different datasets says nothing about the judge. `allow_incompatible` compares
    anyway, for the deliberate case (a new dataset version, a renamed model).
    """
    with open(baseline_path, encoding="utf-8") as f:
        base = json.load(f)
    base_ece = _finite(base.get("ece"), "baseline 'ece'")
    base_acc = _finite(base.get("accuracy"), "baseline 'accuracy'")
    _finite(current.ece, "current 'ece'")
    _finite(current.accuracy, "current 'accuracy'")

    mismatches = _comparable(current.run or {}, base.get("run") or {})
    if isinstance(base.get("n"), int) and base["n"] != current.n:
        mismatches.append(f"n: {base['n']} in the baseline, {current.n} now")
    if mismatches and not allow_incompatible:
        raise IncompatibleBaseline(
            "the baseline is not the same measurement — " + "; ".join(mismatches) +
            ". Compare like with like, or pass --allow-incompatible to compare anyway.")

    cur_prompt = (current.run or {}).get("judge", {}).get("prompt_sha256")
    base_prompt = (base.get("run") or {}).get("judge", {}).get("prompt_sha256")
    if cur_prompt and base_prompt and cur_prompt != base_prompt:
        warnings.warn(
            f"the judge's prompt changed since the baseline (prompt_sha256 "
            f"{base_prompt[:12]}… → {cur_prompt[:12]}…): the numbers below compare two "
            "different questions.", UserWarning, stacklevel=2)

    base = {**base, "ece": base_ece, "accuracy": base_acc}
    failures = []
    ece_drift = current.ece - base["ece"]
    if ece_drift > max_ece_drift:
        failures.append(f"ECE drifted +{ece_drift:.4f} (>{max_ece_drift}): "
                        "the judge is less honest than baseline.")
    acc_drop = base["accuracy"] - current.accuracy
    if acc_drop > max_acc_drop:
        failures.append(f"Accuracy dropped {acc_drop:.2%} (>{max_acc_drop:.0%}).")
    return failures
