"""judge-audit as an MCP server: the agent audits its own judge in place.

Point Claude Code / Cursor / any MCP client at `judge-audit-mcp` and the agent
can, from inside a session:

  - `run_audit`    shadow-audit a judge against a labeled JSONL file: accuracy,
                   ECE, zero-error coverage, cost, latency, provenance.
  - `check_drift`  is the judge less honest than a baseline audit-result.json?
  - `list_judges`  which judges are available and what each one needs.

Same engine as the CLI. The only network calls are the ones the configured
judge makes; the simulated judge makes none and is always labelled SIMULATED.
Requires the optional extra: `pip install "kunko-judge-audit[mcp]"`.
"""

from __future__ import annotations

import argparse
import os

from .cli import JUDGES, _judge
from .ground_truth import ground_truth_of
from .judges.base import Judge
from .judges.simulated import SIMULATED_TAG
from .report import IncompatibleBaseline
from .report import check_drift as _check_drift
from .runner import load_dataset, write_judgments
from .runner import run_audit as _run_audit

try:
    from mcp.server.mcpserver import MCPServer
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "judge-audit-mcp needs the MCP SDK: pip install 'kunko-judge-audit[mcp]'"
    ) from exc

server = MCPServer(
    name="judge-audit",
    instructions=(
        "Independent calibration audits for AI judges. Call run_audit with a labeled "
        "JSONL file to learn whether a judge's confidence is honest (ECE), what share "
        "of decisions can be automated at zero observed errors, and what it costs. Call "
        "check_drift against a previous audit-result.json to see if the judge degraded. "
        "Results from the simulated judge are demos and carry a SIMULATED tag."
    ),
)

JUDGE_INFO: dict[str, dict[str, object]] = {
    "jev": {
        "description": "TypeSafe Jev (judgment model; confidence is P(chosen option)). "
                       "JEV_ENDPOINT points the direct backend at any Jev-compatible server.",
        "env": ["AI_GATEWAY_API_KEY (gateway backend, default; needs Node)",
                "JEV_BACKEND=typesafe + TYPESAFE_API_KEY (direct API)",
                "JEV_BACKEND=typesafe + JEV_ENDPOINT (Jev-compatible server, key optional)",
                "JEV_MODEL, JEV_MIN_INTERVAL_S (optional)"],
    },
    "llm": {
        "description": "Any chat model as a judge; confidence is verbalized by the model "
                       "and labelled as such.",
        "env": ["LLM_PROVIDER=anthropic (default) + ANTHROPIC_API_KEY; extra [anthropic]",
                "LLM_PROVIDER=openai-compatible + LLM_BASE_URL + LLM_MODEL (+ LLM_API_KEY)",
                "LLM_EFFORT (anthropic only, optional)"],
    },
    "nli": {
        "description": "Local zero-shot NLI encoder (DeBERTa-class): the small-model baseline. "
                       "Confidence is the entailment softmax over options; cannot follow "
                       "instructions by design.",
        "env": ["extra [nli] (transformers + torch)",
                "NLI_MODEL, NLI_HYPOTHESIS, NLI_DEVICE (optional)"],
    },
    "finetuned": {
        "description": "A sequence classifier fine-tuned on your own labels "
                       "(scripts/train_classifier.py). Confidence is the softmax probability "
                       "of the chosen option; reads only the state text, never instructions "
                       "or option descriptions.",
        "env": ["extra [nli] (transformers + torch)", "FINETUNED_MODEL_DIR (required)",
                "FINETUNED_DEVICE, FINETUNED_MAX_LEN (optional)"],
    },
    "simulated": {
        "description": "Seeded simulator to see the pipeline without a key. Not a real "
                       "vendor audit; every result is tagged SIMULATED.",
        "env": [],
    },
}


def _resolve(path: str) -> str | None:
    """Absolute path if the file exists, else None. Relative paths resolve from cwd."""
    full = os.path.abspath(path)
    return full if os.path.isfile(full) else None


def _load(labels_path: str) -> tuple[list[dict] | None, dict, dict | None]:
    """(rows, dataset header, error) — rows is None when error is set."""
    full = _resolve(labels_path)
    if full is None:
        return None, {}, {"error": f"labels file not found: {labels_path} (cwd {os.getcwd()})"}
    try:
        rows, dataset_meta = load_dataset(full)
    except (OSError, ValueError) as exc:
        return None, {}, {"error": f"cannot read {labels_path}: {exc}"}
    if not rows:
        return None, {}, {"error": f"{labels_path} has no rows"}
    return rows, dataset_meta, None


def _make_judge(name: str, rows: list[dict]) -> tuple[Judge | None, str, dict | None]:
    if name not in JUDGES:
        return None, "", {"error": f"unknown judge '{name}' (available: {', '.join(JUDGES)})"}
    try:
        judge, tag = _judge(name, rows)
    except (RuntimeError, ValueError) as exc:
        return None, "", {"error": f"judge '{name}' is not configured: {exc}"}
    return judge, tag, None


