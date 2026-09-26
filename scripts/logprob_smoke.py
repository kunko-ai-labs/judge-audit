"""Does this endpoint return token log-probabilities for this model? One cheap call.

v0.5 measures a chat model's confidence three ways (#89); the token log-probability method
only applies where the API returns log-probabilities, and several do not, or ignore the
request silently (docs/judges.md § Why two kinds of confidence). This script asks one
OpenAI-compatible endpoint once, with `logprobs` and `top_logprobs` set, to answer a
one-word classification, and reports what came back. It spends a few hundred tokens.

  LLM_BASE_URL=https://<gateway>/api/v1 LLM_API_KEY=... \\
    python scripts/logprob_smoke.py --model openai/gpt-4.1-mini \\
      --extra-body '{"provider": {"order": ["openai"], "allow_fallbacks": false,
                                  "require_parameters": true}}'
  LLM_BASE_URL=http://localhost:11434/v1 python scripts/logprob_smoke.py --model qwen3:8b

Exit status: 0 log-probabilities came back for the answer, 1 the endpoint answered without
them (unsupported or ignored), 2 the call failed. `--json FILE` writes the finding; the key
is read from LLM_API_KEY and is never printed or written.

The private hosted provider (LLM_PROVIDER=custom) goes through the maintainer's own module,
whose `call()` returns text only; checking it needs that module to expose log-probabilities.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.request

PROMPT = ("Classify the customer message into exactly one category: card, transfer, "
          "account. Answer with the category name only, in lower case.\n\n"
          "Message: My card was declined at the supermarket.")
EXPECTED = "card"


def build_request(model: str, extra_body: dict, top_logprobs: int) -> dict:
    # max_tokens 16: some upstreams refuse log-probabilities on shorter budgets.
    return {"model": model, "temperature": 0, "max_tokens": 16, "logprobs": True,
            "top_logprobs": top_logprobs,
            "messages": [{"role": "user", "content": PROMPT}], **extra_body}


def post(base_url: str, api_key: str, body: dict, timeout: float = 60.0) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def summarize(resp: dict, requested_top: int) -> dict:
    """The finding from one response: did log-probabilities come back, for which tokens,
    and what probability the first answer token carries."""
    choice = (resp.get("choices") or [{}])[0]
    text = ((choice.get("message") or {}).get("content") or "").strip()
    content = ((choice.get("logprobs") or {}).get("content")) or []
    first = next((t for t in content if (t.get("token") or "").strip()), None)
    finding = {
        "served_model": resp.get("model"),
        "upstream_provider": resp.get("provider") if isinstance(resp.get("provider"), str)
        else None,
        "answer": text,
        "answer_is_expected": text.lower().startswith(EXPECTED),
        "logprobs_returned": bool(content),
        "tokens_with_logprobs": len(content),
        "top_logprobs_requested": requested_top,
    }
    if first is not None and isinstance(first.get("logprob"), (int, float)):
        tops = first.get("top_logprobs") or []
        finding.update({
            "first_token": first.get("token"),
            "first_token_probability": round(math.exp(first["logprob"]), 6),
            "top_logprobs_returned": len(tops),
            "alternatives": {t.get("token"): round(math.exp(t["logprob"]), 6)
                             for t in tops if isinstance(t.get("logprob"), (int, float))},
        })
    return finding


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, help="the model id the endpoint expects")
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", ""))
    ap.add_argument("--extra-body", default=os.environ.get("LLM_EXTRA_BODY", ""),
                    help="JSON object merged into the request (e.g. a gateway's routing)")
    ap.add_argument("--top-logprobs", type=int, default=5)
    ap.add_argument("--json", default=None, help="write the finding to this file")
    args = ap.parse_args(argv)
    if not args.base_url:
        print("set LLM_BASE_URL or --base-url", file=sys.stderr)
        return 2
    try:
        extra = json.loads(args.extra_body) if args.extra_body.strip() else {}
        if not isinstance(extra, dict):
            raise ValueError("not a JSON object")
    except ValueError as e:
        print(f"--extra-body: {e}", file=sys.stderr)
        return 2
    body = build_request(args.model, extra, args.top_logprobs)
    try:
        resp = post(args.base_url, os.environ.get("LLM_API_KEY", ""), body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        print(f"HTTP {e.code}: {detail}", file=sys.stderr)
        return 2
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"request failed: {e}", file=sys.stderr)
        return 2
    finding = {"model_requested": args.model, "base_url": args.base_url.rstrip("/"),
               "extra_body": extra, **summarize(resp, args.top_logprobs)}
    print(json.dumps(finding, indent=1, ensure_ascii=False))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(finding, f, indent=1, ensure_ascii=False)
            f.write("\n")
    return 0 if finding["logprobs_returned"] else 1


if __name__ == "__main__":
    sys.exit(main())
