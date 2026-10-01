"""Before a published `logprob` run: is the cached scoring exact on this model, and how fast?

Loads the MLX model the `logprob` judge would use and scores the first N rows of a labels
file three ways: the judge's trimmed cache; a fresh cache per option (the same computation,
step for step); and a full forward pass per option. mlx-lm has an open report of prompt
caching returning different logits for repeated prompts: the gate is that the trimmed cache
equals the fresh one. The full forward pass reaches the same logits by another kernel path
and, in bfloat16, rounds differently: its spread from the cached path is printed as the
model's numerical noise, not a failure (docs/v05-plan.md, amendment 1: on BANKING77 test
rows it moved a near-tie by 0.05 while the trimmed and fresh caches agreed exactly).

  LOGPROB_MODEL=mlx-community/Qwen3-8B-4bit python scripts/logprob_selfcheck.py \\
      <labels.jsonl> --rows 20

The prompt is the one the judge would send (LOGPROB_PROMPT_TEMPLATE, default v1).

It also counts the labels whose first characters merge with the prompt's last token and
are therefore tokenised alone after it (`MLXBackend.continuations`): not an error, but a
number to know before a run.

Exit status 0 when the trimmed and fresh caches agree within --tolerance and no decision
changes, 1 otherwise. Nothing is written; no network after the model is downloaded.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.judges.logprob import LogprobJudge, option_distribution  # noqa: E402
from judge_audit.runner import load_jsonl, questions_of  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("labels")
    ap.add_argument("--model", default=os.environ.get("LOGPROB_MODEL", ""))
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--tolerance", type=float, default=1e-3)
    args = ap.parse_args(argv)
    judge = LogprobJudge(model=args.model or None)
    backend = judge.backend
    worst, flips, rows, seconds = 0.0, 0, 0, 0.0          # trimmed vs fresh cache: the gate
    spread, spread_flips = 0.0, 0                          # trimmed vs full pass: reported
    alone: set[str] = set()

    def top(p: dict[str, float]) -> str:
        return max(p, key=p.__getitem__)

    for row in load_jsonl(args.labels)[:args.rows]:
        for q in questions_of(row):
            prompt = backend.prompt_text(judge.system, judge.render(row["state"], q))
            t0 = time.monotonic()
            cached, _ = option_distribution(backend.option_logprobs(prompt, q.options))
            seconds += time.monotonic() - t0
            alone.update(getattr(backend, "last_tokenised_alone", []) or [])
            fresh, _ = option_distribution(backend.option_logprobs(prompt, q.options,
                                                                   fresh=True))
            full, _ = option_distribution(backend.option_logprobs(prompt, q.options,
                                                                  recompute=True))
            worst = max(worst, max(abs(cached[o] - fresh[o]) for o in q.options))
            flips += top(cached) != top(fresh)
            spread = max(spread, max(abs(cached[o] - full[o]) for o in q.options))
            spread_flips += top(cached) != top(full)
        rows += 1
    rate = 60 * rows / seconds if seconds else float("nan")
    print(f"model {judge.describe()['model_id']} · {rows} rows · trimmed vs fresh cache: "
          f"largest probability difference {worst:.2e} · decisions changed {flips} · cached "
          f"path {rate:.1f} rows/min · labels tokenised alone {len(alone)}"
          + (f" ({', '.join(sorted(alone))})" if alone else ""))
    print(f"full forward pass (numerical spread, reported, not a gate): largest probability "
          f"difference {spread:.2e} · decisions changed {spread_flips}")
    return 0 if worst <= args.tolerance and flips == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
