"""The safe automation rate: how many of a judge's decisions it can take alone at a target
error rate, the threshold to deploy, and a bound on its error (US-003-004, #122;
docs/automation-certificate-plan.md, docs/judges.md § The safe automation rate). Internally,
and in the result JSON, it is the run's `certificate`.

For each question and each target risk r:

- **units are decisions**: every labelled decision with a confidence is one unit; a
  decision without one is never automated and stays in the denominator. The bound treats
  the labelled decisions as independent draws from the traffic: a random sample of it,
  where a text that recurs in the traffic recurs in the sample as often, and no copy was
  added by hand.
- **deploy threshold** (`metrics.selective.certify_threshold`): the fixed-sequence exact
  binomial walk on every unit. With probability at least 1 − δ, the error rate among
  decisions at or above it is at most r — on traffic drawn like the labelled decisions,
  judged by the same judge and prompt (`scope`), with the labels taken as right.
- **out-of-sample check**: the same walk on half the decisions and its threshold applied
  to the other half, both ways, pooled; the halves are split by distinct text
  (`split_by_group`: every copy of a text on one side, independent of row order), at seed
  0 and over seeds 0–9 for its spread. A threshold chosen on half the data usually
  automates less than the deployed one: a conservative check, not a forecast.
- **per-text check**, only when the labelled set repeats texts: each distinct text once,
  automated when any copy is at or above the threshold and wrong when any copy is wrong
  (conservative), certified the same way. It is the number to read if the repeats were
  copied in rather than sampled.
- **segments**: the deployed threshold applied to each segment (by default the true
  label; or a metadata field), with each segment's observed error and its own exact
  one-sided bound. The overall bound does not cover a segment; the worst segment with
  enough automated decisions is named so an average cannot hide it.
- **primary target**: the one target chosen before the run (`--target`, default 5 %).
  Each target is its own 1 − δ statement; the four default ones hold together with
  probability at least 1 − 4δ (80 %). Reading several and keeping the best is neither.

Statistical evidence, not a conformity assessment or a certification by a notified body.
Deterministic, stdlib only.
"""
from __future__ import annotations

import datetime as _dt
import math
from collections.abc import Hashable, Sequence
from typing import Any

from .metrics.selective import certify_threshold, risk_upper_bound, split_by_group

NAME = "safe automation rate"
DEFAULT_TARGETS = (0.01, 0.02, 0.05, 0.10)
PRIMARY_TARGET = 0.05
DELTA = 0.05
START_ERRORS = 2      # the v0.5 plan's D3: start at the cut that bounds with 2 errors
SEED = 0              # the out-of-sample split shown; recorded in every certificate
SPREAD_SEEDS = tuple(range(10))
REVIEW_DAYS = 90      # a rate measured on a date is reviewed by this many days later
MIN_SEGMENT = 30      # automated decisions a segment needs before it is ranked
DISCLAIMER = ("Statistical evidence on the labelled decisions, not a conformity assessment or "
              "a certification by a notified body.")


def _up(x: float | None) -> float | None:
    """A published bound, rounded **up** to 6 decimals: the walk decides on the exact value,
    but the last bits of the beta quantile differ between Python versions, and a committed
    report must regenerate byte-identical on every supported one."""
    return None if x is None else math.ceil(x * 1e6 - 1e-9) / 1e6


def plain_reading(target_risk: float) -> str:
    """"at most 1 in 20 automated decisions wrong" for 5 %; a percentage when 1/r is not
    a whole number."""
    inverse = 1 / target_risk
    if abs(inverse - round(inverse)) < 1e-9:
        return f"at most 1 in {round(inverse)} automated decisions wrong"
    return f"at most {target_risk * 100:g} % of automated decisions wrong"


