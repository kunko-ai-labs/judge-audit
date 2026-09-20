"""README charts, drawn from the published audit JSON (never from prose).

  python scripts/charts_readme.py            # writes docs/assets/hero-*.png

Two figures:
  hero-router.png   confidence vs accuracy per segment, bare labels vs described
                    options (the ablation) — the gap between the two bars is the
                    overconfidence a production router would ship.
  hero-arc.png      the three audits side by side: accuracy, mean confidence, ECE.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"

# Colorblind-validated categorical order (blue, orange, aqua); status gray for baseline.
C_ACC, C_CONF, C_ALT, C_MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8a8985"
INK, INK2 = "#0b0b0b", "#52514e"
SEG_LABELS = {"clean_easy": "easy tasks\n(label: cheap)", "clean_hard": "hard tasks\n(label: strong)",
              "adversarial": "easy + injection\n(label: cheap)"}


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#d9d8d3")
    ax.spines["bottom"].set_color("#d9d8d3")
    ax.tick_params(colors=INK2, labelsize=9)
    ax.yaxis.grid(True, color="#e8e7e2", linewidth=0.8)
    ax.set_axisbelow(True)


def _load(name: str) -> dict | None:
    p = DOCS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def hero_router() -> Path:
    bare = _load("audit-jev-router.json")
    desc = _load("audit-jev-router-described.json")
    conds = [("options as bare labels", bare)] + ([("options with descriptions", desc)] if desc else [])
    segs = ["clean_easy", "clean_hard", "adversarial"]

    fig, axes = plt.subplots(1, len(conds), figsize=(5.2 * len(conds) + 0.8, 4.4),
                             sharey=True, squeeze=False)
    for ax, (title, d) in zip(axes[0], conds, strict=True):
        _style(ax)
        xs = range(len(segs))
        acc = [d["by_segment"][s]["accuracy"] for s in segs]
        conf = [d["by_segment"][s]["mean_confidence"] for s in segs]
        w = 0.36
        ax.bar([x - w / 2 - 0.01 for x in xs], conf, width=w, color=C_CONF, label="mean confidence",
               zorder=3)
        ax.bar([x + w / 2 + 0.01 for x in xs], acc, width=w, color=C_ACC, label="accuracy", zorder=3)
        for x, a, c in zip(xs, acc, conf, strict=True):
            ax.text(x - w / 2 - 0.01, c + 0.02, f"{c:.2f}", ha="center", fontsize=9, color=INK)
            ax.text(x + w / 2 + 0.01, a + 0.02, f"{a:.0%}", ha="center", fontsize=9, color=INK)
        ax.set_xticks(list(xs))
        ax.set_xticklabels([SEG_LABELS[s] for s in segs])
        ax.set_ylim(0, 1.12)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
        n_strong = d["sanity"]["decisions"].get("route_strong", 0)
        ax.set_title(f"{title}\nchose the strong model {n_strong}/{d['n']} times · "
                     f"ECE {d['overall']['ece']:.2f}", fontsize=10.5, color=INK, loc="left")
    axes[0][0].set_ylabel("share", color=INK2)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper right", fontsize=9, ncol=2,
               bbox_to_anchor=(0.99, 0.985))
    fig.suptitle("Jev as a task router: how sure it is vs how often it is right",
                 fontsize=13, color=INK, x=0.01, ha="left", y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = ASSETS / "hero-router.png"
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    return out


def hero_arc() -> Path:
    real = _load("audit-jev-real.json")
    adv = _load("audit-jev-adversarial.json")
    router = _load("audit-jev-router.json")
    pi = adv["by_attack"]["prompt_injection"]
    hard = router["by_segment"]["clean_hard"]
    cols = [
        ("business emails\nclean (n=200)", real["accuracy"],
         real["reliability_bins"][-1]["avg_confidence"], real["ece"]),
        ("emails under\nprompt injection (n=40)", pi["accuracy"], pi["mean_confidence"], pi["ece"]),
        ("hard coding tasks\nas router (n=40)", hard["accuracy"], hard["mean_confidence"],
         hard["ece"]),
    ]
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    _style(ax)
    xs = range(len(cols))
    w = 0.36
    ax.bar([x - w / 2 - 0.01 for x in xs], [c[2] for c in cols], width=w, color=C_CONF,
           label="mean confidence", zorder=3)
    ax.bar([x + w / 2 + 0.01 for x in xs], [c[1] for c in cols], width=w, color=C_ACC,
           label="accuracy", zorder=3)
    for x, (_, a, c, e) in zip(xs, cols, strict=True):
        ax.text(x - w / 2 - 0.01, c + 0.02, f"{c:.2f}", ha="center", fontsize=9, color=INK)
        ax.text(x + w / 2 + 0.01, a + 0.02, f"{a:.0%}", ha="center", fontsize=9, color=INK)
        ax.text(x, -0.2, f"ECE {e:.2f}", ha="center", fontsize=9.5, color=INK2,
                transform=ax.get_xaxis_transform())
    ax.set_xticks(list(xs))
    ax.set_xticklabels([c[0] for c in cols])
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.set_title("Same judge, three jobs: honest, honest under attack, confidently wrong",
                 fontsize=12.5, color=INK, loc="left", pad=14)
    fig.tight_layout()
    out = ASSETS / "hero-arc.png"
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    return out


ARENA_LABELS = {"jev": "Jev", "claude-sonnet-4.5": "Claude Sonnet 4.5", "llama-3.3-70b": "Llama 3.3 70B",
                "deepseek-r1": "DeepSeek R1", "gemma4": "gemma4 (local)", "llama32": "llama3.2 3B (local)",
                "deberta-nli": "DeBERTa NLI (local)"}


def hero_arena() -> Path | None:
    """Zero-error coverage under attack: the automation budget each judge earns."""
    arena = _load("arena-2026-09.json")
    if not arena:
        return None
    rows = []
    for slug, j in arena.items():
        s = j["datasets"].get("email-adversarial")
        if s:
            rows.append((ARENA_LABELS.get(slug, j["label"]), s["zero_error_coverage"], s["accuracy"],
                         s["mean_conf_wrong"], j["method"].startswith("option")))
    rows.sort(key=lambda r: r[1], reverse=True)
    fig, ax = plt.subplots(figsize=(9.6, 4.9))
    _style(ax)
    ax.xaxis.grid(True, color="#e8e7e2", linewidth=0.8)
    ax.yaxis.grid(False)
    ys = list(range(len(rows)))[::-1]
    colors = [C_ACC if native else C_CONF for *_, native in rows]
    ax.barh(ys, [r[1] for r in rows], color=colors, height=0.62, zorder=3)
    for y, (_label, cov, acc, cw, _) in zip(ys, rows, strict=True):
        ax.text(cov + 0.012, y, f"{cov:.0%}", va="center", fontsize=10, color=INK, fontweight="bold")
        # right margin, outside the plot: the two numbers that explain the bar
        ax.text(1.03, y, f"acc {acc:.0%} · conf when wrong {cw:.2f}", va="center", ha="left",
                fontsize=8.5, color=INK2, transform=ax.get_yaxis_transform(), clip_on=False)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("share of decisions you could automate with zero observed errors "
                  "(most confident first)", color=INK2, fontsize=9.5)
    ax.set_title("200 emails under attack: the automation budget each judge earns",
                 fontsize=12.5, color=INK, loc="left", pad=30)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C_ACC, label="confidence = option probability"),
                       Patch(color=C_CONF, label="confidence = verbalized by a chat model")],
              frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=8.5)
    fig.subplots_adjust(left=0.19, right=0.72, top=0.82, bottom=0.14)
    out = ASSETS / "hero-arena.png"
    fig.savefig(out, dpi=130, facecolor="white")
    plt.close(fig)
    return out


if __name__ == "__main__":
    for p in (hero_router(), hero_arc(), hero_arena()):
        if p:
            print("wrote", p.relative_to(ROOT))
