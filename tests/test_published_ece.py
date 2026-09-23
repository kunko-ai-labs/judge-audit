"""What US-004-012 publishes next to the ECE leaves the ECE alone, and says when a point
estimate falls outside its own interval.

Adding the equal-mass ECE and the Brier score must leave every published ECE exactly as
it was. `tests/published_ece.json` holds every ECE value (`ece`, `vote_share_ece`, …) of
every JSON under `docs/`, keyed by file and JSON path, as committed on this branch's base
before the new numbers existed. The regeneration steps in CI prove the committed JSON is
what the code produces today; this test proves the committed JSON still carries the old
values — together, the code computes the same ECE it always did.

The snapshot is taken from the base branch, never from a working tree with new code:

    mkdir /tmp/base && git archive <base> docs | tar -x -C /tmp/base
    python tests/test_published_ece.py /tmp/base > tests/published_ece.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from judge_audit.metrics.calibration import BOOTSTRAP, Interval, ci_fields
from judge_audit.report import OUTSIDE_MARK, interval_notes, interval_of

SNAPSHOT = Path(__file__).resolve().parent / "published_ece.json"


def ece_values(obj, path: str = "") -> dict[str, float]:
    """Every numeric value whose key is an equal-width ECE, by JSON path."""
    out: dict[str, float] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}/{k}"
            if (k == "ece" or k.endswith("_ece")) and isinstance(v, (int, float)):
                out[p] = v
            else:
                out.update(ece_values(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(ece_values(v, f"{path}/{i}"))
    return out


def published(root: Path) -> dict[str, dict[str, float]]:
    snap = {}
    for f in sorted((root / "docs").rglob("*.json")):
        vals = ece_values(json.loads(f.read_text(encoding="utf-8")))
        if vals:
            snap[f.relative_to(root).as_posix()] = vals
    return snap


def test_every_published_ece_is_unchanged(root):
    before = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    now = published(root)
    assert sum(len(v) for v in before.values()) > 300          # the snapshot is not empty
    moved = [f"{f}{p}: {v} -> {now.get(f, {}).get(p, 'missing')}"
             for f, vals in before.items() for p, v in vals.items()
             if now.get(f, {}).get(p) != v]
    assert not moved, f"{len(moved)} published ECE values changed:\n" + "\n".join(moved[:10])


def test_the_new_numbers_are_not_mistaken_for_ece():
    vals = ece_values({"ece": 0.1, "ece_equal_mass": 0.2, "brier": 0.3, "ece_ci": [0, 1],
                       "vote_share_ece": 0.4, "x": [{"ece": 0.5}]})
    assert vals == {"/ece": 0.1, "/vote_share_ece": 0.4, "/x/0/ece": 0.5}


# --- a point outside its own percentile interval is marked, never silent --------------


def point_interval_pairs(obj, path: str = ""):
    """Every published (x, x_ci) pair: (path, point, [lo, hi], flagged)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith("_ci") and isinstance(v, list) and len(v) == 2:
                base = k[:-3]
                x = obj.get(base)
                if isinstance(x, dict):                    # zero_error_coverage is a dict
                    x = x.get("coverage")
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    yield f"{path}/{base}", x, v, obj.get(f"{k}_point_outside") is True
            yield from point_interval_pairs(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from point_interval_pairs(v, f"{path}/{i}")


def test_every_published_point_is_in_its_interval_or_marked(root):
    bad, marked = [], 0
    for f in sorted((root / "docs").rglob("*.json")):
        for path, x, (lo, hi), flagged in point_interval_pairs(
                json.loads(f.read_text(encoding="utf-8"))):
            inside = lo <= x <= hi
            marked += flagged
            if inside == flagged:          # outside and silent, or flagged while inside
                bad.append(f"{f.relative_to(root)}{path}: {x} [{lo}, {hi}] flagged={flagged}")
    assert not bad, "\n".join(bad[:10])
    assert marked >= 2        # DeBERTa NLI, described router, equal-mass ECE (Arena + run)


def test_every_marked_report_prints_the_mark_and_its_legend(root):
    """A ◊ in a table means nothing without the line that defines it."""
    for md in [root / "README.md", *sorted((root / "docs").rglob("*.md"))]:
        if OUTSIDE_MARK in md.read_text(encoding="utf-8"):
            assert "outside its own percentile-bootstrap interval" in md.read_text(
                encoding="utf-8"), md.name
    arena = (root / "docs" / "arena-2026-09.md").read_text(encoding="utf-8")
    assert re.search(r"0\.2131 \[0\.2425, 0\.4501\]" + OUTSIDE_MARK, arena)


def test_ci_fields_flags_a_point_outside_and_nothing_else():
    ci = Interval(0.2425, 0.4501, BOOTSTRAP)
    out = ci_fields("x", ci, 0.2131)
    assert out["x_ci_point_outside"] is True
    assert "x_ci_point_outside" not in ci_fields("x", ci, 0.3)
    assert "x_ci_point_outside" not in ci_fields("x", ci)             # no point, no claim
    assert "x_ci_point_outside" not in ci_fields("x", ci, 0.2425)     # the edge is inside
    assert "x_ci_point_outside" not in ci_fields("x", Interval(0.1, 0.1, BOOTSTRAP), 0.3)
    shown = interval_of({"x": 0.2131, **out}, "x_ci")
    assert shown == f" [0.2425, 0.4501]{OUTSIDE_MARK}"
    assert len(interval_notes(shown)) == 1


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    print(json.dumps(published(base), indent=1, sort_keys=True))
