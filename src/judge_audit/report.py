"""Markdown audit report + CI drift gate."""
from __future__ import annotations

import html
import json
import math
import warnings
from fractions import Fraction

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


def _pct_of(x: float) -> str:
    return f"{x * 100:g}%"


def inline(value: object) -> str:
    """A name from the data or the command line, made safe to print inside a Markdown line
    or a code span: every run of whitespace (newlines included) becomes one space, so a
    value can never open a heading, a list item or a table row, and a backtick becomes an
    apostrophe so it cannot close the code span it sits in."""
    return " ".join(str(value).split()).replace("`", "'")


def threshold_text(t: float) -> str:
    """A deploy threshold as it can be applied: the exact value when it is short, else
    rounded **up** to six significant digits and marked `↑` (deploying at the printed value
    then automates no decision the bound did not cover; the exact value is in the JSON)."""
    import decimal

    exact = repr(float(t))
    if len(exact) <= 8:
        return exact
    d = decimal.Decimal(exact)
    q = decimal.Decimal(1).scaleb(d.adjusted() - 5)            # six significant digits
    up = d.quantize(q, rounding=decimal.ROUND_CEILING)
    return f"{up.normalize():f}↑"


def certificate_cells(t: dict, unit: str) -> tuple[str, str, str]:
    """(safe automation rate, deploy threshold, out-of-sample) for one target."""
    if t["threshold"] is None:
        return f"none: {t.get('reason') or 'no threshold passes'}", "—", "—"
    bound = f", error bound {t['risk_upper']:.1%}" if t.get("risk_upper") is not None else ""
    rate = (f"{t['coverage']:.1%} ({t['automated']:,} of {t['n']:,} {unit}s; "
            f"{t['errors']} wrong{bound})")
    o = t["out_of_sample"]
    if o.get("reason") and not o["automated"]:
        return rate, threshold_text(t["threshold"]), f"not checkable: {o['reason']}"
    lo, hi = o.get("spread_coverage") or (None, None)
    spread = (f" (seeds {o['spread_seeds'][0]}–{o['spread_seeds'][1]}: {lo:.1%}–{hi:.1%})"
              if lo is not None and o.get("spread_seeds") else "")
    oos = (f"{o['coverage']:.1%} automated"
           + (f", {o['risk']:.1%} wrong" if o.get("risk") is not None else "") + spread)
    return rate, threshold_text(t["threshold"]), oos


def certificate_headline(t: dict, unit: str) -> str:
    """The primary target in one sentence (markdown bold on the number)."""
    head = f"Safe automation rate at ≤ {_pct_of(t['target_risk'])} error"
    if t["threshold"] is None:
        return f"**{head}: none** — {t.get('reason') or 'no threshold passes'}."
    rate, thr, oos = certificate_cells(t, unit)
    return (f"**{head}: {t['coverage']:.1%}** of the labelled {unit}s "
            f"({t['automated']:,} of {t['n']:,}; {t['errors']} wrong, error bound "
            f"{t['risk_upper']:.1%}), deploying at confidence ≥ {thr}. Checked out of "
            f"sample, with the threshold chosen on half the data: {oos}.")


def per_text_line(t: dict, q: dict) -> str:
    """When the labelled set repeats texts: the rate counting each text once."""
    p = t.get("per_text")
    if not p:
        return ""
    head = (f"This labelled set repeats texts ({q['n']:,} decisions, {q['texts']:,} distinct "
            "texts). The bound above treats the decisions as a random sample of your "
            "traffic, repeats included as they occur there. If the repeats were copied in "
            "instead, count each text once (at its highest confidence, wrong if any copy is: "
            "not always the more cautious reading when the copies of a text carry different "
            "confidences)")
    if p["threshold"] is None:
        return f"{head}: at this target, none ({p.get('reason') or 'no threshold passes'})."
    return (f"{head}: {p['coverage']:.1%} of the texts ({p['automated']:,} of {p['n']:,}; "
            f"{p['errors']} counted wrong, error bound {p['risk_upper']:.1%}), at confidence "
            f"≥ {threshold_text(p['threshold'])}.")


