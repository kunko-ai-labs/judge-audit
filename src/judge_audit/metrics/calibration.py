"""Calibration metrics: the honesty math. Stdlib only."""
from __future__ import annotations


def expected_calibration_error(confidences: list[float], correct: list[bool],
                               n_bins: int = 10) -> float:
    """ECE with equal-width bins. 0.0 = perfectly honest."""
    bins: list[list[bool]] = [[] for _ in range(n_bins)]
    conf_bins: list[list[float]] = [[] for _ in range(n_bins)]
    for c, ok in zip(confidences, correct, strict=True):
        i = min(int(c * n_bins), n_bins - 1)
        bins[i].append(ok)
        conf_bins[i].append(c)
    ece = 0.0
    n = len(correct)
    for b, cb in zip(bins, conf_bins, strict=True):
        if not b:
            continue
        acc = sum(b) / len(b)
        avg_conf = sum(cb) / len(cb)
        ece += len(b) / n * abs(acc - avg_conf)
    return ece


def reliability_bins(confidences: list[float], correct: list[bool],
                     n_bins: int = 10) -> list[dict]:
    """Per-bin (avg confidence, accuracy, count) for the reliability diagram."""
    out = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        idx = [j for j, c in enumerate(confidences) if lo <= c < hi or (hi == 1.0 and c == 1.0)]
        if not idx:
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "avg_confidence": None,
                        "accuracy": None, "n": 0})
            continue
        cs = [confidences[j] for j in idx]
        oks = [correct[j] for j in idx]
        out.append({"bin": f"{lo:.1f}-{hi:.1f}",
                    "avg_confidence": round(sum(cs) / len(cs), 4),
                    "accuracy": round(sum(oks) / len(oks), 4), "n": len(idx)})
    return out


def accuracy_coverage(confidences: list[float], correct: list[bool],
                      steps: int = 20) -> list[dict]:
    """Selective prediction: sort by confidence desc, accuracy at each coverage level.

    Answers the business question: 'what share can I automate at what error rate?'
    """
    order = sorted(range(len(confidences)), key=lambda j: confidences[j], reverse=True)
    curve = []
    for s in range(1, steps + 1):
        k = max(1, int(len(order) * s / steps))
        top = order[:k]
        acc = sum(correct[j] for j in top) / k
        curve.append({"coverage": round(k / len(order), 4),
                      "accuracy": round(acc, 4), "n": k,
                      "min_confidence": round(confidences[top[-1]], 4)})
    return curve


def zero_error_coverage(confidences: list[float], correct: list[bool]) -> dict:
    """Largest most-confident prefix with zero observed errors (nikhilmudholkar metric)."""
    order = sorted(range(len(confidences)), key=lambda j: confidences[j], reverse=True)
    k = 0
    for j in order:
        if not correct[j]:
            break
        k += 1
    return {"coverage": round(k / len(order), 4) if order else 0.0, "n": k,
            "threshold": round(confidences[order[k - 1]], 4) if k else None}
