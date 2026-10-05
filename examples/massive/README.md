# MASSIVE 1.1 in English, Spanish and Catalan (human-labelled, GT-3)

The same 2,974 test utterances in `en-US`, `es-ES` and `ca-ES`, each labelled with one of 60 intents of a home voice assistant (set an alarm, play a podcast, ask the weather). Row *k* is the same item in every locale: MASSIVE's `id` is in `_meta.id`, and every file lists the items in the same order.

**Caveat that travels with every number measured on these files: translated parallel data, not native traffic; labels from SLURP annotation carried over by localisation.** The `en-US` utterances are SLURP's English text, collected for a research corpus; `es-ES` and `ca-ES` are their localisations, and the intent label of each localised utterance is the English one, not a new annotation.

- **Source:** the MASSIVE 1.1 release archive, [`amazon-massive-dataset-1.1.tar.gz`](https://amazon-massive-nlu-dataset.s3.amazonaws.com/amazon-massive-dataset-1.1.tar.gz), the file the [alexa/massive](https://github.com/alexa/massive) README and the [Hugging Face loader](https://huggingface.co/datasets/AmazonScience/massive) (revision `ff6bd8e4b27c3543e4f8fe2108f32bb95a6f8740`) point to. The archive is served without a commit, so it and each member used are pinned by sha256 in `scripts/fetch_real_datasets.py`.
- **Authors and citation:** Jack FitzGerald, Christopher Hench, Charith Peris, Scott Mackie, Kay Rottmann, Ana Sanchez, Aaron Nash, Liam Urbach, Vishesh Kakarala, Richa Singh, Swetha Ranganath, Laurie Crist, Misha Britan, Wouter Leeuwis, Gokhan Tur and Prem Natarajan, *MASSIVE: A 1M-Example Multilingual Natural Language Understanding Dataset with 51 Typologically-Diverse Languages*, ACL 2023 ([arXiv:2204.08582](https://arxiv.org/abs/2204.08582)). Derived from SLURP: Emanuele Bastianelli, Andrea Vanzo, Pawel Swietojanski and Verena Rieser, *SLURP: A Spoken Language Understanding Resource Package*, EMNLP 2020.
- **Licence:** [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) (the archive's `1.1/LICENSE`, "Copyright Amazon.com Inc. or its affiliates"). The archive's `1.1/NOTICE.md` states that MASSIVE translates and localises SLURP's English text, includes some of it, and that SLURP is CC BY 4.0. The files here are adapted from the original and distributed under the same licence.
- **Changes:** the `test` partition of each locale, and a seeded sample of the `dev` partition, converted to the judge-audit labels format: one `intent` question per utterance, the 60 intent identifiers in alphabetical order as options, English instructions, a dataset header line with provenance and caveats. Texts (`utt`) and intents are unchanged; `_meta` keeps the `id`, the `scenario`, the line in the upstream file (`source_index`) and, for `es-ES` and `ca-ES`, the localisation judges' answers to "Does the sentence match the intent?" (`intent_judgments`: 0 No, 1 Yes, 2 a reasonable interpretation of the goal). The slot annotation, worker IDs and other judgment fields are dropped.

## Upstream, as verified from the archive

| locale | train | dev | test | ids missing vs `en-US` | intent differs from `en-US` |
|---|---|---|---|---|---|
| `en-US` | 11,514 | 2,033 | 2,974 | — | — |
| `es-ES` | 11,514 | 2,033 | 2,974 | 0 | 0 |
| `ca-ES` | 11,514 | 2,033 | 2,974 | 0 | 0 |

All 60 intents (18 scenarios) occur in train; **dev has no `audio_volume_other`, and test has no `cooking_query`** (it stays an option, never the right answer). `general_greet` has one test utterance. The conversion refuses to write anything if a locale lacks or adds an id in any split, or gives an id another intent.

## The files

| file | rows | distinct texts (case and whitespace ignored) | repeated texts: groups / one with two labels | test text also in train or dev | a localisation judge said the intent does not match: one / a majority | bytes | sha256 |
|---|---|---|---|---|---|---|---|
| `labels-test-en-US.jsonl` | 2,974 | 2,970 | 4 / 0 | 26 | — | 4,374,243 | `29934c9c78208c60db4ee6520956eda2acde5f154bcd308108005f6cc216569f` |
| `labels-test-es-ES.jsonl` | 2,974 | 2,944 | 25 / 0 | 156 | 76 / 0 | 4,484,306 | `fd039ab57059d9951348f484a4bbdc428ef5c12670d5a28e13c3295448ac46b4` |
| `labels-test-ca-ES.jsonl` | 2,974 | 2,933 | 33 / 1 | 206 | 120 / 19 | 4,483,445 | `91daf95da295c5d6fafe2d53f66008cceea23d9a98885ba8d207b79130287d38` |
| `labels-pilot-en-US.jsonl` | 230 | 230 | 0 / 0 | — | — | 334,736 | `76c5290c672b561eb5719826b8a916226f6007727c722a46b775a67fc191aee9` |
| `labels-pilot-es-ES.jsonl` | 230 | 230 | 0 / 0 | — | 5 / 0 | 343,367 | `51631f6c4e77ae127a22e5399e3dcea95d9040d936e858e2778a2b6e7c852a45` |
| `labels-pilot-ca-ES.jsonl` | 230 | 230 | 0 / 0 | — | 5 / 0 | 343,421 | `3ba8f67d17ba174c8a16095c474227902b95cb4fb9b92b121256704cf98cccb2` |

- **Repeated texts** follow the repository's one rule (`normalise`: case and whitespace ignored), within one file; each header names the rows that repeat a text, and clustered statistics must count them as one text. The Spanish and Catalan files repeat a text more often than the English one (25 and 33 groups against 4). In `ca-ES`, rows 17 and 1426 hold one text labelled `calendar_query` and `datetime_query`.
- **Test texts also in train or dev** (same locale, same rule) are marked `_meta.text_in_train`.
- **The pilot** is up to 4 `dev` utterances per intent, drawn with `random.Random(2026)` over the intents in alphabetical order, the same items in every locale; dev has fewer for four intents (`audio_volume_other` 0, `cooking_query`, `general_greet` and `music_dislikeness` 2), hence 230 rows, not 240. It comes from dev, not train, so a classifier fine-tuned on train has never seen it. It is for token counts, throughput and variance before the pre-registration fixes *n*, never to score a judge.
- **Not committed:** the whole train and dev splits (about 51 MB and 9 MB in this format for the three locales), for fine-tuning a classifier: `python scripts/fetch_real_datasets.py --massive-full DIR` writes `labels-{train,dev}-<locale>.jsonl` to `DIR` from the same pinned archive.

## Questions and criteria: one language arm today

Every file asks in English (`"Which intent does this request to a voice assistant express? Choose exactly one."`), whatever the language of the utterance; the header's `criteria` says so (`language: en`) and who wrote the wording (the maintainers; the options are MASSIVE's identifiers, unchanged, without definitions — MASSIVE ships no intent descriptions in any language). A translated-criteria arm is another criteria object of the same shape (`MASSIVE_ENGLISH_CRITERIA` in `scripts/fetch_real_datasets.py`) passed to `massive()`: it must say in `origin` who translated it, and it changes the instructions and optional descriptions only, never the option identifiers or the labels. None is written yet; whether to add one is a decision for the v0.6 pre-registration.

## Caveats

- Public since 2022: probably in the pretraining data of the judges audited.
- SLURP's utterances are requests to a home voice assistant collected for a research corpus, not production traffic; one intent each, and MASSIVE publishes no inter-annotator agreement on the intent labels. Label noise is not measured here.
- `es-ES` and `ca-ES` were localised from `en-US`. The paper says professional translators did it; the upstream card names each localiser and judge by an obfuscated MTurk worker ID. `ca-ES` was added in MASSIVE 1.1, after the paper (51 languages), which does not describe its localisation.
- The question wording, the options and the pilot are drafts until the v0.6 pre-registration ([#132](https://github.com/kunko-ai-labs/judge-audit/issues/132)) fixes them. No judge has been run on these files and no metric computed.

Regenerate and verify against the pinned archive: `python scripts/fetch_real_datasets.py --check` (downloads the 40 MB archive; `--src DIR` reads `DIR/massive/amazon-massive-dataset-1.1.tar.gz` offline).

### Pinned upstream files

| file | sha256 |
|---|---|
| `amazon-massive-dataset-1.1.tar.gz` (40,251,390 bytes) | `4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577` |
| `1.1/LICENSE` | `c2e6ea015269147de02117ebdd91f30ef09831251f5345fa8365273b1db1d435` |
| `1.1/NOTICE.md` | `b90534ccd20c6f0e1e5239567af0d150496339542b75a15bfbc3e1e737593ddb` |
| `1.1/data/en-US.jsonl` | `c70f75c6a543a26e249ec383df67733ad9b1066f6c0406c2e04a3f03356e407e` |
| `1.1/data/es-ES.jsonl` | `310462a79fa181ff83c643a8d356c7b8155fd37a25e80a77ba3ca9b29305c4a5` |
| `1.1/data/ca-ES.jsonl` | `7da25fa3f731ea96dc9caa48363863c117c652ad628e5c7be0d9fdab7ccb7ed3` |
