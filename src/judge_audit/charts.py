"""PNG charts for audit reports. matplotlib is an optional extra, never a hard dep."""
from __future__ import annotations

import base64
import io


def _mpl():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError as e:
        raise RuntimeError("charts need matplotlib: pip install 'judge-audit[charts]'") from e


def reliability_diagram_png(result, path: str | None = None) -> bytes:
    """Accuracy vs mean confidence per bin, with the 'perfectly honest' diagonal."""
    plt = _mpl()
    bins = [b for b in result.reliability if b["n"]]
    xs = [b["avg_confidence"] for b in bins]
    ys = [b["accuracy"] for b in bins]
    ns = [b["n"] for b in bins]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="perfectly honest")
    sizes = [max(20, min(400, n * 2)) for n in ns]
    ax.scatter(xs, ys, s=sizes, alpha=0.7, label="judge")
    for x, y, n in zip(xs, ys, ns, strict=True):
        ax.annotate(str(n), (x, y), fontsize=8, ha="center", va="bottom")
    ax.set_xlabel("mean confidence in bin")
    ax.set_ylabel("accuracy in bin")
    ece = "unknown" if result.ece is None else f"{result.ece:.4f}"
    ax.set_title(f"Reliability diagram — {result.judge} (ECE={ece})")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend()
    fig.tight_layout()
    return _save(fig, path)


def accuracy_coverage_png(result, path: str | None = None) -> bytes:
    """Selective prediction: accuracy when automating the most-confident X%."""
    plt = _mpl()
    curve = result.curve
    xs = [r["coverage"] for r in curve]
    ys = [r["accuracy"] for r in curve]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs, ys, marker="o", markersize=3)
    ax.set_xlabel("share of decisions automated (most confident first)")
    ax.set_ylabel("accuracy on automated share")
    ax.set_title(f"Accuracy vs coverage — {result.judge}")
    ax.set_xlim(0, 1)
    ax.set_ylim(min(ys) - 0.05 if ys else 0, 1.0)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save(fig, path)


def _save(fig, path):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    import matplotlib.pyplot as plt
    plt.close(fig)
    data = buf.getvalue()
    if path:
        with open(path, "wb") as f:
            f.write(data)
    return data


def png_to_data_uri(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()
