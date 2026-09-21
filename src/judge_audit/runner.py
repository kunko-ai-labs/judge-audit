"""Shadow-mode runner: judge every labeled row, record everything, automate nothing."""
from __future__ import annotations

import hashlib
import json
import math
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .judges.base import Judge, Question, QuestionType
from .metrics.calibration import (
    accuracy_coverage,
    expected_calibration_error,
    reliability_bins,
    zero_error_coverage,
)


@dataclass
class AuditResult:
    judge: str
    n: int
    accuracy: float
    ece: float
    reliability: list[dict] = field(default_factory=list)
    curve: list[dict] = field(default_factory=list)
    zero_error: dict = field(default_factory=dict)
    total_cost_usd: float = 0.0
    p50_latency_s: float = 0.0
    p99_latency_s: float = 0.0
    run: dict = field(default_factory=dict)
    # One record per judged (row, question): the raw evidence behind the numbers.
    records: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "judge": self.judge, "n": self.n, "accuracy": self.accuracy,
            "ece": self.ece, "reliability_bins": self.reliability,
            "accuracy_coverage": self.curve, "zero_error_coverage": self.zero_error,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "p50_latency_s": round(self.p50_latency_s, 3),
            "p99_latency_s": round(self.p99_latency_s, 3),
            "run": self.run,
        }


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


def is_correct(decision: str, expected: str) -> bool:
    return str(decision).strip().lower() == str(expected).strip().lower()


def run_metadata(judge: Judge, labels_path: str | None = None,
                 n_rows: int | None = None) -> dict:
    """Everything an outsider needs to know how these numbers were produced."""
    from . import __version__
    meta = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge_audit_version": __version__,
        "judge": judge.describe(),
        "python": platform.python_version(),
    }
    if labels_path:
        meta["dataset"] = {
            "path": labels_path,
            "sha256": sha256_of(labels_path),
            "rows": n_rows,
        }
    return meta


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize(judge_name: str, records: list[dict], run: dict | None = None) -> AuditResult:
    """Metrics from per-question records ({confidence, correct, latency_s, cost_usd, ...})."""
    confidences = [r["confidence"] for r in records]
    correct = [bool(r["correct"]) for r in records]
    latencies = [r.get("latency_s", 0.0) for r in records]
    total = len(records)
    hits = sum(correct)
    return AuditResult(
        judge=judge_name, n=total,
        accuracy=round(hits / total, 4) if total else 0.0,
        ece=round(expected_calibration_error(confidences, correct), 4) if total else 0.0,
        reliability=reliability_bins(confidences, correct),
        curve=accuracy_coverage(confidences, correct) if total else [],
        zero_error=zero_error_coverage(confidences, correct),
        total_cost_usd=math.fsum(r.get("cost_usd", 0.0) for r in records),
        p50_latency_s=_percentile(latencies, 50),
        p99_latency_s=_percentile(latencies, 99),
        run=run or {},
        records=records,
    )


def record_of(idx: int, row: dict, judgment, expected: str) -> dict:
    return {
        "idx": idx,
        "question": judgment.question,
        "expected": str(expected),
        "decision": str(judgment.decision),
        "correct": is_correct(judgment.decision, expected),
        "confidence": max(0.0, min(1.0, float(judgment.confidence))),
        "latency_s": judgment.latency_s,
        "cost_usd": judgment.cost_usd,
        "meta": row.get("_meta", {}),
        "raw": judgment.raw,
    }


def run_audit(judge: Judge, rows: list[dict], labels_path: str | None = None) -> AuditResult:
    """rows: [{state, questions: [{name, type, instructions, options?, descriptions?}],
              labels: {name: expected}}]"""
    records: list[dict] = []
    for idx, row in enumerate(rows):
        labels: dict = row.get("labels", {})
        for judgment in judge.decide(row["state"], questions_of(row)):
            expected = labels.get(judgment.question)
            if expected is None:
                continue
            records.append(record_of(idx, row, judgment, expected))
    return summarize(judge.name, records, run_metadata(judge, labels_path, len(rows)))


def write_judgments(result: AuditResult, path: str) -> None:
    """Per-decision evidence as JSONL — commit it next to the report."""
    with open(path, "w", encoding="utf-8") as f:
        for r in result.records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
