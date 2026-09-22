"""README charts, drawn from the published audit JSON (never from prose).

  python scripts/charts_readme.py            # writes docs/assets/hero-*.png (+ -dark variants)

Three figures, each rendered in a light and a dark theme (GitHub picks one
through the <picture> tag in the README):
  hero-arena    zero-error coverage per judge on the emails-under-attack dataset —
                the automation budget each judge earns.
  hero-arc      the three Jev audits side by side: confidence vs accuracy, ECE.
  hero-router   bare labels vs described options (the ablation), per segment.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"

# Colour by job: blue = confidence is an option probability, orange = verbalized by a chat
# model, green = NLI entailment, red = wrong. Validated for CVD separation in both themes.
THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "muted": "#52514e", "grid": "#e8e7e2",
              "faint": "#d9d8d3", "prob": "#2a78d6", "verb": "#eb6834", "nli": "#1baf7a",
              "wrong": "#e34948", "pill": "#f1f0ec"},
    "dark": {"surface": "#0b0f14", "ink": "#e6edf3", "muted": "#8b98a5", "grid": "#1f2732",
             "faint": "#263140", "prob": "#3987e5", "verb": "#e06a3a", "nli": "#199e70",
             "wrong": "#f85149", "pill": "#161c24"},
}
FONT = ["Helvetica Neue", "Arial", "DejaVu Sans"]
DPI = 160

ARENA_LABELS = {"jev": "Jev", "claude-sonnet-4.5": "Claude Sonnet 4.5", "llama-3.3-70b": "Llama 3.3 70B",
                "deepseek-r1": "DeepSeek R1", "gemma4": "gemma4 (local)", "llama32": "llama3.2 3B (local)",
                "deberta-nli": "DeBERTa NLI (local)",
                "finetuned-deberta": "DeBERTa fine-tuned, run 1 (local)",
                "finetuned-deberta-run2": "DeBERTa fine-tuned, run 2 (local)",
                "finetuned-deberta-run2-ts": "DeBERTa fine-tuned, run 2 + temp. scaling (local)"}
SEG_LABELS = {"clean_easy": "easy tasks\n(label: cheap)", "clean_hard": "hard tasks\n(label: strong)",
              "adversarial": "easy + injection\n(label: cheap)"}


def _load(name: str) -> dict | None:
    p = DOCS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _setup(t: dict) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": FONT,
        "figure.facecolor": t["surface"], "axes.facecolor": t["surface"],
        "savefig.facecolor": t["surface"], "text.color": t["ink"],
        "axes.labelcolor": t["muted"], "xtick.color": t["muted"], "ytick.color": t["ink"],
        "axes.edgecolor": t["faint"], "axes.linewidth": 0.8,
    })


def _axes(ax, t: dict, grid: str = "y") -> None:
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["faint"])
    ax.tick_params(length=0, labelsize=10)
    if grid == "y":
        ax.yaxis.grid(True, color=t["grid"], linewidth=0.8)
        ax.xaxis.grid(False)
    else:
        ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
        ax.yaxis.grid(False)
    ax.set_axisbelow(True)


def _titles(fig, t: dict, title: str, subtitle: str, footnote: str, top: float = 0.95) -> None:
    fig.text(0.04, top, title, fontsize=15, fontweight="semibold", color=t["ink"], ha="left", va="top")
    fig.text(0.04, top - 0.062, subtitle, fontsize=10, color=t["muted"], ha="left", va="top")
    fig.text(0.04, 0.025, footnote, fontsize=8.5, color=t["muted"], ha="left", va="bottom")


def _rounded_bar(ax, x, y, w, h, color, horizontal: bool, radius: float) -> None:
    """A bar with a rounded data-end and a square baseline edge."""
    if (horizontal and w <= 0) or (not horizontal and h <= 0):
        return
    # rounding_size is in data units; keep it ≤ half the bar's thickness and length
    r = min(radius, (h if horizontal else w) / 2, (w if horizontal else h) / 2)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                facecolor=color, edgecolor="none", zorder=3))
    if horizontal:
        ax.add_patch(FancyBboxPatch((x, y), min(r, w), h, boxstyle="square,pad=0",
                                    facecolor=color, edgecolor="none", zorder=3))
    else:
        ax.add_patch(FancyBboxPatch((x, y), w, min(r, h), boxstyle="square,pad=0",
                                    facecolor=color, edgecolor="none", zorder=3))


def _hairline(ax, x0, x1, y0, y1, color) -> None:
    ax.plot([x0, x1], [y0, y1], color=color, linewidth=3, solid_capstyle="butt", zorder=3)


def _pill(ax, x, y, text, t: dict, fontsize=9):
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=t["muted"],
            transform=ax.get_xaxis_transform(), clip_on=False,
            bbox={"boxstyle": "round,pad=0.35,rounding_size=0.6", "facecolor": t["pill"],
                  "edgecolor": "none"})


def _save(fig, name: str, theme: str) -> Path:
    out = ASSETS / (f"{name}.png" if theme == "light" else f"{name}-dark.png")
    fig.savefig(out, dpi=DPI)
    plt.close(fig)
    return out


# ----------------------------------------------------------------------------- arena
def hero_arena(theme: str) -> Path | None:
    arena = _load("arena-2026-09.json")
    if not arena:
        return None
    t = THEMES[theme]
    _setup(t)
    rows = []
    for slug, j in arena.items():
        s = j["datasets"].get("email-adversarial")
        if s:
            kind = ("prob" if j["method"].startswith("option")
                    else "nli" if "NLI" in j["method"] or "softmax" in j["method"] else "verb")
            rows.append((ARENA_LABELS.get(slug, j["label"]), s["zero_error_coverage"],
                         s["accuracy"], s["mean_conf_wrong"], kind))
    rows.sort(key=lambda r: r[1], reverse=True)

    fig = plt.figure(figsize=(10.4, 5.6))
    ax = fig.add_axes((0.20, 0.13, 0.50, 0.62))
    _axes(ax, t, grid="x")
    ax.spines["bottom"].set_visible(False)
    n = len(rows)
    ys = list(range(n))[::-1]
    h = 0.58
    for y, (_label, cov, acc, cw, kind) in zip(ys, rows, strict=True):
        color = t[kind]
        if cov > 0:
            _rounded_bar(ax, 0, y - h / 2, cov, h, color, True, 0.06)
        else:
            _hairline(ax, 0, 0.004, y, y, color)
        ax.text(cov + 0.012, y, f"{cov:.0%}", va="center", ha="left", fontsize=11,
                fontweight="bold", color=t["ink"])
        ax.text(1.09, y, f"{acc:.0%}", va="center", ha="right", fontsize=10, color=t["ink"],
                transform=ax.get_yaxis_transform(), clip_on=False)
        ax.text(1.36, y, f"{cw:.2f}", va="center", ha="right", fontsize=10,
                color=t["wrong"] if cw >= 0.8 else t["ink"],
                transform=ax.get_yaxis_transform(), clip_on=False)
    ax.text(1.09, n - 0.3, "accuracy", va="bottom", ha="right", fontsize=8.5, color=t["muted"],
            transform=ax.get_yaxis_transform(), clip_on=False)
    ax.text(1.36, n - 0.3, "conf. when wrong", va="bottom", ha="right", fontsize=8.5,
            color=t["muted"], transform=ax.get_yaxis_transform(), clip_on=False)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10.5)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.legend(handles=[Patch(color=t["prob"], label="confidence = option probability"),
                       Patch(color=t["verb"], label="verbalized by a chat model"),
                       Patch(color=t["nli"], label="local encoder softmax")],
              frameon=False, loc="lower left", bbox_to_anchor=(-0.02, 1.07), ncol=3, fontsize=9,
              handlelength=1.2, columnspacing=1.4)
    _titles(fig, t, "The automation budget each judge earns",
            "200 emails under attack · share of decisions automatable with zero observed errors, "
            "most confident first",
            "examples/email-routing-adversarial · n=200 per judge · raw responses in docs/runs/ · "
            "fine-tuned rows trained on the clean emails' train half, same generator · judge-audit")
    return _save(fig, "hero-arena", theme)


# ------------------------------------------------------------------------------- arc
def hero_arc(theme: str) -> Path:
    t = THEMES[theme]
    _setup(t)
    real = _load("audit-jev-real.json")
    adv = _load("audit-jev-adversarial.json")
    router = _load("audit-jev-router.json")
    pi = adv["by_attack"]["prompt_injection"]
    hard = router["by_segment"]["clean_hard"]
    cols = [
        ("business emails\nclean · n=200", real["accuracy"],
         real["reliability_bins"][-1]["avg_confidence"], real["ece"]),
        ("emails under\nprompt injection · n=40", pi["accuracy"], pi["mean_confidence"], pi["ece"]),
        ("hard coding tasks\nas router · n=40", hard["accuracy"], hard["mean_confidence"],
         hard["ece"]),
    ]
    fig = plt.figure(figsize=(9.6, 5.6))
    ax = fig.add_axes((0.08, 0.24, 0.88, 0.52))
    _axes(ax, t, grid="y")
    w, gap = 0.34, 0.03
    for x, (_, acc, conf, ece) in enumerate(cols):
        _rounded_bar(ax, x - w - gap / 2, 0, w, conf, t["verb"], False, 0.03)
        if acc > 0:
            _rounded_bar(ax, x + gap / 2, 0, w, acc, t["prob"], False, 0.03)
        else:
            _hairline(ax, x + gap / 2, x + gap / 2 + w, 0.004, 0.004, t["prob"])
        ax.text(x - w / 2 - gap / 2, conf + 0.025, f"{conf:.2f}", ha="center", fontsize=10.5,
                fontweight="bold", color=t["ink"])
        ax.text(x + w / 2 + gap / 2, acc + 0.025, f"{acc:.0%}", ha="center", fontsize=10.5,
                fontweight="bold", color=t["wrong"] if acc == 0 else t["ink"])
        _pill(ax, x, -0.235, f"ECE {ece:.2f}", t)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c[0] for c in cols], fontsize=10)
    ax.tick_params(axis="x", pad=8)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.legend(handles=[Patch(color=t["verb"], label="mean confidence"),
                       Patch(color=t["prob"], label="accuracy")],
              frameon=False, loc="lower left", bbox_to_anchor=(-0.01, 1.03), ncol=2, fontsize=9,
              handlelength=1.2, columnspacing=1.4)
    _titles(fig, t, "Same judge, three jobs",
            "Jev is honest on easy email, honest under attack — and confidently wrong as a router",
            "three published Jev audits · raw responses in docs/runs/ · judge-audit")
    return _save(fig, "hero-arc", theme)


# ---------------------------------------------------------------------------- router
def hero_router(theme: str) -> Path:
    t = THEMES[theme]
    _setup(t)
    bare = _load("audit-jev-router.json")
    desc = _load("audit-jev-router-described.json")
    conds = [("BEFORE · options as bare labels", bare)]
    if desc:
        conds.append(("AFTER · options with one-line descriptions", desc))
    segs = ["clean_easy", "clean_hard", "adversarial"]

    fig = plt.figure(figsize=(11.2, 5.8))
    left, width, gap = 0.07, 0.42, 0.06
    for i, (kicker, d) in enumerate(conds):
        ax = fig.add_axes((left + i * (width + gap), 0.20, width, 0.50))
        _axes(ax, t, grid="y")
        if i:
            ax.set_yticklabels([])
        w, g = 0.34, 0.03
        for x, s in enumerate(segs):
            conf = d["by_segment"][s]["mean_confidence"]
            acc = d["by_segment"][s]["accuracy"]
            _rounded_bar(ax, x - w - g / 2, 0, w, conf, t["verb"], False, 0.03)
            if acc > 0:
                _rounded_bar(ax, x + g / 2, 0, w, acc, t["prob"], False, 0.03)
            else:
                _hairline(ax, x + g / 2, x + g / 2 + w, 0.004, 0.004, t["prob"])
            ax.text(x - w / 2 - g / 2, conf + 0.025, f"{conf:.2f}", ha="center", fontsize=10,
                    fontweight="bold", color=t["ink"])
            ax.text(x + w / 2 + g / 2, acc + 0.025, f"{acc:.0%}", ha="center", fontsize=10,
                    fontweight="bold", color=t["wrong"] if acc == 0 else t["ink"])
        n_strong = d["sanity"]["decisions"].get("route_strong", 0)
        ax.text(0, 1.07, kicker, fontsize=10.5, fontweight="semibold", color=t["ink"],
                transform=ax.transAxes, ha="left", va="bottom")
        ax.text(0, 1.01, f"chose the strong model {n_strong}/{d['n']} times · "
                f"ECE {d['overall']['ece']:.2f}",
                fontsize=9, color=t["muted"], transform=ax.transAxes, ha="left", va="bottom")
        ax.set_xticks(range(len(segs)))
        ax.set_xticklabels([SEG_LABELS[s] for s in segs], fontsize=9.5)
        ax.tick_params(axis="x", pad=6)
        ax.set_xlim(-0.6, len(segs) - 0.4)
        ax.set_ylim(0, 1.15)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    fig.legend(handles=[Patch(color=t["verb"], label="mean confidence"),
                        Patch(color=t["prob"], label="accuracy")],
               frameon=False, loc="upper right", bbox_to_anchor=(0.97, 0.965), ncol=2, fontsize=9,
               handlelength=1.2, columnspacing=1.4)
    _titles(fig, t, "Jev as a task router: how sure it is vs how often it is right",
            "Same model, same 120 tasks — two descriptive sentences on the options took hard tasks "
            "from 0 % to 92 % routed right",
            "examples/task-routing · n=120 per run · raw responses in docs/runs/ · judge-audit")
    return _save(fig, "hero-router", theme)


if __name__ == "__main__":
    for theme in ("light", "dark"):
        for p in (hero_arena(theme), hero_arc(theme), hero_router(theme)):
            if p:
                print("wrote", p.relative_to(ROOT))
