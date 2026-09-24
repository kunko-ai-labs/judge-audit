"""Shadow-mode runner: judge every labeled row, record everything, automate nothing."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .ground_truth import parse_ground_truth
from .judges.base import Judge, Question, QuestionType
from .metrics.calibration import (
    CI_LEVEL,
    EQUAL_MASS,
    N_BOOT,
    Interval,
    accuracy_ci,
    accuracy_coverage,
    brier_ci,
    brier_score,
    ci_fields,
    ece_ci,
    expected_calibration_error,
    reliability_bins,
    zero_error_coverage,
    zero_error_coverage_ci,
)

# Percentile bootstrap over distinct texts (docs/judges.md § Confidence intervals): the
# datasets repeat states, and two rows with the same text are not two independent
# observations. The seed is fixed so a published interval recomputes to the digit.
BOOTSTRAP = {"method": "percentile bootstrap over distinct dataset texts (cluster)",
             "level": CI_LEVEL, "n_boot": N_BOOT, "seed": 0}


@dataclass
class AuditResult:
    judge: str
    n: int
    accuracy: float
    ece: float | None
    reliability: list[dict] = field(default_factory=list)
    curve: list[dict] = field(default_factory=list)
    zero_error: dict = field(default_factory=dict)
    total_cost_usd: float | None = 0.0
    p50_latency_s: float = 0.0
    p99_latency_s: float = 0.0
    run: dict = field(default_factory=dict)
    # When a committed report was rebuilt from its checkpoint by a later version: its own
    # time, version and script. Kept apart from `run`, which is what the run itself said.
    regenerated: dict = field(default_factory=dict)
    # 95 % intervals (lo, hi) of the headline numbers; None when skipped. Each
    # knows its method (bootstrap, or exact at the boundary) and publishes it alongside.
    accuracy_ci: Interval | None = None
    ece_ci: Interval | None = None
    zero_error_coverage_ci: Interval | None = None
    # One record per judged (row, question): the raw evidence behind the numbers.
    records: list[dict] = field(default_factory=list)
    # The two calibration numbers that need no fixed bins (docs/judges.md § Three
    # calibration numbers); None when there are no rows, never an imputed 0.
    ece_equal_mass: float | None = None
    brier: float | None = None
    ece_equal_mass_ci: Interval | None = None
    brier_ci: Interval | None = None
    confidence: dict = field(default_factory=dict)
    # Expected (row, question) pairs vs what the judge answered; empty for a report rebuilt
    # from a checkpoint, where `scripts/audit_resumable.py` enforces the same rule.
    completeness: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "judge": self.judge, "n": self.n, "accuracy": self.accuracy,
            "confidence": self.confidence,
            "ece": self.ece, "ece_equal_mass": self.ece_equal_mass, "brier": self.brier,
            "reliability_bins": self.reliability,
            "accuracy_coverage": self.curve, "zero_error_coverage": self.zero_error,
            "total_cost_usd": (round(self.total_cost_usd, 6)
                               if self.total_cost_usd is not None else None),
            "p50_latency_s": round(self.p50_latency_s, 3),
            "p99_latency_s": round(self.p99_latency_s, 3),
            "run": self.run,
        }
        if self.accuracy_ci is not None:
            d.update(**ci_fields("accuracy", self.accuracy_ci, self.accuracy),
                     **ci_fields("ece", self.ece_ci, self.ece),
                     **ci_fields("ece_equal_mass", self.ece_equal_mass_ci, self.ece_equal_mass),
                     **ci_fields("brier", self.brier_ci, self.brier),
                     **ci_fields("zero_error_coverage", self.zero_error_coverage_ci,
                                 self.zero_error.get("coverage")),
                     bootstrap=dict(BOOTSTRAP))
        if self.completeness:
            d["completeness"] = self.completeness
        if self.regenerated:
            d["regenerated"] = self.regenerated
        return d


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(int(p / 100 * len(s)), len(s) - 1)]


def questions_of(row: dict) -> list[Question]:
    return [Question(name=q["name"],
                     type=QuestionType(q.get("type", "choice")),
                     instructions=q.get("instructions", ""),
                     options=q.get("options", []),
                     descriptions=q.get("descriptions", {}))
            for q in row["questions"]]


def clamp_confidence(value) -> float | None:
    """Return a declared probability, or None when it is absent or invalid.

    Out-of-range values are rejected rather than clamped: both clamping and replacing an
    invalid declaration with zero or one would fabricate evidence the judge did not give.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return None
    return confidence


