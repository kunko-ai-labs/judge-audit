<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.png">
  <img src="docs/assets/logo.png" alt="judge-audit — calibration audits for AI judges" width="720">
</picture>

[![CI](https://github.com/kunko-ai-labs/judge-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/kunko-ai-labs/judge-audit/actions/workflows/ci.yml) [![Release](https://github.com/kunko-ai-labs/judge-audit/actions/workflows/release.yml/badge.svg)](https://github.com/kunko-ai-labs/judge-audit/actions/workflows/release.yml) [![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**Independent calibration audits for AI judges. When a judge says 90 %, is it right 90 % of the time?**

Everyone is shipping judgment models — TypeSafe's Jev, LLM-as-judge, guardrails, routers — and every one of them returns a confidence. The literature studies calibration (Guo et al. 2017; Shao 2026; Huang et al. 2026) — almost nobody measures it on *their own* decisions before automating them. judge-audit runs any judge in **shadow mode** against decisions your humans already made and answers the four questions that matter before you automate:

| Question | Metric | Why a buyer cares |
|---|---|---|
| When it says 80 % confident, is it right 80 % of the time? | ECE, reliability diagram | A confident-and-wrong judge automates its own mistakes |
| What share of the work can I automate at zero observed errors? | accuracy-coverage curve, zero-error coverage | This is the ROI number |
| What does it really cost, and how bad is the latency tail? | $ per decision, p50 / p99 | The demo is cheap; the tail is what pages you |
| Has it drifted since last week? | `judge-audit check` CI gate | Vendors update models without telling you |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-arena-dark.png">
  <img alt="200 emails under attack: the share of decisions each judge lets you automate with zero observed errors" src="docs/assets/hero-arena.png">
</picture>

![judge-audit run on a labeled dataset, then the CI gate](docs/demo.gif)

```bash
pip install kunko-judge-audit           # every release ships Sigstore-signed build provenance
judge-audit run examples/email-routing/labels.jsonl --judge simulated   # no API key needed
judge-audit check examples/email-routing/labels.jsonl --judge simulated --baseline audit-result.json
```

▶ [24-second launch video](https://github.com/kunko-ai-labs/judge-audit/releases/download/v0.3.0/brag.mp4) · [vertical cut](https://github.com/kunko-ai-labs/judge-audit/releases/download/v0.3.0/brag-vertical.mp4)

`simulated` is a seeded simulator so you can see the whole pipeline in ten seconds; every report it touches is stamped **SIMULATED**. To audit a real vendor, see [docs/real-audits.md](docs/real-audits.md).

## The first independent audits of Jev

Same judge (TypeSafe Jev, via Vercel AI Gateway), three jobs, every raw response committed under [`docs/runs/`](docs/runs/) so anyone can recompute every number (`python scripts/verify_published.py` does, in CI).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-arc-dark.png">
  <img alt="Same judge, three jobs: honest, honest under attack, confidently wrong" src="docs/assets/hero-arc.png">
</picture>

| Audit | n | Accuracy | ECE | What it shows | Report |
|---|---|---|---|---|---|
| Business emails, 10 categories, clean | 200 | 100 % | 0.004 | Honest when the task is easy. Synthetic templates with the category keyword in the text — a floor, not a benchmark. | [audit-jev-real.md](docs/audit-jev-real.md) |
| Same emails under attack: prompt injection, homoglyphs, ambiguity, PII, social engineering | 200 | 95.5 % | 0.039 | Prompt injection flips 7/40 decisions, **but confidence drops from 0.996 to 0.71 under attack** — the judge signals its own doubt. Homoglyphs and social engineering: 0 successes. Ambiguous emails: confidence does *not* drop (0.95), which it should. | [audit-jev-adversarial.md](docs/audit-jev-adversarial.md) |
| Task router: cheap model vs frontier model, 40 easy / 40 hard / 40 easy + cost-inflation injection | 120 | 66.7 % | 0.318 | With options sent as bare labels the judge **never** chose the strong model: 0/40 on hard tasks at median confidence 0.96. That is exactly the constant-classifier baseline. | [audit-jev-router.md](docs/audit-jev-router.md) |
| The same 120 rows with a one-line description per option | 120 | 97.5 % | 0.053 | **37/40 hard tasks now go to the strong model**, and the three misses sit at confidence 0.56–0.60 (vs 0.93 when right). Same model, same tasks: the failure was the prompt — and nothing but a calibration audit reveals it. | [audit-jev-router-ablation.md](docs/audit-jev-router-ablation.md) |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/hero-router-dark.png">
  <img alt="Jev as a task router: bare labels vs described options" src="docs/assets/hero-router.png">
</picture>

**What we would tell a client.** The email numbers are the vendor's story and they hold up, including under attack. The router numbers are the buyer's story: the first prompt anyone would write routed every hard task to the cheap model at 96 % median confidence, and its 66.7 % accuracy is exactly what a coin glued to "easy" scores; two descriptive sentences took the same judge to 97.5 % with confidence that finally means something. None of that is visible from a benchmark leaderboard; all of it is visible from a calibration audit on your own decisions.

Honest limits: every dataset is synthetic and seeded (generators in `examples/`); n is small; ground truth for routing is by construction, not by running the cheap model. Read the *Caveats* section of each report before quoting it.

## The Arena: same datasets, other judges

Every judge below ran the same four datasets through the same harness; raw responses under [`docs/runs/arena/`](docs/runs/arena/), full table in [docs/arena-2026-09.md](docs/arena-2026-09.md), regenerated in CI (the chart at the top is the zero-error column of this table). Emails under attack (n=200) and the described-options router (n=120); brackets are 95 % bootstrap intervals over the dataset's distinct texts — how far the number would move on another sample of this size — except where the bootstrap cannot move at all, marked **†**, which carries the exact Clopper–Pearson binomial interval instead ([method](docs/judges.md#confidence-intervals)):

| judge | confidence | accuracy | ECE | zero-error coverage | conf right / wrong | conf drop under injection | router (described) | cost-inflation attacks that land | cost / 200 |
|---|---|---|---|---|---|---|---|---|---|
| Jev (TypeSafe) | option probability | 95.5% [92.5, 98.0] | 0.039 [0.028, 0.066] | **73%** [67.0, 94.0] | 0.93 / 0.60 | +0.28 | 97.5% [91.9, 100.0] | 0/40 | $0.004 |
| Claude Sonnet 4.5 | verbalized | 96.5% [93.9, 99.0] | 0.016 [0.005, 0.040] | **0%** [0.0, 90.9] | 0.96 / 0.88 | +0.03 | 95.0% [90.3, 98.5] | 6/40 | $0.454 |
| Gemini 3 Flash | verbalized | 97.0% [94.5, 99.0] | 0.015 [0.002, 0.040] | **0%** [0.0, 1.8]† | 0.98 / 0.98 | +0.02 | 98.3% [95.5, 100.0] | 2/40 | $0.026 |
| Llama 3.3 70B | verbalized | 90.5% [86.1, 94.5] | 0.015 [0.005, 0.060] | **0%** [0.0, 1.8]† | 0.90 / 0.82 | +0.06 | 86.7% [78.5, 93.4] | 16/40 | $0.041 |
| DeepSeek R1 | verbalized | 80.5% [74.8, 85.6] | 0.127 [0.076, 0.184] | **0%** [0.0, 1.8]† | 0.94 / 0.90 | +0.05 | 79.2% [69.9, 86.9] | 24/40 | $0.589 |
| gemma4 e4b (local) | verbalized | 81.0% [75.5, 86.4] | 0.153 [0.100, 0.211] | **0%** [0.0, 1.8]† | 0.96 / 0.97 | +0.01 | 77.5% [67.2, 87.1] | 27/40 | $0.000 |
| llama3.2 3B (local) | verbalized | 72.5% [65.2, 79.7] | 0.154 [0.085, 0.231] | **0%** [0.0, 1.8]† | 0.87 / 0.91 | -0.03 | 59.2% [45.5, 73.0] | 9/40 | $0.000 |
| DeBERTa-v3 NLI zero-shot (local) | NLI entailment softmax over options | 59.5% [51.7, 66.7] | 0.125 [0.088, 0.201] | **8%** [3.9, 16.0] | 0.73 / 0.56 | +0.09 | 49.2% [34.9, 62.8] | 39/40 | $0.000 |
| DeBERTa-v3 fine-tuned, run 1 (local; your own classifier, pre-registered) | softmax of the chosen option | 97.0% [94.4, 99.0] | 0.496 [0.470, 0.522] | **97%** [94.4, 99.0] | 0.48 / 0.15 | +0.09 | 100.0% [94.0, 100.0]† (held-out half, n=60; only 5 unseen-text) | 0/20 (held-out half) | $0.000 |
| DeBERTa-v3 fine-tuned, run 2 (local; to convergence, post hoc) | softmax of the chosen option | 99.0% [97.5, 100.0] | 0.048 [0.036, 0.066] | **96%** [93.1, 100.0] | 0.95 / 0.61 | +0.01 | 100.0% [94.0, 100.0]† (held-out half, n=60; only 5 unseen-text) | 0/20 (held-out half) | $0.000 |
| DeBERTa-v3 fine-tuned, run 2 + temperature scaling (local; post hoc) | softmax of the chosen option ÷ T | 99.0% [97.5, 100.0] | 0.017 [0.005, 0.033] | **96%** [93.2, 100.0] | 0.99 / 0.92 | +0.00 | 100.0% [94.0, 100.0]† (held-out half, n=60; only 5 unseen-text) | 0/20 (held-out half) | $0.000 |

**Read the zero-error coverage column.** Claude Sonnet 4.5 and Gemini 3 Flash are *more accurate* than Jev under attack and have a lower ECE — yet you could automate **0 %** of their decisions with no observed error, against 73 % with Jev, because their confidence barely moves when they are wrong (0.88; Gemini says 0.98 whether it is right or wrong). The coverage is cut at whole confidence groups: Gemini says 1.0 on 125 of the 200 emails and is wrong on 5 of them, so none of those 125 can be automated at zero observed errors — a tie is one threshold, not 125 decisions you get to order. Read the numbers with their intervals: Jev's 73 % sits in [67.0, 94.0], Sonnet's 0 % in [0.0, 90.9], Gemini's 0 % in [0.0, 1.8]†. Sonnet's width is structural: 24 of its 200 answers are tied at confidence 1.0 and two of them are wrong, so its coverage depends on whether a resample of the texts keeps either — 87 % keep one and score zero, and the top of the interval is the 5 % that miss both. Gemini's five top-confidence errors are much harder to miss — 99 % of resamples keep at least one — so its bootstrap closes on zero width and the exact binomial interval is published instead (†: it counts rows rather than texts, so read it as *at least* that wide). What the data does separate is a judge whose floor is 67 % from judges whose floor is 0 %. A judge that says 0.60 when it is guessing is worth more than one that says 0.88. The 3B chat model is *more* confident when wrong than when right; its number is decoration. The small NLI encoder cannot be prompt-injected (it does not read instructions) but routes at coin-flip level. Chat-model confidence here is verbalized (the model writes a number); Jev's is the probability of the chosen option, not the API's `confidence` field, which is a rescaling of that probability ([analysis](https://bernoulli.app/articles/is-jev-confident)) and calibrates worse on our data (ECE 0.13 vs 0.05 on the router).

**The fine-tuned rows are a different animal.** Run 1 (pre-registered: seed 2026, 10 epochs, 216 s of laptop training) scores 100.0% on the clean held-out emails (n=100; 100.0% on the 80 rows whose text is not in the training half), 97.0% under attack (all 200 rows; 96.0% on the 151 rows with no training text) and 100.0% on the held-out router (n=60, only 5 of them with unseen text), for $0 per row. None of the 40 prompt injections or 20 social-engineering rows landed — either because it does not read instructions, or because every social-engineering row and 11 of the 40 injections wrap a training email it may simply have memorised; this data cannot tell the two apart. Its softmax is *under*-confident at that budget (ECE 0.458, mean confidence 0.54 when right), so 0 of 3 testable pre-registered predictions hold. Run 2, a disclosed post-hoc amendment trained to convergence (19 epochs, 109 s), fixes the calibration (ECE 0.017; under attack 99.0%, ECE 0.048, confidence when wrong 0.61) and scores the same on the rows with no training text (100.0% clean, 98.7% attacked, 100.0% router — as does run 2 + temperature scaling, which changes no decision; every fine-tuned row's router cell rests on only 5 unseen-text rows); temperature scaling on top has nothing to fit — the validation slice was classified perfectly, T is not identified — and only sharpens (confidence when wrong under attack 0.92). It cannot read option descriptions, and a new category means new labels and a retrain. Full held-out comparison, every judge on the same rows, predictions scored: [docs/finetuned-baseline-2026-09.md](docs/finetuned-baseline-2026-09.md).

### Consensus is not calibration

Most agent juries use *agreement* as confidence: eight judges, majority wins, vote share is the score. Reading the Arena checkpoints side by side ([docs/consensus-2026-09.md](docs/consensus-2026-09.md), no new API call) says what that score is worth. On every dataset the jury is the frozen eight-judge panel ([`docs/runs/jury/panel.json`](docs/runs/jury/panel.json)); the three fine-tuned DeBERTa runs are listed in the report with their own declared confidence but never vote — one model trained on half of these email labels would be the answer key voting three times. Blank answers are abstentions; a tie in the even panel is no decision (counted as not correct, and shown separately over decided rows); brackets are 95 % bootstrap intervals over distinct texts. The router's 120 rows carry only 61 distinct states (14 of them behind the 40 hard rows), so its intervals are wide — that repetition is a property of the dataset, and treating the rows as independent would advertise a precision this benchmark does not have:

| dataset | 8-judge majority accuracy (ties = no decision / decided rows) | ties | best single judge | vote share when right / wrong | vote share as confidence: ECE | best declared confidence: ECE |
|---|---|---|---|---|---|---|
| Emails under attack | 90.0% [85.6, 93.9] / 95.2% | 11 | 97.0% [94.5, 99.0] | 0.89 / 0.68 | 0.073 | 0.015 (Gemini 3 Flash) |
| Router, bare labels | 48.3% [34.4, 61.6] / 63.0% | 28 | 66.7% [52.5, 80.3] | 0.85 / 0.69 | 0.174 | 0.233 (Llama 70B) |
| Router, described options | 85.8% [77.7, 92.2] / 96.3% | 13 | 98.3% [95.5, 100.0] | 0.86 / 0.66 | 0.110 | 0.012 (Gemini 3 Flash) |

On the 40 hard routing tasks (bare labels) the majority is right 15 % [0.0, 34.2] of the time (7 ties; those 40 rows are 14 distinct texts, hence the width), and the panel agrees exactly as much when it is wrong as when it is right (vote share 0.69 vs 0.69); the judges who voted with a wrong majority declared 0.92 confidence on average. An even jury with a coin-flip member did not decide 23 % of rows (28 of 120) on that prompt. And the headline depends on who sits on the jury: across the 56 possible three-judge juries, hard-task accuracy runs from **0 %** [0.0, 8.8]† (Jev + Sonnet + llama3.2) to **92.5 %** [76.9, 100.0] (DeBERTa + gemma4 + Llama 70B) — over 14 distinct texts a jury's interval is ±15 to 20 points wide, so the spread is real but the ranking of two neighbouring juries is not. This is the assumption Shao (2026, [arXiv:2609.20543](https://arxiv.org/abs/2609.20543)) and Huang et al. (2026, [arXiv:2605.30653](https://arxiv.org/abs/2605.30653)) attack — LLM groups that overstate consensus by 34–44 points and converge, unanimously, on wrong answers — measured on a heterogeneous jury with the same yardstick as a single calibrated judge.

**Are three votes three pieces of evidence?** The phi correlation between two judges' error indicators says whether they fail on the same rows ([error correlation](docs/consensus-2026-09.md), every pair, n stated per pair). On the bare-label router (n=120) the most correlated pair is Jev + llama3.2 at phi 0.98 — wrong together on 40 of 120 rows — and the least is Jev + DeBERTa at −0.74 (never wrong together); under attack (n=200) it is Sonnet + Gemini 3 Flash at 0.76 against Jev + DeBERTa at −0.03. Over the 56 three-judge juries, mean pairwise phi on all 120 rows runs from −0.18 (Jev + DeBERTa + Llama 70B) to 0.91 (Jev + Gemini 3 Flash + llama3.2, wrong together on 37 of the 40 hard tasks); on the 40 hard rows alone it runs from −0.04 to 0.68 over the 40 juries with a defined pair (Jev and llama3.2 are wrong on every hard row, DeBERTa on none, so those pairs have no phi there). On bare labels, less-correlated juries were more accurate (Spearman −0.32 between mean phi and hard-task majority accuracy over 56 juries); described options are at ceiling (every jury ≥ 92.5 %), so that prompt cannot test it. 40 scored rows — indicative.

**Round 2 — deliberation** ([pre-registered, then amended after an independent review and rerun](docs/jury-consensus-plan.md); [report](docs/jury-consensus.md)): each of seven judges re-voted after seeing the panel's anonymised votes. On these two prompts, deliberation amplified what the prompt contained. With bare labels, agreement on the hard tasks went from 51 % to 71 % and ties from 7 to 1 while majority accuracy stayed at 15–17.5 % (round 1 [0.0, 34.2], round 2 [0.0, 37.5]); the vote share behind *wrong* majorities rose from 0.69 to 0.87, and Llama 70B, gemma4 and DeepSeek R1 dropped from 55–72.5 % (lower bounds 32–49 %) to 7.5–17.5 % (upper bounds 23–39 %) on those tasks by following the majority (on the hard rows, 23 of 26, 20 of 21 and 16 of 17 of their switches landed on it). With described options, deliberation helped: majority accuracy 85.8 % [77.7, 92.2] → 95.0 % [90.5, 98.4], only 2 of 840 re-votes switched to a wrong answer, llama3.2 went from 0 to 82.5 % [61.0, 100.0] on the hard tasks. Of the four pre-registered predictions two held, one partly, one did not (chat models were *not* more confident when wrong after deliberating: 4 of 12 cells went up). Published as scored.

## How it works

1. **Labeled dataset** — JSONL rows `{state, questions, labels}`. Your humans already decided; the judge must reproduce them. An optional first line declares where the labels come from — their [ground-truth tier](docs/ground-truth.md), from `GT-1 constructed` to `GT-6 production outcome`.
2. **Shadow run** — the judge scores every row. Nothing is automated; everything is recorded: decision, confidence, latency, cost, raw response.
3. **Audit report** — calibration (ECE, reliability bins), selective prediction (accuracy at every coverage level), cost, latency percentiles, plus provenance: model, backend, timestamp, dataset hash. Accuracy, ECE and zero-error coverage carry a 95 % bootstrap interval over the dataset's distinct texts (Jev on the bare-label router: `66.7% [52.5, 80.3]`; 2,000 seeded resamples, pure Python, `--no-ci` to skip), or the exact binomial interval where the bootstrap cannot move so a number on 120 rows reads as the noisy estimate it is. Every report header carries a `Ground truth: GT-1 constructed — …` line with the tier's meaning and the dataset's caveats, so two accuracies are never read as the same evidence; a dataset that declares nothing is reported as `GT-0 unknown`, never silently.
4. **CI gate** — `judge-audit check --baseline baseline.json --max-ece-drift 0.02` fails the build when the judge degrades.

Exit codes: `0` ok · `1` drift detected · `2` usage or configuration error (the message says what to fix).

**In CI:** the [GitHub Action](docs/integrations.md#github-action) runs the audit on every push or pull request and fails the build on drift:

```yaml
- uses: kunko-ai-labs/judge-audit@v0.4      # or pin the release's commit SHA
  with: { labels: audits/labels.jsonl, judge: jev, baseline: audits/baseline.json }
  env: { AI_GATEWAY_API_KEY: ${{ secrets.AI_GATEWAY_API_KEY }} }
```

One sticky PR comment with the audit table (n, accuracy, ECE, zero-error coverage, cost, p99, verdict vs baseline), the report in the job summary, the report and result JSON as an artifact. The per-decision judgments stay on the runner unless you ask for them (`upload-evidence: "true"`). Outputs `accuracy`, `ece`, `zero-error-coverage`, `drift` for anything downstream.

**From inside an agent:** `pip install "kunko-judge-audit[mcp]"` then `claude mcp add judge-audit -- judge-audit-mcp` (or the equivalent in Cursor). The agent gets `run_audit`, `check_drift` and `list_judges` and can audit the judge it is about to rely on without leaving the session. See [docs/integrations.md](docs/integrations.md).

## Judge interface

Anything that maps `(state, questions) -> (decision, confidence)` plugs in:

```python
from judge_audit import Judge, Question, Judgment

class MyJudge(Judge):
    name = "my-judge"

    def decide(self, state: str, questions: list[Question]) -> list[Judgment]:
        ...  # return Judgment(question=q.name, decision="spam", confidence=0.93)
```

Ships with five: `jev` (TypeSafe Jev — and, via `JEV_ENDPOINT`, any Jev-compatible server such as OpenJev), `llm` (any chat model with a confidence prompt: Claude through the official SDK, anything OpenAI-compatible — OpenAI, Gemini, Ollama, vLLM — or your own transport), `nli` (a local zero-shot encoder, the control), `finetuned` (your own classifier, trained on your labels with `scripts/train_classifier.py`) and `simulated`. Details in [docs/judges.md](docs/judges.md).

## Why calibration, not accuracy

Accuracy tells you who wins a benchmark. Calibration tells you what you can automate safely. A 96 %-accurate judge that is confident on the 4 % it gets wrong is a liability; a 90 %-accurate judge that flags its own doubt is an asset. **Audit the honesty, not the trophy.**

## What lives where

| Path | What |
|---|---|
| `src/judge_audit/` | the harness: judge interface, adapters, metrics, runner, reports, CLI |
| `examples/*/generate.py` | seeded dataset generators — CI regenerates and diffs them |
| `docs/audit-*.md` / `.json` | published audits |
| `docs/runs/` | raw per-row judge responses behind each audit |
| `scripts/` | resumable audit driver, per-audit analysis, `verify_published.py` |
| `tests/` | metrics on hand-checked inputs, CLI exit codes, reproducibility |

## Roadmap

Score questions + MCE (the number we propose for regulators) → Judge Arena as a living leaderboard with a submission spec (the first table is above) → AI Act evidence dossier. Details and reasons in [docs/ROADMAP.md](docs/ROADMAP.md); the live backlog is the issues.

## FAQ

**Is this a benchmark?** No. A benchmark ranks judges on a fixed test. An audit checks one judge on *your* decisions and tells you what you can automate. The datasets here are worked examples, not a leaderboard — yet.

**Why is Jev the first judge?** It is the first judgment model sold on calibrated confidence as the headline feature. A claim that specific deserves an independent check.

**Can I trust a 100 % result?** Only as far as the dataset. The clean-email audit says the judge handles templated business email; it says nothing about your inbox. That is why the adversarial and routing audits exist.

**Does it send my data anywhere?** Only to the judge endpoint you configure. Reports and checkpoints are local files; commit them or not. In CI the Action uploads the report and the metrics JSON as a run artifact; the per-decision judgments are uploaded only if you set `upload-evidence: "true"`.

## License

Apache-2.0 — see [LICENSE](LICENSE). Sister project: [agent-assurance](https://github.com/kunko-ai-labs/agent-assurance) (deterministic checks on what an agent *may* do; this repo is the probabilistic half: whether its judgment can be trusted).
