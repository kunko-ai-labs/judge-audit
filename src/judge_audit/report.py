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
OUTSIDE_MARK = "◊"
OUTSIDE_NOTE = ("**◊** the point estimate lies outside its own percentile-bootstrap interval: "
                "on this sample the resampled statistic is biased away from it (a binned "
                "calibration error tends to rise when texts are resampled), so read the "
                "interval as the spread of the number, not as a range around it.")
THREE_NUMBERS_NOTE = (
    "ECE uses ten equal-width bins; the equal-mass ECE cuts the rows into ten groups of "
    "about equal size (tied confidences never split), so it does not hinge on one crowded "
    "bin; Brier is the mean squared gap between confidence and outcome, needs no bins, and "
    "also rewards accuracy. Three separate numbers, never combined. No log-loss: one wrong "
    "answer at a declared confidence of 1.0 makes it infinite, and clipping the confidence "
    "would impute one.")


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
    """`interval(d[key])` with the method stored next to it (`<key>_method`), and `◊`
    when the point estimate lies outside it (`<key>_point_outside`)."""
    out = interval(d.get(key), pct=pct, digits=digits, method=d.get(f"{key}_method"))
    return out + OUTSIDE_MARK if d.get(f"{key}_point_outside") else out


def interval_notes(*texts: str) -> list[str]:
    """The legend lines for the interval marks that actually appear in `texts`."""
    blob = "\n".join(texts)
    return [note for mark, note in ((EXACT_MARK, EXACT_NOTE),
                                    (DEGENERATE_MARK, DEGENERATE_NOTE),
                                    (OUTSIDE_MARK, OUTSIDE_NOTE)) if mark in blob]


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
    served = run.get("served")
    if served:
        versions = ", ".join(
            f"`{v.get('model') or '?'}`"
            + (f" (fingerprint `{v['system_fingerprint']}`)" if v.get("system_fingerprint") else "")
            + f" × {v['decisions']} decisions" for v in served.get("versions", []))
        lines.append(f"_served as reported by the provider: {versions or 'no version reported'}"
                     + (f" · {served['decisions_without_version']} decisions without a version"
                        if served.get("decisions_without_version") else "") + "_")
    if ds.get("path"):
        lines.append(f"_dataset `{ds.get('path')}` · {ds.get('rows')} rows · "
                     f"sha256 `{str(ds.get('sha256', ''))[:12]}…`_")
    return lines


def regeneration_lines(d: dict) -> list[str]:
    """When and by what a committed report was rebuilt — beside the run, never inside it."""
    g = d.get("regenerated")
    if not g:
        return []
    return [f"_regenerated {g.get('utc')} from `{g.get('checkpoint')}` by "
            f"`{g.get('script')}` · judge-audit {g.get('judge_audit_version')}_"]


def ground_truth_source(d: dict) -> dict:
    """The run block, or — when the run predates tier headers — the run block plus the
    tier the regeneration read from the labels file, so an old run is not shown as GT-0."""
    run = d.get("run", {}) or {}
    gt = (d.get("regenerated") or {}).get("ground_truth")
    if gt and not (run.get("dataset") or {}).get("ground_truth"):
        return {**run, "dataset": {**(run.get("dataset") or {}), "ground_truth": gt}}
    return run


def ground_truth_line(run: dict) -> str:
    """`Ground truth: GT-1 constructed — …` from `run.dataset.ground_truth`; GT-0 when absent.

    Never silent: a report without a declared tier says so and how to declare one.
    """
    return ground_truth_of(run).report_line()


def fmt4(value: float | None) -> str:
    """A calibration number to four decimals; '—' when it is unknown (no rows)."""
    return "—" if value is None else f"{value:.4f}"


def fmt_cost(value: float | None, bold: tuple[str, str] = ("**", "**")) -> str:
    """Known spend in dollars, or an explicit unknown when any billable cost is unknown."""
    b0, b1 = bold
    return f"{b0}${value:.4f}{b1}" if value is not None else f"{b0}unknown{b1}"


def slowest(d: dict, bold=("**", "**")) -> str:
    """` · slowest **x s**` when the result carries it (older JSON does not)."""
    if d.get("max_latency_s") is None:
        return ""
    return f" · slowest {bold[0]}{d['max_latency_s']}s{bold[1]}"


