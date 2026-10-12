"""Resumable audit driver: one row at a time, checkpointed to JSONL.

Long vendor audits hit rate limits and transient errors; re-running from
scratch wastes money and time. This driver appends each row's judgments to
a checkpoint file and skips rows already done, so an interrupted run resumes
where it left off. The checkpoint IS the raw evidence: commit it under
docs/runs/ next to the report so anyone can re-derive every number.

Usage:
  python scripts/audit_resumable.py LABELS --judge jev --checkpoint docs/runs/NAME.ckpt.jsonl \\
      --out docs/audit-NAME.md --json docs/audit-NAME.json [--html docs/audit-NAME.html]

`--rows examples/<dataset>/split-heldout.json:heldout` judges only the row
indices that part of a pre-registered split names; the checkpoint header then
records the split file, its sha256, the part and its size under `rows_subset`,
and the report's n is the subset's. A run without `--rows` judges every row.

`--max-usd X` (above $0, up to $1,000,000, to 6 decimal places) stops the run before any
request once the checkpoint's recorded cost, every session of it counted, is at or above X,
or once a judgment's cost is unknown (the ceiling can no longer be enforced). It exits 3;
the rows written stay a valid, resumable checkpoint. The header records the ceiling as
`max_usd`, and that is the value enforced. A checkpoint resumes under the ceiling its header
records. `--ceiling-amendment <ref>` (the dated amendment) changes it, or, under the same
ceiling, acknowledges the unknown costs recorded so far; only the header line is then
rewritten, appending the previous ceiling, the rows and unknown-cost judgments recorded
under it and the reference to `max_usd_history`. An amendment that changes nothing is
refused. Recorded cost can be below the provider's bill.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from judge_audit import __version__  # noqa: E402
from judge_audit.cli import _judge, nll_text  # noqa: E402
from judge_audit.ground_truth import parse_ground_truth  # noqa: E402
from judge_audit.judges.secrets import evidence_raw  # noqa: E402
from judge_audit.judges.simulated import SIMULATED_TAG  # noqa: E402
from judge_audit.report import fmt4, render_html, render_markdown  # noqa: E402
from judge_audit.runner import (  # noqa: E402
    AuditResult,
    IncompleteAnswers,
    answer_gaps,
    checkpoint_cost,
    checkpoint_record,
    dataset_gaps,
    display_path,
    groups_of,
    is_not_sent,
    load_dataset,
    missing_answer,
    questions_of,
    request_failure,
    run_metadata,
    served_versions,
    sha256_of,
    summarize,
    warn_not_sent,
)

REAL_BANNER = ("> **REAL VENDOR AUDIT** — TypeSafe Jev via the AI Gateway evaluate API (not simulated). "
               "Raw per-row responses: see the checkpoint file named in the provenance line.\n\n")


def load_checkpoint(path: Path) -> dict[int, dict]:
    done: dict[int, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["idx"]] = rec
    return done


def rows_subset(spec: str | None, n_rows: int) -> tuple[list[int], dict | None]:
    """Row indices to judge from `<split.json>:<part>`; (all rows, None) without a spec."""
    if not spec:
        return list(range(n_rows)), None
    path, sep, part = spec.rpartition(":")
    if not sep or not part:
        raise SystemExit(f"--rows expects <split.json>:<part>, got {spec!r}")
    split = json.loads(Path(path).read_text(encoding="utf-8"))
    if part not in split or not isinstance(split[part], list):
        raise SystemExit(f"{path}: no row list named {part!r}")
    idx = sorted(int(i) for i in split[part])
    if idx and (idx[0] < 0 or idx[-1] >= n_rows):
        raise SystemExit(f"{path}:{part} names rows outside 0..{n_rows - 1}")
    return idx, {"split": path, "sha256": sha256_of(path), "part": part, "n": len(idx)}


MAX_USD_LIMIT = Decimal(1_000_000)
CENT_FRACTION = Decimal("0.000001")  # a ceiling is kept to 6 decimal places


def usd(text: str) -> float:
    """A --max-usd value: above $0, up to $1,000,000, to 6 decimal places.

    Returned as the float the header records. Within these bounds the float's shortest
    repr is the decimal typed, so `ceiling_of` enforces exactly what the header says."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a dollar amount: {text!r}") from None
    if (not value.is_finite() or not 0 < value <= MAX_USD_LIMIT
            or value != value.quantize(CENT_FRACTION)):
        raise argparse.ArgumentTypeError(
            f"must be above 0 and up to 1000000 dollars, to 6 decimal places; got {text!r}")
    return float(value)


