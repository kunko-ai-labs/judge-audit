# Ground truth: where the labels come from

"97 % on a constructed dataset" and "93 % on production outcomes" are not the same
evidence. Every judge-audit report therefore states the **provenance tier** of the
labels the judge was measured against, next to the accuracy — in the Markdown and
HTML report header, the CLI summary (`gt=GT-1`), the MCP `run_audit` result, the
Action's PR comment and the Arena dataset headings.

A tier is a provenance class, not a score. The code makes no ordering assumption
beyond the label; a reader compares two audits knowing what each accuracy is
evidence *of*.

## The tiers

Defined once in [`src/judge_audit/ground_truth.py`](../src/judge_audit/ground_truth.py);
the one-line meaning is what a report prints after the tier.

| Tier | Label | Meaning |
|---|---|---|
| GT-0 | unknown | provenance not declared; the accuracy carries no known evidential weight |
| GT-1 | constructed | labels are true by construction of a seeded generator; suitable for calibration stress testing, not evidence of real-world accuracy |
| GT-2 | synthetic, validated | synthetic items whose labels a human or an independent method checked |
| GT-3 | human-annotated | real items labelled by one annotator; annotator error is part of the ground truth |
| GT-4 | expert consensus | real items labelled by several qualified annotators with measured agreement |
| GT-5 | empirically validated | labels checked against an independent measurement of the same fact |
| GT-6 | production outcome | labels are what actually happened downstream; the strongest evidence |

The four published datasets under `examples/` are **GT-1**: routing labels are fixed
by the generator, email categories are synthetic and seeded, and downstream task
quality (does the cheap model really solve the "easy" tasks?) is not measured.
Their caveats say so in every report that uses them.

## What each tier lets you claim

The same accuracy number is evidence of different things depending on the tier. This
table is what a report is allowed to say out loud about a judge, given the tier of the
labels it was measured against — not a ranking of the tiers themselves.

| Tier | Calibration stress test | Comparison between judges on this data | Evidence about production behaviour |
|---|---|---|---|
| GT-0 unknown | ✗ | ✗ | ✗ |
| GT-1 constructed | ✓ | ✓ | ✗ |
| GT-2 synthetic, validated | ✓ | ✓ | with caveats |
| GT-3 human-annotated | ✓ | ✓ | with caveats |
| GT-4 expert consensus | ✓ | ✓ | with caveats |
| GT-5 empirically validated | ✓ | ✓ | ✓ |
| GT-6 production outcome | ✓ | ✓ | ✓ |

GT-0 supports no claim at all — an undeclared provenance means the accuracy carries no
known evidential weight, full stop. GT-1 through GT-4 can already stress-test
calibration and compare judges against each other, because both claims only need labels
that are *internally consistent*, not *true of the world*: a judge that is well
calibrated or better-calibrated-than-another on constructed labels really is, on those
labels. Only GT-5 and GT-6 support a claim about production behaviour without a
caveat, because only they check a label against something that happened independently
of the annotation — GT-2 through GT-4 read "with caveats" because a human or expert
panel's judgment, however careful, is not the same evidence as an outcome that actually
occurred.

## Declaring the tier: the dataset header line

A labels JSONL declares its provenance with **one header line as its first line**.
It is the only form the runner reads; rows never carry the tier.

```json
{"idx": -1, "dataset": {"ground_truth": {"tier": "GT-1", "label": "constructed", "validation": "not_validated", "purpose": ["calibration stress test"], "caveats": ["routing label by design", "downstream task quality not measured"]}}}
{"state": "...", "questions": [...], "labels": {...}, "_meta": {...}}
{"state": "...", "questions": [...], "labels": {...}, "_meta": {...}}
```

`ground_truth` fields:

| Field | Required | Meaning |
|---|---|---|
| `tier` | yes | one of `GT-0` … `GT-6`; anything else fails at load with `ValueError: unknown ground-truth tier` |
| `label` | no | must equal the tier's label when present (a readability aid, never a second source of truth) |
| `validation` | no | how the labels were checked, free text; default `not_validated` |
| `purpose` | no | list of strings: what the dataset is meant to measure |
| `caveats` | no | list of strings: what an accuracy on it cannot show; printed after the meaning |

Unknown fields inside `ground_truth` are an error (typos would otherwise vanish
silently). Other keys next to `ground_truth` inside `dataset` are kept in the header
object and ignored by the runner.

Without a header the report says
`Ground truth: GT-0 unknown — declare it with a dataset header line (see docs/ground-truth.md)`.
It is never silent.

## What the header changes and what it does not

- `judge_audit.runner.load_dataset(path) -> (rows, dataset)` returns the rows and the
  header's `dataset` object (`{}` when absent). `load_jsonl(path)` keeps returning the
  rows only; both validate the tier.
- `run_metadata` records `dataset.ground_truth` (tier, label, meaning, validation,
  purpose, caveats) so `audit-result.json` is self-describing for tools that do not
  import the package (the Action's PR comment is stdlib only).
- `dataset.sha256` still covers the whole file, header included. `dataset.sha256_rows`
  is the digest of the rows alone — it equals the `sha256` a checkpoint recorded
  before the header existed, which is how `scripts/verify_published.py` keeps the
  committed checkpoints tied to the labels files without editing raw evidence.
- Row indices (`idx` in checkpoints and judgments) count rows only; the header is not
  a row and a judge never sees it.

## Raising a tier

A dataset moves up a tier when the evidence does, not when the wording does: a
human review of the synthetic labels makes it GT-2; running the cheap model on the
"easy" routing tasks and checking it solves them would make the router datasets
GT-5. Regenerate the file with the new header, commit the checkpoint of the
validation run next to it, and the next report says so.