def completeness_line(d: dict, bold=("**", "**")) -> str:
    """Expected decisions vs answered ones, for a live run; "" for a checkpoint rebuild.
    Only integers go into it, so it needs no escaping in HTML."""
    c = d.get("completeness")
    if not c:
        return ""
    b0, b1 = bold
    return (f"answered {b0}{int(c['answered'])}/{int(c['expected'])}{b1} expected decisions · "
            f"{int(c['missing'])} skipped (counted wrong, confidence unknown) · "
            f"{int(c['unexpected'])} answers to questions not asked (dropped)")


def confidence_coverage(d: dict) -> dict:
    """Normalise the JSON coverage field, including reports written before it existed."""
    value = d.get("confidence")
    if isinstance(value, dict):
        return {"known": int(value.get("known", 0)), "total": int(value.get("total", d["n"]))}
    return {"known": int(d["n"]), "total": int(d["n"])}


def zero_error_sentence(d: dict, zec_ci: str = "") -> str:
    """Human-readable selective prediction result, including the no-confidence case."""
    zero = d["zero_error_coverage"]
    if zero.get("coverage") is None:
        return "Zero-error coverage is **unknown**: no decisions have known confidence."
    return (f"Zero observed errors through the most confident **{zero['coverage']:.1%}**"
            f"{zec_ci} ({zero['n']} decisions, confidence ≥ {zero['threshold']}).")


def calibration_numbers(d: dict, bold: tuple[str, str] = ("**", "**")) -> str:
    """`ECE (equal-mass) **y** [ci] · Brier **z** [ci] · NLL **w** [ci]` — the numbers
    that need no fixed bins, printed right after the equal-width ECE they qualify. NLL
    appears only in results that carry it (reports rebuilt from older JSON do not)."""
    b0, b1 = bold
    out = (f" · ECE (equal-mass) {b0}{fmt4(d.get('ece_equal_mass'))}{b1}"
           f"{interval_of(d, 'ece_equal_mass_ci')}"
           f" · Brier {b0}{fmt4(d.get('brier'))}{b1}{interval_of(d, 'brier_ci')}")
    if "nll" in d:
        inf = d.get("nll_infinite") or 0
        out += (f" · NLL {b0}∞{b1} ({inf} answer{'s' if inf != 1 else ''} declared certain "
                "and wrong)" if inf else
                f" · NLL {b0}{fmt4(d.get('nll'))}{b1}{interval_of(d, 'nll_ci')}")
    return out


def render_markdown(result: AuditResult) -> str:
    d = result.to_dict()
    acc_ci = interval_of(d, "accuracy_ci", pct=True)
    ece_ci = interval_of(d, "ece_ci")
    zec_ci = interval_of(d, "zero_error_coverage_ci", pct=True)
    confidence = confidence_coverage(d)
    complete = completeness_line(d)
    lines = [
        f"# Audit report — {d['judge']}",
        "",
        f"**n={d['n']}** · accuracy **{d['accuracy']:.1%}**{acc_ci} · "
        f"confidence known **{confidence['known']}/{confidence['total']}** · "
        f"ECE **{fmt4(d.get('ece'))}**{ece_ci}" + calibration_numbers(d),
        f"· cost {fmt_cost(d.get('total_cost_usd'))} · p50 **{d['p50_latency_s']}s** · "
        f"p99 **{d['p99_latency_s']}s**{slowest(d)}",
        *([complete] if complete else []),
        "",
        *provenance_lines(d.get("run", {})),
        *regeneration_lines(d),
        "",
        f"**{ground_truth_line(ground_truth_source(d))}**",
        *ci_lines(d),
        "",
        "## Can I automate this?",
        "",
        zero_error_sentence(d, zec_ci),
        "Retrospective on this dataset — not a production guarantee.",
        "",
        "## Accuracy vs coverage",
        "",
        "| coverage | accuracy | min confidence | n |",
        "|---|---|---|---|",
    ]
    # Every point: the curve already has one per real threshold (at most 20), and
    # sampling it would drop thresholds. One decimal, so 93.5 % is not printed as 94 %.
    for row in d["accuracy_coverage"]:
        lines.append(f"| {row['coverage']:.1%} | {row['accuracy']:.1%} | "
                     f"{row['min_confidence']:.2f} | {row['n']} |")
    lines += ["", "## Calibration (reliability bins)", "",
              "| confidence bin | avg confidence | accuracy | n |",
              "|---|---|---|---|"]
    for b in d["reliability_bins"]:
        if b["n"]:
            lines.append(f"| {b['bin']} | {b['avg_confidence']:.3f} | "
                         f"{b['accuracy']:.1%} | {b['n']} |")
    lines += ["", "_A perfectly honest judge sits on the diagonal: "
                  "avg confidence == accuracy in every bin._",
              "", f"_{THREE_NUMBERS_NOTE}_"]
    return "\n".join(lines) + "\n"