def is_correct(decision: str, expected: str) -> bool:
    return str(decision).strip().lower() == str(expected).strip().lower()


def checkpoint_parse_status(judgment: dict) -> str:
    """Parse status for current and legacy checkpoint rows, without broad inference.

    Old LLM checkpoints recorded `raw.parsed` for every answer. A null parsed object is
    therefore explicit evidence of no answer; its historical 0.0 confidence was imputed and
    becomes unknown. Other adapters often have no `raw.parsed` key at all, which says nothing
    about parsing and stays `parsed`.
    """
    status = judgment.get("parse_status")
    if status in {"parsed", "no_answer", "no_confidence"}:
        return status
    raw = judgment.get("raw")
    if isinstance(raw, dict) and "parsed" in raw:
        parsed = raw["parsed"]
        if parsed is None:
            return "no_answer"
        if not isinstance(parsed, dict) or not str(parsed.get("decision", "")).strip():
            return "no_answer"
        if clamp_confidence(parsed.get("confidence")) is None:
            return "no_confidence"
    return "parsed"


def checkpoint_confidence(judgment: dict) -> float | None:
    """Declared confidence in a current or legacy checkpoint judgment.

    Unknown for a no-answer (a blank decision: any number there, including the 0.0 the old
    parser imputed, belongs to no decision) and for a missing or invalid declaration."""
    if checkpoint_parse_status(judgment) in {"no_answer", "no_confidence"}:
        return None
    return clamp_confidence(judgment.get("confidence"))


def _local_endpoint(run: dict | None) -> bool:
    judge = (run or {}).get("judge") or {}
    if judge.get("provider") != "openai-compatible":
        return False
    try:
        host = urllib.parse.urlparse(str(judge.get("base_url", ""))).hostname
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def checkpoint_cost(judgment: dict, run: dict | None = None) -> float | None:
    """Known row cost; legacy unpriced local endpoints are known free, hosted ones unknown."""
    raw = judgment.get("raw")
    if isinstance(raw, dict) and raw.get("priced") is False:
        return 0.0 if _local_endpoint(run) else None
    value = judgment.get("cost_usd")
    if value is None or isinstance(value, bool):
        return None
    try:
        cost = float(value)
    except (TypeError, ValueError):
        return None
    return cost if math.isfinite(cost) and cost >= 0.0 else None


def checkpoint_record(idx: int, row: dict, judgment: dict, expected: str,
                      run: dict | None = None) -> dict:
    """Normalise one checkpoint judgment into the record schema used by `summarize`."""
    return {
        "idx": idx,
        "question": judgment["question"],
        "expected": str(expected),
        "decision": str(judgment.get("decision", "")),
        "correct": is_correct(judgment.get("decision", ""), expected),
        "confidence": checkpoint_confidence(judgment),
        "parse_status": checkpoint_parse_status(judgment),
        "latency_s": judgment.get("latency_s", 0.0),
        "cost_usd": checkpoint_cost(judgment, run),
        "meta": row.get("_meta", {}),
        "raw": judgment.get("raw", {}),
    }


def display_path(path: str | Path) -> str:
    """The path as a provenance line should publish it: never somebody's home directory.

    A file inside the working directory is named relative to it (`docs/runs/x.ckpt.jsonl`),
    a file elsewhere under the user's home as `~/…`; anything else is left alone. The
    point is a report that reads the same on every machine and leaks none of them (#58).
    """
    p = Path(path)
    if not p.is_absolute():
        return str(path)
    for base, prefix in ((Path.cwd(), ""), (Path.home(), "~/")):
        try:
            return prefix + str(p.relative_to(base))
        except ValueError:
            continue
    return str(path)


