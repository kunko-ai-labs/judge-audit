"""Before a published `logprob` run: is the cached scoring exact on this model, and how fast?

Loads the MLX model the `logprob` judge would use and scores the first N rows of a labels
file three ways: the judge's trimmed cache; a fresh cache per option (the same computation,
step for step); and a full forward pass per option. mlx-lm has an open report of prompt
caching returning different logits for repeated prompts: the gate is that the trimmed cache
equals the fresh one. The full forward pass reaches the same logits by another kernel path
and, in bfloat16, rounds differently: its probability spread is printed as the model's
numerical noise, and it fails the check only past a loose bound, a log-odds shift above
four bfloat16 steps at logit magnitudes 32-64 (1.0), or a changed decision whose trimmed-
path margin exceeds it (docs/v05-plan.md, amendment 1: on BANKING77 test rows it moved a
near-tie by 0.25 in log-odds, one step, while the trimmed and fresh caches agreed exactly).
`--per-row` prints each row's comparison.

  LOGPROB_MODEL=mlx-community/Qwen3-8B-4bit python scripts/logprob_selfcheck.py \\
      <labels.jsonl> --rows 20

The prompt is the one the judge would send (LOGPROB_PROMPT_TEMPLATE, default v1).

It also counts the labels whose first characters merge with the prompt's last token and
are therefore tokenised alone after it (`MLXBackend.continuations`): not an error, but a
number to know before a run.

Exit status 0 when the trimmed and fresh caches' log-probabilities agree within --tolerance
with no decision
changed, and the full pass stays within the loose bound; 1 otherwise. Nothing is written; no network after the model is downloaded.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.judges.logprob import LogprobJudge, option_distribution  # noqa: E402
from judge_audit.runner import load_jsonl, questions_of  # noqa: E402

# The full pass's loose bound (plan amendment 1): bfloat16 keeps 8 significant bits, so at
# logit magnitudes of 32-64 one step is 0.25 in log-odds; four steps is noise's ceiling here.
LOG_ODDS_BOUND = 1.0
FLOOR = 0.01            # log-odds are compared only where both paths give at least 1 %


def log_odds_shift(a: dict[str, float], b: dict[str, float]) -> float:
    """Largest change, between two distributions, in the log-odds of any pair of options both
    give at least FLOOR: max over pairs of |(ln a_i - ln a_j) - (ln b_i - ln b_j)|, that is
    the spread of d_o = ln a(o) - ln b(o). 0 with fewer than two such options."""
    d = [math.log(a[o]) - math.log(b[o]) for o in a if a[o] >= FLOOR and b.get(o, 0.0) >= FLOOR]
    return max(d) - min(d) if len(d) > 1 else 0.0


def margin(p: dict[str, float]) -> float:
    """Log-odds between the two most probable options (inf when the second is 0)."""
    first, second = sorted(p.values(), reverse=True)[:2]
    return math.inf if second <= 0 else math.log(first) - math.log(second)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("labels")
    ap.add_argument("--model", default=os.environ.get("LOGPROB_MODEL", ""))
    ap.add_argument("--rows", type=int, default=20)
    ap.add_argument("--tolerance", type=float, default=1e-3)
    ap.add_argument("--log-odds-bound", type=float, default=LOG_ODDS_BOUND)
    ap.add_argument("--per-row", action="store_true",
                    help="print each row's three-way comparison and top two options")
    args = ap.parse_args(argv)
    judge = LogprobJudge(model=args.model or None)
    backend = judge.backend
    worst, flips, rows, seconds = 0.0, 0, 0, 0.0          # trimmed vs fresh cache: the gate
    spread, spread_flips = 0.0, 0                          # trimmed vs full pass: reported
    shift, wide_flips = 0.0, 0          # ... and its loose bound: log-odds, flips past it
    alone: set[str] = set()

    def top(p: dict[str, float]) -> str:
        return max(p, key=p.__getitem__)

    for row in load_jsonl(args.labels)[:args.rows]:
        for q in questions_of(row):
            prompt = backend.prompt_text(judge.system, judge.render(row["state"], q))
            t0 = time.monotonic()
            raw = backend.option_logprobs(prompt, q.options)
            cached, _ = option_distribution(raw)
            seconds += time.monotonic() - t0
            alone.update(getattr(backend, "last_tokenised_alone", []) or [])
            raw_fresh = backend.option_logprobs(prompt, q.options, fresh=True)
            fresh, _ = option_distribution(raw_fresh)
            full, _ = option_distribution(backend.option_logprobs(prompt, q.options,
                                                                  recompute=True))
            # the gate compares raw log-probabilities: exact agreement is expected, and a
            # broken trim shows on unlikely options long before their probabilities move
            worst = max(worst, max(abs(raw[o] - raw_fresh[o]) for o in q.options))
            flips += top(cached) != top(fresh)
            spread = max(spread, max(abs(cached[o] - full[o]) for o in q.options))
            flipped = top(cached) != top(full)
            spread_flips += flipped
            shift = max(shift, log_odds_shift(cached, full))
            wide_flips += flipped and margin(cached) > args.log_odds_bound
            if args.per_row:
                d = max(abs(cached[o] - full[o]) for o in q.options)
                two = sorted(cached.items(), key=lambda kv: -kv[1])[:2]
                two_full = sorted(full.items(), key=lambda kv: -kv[1])[:2]
                print(f"row {rows} trimmed-vs-full {d:.2e} trimmed-vs-fresh "
                      f"{max(abs(cached[o] - fresh[o]) for o in q.options):.2e} | trimmed top2 "
                      f"{[(k, round(v, 4)) for k, v in two]} | full top2 "
                      f"{[(k, round(v, 4)) for k, v in two_full]}")
        rows += 1
    rate = 60 * rows / seconds if seconds else float("nan")
    print(f"model {judge.describe()['model_id']} · {rows} rows · trimmed vs fresh cache: "
          f"largest log-probability difference {worst:.2e} · decisions changed {flips} · cached "
          f"path {rate:.1f} rows/min · labels tokenised alone {len(alone)}"
          + (f" ({', '.join(sorted(alone))})" if alone else ""))
    print(f"full forward pass (numerical spread, reported, not a gate): largest probability "
          f"difference {spread:.2e} · decisions changed {spread_flips}")
    print(f"full forward pass, loose bound: largest log-odds shift {shift:.3f} (bound "
          f"{args.log_odds_bound:g}) · decisions changed with a trimmed-path margin above the "
          f"bound {wide_flips}")
    exact = worst <= args.tolerance and flips == 0
    loose = shift <= args.log_odds_bound and wide_flips == 0
    return 0 if exact and loose else 1

if __name__ == "__main__":
    sys.exit(main())