def worst_segment_line(t: dict, c: dict) -> str:
    """The worst segment above the primary threshold, or why none is ranked."""
    if t["threshold"] is None or not t.get("segments"):
        return ""
    by = "true label" if c.get("segment_by") == "label" else f"`{inline(c.get('segment_by'))}`"
    small = t.get("segments_too_small", 0)
    tail = (f" {small} segment{'s' if small != 1 else ''} with fewer than "
            f"{c['min_segment']} automated {c['unit']}s {'are' if small != 1 else 'is'} not "
            "ranked." if small else "")
    hidden = t.get("errors_in_small_segments", 0)
    if hidden:
        tail += (f" {hidden} of the {t['errors']} errors above the threshold sit in segments "
                 "too small to rank.")
    w = t.get("worst_segment")
    if w is None:
        return (f"Segments ({by}): none has {c['min_segment']} automated {c['unit']}s, so "
                f"none is ranked.{tail}")
    return (f"Worst segment above that threshold ({by}): `{inline(w['segment'])}`, {w['errors']} of "
            f"{w['automated']} automated {c['unit']}s wrong ({w['rate']:.1%}; its own error "
            f"bound {w['risk_upper']:.1%}). The overall bound does not cover a segment.{tail}")


def scope_line(c: dict) -> str:
    """What the rate is valid for, and when to review it."""
    s = c.get("scope") or {}
    parts = [f"judge `{inline(s['judge'])}`" if s.get("judge") else None,
             f"model `{inline(s['model'])}`" if s.get("model") else None,
             f"revision `{inline(str(s['revision'])[:12])}`" if s.get("revision") else None,
             (f"prompt `{inline(str(s['prompt_sha256'])[:8])}…`"
              if s.get("prompt_sha256") else None),
             f"served `{inline(', '.join(s['served']))}`" if s.get("served") else None,
             f"data `{inline(s['dataset'])}`" if s.get("dataset") else None,
             (f"sha256 `{inline(str(s['dataset_sha256'])[:12])}…`"
              if s.get("dataset_sha256") else None),
             f"measured {inline(s['measured_utc'])}" if s.get("measured_utc") else None]
    what = " · ".join(p for p in parts if p) or "this run"
    review = (f"Review by {inline(s['review_by'])}, and measure again as soon as any of these "
              "changes." if s.get("review_by") else
              "Measure again as soon as any of these changes.")
    return f"Valid only for: {what}. {review}"


def certificate_note(c: dict, regenerated: bool = False) -> str:
    level = 1 - c["delta"]
    k = len(c.get("targets") or [])
    joint = (f"; the {k} rows hold together with probability at least "
             f"{max(0.0, 1 - k * c['delta']):.0%}" if k > 1 else "")
    regen = (" (this report was regenerated from an archived checkpoint with the "
             "default target: the target was not fixed in advance)"
             if regenerated or (c.get("scope") or {}).get("regenerated") else "")
    return (f"With {level:.0%} confidence, the error rate among decisions at or above the "
            "threshold is at most the target — on traffic drawn like these labelled "
            "decisions (a random sample of it, each decision an independent draw), judged by "
            "the judge and prompt above, with the labels taken as right. Label errors cut "
            "both ways: a wrong label the judge disagrees with counts as a judge error, one "
            "it agrees with hides an error. The primary target is the one passed with "
            f"`--target` (here {_pct_of(c['primary_target'])}), to be chosen before the run"
            f"{regen}; every row is its own "
            f"{level:.0%} statement{joint}; keeping the best-looking row after reading them is "
            "neither. The rate is the share of the labelled decisions the threshold covers; "
            "the out-of-sample check chooses the threshold on half of them (split by distinct "
            f"text, seed {c['seed']}, spread over other seeds in brackets) and applies it to "
            "the other half, a conservative check rather than a forecast. A decision without "
            "a confidence is never automated. Exact one-sided binomial bound, fixed-sequence "
            "walk from the most confident down, starting at the cut that bounds the error "
            f"with {c['start_errors']} errors (docs/judges.md § The safe automation rate). "
            f"{c.get('disclaimer', '')}").rstrip()


def _primary(q: dict) -> dict:
    return next((t for t in q["targets"] if t.get("primary")), q["targets"][0])


def certificate_lines(d: dict) -> list[str]:
    """The "Can I automate this?" section; [] for a result without a certificate (JSON
    written before it existed)."""
    c = d.get("certificate")
    if not c or not c.get("questions"):
        return []
    lines: list[str] = []
    several = len(c["questions"]) > 1
    for q in c["questions"]:
        if several:
            lines += [f"### `{inline(q['question'])}`", ""]
        p = _primary(q)
        lines += [certificate_headline(p, c["unit"]), ""]
        for extra in (per_text_line(p, q), worst_segment_line(p, c)):
            if extra:
                lines += [extra, ""]
        lines += ["| at most this error | in plain words | safe automation rate | "
                  "deploy at confidence ≥ | checked out of sample |",
                  "|---|---|---|---|---|"]
        for t in q["targets"]:
            rate, thr, oos = certificate_cells(t, c["unit"])
            mark = " (primary)" if t.get("primary") else ""
            lines.append(f"| {_pct_of(t['target_risk'])}{mark} | {t['plain']} | {rate} | "
                         f"{thr} | {oos} |")
        lines.append("")
    lines += [f"_{scope_line(c)}_", "",
              f"_{certificate_note(c, bool(d.get('regenerated')))}_"]
    return lines