def ceiling_of(max_usd: float) -> Decimal:
    """The ceiling enforced for a header's `max_usd`: the decimal its number reads as."""
    return Decimal(repr(max_usd))


def amendment_ref(text: str) -> str:
    """A --ceiling-amendment value: one short printable line naming the amendment."""
    # isprintable() before strip(): strip() would drop a trailing U+2028 or U+0085.
    ref = text.strip(" ")
    if not ref or len(ref) > 200 or not text.isprintable():
        raise argparse.ArgumentTypeError("one printable line of 1 to 200 characters naming "
                                         "the amendment, e.g. 'v06-plan amendment 2026-10-20'")
    return ref


def acknowledged_unknowns(run: dict | None) -> int:
    """Judgments of unknown cost that a ceiling amendment has acknowledged so far."""
    history = (run or {}).get("max_usd_history") or []
    return max((int(e.get("unknown_cost_judgments") or 0) for e in history), default=0)


def ceiling_change(ckpt: Path, run: dict, max_usd: float | None, ref: str | None,
                   unknown: int) -> bool:
    """Whether this session records a ceiling amendment in the header.

    The header's ceiling governs the rest of the run. Another one, or none, would leave it
    recording a ceiling that no longer held: a dated amendment may change it (never remove
    it), or, under the same ceiling, acknowledge the unknown costs that stopped the run.
    An amendment that would change nothing is refused rather than recorded."""
    was = run.get("max_usd")
    recorded = "records no --max-usd" if was is None else f"records --max-usd {was}"
    unacknowledged = unknown > acknowledged_unknowns(run)
    if was == max_usd:
        if ref is None:
            return False
        if was is None or not unacknowledged:
            raise SystemExit(f"{ckpt} {recorded} and no unknown cost to acknowledge: "
                             f"--ceiling-amendment {ref!r} changes nothing; drop it")
    elif max_usd is None:
        raise SystemExit(f"{ckpt} {recorded}, this run has none; resume under the recorded "
                         "ceiling")
    elif ref is None:
        raise SystemExit(f"{ckpt} {recorded}, this run has {max_usd}; a changed ceiling "
                         "needs --ceiling-amendment <ref>, or use a new checkpoint")
    if any(e.get("amendment") == ref for e in run.get("max_usd_history") or []):
        raise SystemExit(f"{ckpt}: amendment {ref!r} is already recorded in its header; "
                         "each change needs its own reference")
    return True


