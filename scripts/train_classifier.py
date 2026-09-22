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

`--run 2` is the post-hoc amendment of docs/finetuned-baseline-2026-09.md:
20 % of the train half (label-stratified, seeded) becomes a validation slice,
training runs on the other 80 % with early stopping on the epoch's mean train
loss (< 0.05, or no improvement for 3 epochs; cap 40), and one temperature is
fitted on the validation logits (Guo et al. 2017) and written to the sidecar.
Model under ~/.cache/judge-audit/finetuned/<dataset>-run2/, record in
docs/runs/finetuned/<dataset>.train-run2.json. The held-out half is untouched.

  python scripts/train_classifier.py --dataset email-routing
  python scripts/train_classifier.py --dataset task-routing --run 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
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

from split_heldout import SPLITS, load_split, split_path, stratum_of  # noqa: E402

from judge_audit import __version__  # noqa: E402
from judge_audit.judges.finetuned import SIDECAR  # noqa: E402
from judge_audit.judges.nli import _pick_device  # noqa: E402
from judge_audit.runner import load_jsonl, sha256_of, sha256_rows_of  # noqa: E402

DEFAULT_BACKBONE = "microsoft/deberta-v3-base"
BACKBONE_CHOICE = ("microsoft/deberta-v3-base: the plain pre-trained backbone, chosen because it "
                   "downloaded in 16 s; the local MoritzLaurer/deberta-v3-base-zeroshot-v2.0 "
                   "backbone was the pre-registered fallback and was not needed. A plain backbone "
                   "keeps the fine-tuned row free of any zero-shot NLI training.")


# Run-2 early stopping (amendment): stop below this loss, or after PATIENCE epochs
# without improvement, or at the cap.
RUN2_STOP_LOSS = 0.05
RUN2_PATIENCE = 3
RUN2_MAX_EPOCHS = 40
RUN2_VAL_FRAC = 0.2


def carve_validation(rows: list[dict], train_idx: list[int], question: str,
                     meta_keys: tuple[str, ...], seed: int,
                     frac: float = RUN2_VAL_FRAC) -> tuple[list[int], list[int]]:
    """(train, validation) indices: the first ceil(frac) of each stratum after a seeded shuffle.

    Same stratification as the held-out split, applied to the train half only, so
    the validation slice never overlaps the held-out half by construction.
    """
    strata: dict[str, list[int]] = {}
    for idx in train_idx:
        strata.setdefault(stratum_of(rows[idx], question, meta_keys), []).append(idx)
    rng = random.Random(seed)
    train: list[int] = []
    val: list[int] = []
    for key in sorted(strata):
        members = list(strata[key])
        rng.shuffle(members)
        k = math.ceil(frac * len(members))
        val += members[:k]
        train += members[k:]
    return sorted(train), sorted(val)


T_BOUNDS = (0.1, 10.0)