@server.tool(description=(
    "Audit a judge in shadow mode against a labeled JSONL file "
    "({state, questions, labels} per line). Returns n, accuracy, ECE (equal-width bins), "
    "ece_equal_mass (equal-mass bins, ties never split), brier (Brier score, no bins), "
    "nll (log loss, never clipped: null when infinite, with nll_infinite = the answers "
    "declared certain and wrong), "
    "reliability bins, accuracy-coverage curve, zero-error coverage (calibration metrics use "
    "only the confidence.known rows out of confidence.total and are null when none are known; "
    "each headline number with a 95 % bootstrap interval: accuracy_ci / ece_ci / "
    "ece_equal_mass_ci / brier_ci / nll_ci / zero_error_coverage_ci), total cost (null when "
    "an unknown billable price prevents aggregation), p50/p99 and slowest latency, the run "
    "provenance (judge, model, backend, dataset sha256) and ground_truth: the dataset's "
    "provenance tier (GT-0 unknown … GT-6 production outcome; docs/ground-truth.md) that says "
    "what the accuracy is evidence of. judge: jev | llm | simulated "
    "(default; no key, tagged SIMULATED). judgments_path: optional JSONL to write "
    "per-decision evidence."))
def run_audit(labels_path: str, judge: str = "simulated",
              judgments_path: str | None = None) -> dict:
    rows, dataset_meta, err = _load(labels_path)
    if err or rows is None:
        return err or {"error": "internal: no rows or judge"}
    j, tag, err = _make_judge(judge, rows)
    if err or j is None:
        return err or {"error": "internal: no rows or judge"}
    try:
        result = _run_audit(j, rows, labels_path=os.path.abspath(labels_path),
                            dataset_meta=dataset_meta)
    except Exception as exc:  # judge/network failure: report, do not crash the server
        return {"error": f"audit failed: {type(exc).__name__}: {exc}"}
    out = result.to_dict()
    gt = ground_truth_of(result.run)
    out["ground_truth"] = {"tier": gt.tier, "label": gt.label, "line": gt.report_line()}
    if tag:
        out["tag"] = tag
    if judgments_path:
        try:
            write_judgments(result, judgments_path)
            out["judgments_path"] = os.path.abspath(judgments_path)
        except OSError as exc:
            out["judgments_error"] = f"cannot write {judgments_path}: {exc}"
    return out


@server.tool(description=(
    "CI-style drift gate: re-audit the judge and compare with a baseline audit-result.json. "
    "ok is false when ECE rose more than max_ece_drift or accuracy fell more than "
    "max_acc_drop; failures explains which. A baseline without numeric ece/accuracy is "
    "an error, and so is one that measured another dataset, judge or n — pass "
    "allow_incompatible to compare anyway."))
def check_drift(labels_path: str, baseline_path: str, judge: str = "simulated",
                max_ece_drift: float = 0.02, max_acc_drop: float = 0.01,
                allow_incompatible: bool = False) -> dict:
    rows, dataset_meta, err = _load(labels_path)
    if err or rows is None:
        return err or {"error": "internal: no rows or judge"}
    baseline = _resolve(baseline_path)
    if baseline is None:
        return {"error": f"baseline file not found: {baseline_path} (cwd {os.getcwd()})"}
    j, tag, err = _make_judge(judge, rows)
    if err or j is None:
        return err or {"error": "internal: no rows or judge"}
    try:
        result = _run_audit(j, rows, labels_path=os.path.abspath(labels_path),
                            dataset_meta=dataset_meta)
        failures = _check_drift(result, baseline, max_ece_drift, max_acc_drop,
                                allow_incompatible=allow_incompatible)
    except IncompatibleBaseline as exc:
        return {"error": str(exc), "incompatible_baseline": True}
    except (OSError, ValueError, KeyError) as exc:
        return {"error": f"cannot use baseline {baseline_path}: {exc}"}
    except Exception as exc:
        return {"error": f"audit failed: {type(exc).__name__}: {exc}"}
    out = {"ok": not failures, "failures": failures,
           "ece": result.ece, "accuracy": result.accuracy, "n": result.n,
           "ground_truth": ground_truth_of(result.run).tier,
           "baseline": baseline}
    if tag:
        out["tag"] = tag
    return out


@server.tool(description=(
    "List the judges this server can audit, with what each needs. simulated needs "
    "nothing and is a demo; jev and llm call the configured model API."))
def list_judges() -> dict:
    return {"judges": [{"name": name, **JUDGE_INFO[name]} for name in JUDGES],
            "simulated_tag": SIMULATED_TAG}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="judge-audit-mcp",
        description="judge-audit as an MCP server over stdio (tools: run_audit, check_drift, "
                    "list_judges). Add it with: claude mcp add judge-audit -- judge-audit-mcp")
    ap.parse_args(argv)
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