def scope_of(run: dict | None) -> dict:
    """What the rate is valid for: the judge, model, revision, prompt and served versions,
    the labelled data, and when it was measured (with the date to review it by). A change
    in any of them means the rate no longer applies and must be measured again."""
    run = run or {}
    j, ds = run.get("judge") or {}, run.get("dataset") or {}
    measured = run.get("timestamp_utc") or run.get("recomputed_utc")
    review = None
    if measured:
        try:
            when = _dt.datetime.fromisoformat(str(measured).replace("Z", "+00:00"))
            review = (when + _dt.timedelta(days=REVIEW_DAYS)).date().isoformat()
        except ValueError:
            review = None
    served = sorted({f"{v.get('model') or '?'}"
                     + (f" ({v['system_fingerprint']})" if v.get("system_fingerprint") else "")
                     for v in ((run.get("served") or {}).get("versions") or [])})
    return {"judge": j.get("name"), "model": j.get("model_id") or j.get("model"),
            "revision": j.get("loaded_revision") or j.get("revision"),
            "prompt_sha256": j.get("prompt_sha256"), "served": served or None,
            "dataset": ds.get("path"),
            "dataset_sha256": ds.get("sha256_rows") or ds.get("sha256"),
            "measured_utc": measured, "review_by": review}


def scope_changes(old: dict, new: dict) -> list[str]:
    """The scope fields both declare that differ: why an old rate no longer applies."""
    return [f"{k}: {old[k]!r} → {new[k]!r}" for k in
            ("judge", "model", "revision", "prompt_sha256", "served", "dataset_sha256")
            if old.get(k) is not None and new.get(k) is not None and old[k] != new[k]]


def _out_of_sample(conf: list[float], ok: list[bool], keys: list[Hashable], r: float,
                   delta: float, start_errors: int, seed: int) -> tuple[int, int]:
    """(automated, wrong) on the test halves: the walk on one half (split by text), its
    threshold applied to the other, both ways."""
    a, b = split_by_group(keys, seed)
    covered = errors = 0
    for cal, test in ((a, b), (b, a)):
        t = certify_threshold([conf[i] for i in cal], [ok[i] for i in cal], r, delta,
                              start_errors)["threshold"]
        if t is None:
            continue
        hit = [i for i in test if conf[i] >= t]
        covered += len(hit)
        errors += sum(1 for i in hit if not ok[i])
    return covered, errors


def _per_text(conf: list[float], ok: list[bool], keys: list[Hashable], n_texts: int,
              r: float, delta: float, start_errors: int) -> dict:
    """The per-text check: each distinct text once (highest confidence of its copies,
    wrong when any copy is wrong), certified the same way; its share is of all texts."""
    units: dict[Hashable, list] = {}
    for c, o, k in zip(conf, ok, keys, strict=True):
        u = units.setdefault(k, [c, o])
        u[0], u[1] = max(u[0], c), u[1] and o
    res = certify_threshold([u[0] for u in units.values()], [u[1] for u in units.values()],
                            r, delta, start_errors)
    return {"n": n_texts, "automated": res["covered"], "errors": res["errors"],
            "coverage": round(res["covered"] / n_texts, 4) if n_texts else 0.0,
            "threshold": res["threshold"], "risk_upper": _up(res["risk_upper"]),
            "reason": res["reason"].replace("units", "texts") if res["reason"] else None}


def _segments(segs: list, conf: list[float | None], ok: list[bool],
              threshold: float | None, delta: float) -> dict:
    """The deployed threshold applied to each segment: automated decisions, errors,
    observed rate and exact one-sided bound per segment (most error-prone first), the worst
    segment with at least MIN_SEGMENT automated decisions, and how many have fewer."""
    if threshold is None or all(s is None for s in segs):
        return {"segments": [], "worst_segment": None, "segments_too_small": 0}
    seen: dict[str, list[int]] = {}
    for seg, c, o in zip(segs, conf, ok, strict=True):
        s = seen.setdefault(str(seg), [0, 0])
        if c is not None and c >= threshold:
            s[0] += 1
            s[1] += 0 if o else 1
    rows: list[dict[str, Any]] = [
        {"segment": k, "automated": a, "errors": e,
         "rate": round(e / a, 4) if a else None,
         "risk_upper": _up(risk_upper_bound(e, a, delta)) if a else None}
        for k, (a, e) in seen.items()]
    rows.sort(key=lambda s: (-(s["rate"] or 0.0), -(s["risk_upper"] or 0.0), s["segment"]))
    ranked = [s for s in rows if s["automated"] >= MIN_SEGMENT]
    return {"segments": rows, "worst_segment": ranked[0] if ranked else None,
            "segments_too_small": sum(1 for s in rows if 0 < s["automated"] < MIN_SEGMENT)}


