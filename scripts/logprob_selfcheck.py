"""Before a published `logprob` run: is the cached scoring exact on this model, and how fast?

Loads the MLX model the `logprob` judge would use, scores the first N rows of a labels file
twice (trimmed cache, then a full forward pass per option) and reports the largest
difference in any option's probability, whether the chosen option ever changes, and the
rows per minute of the cached path. mlx-lm has an open report of prompt caching returning
different logits for repeated prompts; this is the check that it does not happen here.

  LOGPROB_MODEL=mlx-community/Qwen3-8B-4bit python scripts/logprob_selfcheck.py \\
      <labels.jsonl> --rows 20

It also counts the labels whose first characters merge with the prompt's last token and
are therefore tokenised alone after it (`MLXBackend.continuations`): not an error, but a
number to know before a run.

Exit status 0 when every probability agrees within --tolerance and no decision changes,
1 otherwise. Nothing is written; no network after the model is downloaded.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.judges.logprob import (  # noqa: E402
    SYSTEM,
    LogprobJudge,
    option_distribution,
    render,
)
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
    worst, flips, rows, seconds = 0.0, 0, 0, 0.0
    alone: set[str] = set()
    for row in load_jsonl(args.labels)[:args.rows]:
        for q in questions_of(row):
            prompt = backend.prompt_text(SYSTEM, render(row["state"], q))
            t0 = time.monotonic()
            cached, _ = option_distribution(backend.option_logprobs(prompt, q.options))
            seconds += time.monotonic() - t0
            alone.update(getattr(backend, "last_tokenised_alone", []) or [])
            fresh, _ = option_distribution(backend.option_logprobs(prompt, q.options,
                                                                   recompute=True))
            worst = max(worst, max(abs(cached[o] - fresh[o]) for o in q.options))
            flips += max(cached, key=cached.__getitem__) != max(fresh, key=fresh.__getitem__)
        rows += 1
    rate = 60 * rows / seconds if seconds else float("nan")
    print(f"model {judge.describe()['model_id']} · {rows} rows · largest probability "
          f"difference {worst:.2e} · decisions changed {flips} · cached path {rate:.1f} rows/min"
          f" · labels tokenised alone {len(alone)}" + (f" ({', '.join(sorted(alone))})"
                                                        if alone else ""))
    return 0 if worst <= args.tolerance and flips == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
