"""Re-parse the raw replies in Arena checkpoints with the current parser. No API call.

A checkpoint keeps every model's raw text (`raw.text`). When the parser
improves (e.g. JSON followed by prose, or prose containing `{`), the
decisions derived from that text can be recomputed offline; the evidence
itself never changes. The checkpoint header records what was reparsed.

  python scripts/reparse_checkpoints.py            # rewrite in place, print what changed
  python scripts/reparse_checkpoints.py --dry-run  # print only
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from arena_report import ARENA, DATASETS  # noqa: E402

from judge_audit import __version__  # noqa: E402
from judge_audit.judges.llm import parse_reply  # noqa: E402
from judge_audit.runner import load_jsonl, questions_of  # noqa: E402


def reparse(ckpt: Path, rows: list[dict], dry_run: bool) -> int:
    lines = ckpt.read_text(encoding="utf-8").splitlines()
    out, changed, header_at = [], 0, None
    for line in lines:
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["idx"] < 0:
            header_at = len(out)
            out.append(rec)
            continue
        qs = questions_of(rows[rec["idx"]])
        for j in rec["judgments"]:
            raw = j.get("raw")
            text = raw.get("text") if isinstance(raw, dict) else None
            if not text:
                continue
            decision, confidence, ans, status = parse_reply(text, qs)[j["question"]]
            if (decision, confidence, status) != (
                    j["decision"], j["confidence"], j.get("parse_status", "parsed")):
                changed += 1
                j["decision"], j["confidence"], j["parse_status"] = decision, confidence, status
                raw["parsed"] = ans
        out.append(rec)
    if changed and header_at is not None:
        run = out[header_at].setdefault("run", {})
        run.setdefault("reparsed", []).append({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "judge_audit_version": __version__, "judgments_changed": changed})
    if changed and not dry_run:
        ckpt.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    total = 0
    for d in sorted(p for p in ARENA.iterdir() if p.is_dir()):
        for ds, (labels, _) in DATASETS.items():
            ck = d / f"{ds}.ckpt.jsonl"
            if not ck.exists():
                continue
            n = reparse(ck, load_jsonl(str(ROOT / labels)), a.dry_run)
            if n:
                print(f"{d.name}/{ds}: {n} judgment(s) re-parsed")
            total += n
    print(f"{total} judgment(s) changed{' (dry run)' if a.dry_run else ''}")


if __name__ == "__main__":
    main()
