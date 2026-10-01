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

The human-labelled datasets added for v0.5 ([#86](https://github.com/kunko-ai-labs/judge-audit/issues/86))
are **GT-3**: human-written queries with one label each and no inter-annotator agreement
published. CLINC150's (`examples/clinc150/`) were written by crowd workers to a prompt
(paraphrase a seed phrase, or answer a scenario, for a given intent; Larson et al. 2019), so
they are not production traffic. BANKING77's (`examples/banking77/`) are online-banking
customer-service queries per their authors; how they were collected and labelled is not
documented upstream. Their label noise is **not yet measured**: a random sample (500 rows
per dataset, `examples/*/relabel-sample.json`, drawn and committed before anyone labels it)
is ready for two annotators blind to the label (`scripts/relabel.py`). Once scored, it gives
the share of rows both annotators label differently from the dataset, with a Wilson 95 %
interval; the adjudicated sample is what can be reported as GT-4.

### The v2 synthetic stress sets ([#87](https://github.com/kunko-ai-labs/judge-audit/issues/87))

The v1 synthetic files stay as they are: the published audits were run on them, so they
are frozen evidence and are never regenerated with new content (`scripts/synthetic_v2.py
--check` pins their sha256). Their weakness is documented next to their numbers
([#54](https://github.com/kunko-ai-labs/judge-audit/issues/54)): texts repeat within a
file, and some attacked emails are clean emails. The v2 sets are for the audits to come.
They are still **GT-1**: synthetic and seeded, each label true by construction of its
template, never checked by a person. A score on them is a stress test, not evidence of
accuracy on real mail or real routing. No audit has been run on them yet.

| File | Rows | Distinct texts | Templates dev / held out | Rows dev / held out |
|---|---|---|---|---|
| `examples/email-routing-v2/labels.jsonl` | 1000 | 1000 | 60 / 20 | 750 / 250 |
| `examples/email-routing-adversarial-v2/labels.jsonl` | 1000 | 1000 | 105 / 31 | 761 / 239 |
| `examples/task-routing-v2/labels.jsonl` | 1050 | 1050 | 72 / 24 | 784 / 266 |

What changed against v1:

- **No repeated text.** No two rows share a `state` once case and whitespace are ignored
  (the rule of `scripts/fetch_real_datasets.py`). Every email of the adversarial file,
  controls included, is built on a base email (`_meta.base`) that appears nowhere in the
  clean file, and no two share one; no attacked router task is the text of a clean row.
- **More templates and vocabulary.** 80 email templates instead of 24 (four English and
  four German per category), 32 items instead of 8, and company, sender, city, country and
  date fills; 20 ambiguous, 16 injection, 10 social-engineering and 10 PII templates
  instead of 10, 8, 5 and 5; 40 easy and 40 hard coding-task families instead of 14 and
  14, and 16 cost-inflation injections instead of 8. The label schema, the questions and
  the header line are v1's.
- **A template-level split, committed before any use.** Each directory's
  `split-templates.json` names the development and the held-out templates: a quarter of
  each stratum (category × language for emails, family × language for attacks, difficulty
  for coding tasks), drawn with one seed fixed before any file existed. A row is held out
  when every template it was built from is; the adversarial file keeps the clean file's
  halves for the email templates. v1 counts as development data (its files back the
  published audits and `split-heldout.json`'s training halves), so no held-out template
  shares a run of six words (slots count as words, digits and punctuation do not) with a
  v2 development template or with any string of the v1 generators; the check enforces it.

**The held-out rule: held-out templates are never used in development.** No prompt
wording, few-shot example, training row, threshold or calibration fit may come from a row
built on one; held-out rows are scored once, under a pre-registered protocol. Rows of one
template differ only in their fills, so they are near-duplicates by design: a score on
rows whose templates were seen in development says how well a judge fits those templates.
Held out means precisely this: templates never used in development and sharing no run of
six words with a development template or with v1. It does not mean unseen topics or
vocabulary: shorter phrases ("for an empty list"), the categories, the items, companies
and other fill values, the homoglyph disguises, and the router's openings and style
requests appear on both sides. A held-out score measures new sentence templates for
familiar intents, not new intents.

## What each tier lets you claim

The same accuracy number is evidence of different things depending on the tier. This
table is what a report is allowed to say out loud about a judge, given the tier of the
labels it was measured against — not a ranking of the tiers themselves.

| Tier | Calibration stress test | Comparison between judges on this data | Evidence about production behaviour |
|---|---|---|---|
| GT-0 unknown | ✗ | ✗ | ✗ |
| GT-1 constructed | ✓ | ✓ | ✗ |
| GT-2 synthetic, validated | ✓ | ✓ | ✗ |
| GT-3 human-annotated | with caveats (label noise) | with caveats (label noise) | with caveats |
| GT-4 expert consensus | ✓ | ✓ | with caveats |
| GT-5 empirically validated | ✓ | ✓ | with caveats (only if items are sampled from production) |
| GT-6 production outcome | ✓ | ✓ | ✓ |

**GT-0** supports no claim at all — an undeclared provenance means the accuracy carries
no known evidential weight, full stop.

**Calibration and comparison need labels that are right for these items**, not items
that look like production. GT-1 labels are right by construction and GT-2 labels were
checked, so a judge that is well calibrated, or better calibrated than another, on them
really is — on those items. A GT-3 label is one annotator's call, and an unmeasured share
of such labels is wrong. A wrong label moves the numbers even for a perfectly calibrated
judge: ten answers at confidence 0.9, nine of them right, have ECE 0.000 against reality;
mislabel one of the nine right rows and ECE against the labels is 0.100. The same noise
blurs a comparison, because a judge is penalised for agreeing with the truth where the
label is wrong. GT-4 measures its annotators' agreement, so the size of that residual
noise is known and can be reported next to the number.

**Production behaviour needs items that come from production.** GT-1 and GT-2 items are
synthetic, so neither says anything about how the judge behaves on real traffic, however
good its labels. GT-3 and GT-4 items are real, but they are evidence about production only
if they were drawn from the deployment's own traffic, and GT-3 carries the label noise
above. GT-5 checks every label against an independent measurement, which makes the labels
strong but says nothing about where the items came from: it is evidence about production
only when the items were sampled from production. Only GT-6 — what actually happened
downstream of real production items — supports the claim without a caveat.

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