def ci_lines(d: dict) -> list[str]:
    """What the brackets are — and, when one appears, what a † or a ‡ means."""
    b = d.get("bootstrap")
    if not b:
        return []
    marks = "".join(interval_of(d, k) for k in ("accuracy_ci", "ece_ci", "ece_equal_mass_ci",
                                                "brier_ci", "nll_ci",
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
    confidence = confidence_coverage(d)
    zero = d["zero_error_coverage"]
    zero_html = ("Zero-error coverage is <b>unknown</b>: no decisions have known confidence."
                 if zero.get("coverage") is None else
                 f"Zero observed errors through the most confident <b>{zero['coverage']:.1%}</b>"
                 f"{zec_ci} ({zero['n']} decisions, confidence ≥ {zero['threshold']}).")
    ci_note = "".join(f"<p class=\"prov\">{html.escape(line.strip('_'))}</p>"
                      for line in ci_lines(d) if line)
    rel = png_to_data_uri(reliability_diagram_png(result))
    acc = png_to_data_uri(accuracy_coverage_png(result))
    # Everything below is provenance a caller controls — model names, dataset paths, a
    # judge's tag — so it is escaped before it reaches the page, not trusted as markup.
    banner = f'<div class="banner">⚠️ {html.escape(tag)}</div>' if tag else ""
    prov = "<br>".join(html.escape(line.strip("_"))
                       for line in [*provenance_lines(d.get("run", {})),
                                    *regeneration_lines(d)])
    gt = html.escape(ground_truth_line(ground_truth_source(d)))
    judge = html.escape(str(d["judge"]))
    curve_rows = "".join(
        f"<tr><td>{r['coverage']:.1%}</td><td>{r['accuracy']:.1%}</td>"
        f"<td>{r['min_confidence']:.2f}</td><td>{r['n']}</td></tr>"
        for r in d["accuracy_coverage"])
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
<p class="metric"><b>{d['n']}</b> decisions · accuracy <b>{d['accuracy']:.1%}</b>{acc_ci} · confidence known <b>{confidence['known']}/{confidence['total']}</b> · ECE <b>{fmt4(d.get('ece'))}</b>{ece_ci}{calibration_numbers(d, ("<b>", "</b>"))}<br>
cost {fmt_cost(d.get('total_cost_usd'), ("<b>", "</b>"))} · p50 <b>{d['p50_latency_s']}s</b> · p99 <b>{d['p99_latency_s']}s</b>{slowest(d, ("<b>", "</b>"))}</p>
{f'<p class="complete">{completeness_line(d, ("<b>", "</b>"))}</p>' if d.get("completeness") else ""}
<p class="prov">{prov}</p>
<p class="gt"><b>{gt}</b></p>
{ci_note}
<h2>Can I automate this?</h2>
<p>{zero_html}<br>
<em>Retrospective on this dataset — not a production guarantee.</em></p>
<h2>Reliability diagram</h2>
<img src="{rel}" alt="reliability diagram">
<h2>Accuracy vs coverage</h2>
<img src="{acc}" alt="accuracy coverage curve">
<table><tr><th>coverage</th><th>accuracy</th><th>min confidence</th><th>n</th></tr>{curve_rows}</table>
<h2>Calibration bins</h2>
<table><tr><th>bin</th><th>avg confidence</th><th>accuracy</th><th>n</th></tr>{bin_rows}</table>
<p><em>A perfectly honest judge sits on the diagonal: avg confidence == accuracy in every bin.</em></p>
<p class="prov">{html.escape(THREE_NUMBERS_NOTE)}</p>
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

    def versions(run: dict | None) -> set[str]:
        return {f"{v.get('model') or '?'}"
                + (f" (fp {v['system_fingerprint']})" if v.get("system_fingerprint") else "")
                for v in ((run or {}).get("served") or {}).get("versions", [])}

    cur_served, base_served = versions(current.run), versions(base.get("run"))
    if cur_served and base_served and cur_served != base_served:
        warnings.warn(
            f"the provider served a different model version or backend fingerprint than "
            f"in the baseline ({', '.join(sorted(base_served))} → "
            f"{', '.join(sorted(cur_served))}): a drift below may be the provider's, not "
            "the judge configuration's.", UserWarning, stacklevel=2)

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
