# CLINC150, banking and credit-card domains plus out-of-scope queries (human-labelled, GT-3)

Requests to a task-oriented assistant, each labelled with one of 150 intents in 10 domains, or as out of scope.

- **Source:** [clinc/oos-eval](https://github.com/clinc/oos-eval), `data/data_full.json` and `data/domains.json`, commit `828f8093932c8fe6ca7936c3d2e52903b1c523de`.
- **Authors and citation:** Stefan Larson, Anish Mahendran, Joseph J. Peper, Christopher Clarke, Andrew Lee, Parker Hill, Jonathan K. Kummerfeld, Kevin Leach, Michael A. Laurenzano, Lingjia Tang and Jason Mars, *An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction*, EMNLP-IJCNLP 2019.
- **Licence:** [Creative Commons Attribution 3.0 Unported](https://creativecommons.org/licenses/by/3.0/) (the upstream repository's `LICENSE`). The file here is adapted from the original.
- **Changes:** the test split restricted to the `banking` and `credit_cards` domains (30 intents, 900 queries) plus all 1,000 out-of-scope test queries, relabelled `out_of_scope`; converted to the judge-audit labels format with the 30 intent names and `out_of_scope` as options. Texts and in-scope labels are unchanged.

The domain subset is a draft until the v0.5 pre-registration fixes it. Regenerate and verify: `python scripts/fetch_real_datasets.py --check`.