def certificate_html(d: dict) -> str:
    """`certificate_lines` as HTML, every value escaped."""
    c = d.get("certificate")
    if not c or not c.get("questions"):
        return ""

    def text(s: str) -> str:            # our markdown → escaped HTML (bold and code only)
        out = html.escape(s)
        while out.count("**") >= 2:
            out = out.replace("**", "<b>", 1).replace("**", "</b>", 1)
        while out.count("`") >= 2:
            out = out.replace("`", "<code>", 1).replace("`", "</code>", 1)
        return out

    out = []
    for q in c["questions"]:
        if len(c["questions"]) > 1:
            out.append(f"<h3><code>{html.escape(str(q['question']))}</code></h3>")
        p = _primary(q)
        out.append(f"<p>{text(certificate_headline(p, c['unit']))}</p>")
        for extra in (per_text_line(p, q), worst_segment_line(p, c)):
            if extra:
                out.append(f"<p>{text(extra)}</p>")
        rows = "".join(
            "<tr>" + "".join(f"<td>{html.escape(x)}</td>" for x in (
                _pct_of(t["target_risk"]) + (" (primary)" if t.get("primary") else ""),
                t["plain"], *certificate_cells(t, c["unit"]))) + "</tr>"
            for t in q["targets"])
        out.append("<table><tr><th>at most this error</th><th>in plain words</th>"
                   "<th>safe automation rate</th><th>deploy at confidence ≥</th>"
                   f"<th>checked out of sample</th></tr>{rows}</table>")
    out.append(f'<p class="prov">{text(scope_line(c))}</p>')
    out.append(f'<p class="prov">{text(certificate_note(c, bool(d.get("regenerated"))))}</p>')
    return "\n".join(out)


def certificate_summary(d: dict) -> str:
    """`safe_automation@5%=41.0%` for the CLI line: the primary target, per question when
    several."""
    c = d.get("certificate")
    if not c or not c.get("questions"):
        return ""
    parts = []
    for q in c["questions"]:
        p = _primary(q)
        name = f"[{q['question']}]" if len(c["questions"]) > 1 else ""
        rate = "none" if p["threshold"] is None else f"{p['coverage']:.1%}"
        parts.append(f"safe_automation{name}@{_pct_of(p['target_risk'])}={rate}")
    return " ".join(parts)


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
        *certificate_lines(d),
        *([""] if d.get("certificate") else []),
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
{certificate_html(d)}
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


def parse_min_safe_rate(spec: str) -> tuple[float, float]:
    """`0.05:0.40` → (0.05, 0.40): at an error of at most 5 %, the safe automation rate
    must be at least 40 %. Raises ValueError on anything else."""
    risk_s, sep, share_s = spec.partition(":")
    try:
        risk, share = float(risk_s), float(share_s)
    except ValueError:
        raise ValueError(f"--min-safe-rate expects RISK:SHARE such as 0.05:0.40, "
                         f"got {spec!r}") from None
    if not sep or not (0 < risk < 1 and math.isfinite(risk)) or not 0 <= share <= 1:
        raise ValueError(f"--min-safe-rate expects 0 < RISK < 1 and 0 <= SHARE <= 1, "
                         f"got {spec!r}")
    return risk, share


def check_safe_rate(certificate: dict, minimums: list[tuple[float, float]]) -> list[str]:
    """The gate: one failure per question and minimum whose safe automation rate at that
    risk is below the minimum. Every risk must be in the certificate."""
    failures = []
    for risk, share in minimums:
        for q in certificate.get("questions", []):
            t = next((t for t in q["targets"] if math.isclose(t["target_risk"], risk)), None)
            if t is None:
                raise ValueError(f"the certificate has no target {risk:g}")
            if not t["n"]:
                have = Fraction(0)
            else:
                have = Fraction(t["automated"], t["n"])     # exact, never the rounded JSON
            if have < Fraction(str(share)):
                why = f" ({t['reason']})" if t.get("reason") else ""
                digits = next((d for d in range(1, 7)
                               if f"{float(have):.{d}%}" != f"{share:.{d}%}"), 6)
                failures.append(
                    f"Safe automation rate at ≤ {_pct_of(risk)} error: "
                    f"{float(have):.{digits}%} of `{inline(q['question'])}` decisions (minimum "
                    f"{share:.{digits}%}){why}.")
    return failures


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