def fit_temperature(logits, targets) -> tuple[float, float, float, bool]:
    """(T, NLL before, NLL after, hit a bound): one scalar T minimising NLL of logits / T.

    Guo et al. 2017, as a bounded 1-D search: NLL is convex in 1/T, so a golden-
    section search on log T over T_BOUNDS finds the minimum. The bound matters when
    the validation slice is classified perfectly — then NLL keeps falling as T -> 0
    and the fit would push every confidence to 1; the record says when that happened.
    """
    import torch
    logits = logits.detach().float().cpu()
    targets = targets.detach().cpu()
    nll = torch.nn.CrossEntropyLoss()

    def f(log_t: float) -> float:
        return float(nll(logits / math.exp(log_t), targets))

    lo, hi = math.log(T_BOUNDS[0]), math.log(T_BOUNDS[1])
    phi = (math.sqrt(5) - 1) / 2
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = f(a), f(b)
    for _ in range(100):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = f(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = f(b)
    log_t = (lo + hi) / 2
    t = math.exp(log_t)
    bounded = t <= T_BOUNDS[0] * 1.001 or t >= T_BOUNDS[1] / 1.001
    return t, f(0.0), f(log_t), bounded


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
    ap.add_argument("--run", type=int, default=1, choices=(1, 2),
                    help="1: pre-registered protocol; 2: amendment (validation slice, early "
                         "stopping, temperature scaling)")
    args = ap.parse_args()
    run2 = args.run == 2
    if run2:
        args.epochs = RUN2_MAX_EPOCHS
    elif args.epochs > 10:
        sys.exit("pre-registered protocol allows at most 10 epochs")

    import torch
    from huggingface_hub import snapshot_download
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        get_linear_schedule_with_warmup,
    )

    labels_rel, question, meta_keys = SPLITS[args.dataset]
    labels_path = ROOT / labels_rel
    split = load_split(split_path(args.dataset))
    if split["sha256_rows"] != sha256_rows_of(str(labels_path)):
        sys.exit(f"{labels_rel} changed since the split was registered; refusing to train")
    rows = load_jsonl(str(labels_path))
    train_idx, val_idx = list(split["train"]), []
    if run2:
        train_idx, val_idx = carve_validation(rows, train_idx, question, meta_keys, args.seed)
        assert not set(val_idx) & set(split["heldout"]) and not set(train_idx) & set(val_idx)
    train_rows = [rows[i] for i in train_idx]
    val_rows = [rows[i] for i in val_idx]
    options = sorted({str(o) for r in rows for o in r["questions"][0]["options"]})
    label2id = {lab: i for i, lab in enumerate(options)}
    if len(train_rows) + len(val_rows) != split["n_train"]:
        sys.exit("split and labels file disagree on the train size")

    device = _pick_device(args.device)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    suffix = "-run2" if run2 else ""
    out_dir = Path(args.out_dir or Path.home() / ".cache" / "judge-audit" / "finetuned"
                   / f"{args.dataset}{suffix}")
    out_dir.mkdir(parents=True, exist_ok=True)
    train_json = Path(args.train_json or ROOT / "docs" / "runs" / "finetuned" /
                      f"{args.dataset}.train{suffix}.json")
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

    print(f"{args.dataset} run {args.run}: {len(texts)} train rows, {len(val_rows)} validation, "
          f"{len(options)} labels, up to {args.epochs} epochs, {total_steps} steps on {device} "
          f"({args.backbone}@{revision[:12]})", flush=True)
    t0 = time.monotonic()
    losses: list[float] = []
    stopped_by = "epoch cap"
    best, since_best = math.inf, 0
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
        if run2:
            if losses[-1] < best:
                best, since_best = losses[-1], 0
            else:
                since_best += 1
            if losses[-1] < RUN2_STOP_LOSS:
                stopped_by = f"train loss < {RUN2_STOP_LOSS}"
                break
            if since_best >= RUN2_PATIENCE:
                stopped_by = f"no improvement for {RUN2_PATIENCE} epochs"
                break
    wall = time.monotonic() - t0
    epochs_run = len(losses)

    # Train-set fit only (the held-out half is never read here).
    model.eval()
    hits = 0
    with torch.no_grad():
        for b in range(0, len(texts), args.batch):
            enc = tok(texts[b:b + args.batch], truncation=True, max_length=args.max_len,
                      padding=True, return_tensors="pt").to(device)
            hits += int((model(**enc).logits.argmax(-1).cpu() == targets[b:b + args.batch]).sum())

    # Temperature scaling on the validation slice (run 2 only): the model never
    # trained on these rows, and they are not the held-out half.
    temperature_scaling = None
    if run2:
        val_texts = [r["state"] for r in val_rows]
        val_targets = torch.tensor([label2id[str(r["labels"][question])] for r in val_rows])
        chunks = []
        with torch.no_grad():
            for b in range(0, len(val_texts), args.batch):
                enc = tok(val_texts[b:b + args.batch], truncation=True, max_length=args.max_len,
                          padding=True, return_tensors="pt").to(device)
                chunks.append(model(**enc).logits.float().cpu())
        val_logits = torch.cat(chunks)
        t_fit, nll_before, nll_after, bounded = fit_temperature(val_logits, val_targets)
        val_acc = float((val_logits.argmax(-1) == val_targets).float().mean())
        temperature_scaling = {
            "method": "Guo et al. 2017: one scalar T minimising validation NLL; golden-section "
                      f"search on log T within T in [{T_BOUNDS[0]}, {T_BOUNDS[1]}]",
            "temperature": round(t_fit, 4), "hit_bound": bounded, "n_val": len(val_rows),
            # A perfectly classified slice has no NLL minimum: T is wherever the NLL
            # became numerically zero, not a calibrated value. Said here and in the report.
            "identified": val_acc < 1.0,
            "validation_indices": val_idx, "validation_rows_sha256": sha256_rows(val_rows),
            "val_accuracy": round(val_acc, 4),
            "val_nll_before": round(nll_before, 4), "val_nll_after": round(nll_after, 4),
        }
        flag = " (NOT IDENTIFIED: validation classified perfectly)" if val_acc >= 1.0 else (
            " (AT BOUND)" if bounded else "")
        print(f"  temperature {t_fit:.3f}{flag} (validation NLL "
              f"{nll_before:.3f} -> {nll_after:.3f}, n={len(val_rows)}, val accuracy "
              f"{val_acc:.1%})", flush=True)

    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    config_sha = sha256_of(str(out_dir / "config.json"))
    split_file = split_path(args.dataset)
    sidecar = {
        "name": f"deberta-v3-base-ft-{args.dataset}{suffix}", "backbone": args.backbone,
        "backbone_revision": revision, "dataset": args.dataset, "question": question,
        "labels": options, "seed": args.seed, "epochs": epochs_run, "run": args.run,
        "train_rows_sha256": sha256_rows(train_rows),
        "split": {"path": str(split_file.relative_to(ROOT)), "sha256": sha256_of(str(split_file)),
                  "part": "train" if not run2 else "train (80 % slice)", "n": len(train_rows)},
        "config_sha256": config_sha, "judge_audit_version": __version__,
    }
    if temperature_scaling:
        sidecar["temperature"] = temperature_scaling["temperature"]
        sidecar["temperature_scaling"] = {k: v for k, v in temperature_scaling.items()
                                          if k != "validation_indices"}
    (out_dir / SIDECAR).write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")

    record = {
        "dataset": args.dataset, "labels_file": labels_rel,
        "labels_sha256_rows": split["sha256_rows"], "question": question,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "backbone": args.backbone, "backbone_revision": revision,
        "backbone_choice": BACKBONE_CHOICE,
        "run": args.run,
        "hyper_parameters": {"seed": args.seed, "max_epochs": args.epochs, "lr": args.lr,
                             "batch": args.batch, "max_len": args.max_len,
                             "optimizer": "AdamW(weight_decay=0.01), grad clip 1.0",
                             "dtype": "float32 (the backbone config declares float16)",
                             "schedule": "linear, 10% warm-up", "steps_planned": total_steps,
                             "early_stopping": (f"train loss < {RUN2_STOP_LOSS} or no improvement "
                                                f"for {RUN2_PATIENCE} epochs, cap {RUN2_MAX_EPOCHS}"
                                                if run2 else None)},
        "seed": args.seed, "epochs": epochs_run, "stopped_by": stopped_by,
        "labels": options, "n_train": len(train_rows), "n_val": len(val_rows),
        "train_indices": train_idx, "validation_indices": val_idx,
        "train_rows_sha256": sidecar["train_rows_sha256"],
        "split": sidecar["split"],
        "temperature_scaling": temperature_scaling,
        "train_loss_per_epoch": losses, "train_accuracy_final": round(hits / len(texts), 4),
        "wall_time_s": round(wall, 1), "hardware": hardware(device),
        "determinism": "seeded (python, torch, batch order); MPS kernels are not guaranteed "
                       "bit-reproducible across torch versions",
        "software": {"python": platform.python_version(), "torch": torch.__version__,
                     "transformers": __import__("transformers").__version__,
                     "judge_audit": __version__},
        "model_dir": "~/" + str(out_dir.relative_to(Path.home())) if out_dir.is_relative_to(
            Path.home()) else str(out_dir),
        "model_dir_config_sha256": config_sha,
        "held_out_evaluated_here": False,
    }
    train_json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
    print(f"trained in {wall:.0f}s, train-set accuracy {hits / len(texts):.1%} -> {out_dir}\n"
          f"provenance -> {train_json.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
