# BANKING77 (human-labelled, GT-3)

Online-banking customer-service queries, each labelled with one of 77 intents. How the queries were collected and labelled is not documented upstream; no inter-annotator agreement is published.

- **Source:** [PolyAI-LDN/task-specific-datasets](https://github.com/PolyAI-LDN/task-specific-datasets), `banking_data/`, commit `57ec275d8078af65b7731c2a98be812d844a6d6b`.
- **Authors and citation:** Iñigo Casanueva, Tadas Temcinas, Daniela Gerz, Matthew Henderson and Ivan Vulic, *Efficient Intent Detection with Dual Sentence Encoders*, 2nd Workshop on NLP for ConvAI, ACL 2020.
- **Licence:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) (the upstream repository's `LICENSE`). The files here are adapted from the original and distributed under the same licence.
- **Changes:** converted from CSV to the judge-audit labels format (one `intent` question per query, the 77 label names from `categories.json` as options, a dataset header line with provenance and caveats). Texts and labels are unchanged. `labels-pilot.jsonl` is a seeded sample of the train split (4 queries per intent).

| file | rows | what for |
|---|---|---|
| `labels-test.jsonl` | 3,080 (the official test split; 3,079 distinct texts ignoring case and whitespace: rows 1441 and 1461 differ by a leading newline, same label) | the v0.5 benchmark |
| `labels-pilot.jsonl` | 308 (train split) | the pilot before the pre-registration; never scored in the study |
| `relabel-sample.json` | 500 test indices | a random sample for two blind annotators (`scripts/relabel.py`); label noise is not measured until it is labelled and scored |

Regenerate and verify against the pinned upstream files: `python scripts/fetch_real_datasets.py --check`. Caveats (public since 2020, probably seen in pretraining; over 1,400 of the 10,003 train queries, about 14 %, flagged as possibly mislabelled by automated detection in [Ying & Thomas 2022](https://aclanthology.org/2022.insights-1.19/), not by relabelling; misleading label names) are in each file's header and printed by every report.
