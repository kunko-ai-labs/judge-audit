"""The automation certificate: how much of the labelled traffic a judge can decide alone at
a target error rate, the threshold to deploy, and a certified bound (US-003-004, #122;
docs/automation-certificate-plan.md, docs/judges.md § The automation certificate).

For each question and each target risk r:

- **units**: one per distinct text (its lowest confidence; right only when every row of
  that text is right), so a repeated text is not counted as independent evidence. A text
  with any row lacking a confidence is never automated and stays in the denominator.
- **deploy threshold** (`metrics.selective.certify_threshold`): the fixed-sequence exact
  binomial walk on every unit with a confidence. With probability at least 1 − δ, the
  error rate among decisions at or above it is at most r — on traffic drawn like the
  labelled rows, with the labels taken as right.
- **out-of-sample check** (`coverage_at_risk_crossfit`): the threshold chosen on half the
  texts and applied to the other half, both ways, pooled — the honest estimate of the
  share the deployed threshold will automate.

Each target is its own 1 − δ statement; reading several together is not a joint one.
Deterministic, stdlib only.
"""
from __future__ import annotations

import math
from collections.abc import Hashable, Sequence

from .metrics.selective import certify_threshold, coverage_at_risk_crossfit

DEFAULT_TARGETS = (0.01, 0.02, 0.05, 0.10)
DELTA = 0.05
START_ERRORS = 2      # the v0.5 plan's D3: start at the cut that certifies with 2 errors
SEED = 0              # the cross-fit's split; recorded in every certificate


def plain_reading(target_risk: float) -> str:
    """"at most 1 in 20 automated decisions wrong" for 5 %; a percentage when 1/r is not
    a whole number."""
    inverse = 1 / target_risk
    if abs(inverse - round(inverse)) < 1e-9:
        return f"at most 1 in {round(inverse)} automated decisions wrong"
    return f"at most {target_risk * 100:g} % of automated decisions wrong"


def _units(records: list[dict], groups: Sequence[Hashable] | None
           ) -> dict[str, dict[Hashable, tuple[float | None, bool]]]:
    """{question: {text: (lowest confidence or None, every row right)}}, questions and
    texts in first-appearance order."""
    out: dict[str, dict[Hashable, tuple[float | None, bool]]] = {}
    for i, r in enumerate(records):
        key = groups[i] if groups is not None else i
        units = out.setdefault(str(r["question"]), {})
        conf = r.get("confidence")
        conf = None if conf is None else float(conf)
        if key in units:
            c0, ok0 = units[key]
            conf = None if c0 is None or conf is None else min(c0, conf)
            units[key] = (conf, ok0 and bool(r["correct"]))
        else:
            units[key] = (conf, bool(r["correct"]))
    return out


def automation_certificate(records: list[dict], groups: Sequence[Hashable] | None = None,
                           targets: Sequence[float] = DEFAULT_TARGETS, delta: float = DELTA,
                           start_errors: int = START_ERRORS, seed: int = SEED) -> dict:
    """The certificate of one run: per question, per target, the deploy threshold and the
    share it automates, with the out-of-sample check. `records` are the runner's
    ({question, confidence, correct, ...}); `groups` one text key per record (without it
    every row is its own unit). See the module docstring for what is certified."""
    if groups is not None and len(groups) != len(records):
        raise ValueError(f"{len(groups)} group keys for {len(records)} records")
    unit = "text" if groups is not None else "row"
    questions = []
    for question, units in _units(records, groups).items():
        n = len(units)
        scored = [(c, ok) for c, ok in units.values() if c is not None]
        conf = [c for c, _ in scored]
        ok = [o for _, o in scored]
        if any(not math.isfinite(c) for c in conf):
            raise ValueError(f"question {question!r}: a confidence is not finite")
        rows = []
        for r in targets:
            cert = certify_threshold(conf, ok, r, delta, start_errors)
            fit = coverage_at_risk_crossfit(conf, ok, r, delta, seed=seed,
                                            start_errors=start_errors)
            oos = fit["pooled"]
            half = (len(conf) + 1) // 2
            rows.append({
                "target_risk": r, "plain": plain_reading(r),
                "threshold": cert["threshold"], "n": n, "automated": cert["covered"],
                "coverage": round(cert["covered"] / n, 4) if n else 0.0,
                "errors": cert["errors"], "risk_upper": cert["risk_upper"],
                "min_units": cert["min_covered"],
                "reason": (cert["reason"].replace("units", f"{unit}s")
                           if cert["reason"] else None),
                "out_of_sample": {
                    "n": n, "automated": oos["covered"], "errors": oos["errors"],
                    "coverage": round(oos["covered"] / n, 4) if n else 0.0,
                    "risk": oos["risk"],
                    "reason": (f"a half holds at most {half} {unit}s with a confidence; the "
                               f"target needs {cert['min_covered']}"
                               if half < cert["min_covered"] else None)},
            })
        questions.append({"question": question, "n": n, "scored": len(scored),
                          "targets": rows})
    return {"unit": unit, "delta": delta,
            "start_errors": start_errors, "seed": seed, "targets": list(targets),
            "questions": questions}
