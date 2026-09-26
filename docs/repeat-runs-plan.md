# Repeat runs of the headline: pre-registration

**Committed before the first API call.** This page fixes the protocol, the metrics and the predictions for re-running the three judges behind the README headline. The results are published whether or not the predictions hold (`docs/repeats-2026-09.md`, generated from the checkpoints).

## Why
The Arena ran each judge once. The bootstrap intervals say how far a number would move on *another sample of texts*. They say nothing about how far it moves when the *same* judge answers the *same* 200 emails again. This study measures that second spread for the three judges the headline names.

## Protocol
- **Dataset:** `examples/email-routing-adversarial/labels.jsonl`, the 200 emails under attack (GT-1 synthetic, 189 distinct texts). It is byte-identical to the Arena run.
- **Judges and settings:**

  | Judge | Settings |
  |---|---|
  | Gemini 3 Flash | `gemini-3-flash-preview` through its OpenAI-compatible endpoint, as in the Arena |
  | Claude Sonnet 4.5 | the same hosted model and private provider module as in the Arena (provider `hosted-api`) |
  | Jev | **the direct TypeSafe API** (`jev-latest`) |

  - Jev's Arena run under attack (2026-09-19) went through the AI Gateway evaluate API (`typesafe-ai/jev`), which is not available to us now. A Jev difference between the original and the repeats may therefore come from the backend or the model version, not only from run-to-run variation. The report keeps the original out of Jev's spread and says so.
  - The chat models get the same system prompt and the same render template as the Arena runs. Their text is byte-identical to judge-audit 0.3.1, and `prompt_sha256` is now recorded. Temperature is 0, as in the Arena.
- **Runs:** three new runs per judge, r1–r3, one after another. Each has its own checkpoint, `docs/runs/repeats/<judge>/email-adversarial.r<k>.ckpt.jsonl`, written by `scripts/audit_resumable.py`. No checkpoint of the Arena is touched.
- **Completeness:** every run must answer all 200 rows. `scripts/check_complete.py` covers these checkpoints in CI. A run that dies is resumed; it is not restarted from scratch.
- **Cost ceiling:** under $2 for all nine runs at list prices (Sonnet ~$0.45, Gemini ~$0.03 and Jev ~$0.004 per run).

## Metrics, per run and across runs
- Accuracy, zero-error coverage with its 95 % interval (exact where the bootstrap cannot move), and mean confidence when right and when wrong.
- `nll_infinite`: answers declared certain and wrong.
- **Across runs:** the spread (min–max and SD) of each metric over the runs that share a configuration: the three repeats plus the Arena run for the chat models, the three repeats alone for Jev. It is printed next to the bootstrap interval of the Arena run.

## Predictions
1. **Gemini 3 Flash's zero-error coverage is 0 % in each of the three repeats.** Its confidence does not separate its errors.
2. **Jev's zero-error coverage is at least 50 % in each repeat.**
3. **The headline separation holds in every repeat.** In each one, Gemini's exact 95 % upper bound on zero-error coverage lies below Jev's 95 % lower bound.
4. **Claude Sonnet 4.5's zero-error coverage stays below Jev's in each repeat** (point estimates; the Arena interval for Sonnet is too wide to predict separation).
5. **Each judge's accuracy in each repeat lies inside its Arena 95 % interval:** Gemini [94.5, 99.0], Sonnet [93.9, 99.0], Jev [92.5, 98.0].
6. **`nll_infinite` is at least 1 for Gemini and Sonnet in each repeat, and 0 for Jev.**

A prediction that fails is reported as failed, next to the ones that hold.
