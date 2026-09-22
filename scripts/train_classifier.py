"""Fine-tune a sequence classifier on the train half of a pre-registered split.

The "your own classifier" row of the Arena (docs/finetuned-baseline-2026-09.md).
Trains `microsoft/deberta-v3-base` (or `--backbone`) with a fresh classification
head on the rows `examples/<dataset>/split-heldout.json` marks as `train`, and
never touches the held-out half: this script does not evaluate anything. The
model goes to ~/.cache/judge-audit/finetuned/<dataset>/ (never committed) with
a `judge-audit.json` provenance sidecar; everything a reader needs to reproduce
or distrust the run goes to docs/runs/finetuned/<dataset>.train.json (committed).

Pre-registered hyper-parameters (issue #51): seed 2026, at most 10 epochs,
lr 2e-5, batch 8, max 256 tokens, AdamW with 10 % linear warm-up then linear
decay, laptop CPU/MPS. Change them and it is a different, unregistered run.

  python scripts/train_classifier.py --dataset email-routing
  python scripts/train_classifier.py --dataset task-routing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from split_heldout import SPLITS, load_split, split_path  # noqa: E402

from judge_audit import __version__  # noqa: E402
from judge_audit.judges.finetuned import SIDECAR  # noqa: E402
from judge_audit.judges.nli import _pick_device  # noqa: E402
from judge_audit.runner import load_jsonl, sha256_of, sha256_rows_of  # noqa: E402

DEFAULT_BACKBONE = "microsoft/deberta-v3-base"
BACKBONE_CHOICE = ("microsoft/deberta-v3-base: the plain pre-trained backbone, chosen because it "
                   "downloaded in 16 s; the local MoritzLaurer/deberta-v3-base-zeroshot-v2.0 "
                   "backbone was the pre-registered fallback and was not needed. A plain backbone "
                   "keeps the fine-tuned row free of any zero-shot NLI training.")


def sha256_rows(rows: list[dict]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update((json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    return h.hexdigest()


def hardware(device: str) -> str:
    chip = platform.machine()
    if sys.platform == "darwin":
        try:
            chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], check=True,
                                  capture_output=True, text=True).stdout.strip() or chip
        except (OSError, subprocess.CalledProcessError):
            pass
    return f"{chip} ({platform.system()} {platform.release()}), device {device}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=sorted(SPLITS))
    ap.add_argument("--backbone", default=DEFAULT_BACKBONE)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--out-dir", default=None,
                    help="model directory (default ~/.cache/judge-audit/finetuned/<dataset>)")
    ap.add_argument("--train-json", default=None,
                    help="provenance record (default docs/runs/finetuned/<dataset>.train.json)")
    args = ap.parse_args()
    if args.epochs > 10:
        sys.exit("pre-registered protocol allows at most 10 epochs")

    import torch
    from huggingface_hub import snapshot_download
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_linear_schedule_with_warmup,
    )

    labels_rel, question, _meta = SPLITS[args.dataset]
    labels_path = ROOT / labels_rel
    split = load_split(split_path(args.dataset))
    if split["sha256_rows"] != sha256_rows_of(str(labels_path)):
        sys.exit(f"{labels_rel} changed since the split was registered; refusing to train")
    rows = load_jsonl(str(labels_path))
    train_rows = [rows[i] for i in split["train"]]
    options = sorted({str(o) for r in rows for o in r["questions"][0]["options"]})
    label2id = {lab: i for i, lab in enumerate(options)}
    if len(train_rows) != split["n_train"]:
        sys.exit("split and labels file disagree on the train size")

    device = _pick_device(args.device)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    out_dir = Path(args.out_dir or Path.home() / ".cache" / "judge-audit" / "finetuned" / args.dataset)
    out_dir.mkdir(parents=True, exist_ok=True)
    train_json = Path(args.train_json or ROOT / "docs" / "runs" / "finetuned" /
                      f"{args.dataset}.train.json")
    train_json.parent.mkdir(parents=True, exist_ok=True)

    snapshot = snapshot_download(args.backbone)
    revision = Path(snapshot).name
    tok = AutoTokenizer.from_pretrained(args.backbone)
    # The backbone's config declares float16; fp16 AdamW diverges to NaN on the first
    # step, so the weights are loaded and trained in float32 (recorded below).
    model = AutoModelForSequenceClassification.from_pretrained(
        args.backbone, num_labels=len(options), dtype=torch.float32,
        id2label={i: lab for lab, i in label2id.items()}, label2id=label2id).to(device)

    texts = [r["state"] for r in train_rows]
    targets = torch.tensor([label2id[str(r["labels"][question])] for r in train_rows])
    steps_per_epoch = (len(texts) + args.batch - 1) // args.batch
    total_steps = steps_per_epoch * args.epochs
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * total_steps), total_steps)
    order_rng = random.Random(args.seed)

    print(f"{args.dataset}: {len(texts)} train rows, {len(options)} labels, {args.epochs} epochs, "
          f"{total_steps} steps on {device} ({args.backbone}@{revision[:12]})", flush=True)
    t0 = time.monotonic()
    losses: list[float] = []
    model.train()
    for epoch in range(args.epochs):
        idx = list(range(len(texts)))
        order_rng.shuffle(idx)
        total = 0.0
        for b in range(0, len(idx), args.batch):
            batch = idx[b:b + args.batch]
            enc = tok([texts[i] for i in batch], truncation=True, max_length=args.max_len,
                      padding=True, return_tensors="pt").to(device)
            out = model(**enc, labels=targets[batch].to(device))
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += float(out.loss) * len(batch)
        losses.append(round(total / len(texts), 4))
        print(f"  epoch {epoch + 1}/{args.epochs} train loss {losses[-1]:.4f}", flush=True)
    wall = time.monotonic() - t0

    # Train-set fit only (the held-out half is never read here).
    model.eval()
    hits = 0
    with torch.no_grad():
        for b in range(0, len(texts), args.batch):
            enc = tok(texts[b:b + args.batch], truncation=True, max_length=args.max_len,
                      padding=True, return_tensors="pt").to(device)
            hits += int((model(**enc).logits.argmax(-1).cpu() == targets[b:b + args.batch]).sum())

    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    config_sha = sha256_of(str(out_dir / "config.json"))
    split_file = split_path(args.dataset)
    sidecar = {
        "name": f"deberta-v3-base-ft-{args.dataset}", "backbone": args.backbone,
        "backbone_revision": revision, "dataset": args.dataset, "question": question,
        "labels": options, "seed": args.seed, "epochs": args.epochs,
        "train_rows_sha256": sha256_rows(train_rows),
        "split": {"path": str(split_file.relative_to(ROOT)), "sha256": sha256_of(str(split_file)),
                  "part": "train", "n": len(train_rows)},
        "config_sha256": config_sha, "judge_audit_version": __version__,
    }
    (out_dir / SIDECAR).write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")

    record = {
        "dataset": args.dataset, "labels_file": labels_rel,
        "labels_sha256_rows": split["sha256_rows"], "question": question,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backbone": args.backbone, "backbone_revision": revision,
        "backbone_choice": BACKBONE_CHOICE,
        "hyper_parameters": {"seed": args.seed, "epochs": args.epochs, "lr": args.lr,
                             "batch": args.batch, "max_len": args.max_len,
                             "optimizer": "AdamW(weight_decay=0.01), grad clip 1.0",
                             "dtype": "float32 (the backbone config declares float16)",
                             "schedule": "linear, 10% warm-up", "steps": total_steps},
        "seed": args.seed, "epochs": args.epochs,
        "labels": options, "n_train": len(train_rows),
        "train_rows_sha256": sidecar["train_rows_sha256"],
        "split": sidecar["split"],
        "train_loss_per_epoch": losses, "train_accuracy_final": round(hits / len(texts), 4),
        "wall_time_s": round(wall, 1), "hardware": hardware(device),
        "determinism": "seeded (python, torch, batch order); MPS kernels are not guaranteed "
                       "bit-reproducible across torch versions",
        "software": {"python": platform.python_version(), "torch": torch.__version__,
                     "transformers": __import__("transformers").__version__,
                     "judge_audit": __version__},
        "model_dir": str(out_dir), "model_dir_config_sha256": config_sha,
        "held_out_evaluated_here": False,
    }
    train_json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    print(f"trained in {wall:.0f}s, train-set accuracy {hits / len(texts):.1%} -> {out_dir}\n"
          f"provenance -> {train_json.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
