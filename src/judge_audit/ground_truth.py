"""Ground-truth provenance tiers: where a dataset's labels come from.

A provenance class, not a score. "97 % on a constructed dataset" and "93 % on
production outcomes" are not the same evidence, and every report says which
one it is. The tiers are defined once here (the label and the one-line meaning
a report prints) and documented in docs/ground-truth.md.

A labels JSONL declares its tier with a dataset header as its first line:

    {"idx": -1, "dataset": {"ground_truth": {"tier": "GT-1", "validation": "not_validated",
                                              "purpose": [...], "caveats": [...]}}}

`runner.load_dataset` parses it; a tier the table does not know fails loudly.
The code makes no ordering assumption beyond the label.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# tier -> (label, one-line meaning printed next to the numbers)
TIERS: dict[str, tuple[str, str]] = {
    "GT-0": ("unknown",
             "provenance not declared; the accuracy carries no known evidential weight"),
    "GT-1": ("constructed",
             "labels are true by construction of a seeded generator; suitable for "
             "calibration stress testing, not evidence of real-world accuracy"),
    "GT-2": ("synthetic, validated",
             "synthetic items whose labels a human or an independent method checked"),
    "GT-3": ("human-annotated",
             "real items labelled by one annotator; annotator error is part of the ground truth"),
    "GT-4": ("expert consensus",
             "real items labelled by several qualified annotators with measured agreement"),
    "GT-5": ("empirically validated",
             "labels checked against an independent measurement of the same fact"),
    "GT-6": ("production outcome",
             "labels are what actually happened downstream; the strongest evidence"),
}

UNKNOWN_TIER = "GT-0"
HEADER_HINT = "declare it with a dataset header line (see docs/ground-truth.md)"
_FIELDS = ("tier", "label", "meaning", "validation", "purpose", "caveats")


@dataclass(frozen=True)
class GroundTruth:
    tier: str = UNKNOWN_TIER
    validation: str = "not_validated"
    purpose: tuple[str, ...] = field(default_factory=tuple)
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def label(self) -> str:
        return TIERS[self.tier][0]

    @property
    def meaning(self) -> str:
        return TIERS[self.tier][1]

    @property
    def declared(self) -> bool:
        return self.tier != UNKNOWN_TIER

    def to_dict(self) -> dict:
        """What run metadata records: the meaning travels with the tier so a stdlib
        consumer (the Action's PR comment) can print it without this module."""
        return {"tier": self.tier, "label": self.label, "meaning": self.meaning,
                "validation": self.validation,
                "purpose": list(self.purpose), "caveats": list(self.caveats)}

    def report_line(self) -> str:
        """`Ground truth: GT-1 constructed — <meaning>; <caveats>` — the line every report shows."""
        if not self.declared:
            return f"Ground truth: {self.tier} {self.label} — {HEADER_HINT}"
        tail = "; ".join((self.meaning, *self.caveats))
        return f"Ground truth: {self.tier} {self.label} — {tail}"


def parse_ground_truth(raw: dict | None) -> GroundTruth:
    """Validate a `ground_truth` object; None (no header) is GT-0. Unknown tiers fail loudly."""
    if raw is None:
        return GroundTruth()
    if not isinstance(raw, dict):
        raise ValueError(f"ground_truth must be an object, got {type(raw).__name__}")
    unknown = sorted(set(raw) - set(_FIELDS))
    if unknown:
        raise ValueError(f"ground_truth has unknown field(s) {unknown}; allowed: {list(_FIELDS)}")
    tier = raw.get("tier")
    if tier not in TIERS:
        raise ValueError(f"unknown ground-truth tier {tier!r}; known: {', '.join(TIERS)}")
    label, meaning = TIERS[tier]
    if "label" in raw and raw["label"] != label:
        raise ValueError(f"ground_truth label {raw['label']!r} does not match {tier} ({label!r})")
    if "meaning" in raw and raw["meaning"] != meaning:
        raise ValueError(f"ground_truth meaning for {tier} is defined by the tier table, "
                         "not by the dataset")
    validation = raw.get("validation", "not_validated")
    if not isinstance(validation, str) or not validation:
        raise ValueError("ground_truth.validation must be a non-empty string")
    lists = {}
    for key in ("purpose", "caveats"):
        value = raw.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise ValueError(f"ground_truth.{key} must be a list of strings")
        lists[key] = tuple(value)
    return GroundTruth(tier=tier, validation=validation, **lists)


def ground_truth_of(run: dict | None) -> GroundTruth:
    """The tier a recorded run carries (`run.dataset.ground_truth`), GT-0 when absent."""
    ds = (run or {}).get("dataset") or {}
    return parse_ground_truth(ds.get("ground_truth"))
