---
name: "🐛 Bug report"
about: "A wrong metric, a crash, a fabricated confidence or an integration that does not behave as documented"
title: "[BUG] "
labels: ["type:bug"]
assignees: ""
---

## What happened

<!-- One or two sentences. -->

## How to reproduce

```bash
pip install kunko-judge-audit==<version>
judge-audit ...
```

<!-- The smallest input that shows it: a few rows of labels.jsonl, or one of the examples/ datasets. -->

## Expected vs got

| | value |
|---|---|
| expected | |
| got | |

Why the expected value is right (a hand computation, a reference, the docs line):

## Environment

- judge-audit version (`judge-audit --version`):
- Python version and OS:
- Judge (`--judge …`) and model, if not simulated:

<!-- Never paste an API key or a customer's data. -->