def run_metadata(judge: Judge, labels_path: str | None = None,
                 n_rows: int | None = None, dataset_meta: dict | None = None) -> dict:
    """Everything an outsider needs to know how these numbers were produced.

    `dataset_meta` is the header object `load_dataset` returns; when it is not
    given the header is read from `labels_path`, so the ground-truth tier is
    never silently GT-0 for a file that declares one.
    """
    from . import __version__
    meta = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge_audit_version": __version__,
        "judge": judge.describe(),
        "python": platform.python_version(),
    }
    if labels_path:
        if dataset_meta is None:
            dataset_meta = read_dataset_header(labels_path)
        meta["dataset"] = {
            "path": display_path(labels_path),
            "sha256": sha256_of(labels_path),
            "sha256_rows": sha256_rows_of(labels_path),
            "rows": n_rows,
            "ground_truth": parse_ground_truth(dataset_meta.get("ground_truth")).to_dict(),
        }
    return meta


def sha256_of(path: str) -> str:
    """Digest of the whole file, header line included."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_rows_of(path: str) -> str:
    """Digest of the rows only: the file minus its dataset header line.

    Equals `sha256_of` for a file without a header, and equals the whole-file
    digest recorded by runs made before the header existed.
    """
    with open(path, "rb") as f:
        data = f.read()
    _, rows = _split_header(data)
    return hashlib.sha256(rows).hexdigest()


def groups_of(records: list[dict], rows: list[dict]) -> list[str]:
    """One cluster key per record: the text of the row it judged.

    The datasets repeat states (the router has 61 distinct texts in 120 rows), so the
    published interval resamples distinct texts, not rows. A record whose row is not in
    `rows` falls back to its own index — it is then its own cluster."""
    return [str(rows[r["idx"]]["state"]) if 0 <= r.get("idx", -1) < len(rows)
            else f"#{i}" for i, r in enumerate(records)]


def bootstrap_enabled() -> bool:
    """`JUDGE_AUDIT_BOOTSTRAP=0` (or `false`, `no`, `off`) skips the intervals."""
    return os.environ.get("JUDGE_AUDIT_BOOTSTRAP", "1").strip().lower() not in (
        "0", "false", "no", "off")


def summarize(judge_name: str, records: list[dict], run: dict | None = None,
              ci: bool | None = None, groups: list[str] | None = None) -> AuditResult:
    """Metrics from per-question records ({confidence, correct, latency_s, cost_usd, ...}).

    `ci` adds the bootstrap intervals; None defers to `JUDGE_AUDIT_BOOTSTRAP`.
    `groups` is one cluster key per record (`groups_of`); without it every row is its own
    cluster, which overstates precision on a dataset with repeated texts."""
    total = len(records)
    hits = sum(bool(r["correct"]) for r in records)
    known_idx = [i for i, r in enumerate(records)
                 if clamp_confidence(r.get("confidence")) is not None]
    confidences = [clamp_confidence(records[i]["confidence"]) for i in known_idx]
    correct = [bool(records[i]["correct"]) for i in known_idx]
    known_groups = [groups[i] for i in known_idx] if groups is not None else None
    # a skipped question has no latency (None): it is left out, not counted as instant
    latencies = [lat for lat in (r.get("latency_s", 0.0) for r in records) if lat is not None]
    costs = [r.get("cost_usd") for r in records]
    total_cost = None if any(cost is None for cost in costs) else math.fsum(costs)
    known = len(confidences)
    if ci is None:
        ci = bootstrap_enabled()
    return AuditResult(
        judge=judge_name, n=total,
        accuracy=round(hits / total, 4) if total else 0.0,
        confidence={"known": known, "total": total},
        ece=(round(expected_calibration_error(confidences, correct), 4) if known else None),
        reliability=reliability_bins(confidences, correct) if known else [],
        curve=accuracy_coverage(confidences, correct) if known else [],
        zero_error=(zero_error_coverage(confidences, correct) if known else
                    {"coverage": None, "n": 0, "threshold": None}),
        total_cost_usd=total_cost,
        p50_latency_s=_percentile(latencies, 50),
        p99_latency_s=_percentile(latencies, 99),
        run=run or {},
        accuracy_ci=accuracy_ci([bool(r["correct"]) for r in records], groups=groups)
        if ci and total else None,
        ece_ci=ece_ci(confidences, correct, groups=known_groups) if ci and known else None,
        zero_error_coverage_ci=(zero_error_coverage_ci(
            confidences, correct, groups=known_groups) if ci and known else None),
        records=records,
        ece_equal_mass=(round(expected_calibration_error(confidences, correct,
                                                         binning=EQUAL_MASS), 4)
                        if known else None),
        brier=round(brier_score(confidences, correct), 4) if known else None,
        ece_equal_mass_ci=(ece_ci(confidences, correct, groups=known_groups,
                                  binning=EQUAL_MASS) if ci and known else None),
        brier_ci=brier_ci(confidences, correct, groups=known_groups) if ci and known else None,
    )


def record_of(idx: int, row: dict, judgment, expected: str) -> dict:
    confidence = clamp_confidence(judgment.confidence)
    status = judgment.parse_status
    if status == "no_answer":
        confidence = None
    elif confidence is None:  # any adapter: an absent or invalid number is not a confidence
        status = "no_confidence"
    return {
        "idx": idx,
        "question": judgment.question,
        "expected": str(expected),
        "decision": str(judgment.decision),
        "correct": is_correct(judgment.decision, expected),
        "confidence": confidence,
        "parse_status": status,
        "latency_s": judgment.latency_s,
        "cost_usd": judgment.cost_usd,
        "meta": row.get("_meta", {}),
        "raw": judgment.raw,
    }


class IncompleteAnswers(ValueError):
    """The judge broke the answer contract (two answers to one question), or the dataset
    labels a question it never asks. Either way the audit would not mean what it says."""


def answer_gaps(row: dict, answered: list[str]) -> dict:
    """What a row's answers lack or add against its labels: {missing, duplicate, unexpected,
    orphan_labels}, each a sorted list of question names. Shared by the live runner and the
    checkpoint check, so a report built either way counts the same decisions."""
    labels = set(row.get("labels", {}))
    asked = {q["name"] for q in row["questions"]}
    seen = [q for q in answered if q in asked]
    blank = sorted(q for q, v in row.get("labels", {}).items()
                   if v is None or not str(v).strip())
    return {"missing": sorted(labels - set(seen)),
            "duplicate": sorted({q for q in seen if seen.count(q) > 1}),
            "unexpected": sorted(q for q in answered if q not in asked),
            "orphan_labels": sorted(labels - asked),
            "blank_labels": blank}


def dataset_gaps(idx: int, row: dict) -> None:
    """A label naming no question, or a blank / null label, is a dataset error: raise before
    anyone pays for a call. (A blank label would score a skipped question as correct.)"""
    g = answer_gaps(row, [])
    if g["orphan_labels"]:
        raise IncompleteAnswers(
            f"row {idx}: label(s) {g['orphan_labels']} name no question in the row")
    if g["blank_labels"]:
        raise IncompleteAnswers(f"row {idx}: label(s) {g['blank_labels']} are blank or null")


def missing_answer(question: str, returned: list) -> dict:
    """The checkpoint judgment written for a labelled question the judge did not answer.

    Latency unknown (None, left out of the percentiles: a silent judge must not look fast).
    Cost 0.0 — the row's call is already paid by the answers it returned — unless nothing
    came back with a known cost, in which case it is unknown too."""
    costs = [getattr(j, "cost_usd", None) if not isinstance(j, dict) else j.get("cost_usd")
             for j in returned]
    known = bool(costs) and all(c is not None for c in costs)
    return {"question": question, "decision": "", "confidence": None, "latency_s": None,
            "cost_usd": 0.0 if known else None, "raw": {"missing": True},
            "parse_status": "no_answer"}


def reconcile(idx: int, row: dict, judgments, counts: dict) -> list[dict]:
    """One record per labelled question, answered or not.

    A labelled question the judge skipped is a no-answer record — wrong, confidence unknown —
    so it stays in `n`: a judge cannot raise its score by staying silent. An answer to a
    question the row does not ask is counted and dropped; a second answer to the same
    question, or a label with no question, raises `IncompleteAnswers`."""
    labels: dict = row.get("labels", {})
    asked = {q["name"] for q in row["questions"]}
    dataset_gaps(idx, row)
    judgments = list(judgments)
    answered: dict = {}
    for judgment in judgments:
        if judgment.question not in asked:
            counts["unexpected"] += 1
            continue
        if judgment.question in answered:
            raise IncompleteAnswers(
                f"row {idx}: the judge answered {judgment.question!r} twice")
        answered[judgment.question] = judgment
    records = []
    for name, expected in labels.items():
        counts["expected"] += 1
        judgment = answered.get(name)
        if judgment is None:
            counts["missing"] += 1
            records.append(checkpoint_record(idx, row, missing_answer(name, judgments), expected))
        else:
            counts["answered"] += 1
            records.append(record_of(idx, row, judgment, expected))
    return records


def run_audit(judge: Judge, rows: list[dict], labels_path: str | None = None,
              dataset_meta: dict | None = None, ci: bool | None = None) -> AuditResult:
    """rows: [{state, questions: [{name, type, instructions, options?, descriptions?}],
              labels: {name: expected}}]; dataset_meta: the header from `load_dataset`;
    ci: bootstrap intervals (None: unless `JUDGE_AUDIT_BOOTSTRAP=0`)."""
    records: list[dict] = []
    counts = {"expected": 0, "answered": 0, "missing": 0, "unexpected": 0}
    for idx, row in enumerate(rows):
        records += reconcile(idx, row, judge.decide(row["state"], questions_of(row)), counts)
    result = summarize(judge.name, records,
                       run_metadata(judge, labels_path, len(rows), dataset_meta), ci=ci,
                       groups=groups_of(records, rows))
    result.completeness = counts
    return result


def write_judgments(result: AuditResult, path: str) -> None:
    """Per-decision evidence as JSONL — commit it next to the report."""
    with open(path, "w", encoding="utf-8") as f:
        for r in result.records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _is_header(obj) -> bool:
    return isinstance(obj, dict) and obj.get("idx") == -1


def _split_header(data: bytes) -> tuple[bytes | None, bytes]:
    """(header line, everything after it) — header None when the first line is a row."""
    nl = data.find(b"\n")
    first = data if nl < 0 else data[:nl + 1]
    try:
        obj = json.loads(first)
    except ValueError:
        return None, data
    if not _is_header(obj):
        return None, data
    return first, data[len(first):]


def _validate_header(obj: dict, path: str) -> dict:
    ds = obj.get("dataset")
    if not isinstance(ds, dict):
        raise ValueError(f"{path}: dataset header line must carry a 'dataset' object")
    parse_ground_truth(ds.get("ground_truth"))  # unknown tier / shape fails here, loudly
    return ds


def read_dataset_header(path: str) -> dict:
    """The header's `dataset` object ({} when the file has none), validated."""
    with open(path, "rb") as f:
        first = f.readline()
    try:
        obj = json.loads(first) if first.strip() else None
    except ValueError:
        return {}
    return _validate_header(obj, path) if _is_header(obj) else {}


def load_dataset(path: str) -> tuple[list[dict], dict]:
    """Rows and the dataset header ({} when absent).

    The header is an optional first line `{"idx": -1, "dataset": {...}}`; its
    `ground_truth` object is validated (docs/ground-truth.md). Rows are every
    other non-empty line, in order.
    """
    rows: list[dict] = []
    dataset: dict = {}
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line)
            if _is_header(obj):
                if rows or dataset:
                    raise ValueError(f"{path}:{lineno}: dataset header must be the first line")
                dataset = _validate_header(obj, path)
                continue
            rows.append(obj)
    return rows, dataset


def load_jsonl(path: str) -> list[dict]:
    """Rows only; the dataset header line, if any, is validated and dropped."""
    return load_dataset(path)[0]
