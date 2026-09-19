# Security policy

judge-audit reads a labeled JSONL file, calls the judge you configure, and writes reports. It never automates a decision, never sends your data anywhere except to the judge endpoint you chose, and never reads a secret's value beyond the API key variable you set. If you find a way to make it do any of those things, or a way to make an audit report a judge as *more* calibrated than the raw judgments show, that is a security issue.

**Report privately:** open a [GitHub security advisory](https://github.com/kunko-ai-labs/judge-audit/security/advisories/new) with a minimal dataset or checkpoint that reproduces it. You will get a reply within 7 days.

**Not security issues (open a normal issue):** a metric you would compute differently, a dataset row you think is mislabeled, an adapter for a judge we do not support yet. Those are methodology questions and we want them in the open.

**Raw audit evidence** under `docs/runs/` contains vendor responses to synthetic inputs only. Never commit a checkpoint produced from real customer data.

Supported: the latest minor release (`vX.Y`). Fixes ship as a patch on it.
