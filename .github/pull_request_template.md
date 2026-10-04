## What and why

<!-- One paragraph. Link the issue: Closes #… -->

## Evidence

<!-- What you verified and how. For a new or changed number: the checkpoint, the command, and that the report regenerates from it. -->

## Checks

- [ ] `ruff check src tests scripts examples` and `mypy`
- [ ] `pytest -q` (tests for the change written first)
- [ ] `python scripts/verify_published.py` and `python scripts/verify_readme.py`
- [ ] No API key, customer data or platform name in code, logs or reports
