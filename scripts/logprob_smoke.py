"""Does this endpoint return token log-probabilities for this model? One cheap call.

v0.5 measures a chat model's confidence three ways (#89); the token log-probability method
only applies where the API returns log-probabilities, and several do not, or ignore the
request silently (docs/judges.md § Why two kinds of confidence). This script asks one
OpenAI-compatible endpoint once, with `logprobs` and `top_logprobs` set, to answer a
one-word classification with no system prompt, and reports what came back. It spends a few
hundred tokens. Exit 0 means log-probabilities came back for a plain one-word request;
whether they also come back for a judge's own request is checked in that run.

  LLM_BASE_URL=https://<gateway>/api/v1 LLM_API_KEY=... \\
    python scripts/logprob_smoke.py --model <model id> \\
      --extra-body '{"provider": {"order": ["<upstream>"], "allow_fallbacks": false,
                                  "require_parameters": true}}'
  LLM_BASE_URL=http://localhost:11434/v1 python scripts/logprob_smoke.py --model qwen3:8b

Exit status:
  0  numeric log-probabilities came back for the answer
  1  the endpoint answered without them (unsupported, or silently ignored)
  2  the call failed, or the reply was not a chat completion
  3  something came back under `logprobs` in a shape this script does not read
The key is read from LLM_API_KEY. Every occurrence of it is removed from what the script
prints or writes, including an error body or a field that echoes the request's headers.
`--extra-body` takes the same routing object as the `llm` judge's LLM_EXTRA_BODY and is
checked the same way.

The private hosted provider (LLM_PROVIDER=custom) goes through the maintainer's own module,
whose `call()` returns text only; checking it needs that module to expose log-probabilities.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from judge_audit.judges.llm import extra_body_of  # noqa: E402

PROMPT = ("Classify the customer message into exactly one category: card, transfer, "
          "account. Answer with the category name only, in lower case.\n\n"
          "Message: My card was declined at the supermarket.")
EXPECTED = "card"
THINK = re.compile(r"^\s*<think>.*?</think>", re.DOTALL)
YES, NO, FAILED, UNREADABLE = 0, 1, 2, 3


def redact(text: str, key: str) -> str:
    """`text` with every occurrence of the key replaced; a key shorter than 8 characters is
    not a key worth searching for and would redact ordinary words."""
    return text.replace(key, "[redacted]") if key and len(key) >= 8 else text


def build_request(model: str, extra_body: dict, top_logprobs: int) -> dict:
    # The routing object goes first, so nothing in it can override the fields below.
    # max_tokens 16: some upstreams refuse log-probabilities on shorter budgets.
    return {**extra_body, "model": model, "temperature": 0, "max_tokens": 16,
            "logprobs": True, "top_logprobs": top_logprobs,
            "messages": [{"role": "user", "content": PROMPT}]}


def post(base_url: str, api_key: str, body: dict, timeout: float = 60.0) -> object:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base_url.rstrip('/')}/chat/completions",
                                 data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _visible(text: str) -> str:
    """The answer without a leading reasoning block (`<think>…</think>`) or markup."""
    text = THINK.sub("", text)
    return text.strip().lower().strip("*_ .\n")


def _answer_token(content: list) -> dict | None:
    """The first token that starts the expected answer after any reasoning block; markup
    (`**`) and whitespace before it are skipped."""
    ends = [i for i, t in enumerate(content)
            if isinstance(t, dict) and "</think>" in (t.get("token") or "")]
    for t in content[ends[-1] + 1:] if ends else content:
        text = (t.get("token") or "").strip().lower() if isinstance(t, dict) else ""
        if text and EXPECTED.startswith(text):
            return t
    return None


def summarize(resp: object, requested_top: int) -> tuple[int, dict]:
    """(exit status, finding) from one response."""
    if not isinstance(resp, dict) or "error" in resp or not isinstance(resp.get("choices"), list):
        detail = resp.get("error") if isinstance(resp, dict) else type(resp).__name__
        return FAILED, {"error": f"not a chat completion: {str(detail)[:200]}"}
    choice = resp["choices"][0] if resp["choices"] else {}
    message = choice.get("message") if isinstance(choice, dict) else None
    text = ((message or {}).get("content") or "").strip() if isinstance(message, dict) else ""
    lp = choice.get("logprobs") if isinstance(choice, dict) else None
    finding: dict = {
        "served_model": resp.get("model"),
        "answer": text,
        "answer_is_expected": _visible(text).startswith(EXPECTED),
        "top_logprobs_requested": requested_top,
    }
    content = lp.get("content") if isinstance(lp, dict) else None
    if lp is not None and not isinstance(content, list):
        finding["logprobs_returned"] = "unreadable shape"
        finding["logprobs_keys"] = sorted(lp)[:10] if isinstance(lp, dict) else type(lp).__name__
        return UNREADABLE, finding
    numeric = [t for t in (content or []) if isinstance(t, dict)
               and isinstance(t.get("logprob"), (int, float)) and math.isfinite(t["logprob"])]
    finding["logprobs_returned"] = bool(numeric)
    finding["tokens_with_logprobs"] = len(numeric)
    token = _answer_token(numeric) if finding["answer_is_expected"] else None
    if token is not None:
        tops = [t for t in (token.get("top_logprobs") or [])
                if isinstance(t, dict) and isinstance(t.get("logprob"), (int, float))]
        finding.update({
            "answer_token": token.get("token"),
            "answer_token_probability": round(math.exp(token["logprob"]), 6),
            "top_logprobs_returned": len(tops),
            "alternatives": {t.get("token"): round(math.exp(t["logprob"]), 6) for t in tops},
        })
    else:
        finding["answer_token"] = None
    return (YES if numeric else NO), finding


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, help="the model id the endpoint expects")
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", ""))
    ap.add_argument("--extra-body", default=os.environ.get("LLM_EXTRA_BODY", ""),
                    help="a routing object, as LLM_EXTRA_BODY")
    ap.add_argument("--top-logprobs", type=int, default=5)
    ap.add_argument("--json", default=None, help="write the finding to this file")
    args = ap.parse_args(argv)
    key = os.environ.get("LLM_API_KEY", "")

    def emit(text: str, stream=sys.stdout) -> None:
        print(redact(text, key), file=stream)

    if not args.base_url:
        emit("set LLM_BASE_URL or --base-url", sys.stderr)
        return FAILED
    try:
        extra = extra_body_of(args.extra_body)
    except ValueError as e:
        emit(f"--extra-body: {e}", sys.stderr)
        return FAILED
    body = build_request(args.model, extra, args.top_logprobs)
    try:
        resp = post(args.base_url, key, body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        emit(f"HTTP {e.code}: {detail}", sys.stderr)
        return FAILED
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        emit(f"request failed: {e}", sys.stderr)
        return FAILED
    status, finding = summarize(resp, args.top_logprobs)
    finding = {"model_requested": args.model, "base_url": args.base_url.rstrip("/"),
               "extra_body": extra, **finding, "exit_status": status}
    text = redact(json.dumps(finding, indent=1, ensure_ascii=False), key)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return status


if __name__ == "__main__":
    sys.exit(main())