def automation_certificate(records: list[dict], groups: Sequence[Hashable] | None = None,
                           targets: Sequence[float] = DEFAULT_TARGETS, delta: float = DELTA,
                           start_errors: int = START_ERRORS, seed: int = SEED,
                           primary: float = PRIMARY_TARGET, run: dict | None = None,
                           segment_by: str | None = None) -> dict:
    """The safe automation rate of one run: per question, per target, the deploy threshold
    and the share of decisions it automates, with the out-of-sample check, the per-text
    check when texts repeat, and the segments. `records` are the runner's ({question,
    confidence, correct, segment?}); `groups` one text key per record (without it every
    row is its own text); `primary` must be one of `targets`; `segment_by` names what the
    records' `segment` holds. See the module docstring."""
    if groups is not None and len(groups) != len(records):
        raise ValueError(f"{len(groups)} group keys for {len(records)} records")
    if not any(math.isclose(primary, t) for t in targets):
        raise ValueError(f"the primary target {primary:g} is not among the targets")
    by_q: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        by_q.setdefault(str(rec["question"]), []).append(i)
    questions = []
    for question, idx in by_q.items():
        n = len(idx)
        keys_all = [groups[i] if groups is not None else i for i in idx]
        conf_all = [None if records[i].get("confidence") is None
                    else float(records[i]["confidence"]) for i in idx]
        ok_all = [bool(records[i]["correct"]) for i in idx]
        segs = [records[i].get("segment") for i in idx]
        if any(c is not None and not math.isfinite(c) for c in conf_all):
            raise ValueError(f"question {question!r}: a confidence is not finite")
        have = [k for k, c in enumerate(conf_all) if c is not None]
        conf = [float(conf_all[k]) for k in have]  # type: ignore[arg-type]
        ok = [ok_all[k] for k in have]
        keys = [keys_all[k] for k in have]
        n_texts = len(set(keys_all))
        repeats = n_texts < n
        rows = []
        for r in targets:
            cert = certify_threshold(conf, ok, r, delta, start_errors)
            spread = [_out_of_sample(conf, ok, keys, r, delta, start_errors, s)
                      for s in SPREAD_SEEDS]
            covered, wrong = (spread[SPREAD_SEEDS.index(seed)] if seed in SPREAD_SEEDS
                              else _out_of_sample(conf, ok, keys, r, delta, start_errors,
                                                  seed))
            half = max(len(part) for part in split_by_group(keys, seed)) if keys else 0
            row = {
                "target_risk": r, "plain": plain_reading(r),
                "primary": math.isclose(r, primary),
                "threshold": cert["threshold"], "n": n, "automated": cert["covered"],
                "coverage": round(cert["covered"] / n, 4) if n else 0.0,
                "errors": cert["errors"], "risk_upper": _up(cert["risk_upper"]),
                "min_units": cert["min_covered"],
                "reason": (cert["reason"].replace("units", "decisions")
                           if cert["reason"] else None),
                "out_of_sample": {
                    "n": n, "seed": seed, "automated": covered, "errors": wrong,
                    "coverage": round(covered / n, 4) if n else 0.0,
                    "risk": round(wrong / covered, 4) if covered else None,
                    "spread_seeds": [SPREAD_SEEDS[0], SPREAD_SEEDS[-1]],
                    "spread_coverage": ([round(min(c for c, _ in spread) / n, 4),
                                         round(max(c for c, _ in spread) / n, 4)]
                                        if n else [0.0, 0.0]),
                    "reason": (f"a half holds at most {half} decisions with a confidence; "
                               f"the target needs {cert['min_covered']}"
                               if half < cert["min_covered"] else None)},
                **_segments(segs, conf_all, ok_all, cert["threshold"], delta),
            }
            if repeats:
                row["per_text"] = _per_text(conf, ok, keys, n_texts, r, delta, start_errors)
            rows.append(row)
        questions.append({"question": question, "n": n, "scored": len(have),
                          "texts": n_texts, "targets": rows})
    return {"name": NAME, "unit": "decision", "delta": delta, "start_errors": start_errors,
            "seed": seed, "targets": list(targets), "primary_target": primary,
            "segment_by": segment_by if any(r.get("segment") is not None for r in records)
            else None,
            "min_segment": MIN_SEGMENT, "scope": scope_of(run), "disclaimer": DISCLAIMER,
            "questions": questions}