def amend_ceiling(ckpt: Path, header: dict, max_usd: float, ref: str, until_rows: int,
                  unknown: int) -> dict:
    """Rewrite only the checkpoint's header line with a ceiling changed by amendment.

    The previous ceiling, how many rows and unknown-cost judgments were recorded under it
    and the amendment's reference are appended to `max_usd_history`. Every other line keeps
    its bytes, CRLF included, and the header keeps its line ending. The new file is written
    beside the old one with its mode, synced, then moved into place: a failure leaves the
    old checkpoint byte for byte and no temporary file."""
    run = dict(header["run"])
    run["max_usd_history"] = [*(run.get("max_usd_history") or []), {
        "max_usd": run.get("max_usd"), "until_rows": until_rows,
        "unknown_cost_judgments": unknown, "amendment": ref,
        "changed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}]
    run["max_usd"] = max_usd
    new = {**header, "run": run}
    lines = ckpt.read_bytes().splitlines(keepends=True)
    at = next(i for i, line in enumerate(lines)
              if line.strip() and json.loads(line).get("idx") == -1)
    ending = lines[at][len(lines[at].rstrip(b"\r\n")):] or b"\n"
    lines[at] = json.dumps(new, allow_nan=False).encode("utf-8") + ending
    tmp = ckpt.with_name(ckpt.name + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(b"".join(lines))
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, stat.S_IMODE(ckpt.stat().st_mode))
        os.replace(tmp, ckpt)
    except OSError as e:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"{display_path(ckpt)}: could not rewrite the header "
                         f"({type(e).__name__}); the checkpoint is unchanged") from None
    return new


def recorded_cost(records, run: dict | None) -> tuple[Decimal, int]:
    """The recorded cost of checkpoint rows and how many of their judgments have none.

    Each judgment's cost is the one the report totals (`checkpoint_cost`), so an unknown
    cost is never counted as $0. The recorded values are summed as decimals: in floats
    0.7 + 0.1 falls short of a 0.8 ceiling and one more request would be sent."""
    spent, unknown = Decimal(0), 0
    for rec in records:
        for j in rec.get("judgments", []):
            cost = checkpoint_cost(j, run)
            if cost is None:
                unknown += 1
            else:
                spent += Decimal(repr(cost))
    return spent, unknown


def ceiling_stop(spent: Decimal, unknown: int, max_usd: Decimal,
                 acknowledged: int = 0) -> str | None:
    """Why --max-usd stops the run before its next request, or None to send it. Unknown
    costs that an amendment acknowledged no longer stop it; any further one does."""
    if unknown > acknowledged:
        beyond = f" beyond the {acknowledged} acknowledged" if acknowledged else ""
        return (f"cost ceiling cannot be enforced: {unknown - acknowledged} judgment(s) "
                f"recorded with unknown cost{beyond} (${spent:f} known, ceiling "
                f"${max_usd:f}); a dated --ceiling-amendment can acknowledge them")
    if spent >= max_usd:
        return f"cost ceiling reached: ${spent:f} recorded of ${max_usd:f}"
    return None


def build_result(judge_name: str, rows: list[dict], dataset_meta: dict, wanted: list[int],
                 done: dict[int, dict], ckpt: Path, started: dict,
                 subset: dict | None, cluster_rows: list[dict] | None = None) -> AuditResult:
    """The report of a complete checkpoint: pure function of the checkpoint and the labels.

    `scripts/runs_report.py` calls this same function to regenerate every committed
    per-run report, so a fresh run and a regeneration write the same bytes.
    `cluster_rows` supplies the bootstrap's cluster texts when they are not the judged
    rows' own: a deliberation dataset clusters on the original texts, as jury_report does.
    """
    if -1 in done:
        run = dict(done[-1]["run"])
    else:
        # Checkpoint predates run headers: say so instead of inventing a timestamp.
        run = {k: v for k, v in started.items() if k != "timestamp_utc"}
        run["recomputed_utc"] = started["timestamp_utc"]
        run["note"] = "original run time not recorded in this checkpoint"
    run["checkpoint"] = display_path(ckpt)
    # The tier is a property of the dataset, not of the run: read it from the labels
    # file so a checkpoint that predates ground-truth headers still reports it.
    run["dataset"] = dict(run.get("dataset") or {})
    run["dataset"]["ground_truth"] = parse_ground_truth(
        dataset_meta.get("ground_truth")).to_dict()
    if subset:
        run["rows_subset"] = subset
    records = []
    # Checkpoint order — the order the judge answered, which a resumed run does not keep
    # sorted — as the Arena and jury tables read it, so their intervals (seeded bootstrap
    # over clusters in first-seen order) are the same numbers as this report's.
    chosen = set(wanted)
    for idx in [k for k in done if k in chosen]:
        row = rows[idx]
        labels = row.get("labels", {})
        for j in done[idx]["judgments"]:
            expected = labels.get(j["question"])
            if expected is None:
                continue
            records.append(checkpoint_record(idx, row, j, expected, run))
    # Intervals resample distinct texts, as every published interval does (the report
    # says so); without `groups` they would silently be row-i.i.d. and too narrow.
    served = served_versions(records)  # None for checkpoints written before it was recorded
    if served:
        run["served"] = served
    return summarize(judge_name, records, run,
                     groups=groups_of(records, cluster_rows or rows))


def checkpoint_row(idx: int, row: dict, judgments: list) -> dict:
    """The checkpoint line for one judged row, under the live runner's contract: a skipped
    labelled question is written down as a no-answer (wrong, confidence and latency
    unknown); a doubled answer stops the run. A judge that doubles the same answer every
    time therefore stops a resumed run on the same row: fix the adapter, not the data."""
    gap = answer_gaps(row, [j.question for j in judgments])
    if gap["duplicate"]:
        raise SystemExit(f"row {idx}: the judge answered {gap['duplicate']} twice — "
                         "the checkpoint would not be complete")
    return {"idx": idx,
            "judgments": [{"question": j.question, "decision": j.decision,
                           "confidence": j.confidence, "latency_s": j.latency_s,
                           "cost_usd": j.cost_usd, "raw": evidence_raw(j.raw),
                           "parse_status": j.parse_status} for j in judgments]
            + [missing_answer(q, judgments) for q in gap["missing"]]}


def recorded_judge(done: dict[int, dict]) -> str | None:
    """The adapter name the checkpoint's header recorded (`llm` for `llm:gemma4:e4b`)."""
    if -1 not in done:
        return None
    name = (done[-1]["run"].get("judge") or {}).get("name")
    return str(name).split(":")[0] if name else None


# What makes two runs of one adapter the same measurement: a checkpoint resumed with any of
# these changed would mix two methods under one header (e.g. LLM_SAMPLES or LLM_TEMPERATURE),
# or two endpoints (LLM_PROVIDER, LLM_BASE_URL).
METHOD_KEYS = ("name", "provider", "model", "base_url", "confidence_method", "temperature",
               "samples", "prompt_sha256")


def same_method(ckpt: Path, recorded: dict, now: dict) -> None:
    for key in METHOD_KEYS:
        if (key in recorded or key in now) and recorded.get(key) != now.get(key):
            raise SystemExit(f"{ckpt} was started with judge {key}={recorded.get(key)!r}, "
                             f"this run has {now.get(key)!r}; use a new checkpoint")


def tag_of(judge_name: str) -> str:
    """The banner a report of this judge carries: only the simulated judge is fake."""
    return SIMULATED_TAG if judge_name == "simulated" else ""


def report_markdown(result: AuditResult, judge_name: str) -> str:
    md = render_markdown(result)
    if judge_name == "jev":
        return REAL_BANNER + md
    tag = tag_of(judge_name)
    return f"> ⚠️ **{tag}**\n\n" + md if tag else md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("labels")
    ap.add_argument("--judge", default="jev")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--html", default=None)
    ap.add_argument("--rows", default=None,
                    help="<split.json>:<part> — judge only these row indices (held-out runs)")
    ap.add_argument("--cluster-labels", default=None,
                    help="labels file whose row texts are the interval's clusters (default: "
                         "LABELS; a deliberation round passes the original dataset)")
    ap.add_argument("--max-usd", type=usd, default=None, metavar="X",
                    help="stop before the next request once the checkpoint's recorded cost "
                         "reaches X dollars (recorded cost can be below the provider's bill)")
    ap.add_argument("--ceiling-amendment", type=amendment_ref, default=None, metavar="REF",
                    help="resume a checkpoint under a --max-usd other than the one its header "
                         "records; REF names the dated amendment that changed it")
    args = ap.parse_args()
    if args.ceiling_amendment is not None and args.max_usd is None:
        ap.error("--ceiling-amendment needs --max-usd: an amendment changes a ceiling, "
                 "it does not remove one")
    max_usd = args.max_usd  # the float the header records and `ceiling_of` enforces

    rows, dataset_meta = load_dataset(args.labels)
    wanted, subset = rows_subset(args.rows, len(rows))
    ckpt = Path(args.checkpoint)
    ckpt.parent.mkdir(parents=True, exist_ok=True)
    done = load_checkpoint(ckpt)
    if -1 in done:
        was = done[-1]["run"].get("rows_subset") or {}
        now = subset or {}
        if (was.get("sha256"), was.get("part")) != (now.get("sha256"), now.get("part")):
            raise SystemExit(f"{ckpt} was started with a different --rows subset; "
                             "use a new checkpoint")
    n_done = sum(k in done for k in wanted)
    print(f"checkpoint: {n_done}/{len(wanted)} rows already done"
          + (f" (subset {subset['part']} of {subset['split']})" if subset else ""))

    # Who answered is what the checkpoint recorded, not what this command line says: a
    # simulated checkpoint recomputed with `--judge llm` is still a simulation.
    name = recorded_judge(done) or args.judge
    if n_done >= len(wanted):
        # Complete checkpoint: recompute only. No key, no judge, no API call.
        judge, tag = None, tag_of(name)
        started = {"judge": {"name": name, "model": "typesafe-ai/jev", "backend": "gateway"}
                   if name == "jev" else {"name": name},
                   "judge_audit_version": __version__,
                   "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    else:
        if name != args.judge:
            raise SystemExit(f"{ckpt} was started by judge {name!r}, not {args.judge!r}; "
                             "use a new checkpoint")
        judge, tag = _judge(args.judge, rows)
        started = run_metadata(judge, args.labels, len(rows), dataset_meta)
        if -1 in done:
            # The header is written once, by the first session; a resumed session must send
            # the same routing fields, or the header would record a routing that no longer held.
            was = (done[-1]["run"].get("judge") or {}).get("extra_body")
            now = (started.get("judge") or {}).get("extra_body")
            if was != now:
                raise SystemExit(f"{ckpt} was started with LLM_EXTRA_BODY {was!r}, not {now!r}; "
                                 "resume with the same routing or use a new checkpoint")
            same_method(ckpt, done[-1]["run"].get("judge") or {}, started["judge"])
            was_max = done[-1]["run"].get("max_usd")
            _, unknown = recorded_cost((done[k] for k in done if k >= 0), done[-1]["run"])
            if ceiling_change(ckpt, done[-1]["run"], max_usd, args.ceiling_amendment, unknown):
                assert max_usd is not None and args.ceiling_amendment is not None
                done[-1] = amend_ceiling(ckpt, done[-1], max_usd, args.ceiling_amendment,
                                         sum(1 for k in done if k >= 0), unknown)
                print(f"ceiling {was_max} -> {max_usd} under {args.ceiling_amendment!r}, "
                      f"{unknown} unknown-cost judgment(s) acknowledged", flush=True)
    if subset:
        started["rows_subset"] = subset
    if max_usd is not None:
        started["max_usd"] = max_usd

    with open(ckpt, "a", encoding="utf-8") as f:
        if not done:
            # First line of a fresh checkpoint: how this run was produced.
            header = {"idx": -1, "run": started}
            f.write(json.dumps(header, allow_nan=False) + "\n")
            done[-1] = header  # the report reads the run time from here, as a rerun would
        warned = False  # one not-sent warning per invocation, at the first such row
        run = (done.get(-1) or {}).get("run")
        # Every session's rows count, so a resumed run cannot reset the ceiling's count.
        spent, unknown = recorded_cost((done[k] for k in done if k >= 0), run)
        for idx in wanted:
            row = rows[idx]
            if idx in done:
                continue
            try:
                dataset_gaps(idx, row)  # a dataset error stops the run before the paid call
            except IncompleteAnswers as e:
                raise SystemExit(str(e)) from e
            stop = (ceiling_stop(spent, unknown, ceiling_of(max_usd),
                                 acknowledged_unknowns(run))
                    if max_usd is not None else None)
            if stop:
                print(f"{stop}; {sum(1 for k in done if k >= 0)} rows kept in "
                      f"{display_path(ckpt)}", file=sys.stderr)
                raise SystemExit(3)
            # If the gateway's rate-limit window outlasts the adapter's backoff,
            # or a call stalls (timeout), sleep it off and retry instead of
            # losing the whole run.
            for attempt in range(4):
                try:
                    judgments = list(judge.decide(row["state"], questions_of(row)))
                    break
                except Exception as e:
                    transient = ("rate-limited" in str(e).lower()
                                 or "timeout" in type(e).__name__.lower()
                                 or "timed out" in str(e).lower())
                    if transient and attempt < 3:
                        wait = (attempt + 1) * 600
                        print(f"  transient error at row {idx} "
                              f"({type(e).__name__}); sleeping {wait}s "
                              f"(attempt {attempt + 1}/3)", flush=True)
                        time.sleep(wait)
                    elif os.environ.get("JUDGE_AUDIT_DEBUG"):
                        raise
                    else:
                        # The rows already judged are on disk: a rerun resumes after them.
                        print(f"judge request failed: row {idx}: {request_failure(e)}; "
                              f"{sum(1 for k in done if k >= 0)} rows "
                              f"kept in {display_path(ckpt)}; rerun to resume",
                              file=sys.stderr)
                        raise SystemExit(2) from None
            rec = checkpoint_row(idx, row, judgments)
            if not warned:
                first = next((j for j in rec["judgments"] if is_not_sent(j.get("raw"))), None)
                if first is not None:
                    warn_not_sent(name, idx, first["question"], first["raw"],
                                  getattr(judge, "over_length_advice", None))
                    warned = True
            f.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            done[idx] = rec
            n_done += 1
            row_spent, row_unknown = recorded_cost([rec], run)
            spent, unknown = spent + row_spent, unknown + row_unknown
            if n_done % 10 == 0:
                print(f"  {n_done}/{len(wanted)}", flush=True)

    cluster_rows = load_dataset(args.cluster_labels)[0] if args.cluster_labels else None
    result = build_result(name, rows, dataset_meta, wanted, done, ckpt, started, subset,
                          cluster_rows)
    md = report_markdown(result, name)
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.json).write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    if args.html:
        Path(args.html).write_text(render_html(result, tag=tag), encoding="utf-8")
    confidence = result.confidence
    cost = f"${result.total_cost_usd:.4f}" if result.total_cost_usd is not None else "unknown"
    print(f"judge={result.judge} n={result.n} accuracy={result.accuracy:.1%} "
          f"{'not_sent=' + str(result.not_sent) + ' ' if result.not_sent else ''}"
          f"confidence_known={confidence['known']}/{confidence['total']} "
          f"ece={fmt4(result.ece)} ece_equal_mass={fmt4(result.ece_equal_mass)} "
          f"brier={fmt4(result.brier)} nll={nll_text(result)} gt={result.run['dataset']['ground_truth']['tier']} "
          f"cost={cost} -> {args.out}")


if __name__ == "__main__":
    main()
