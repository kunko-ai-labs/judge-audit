"""Ground-truth provenance tiers: declared once, parsed at load, printed in every report."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from judge_audit.ground_truth import (
    TIERS,
    GroundTruth,
    ground_truth_of,
    parse_ground_truth,
)
from judge_audit.judges.simulated import SimulatedJudge
from judge_audit.metrics.calibration import expected_calibration_error
from judge_audit.report import ground_truth_line, render_html, render_markdown
from judge_audit.runner import (
    load_dataset,
    load_jsonl,
    read_dataset_header,
    run_audit,
    run_metadata,
    sha256_of,
    sha256_rows_of,
)

ROOT = Path(__file__).resolve().parent.parent

GT1 = {"tier": "GT-1", "label": "constructed", "validation": "not_validated",
       "purpose": ["calibration stress test"],
       "caveats": ["routing label by design", "downstream task quality not measured"]}


def _with_header(labels_path: Path, header: dict) -> Path:
    """The fixture rows with a dataset header line in front; rows stay byte-identical."""
    body = labels_path.read_bytes()
    out = labels_path.with_name("tiered.jsonl")
    out.write_bytes(json.dumps({"idx": -1, "dataset": header}).encode() + b"\n" + body)
    return out


# --- the table -----------------------------------------------------------------

def test_seven_tiers_defined_once_with_a_label_and_a_one_line_meaning():
    assert list(TIERS) == [f"GT-{i}" for i in range(7)]
    labels = [TIERS[t][0] for t in TIERS]
    assert labels == ["unknown", "constructed", "synthetic, validated", "human-annotated",
                      "expert consensus", "empirically validated", "production outcome"]
    for tier, (label, meaning) in TIERS.items():
        assert label and meaning and "\n" not in meaning, tier


def test_parse_accepts_every_tier_and_defaults_to_gt0():
    for tier in TIERS:
        gt = parse_ground_truth({"tier": tier})
        assert gt.tier == tier and gt.label == TIERS[tier][0]
        assert gt.validation == "not_validated" and gt.caveats == ()
    assert parse_ground_truth(None) == GroundTruth() and not GroundTruth().declared
    assert ground_truth_of({}).tier == "GT-0" and ground_truth_of(None).tier == "GT-0"


@pytest.mark.parametrize("raw, fragment", [
    ({"tier": "GT-7"}, "unknown ground-truth tier 'GT-7'"),
    ({"tier": "gt-1"}, "unknown ground-truth tier 'gt-1'"),
    ({}, "unknown ground-truth tier None"),
    ({"tier": "GT-1", "label": "production outcome"}, "does not match GT-1"),
    ({"tier": "GT-1", "caveat": ["typo"]}, "unknown field(s) ['caveat']"),
    ({"tier": "GT-1", "caveats": "not a list"}, "caveats must be a list of strings"),
    ({"tier": "GT-1", "validation": ""}, "validation must be a non-empty string"),
    ("GT-1", "must be an object"),
])
def test_parse_fails_loudly(raw, fragment):
    with pytest.raises(ValueError, match=re.escape(fragment)):
        parse_ground_truth(raw)


def test_to_dict_carries_the_meaning_for_stdlib_consumers():
    d = parse_ground_truth(GT1).to_dict()
    assert d == {"tier": "GT-1", "label": "constructed", "meaning": TIERS["GT-1"][1],
                 "validation": "not_validated", "purpose": ["calibration stress test"],
                 "caveats": ["routing label by design", "downstream task quality not measured"]}
    # and round-trips through the parser (a recorded run is re-validated, not trusted)
    assert parse_ground_truth(d) == parse_ground_truth(GT1)


# --- the header line -----------------------------------------------------------

def test_load_dataset_returns_rows_and_header_and_load_jsonl_rows_only(labels_path):
    rows_plain, meta_plain = load_dataset(str(labels_path))
    assert len(rows_plain) == 12 and meta_plain == {}
    tiered = _with_header(labels_path, {"ground_truth": GT1})
    rows, meta = load_dataset(str(tiered))
    assert rows == rows_plain and meta == {"ground_truth": GT1}
    assert load_jsonl(str(tiered)) == rows_plain
    assert read_dataset_header(str(tiered)) == {"ground_truth": GT1}
    assert read_dataset_header(str(labels_path)) == {}


def test_unknown_tier_in_the_header_fails_at_load(labels_path):
    bad = _with_header(labels_path, {"ground_truth": {"tier": "GT-9"}})
    with pytest.raises(ValueError, match="unknown ground-truth tier 'GT-9'"):
        load_jsonl(str(bad))
    with pytest.raises(ValueError, match="unknown ground-truth tier 'GT-9'"):
        read_dataset_header(str(bad))


def test_header_must_be_first_and_must_carry_a_dataset_object(labels_path):
    body = labels_path.read_text()
    late = labels_path.with_name("late.jsonl")
    late.write_text(body + json.dumps({"idx": -1, "dataset": {}}) + "\n")
    with pytest.raises(ValueError, match="must be the first line"):
        load_dataset(str(late))
    bare = labels_path.with_name("bare.jsonl")
    bare.write_text(json.dumps({"idx": -1}) + "\n" + body)
    with pytest.raises(ValueError, match="'dataset' object"):
        load_dataset(str(bare))


def test_sha256_covers_the_header_and_sha256_rows_does_not(labels_path):
    tiered = _with_header(labels_path, {"ground_truth": GT1})
    assert sha256_rows_of(str(tiered)) == sha256_of(str(labels_path))
    assert sha256_of(str(tiered)) != sha256_of(str(labels_path))
    assert sha256_rows_of(str(labels_path)) == sha256_of(str(labels_path))


# --- run metadata and reports --------------------------------------------------

def test_run_metadata_records_the_tier_gt0_when_absent(labels_path):
    rows, meta = load_dataset(str(labels_path))
    judge = SimulatedJudge(rows)
    ds = run_metadata(judge, str(labels_path), len(rows), meta)["dataset"]
    assert ds["ground_truth"]["tier"] == "GT-0" and ds["ground_truth"]["label"] == "unknown"
    assert ds["sha256"] == ds["sha256_rows"] == sha256_of(str(labels_path))

    tiered = _with_header(labels_path, {"ground_truth": GT1})
    rows, meta = load_dataset(str(tiered))
    res = run_audit(SimulatedJudge(rows), rows, labels_path=str(tiered), dataset_meta=meta)
    gt = res.run["dataset"]["ground_truth"]
    assert gt["tier"] == "GT-1" and gt["caveats"] == GT1["caveats"]
    # the header is read from the file when the caller did not pass it
    res2 = run_audit(SimulatedJudge(rows), rows, labels_path=str(tiered))
    assert res2.run["dataset"]["ground_truth"] == gt
    assert res2.run["dataset"]["sha256_rows"] == sha256_of(str(labels_path))


def test_report_line_declared_and_undeclared():
    run = {"dataset": {"ground_truth": parse_ground_truth(GT1).to_dict()}}
    assert ground_truth_line(run) == (
        "Ground truth: GT-1 constructed — " + TIERS["GT-1"][1]
        + "; routing label by design; downstream task quality not measured")
    assert ground_truth_line({}) == ("Ground truth: GT-0 unknown — declare it with a dataset "
                                     "header line (see docs/ground-truth.md)")


def test_markdown_and_html_headers_show_the_tier(labels_path):
    tiered = _with_header(labels_path, {"ground_truth": GT1})
    rows, meta = load_dataset(str(tiered))
    res = run_audit(SimulatedJudge(rows), rows, labels_path=str(tiered), dataset_meta=meta)
    line = "Ground truth: GT-1 constructed — " + TIERS["GT-1"][1] + "; routing label by design"
    md = render_markdown(res)
    assert line in md and md.index(line) < md.index("## Can I automate this?")
    pytest.importorskip("matplotlib")
    html = render_html(res)
    assert line in html and html.index(line) < html.index("<h2>Can I automate this?</h2>")

    plain = run_audit(SimulatedJudge(rows), rows, labels_path=str(labels_path))
    hint = "Ground truth: GT-0 unknown — declare it with a dataset header line"
    assert hint in render_markdown(plain)


# --- CLI, MCP ------------------------------------------------------------------

def test_cli_summary_line_and_result_json_carry_the_tier(labels_path, tmp_path):
    tiered = _with_header(labels_path, {"ground_truth": GT1})
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(tiered),
                        "--judge", "simulated"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert " gt=GT-1 " in r.stdout
    res = json.loads((tmp_path / "audit-result.json").read_text())
    assert res["run"]["dataset"]["ground_truth"]["tier"] == "GT-1"
    assert "Ground truth: GT-1 constructed — " in (tmp_path / "audit-report.md").read_text()
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(labels_path),
                        "--judge", "simulated"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0 and " gt=GT-0 " in r.stdout


def test_cli_unknown_tier_is_exit_2(labels_path, tmp_path):
    bad = _with_header(labels_path, {"ground_truth": {"tier": "GT-42"}})
    r = subprocess.run([sys.executable, "-m", "judge_audit.cli", "run", str(bad),
                        "--judge", "simulated"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 2 and "unknown ground-truth tier 'GT-42'" in r.stderr


def test_mcp_run_audit_shows_the_tier_next_to_accuracy(labels_path):
    pytest.importorskip("mcp")
    from judge_audit import mcp_server
    tiered = _with_header(labels_path, {"ground_truth": GT1})
    out = mcp_server.run_audit(str(tiered))
    assert out["ground_truth"]["tier"] == "GT-1"
    assert out["ground_truth"]["line"].startswith("Ground truth: GT-1 constructed — ")
    assert out["run"]["dataset"]["ground_truth"]["tier"] == "GT-1"
    plain = mcp_server.run_audit(str(labels_path))
    assert plain["ground_truth"]["tier"] == "GT-0"
    assert "docs/ground-truth.md" in plain["ground_truth"]["line"]
    bad = _with_header(labels_path, {"ground_truth": {"tier": "GT-9"}})
    assert "unknown ground-truth tier 'GT-9'" in mcp_server.run_audit(str(bad))["error"]


# --- the published datasets ----------------------------------------------------

@pytest.mark.parametrize("labels", [
    "examples/email-routing/labels.jsonl",
    "examples/email-routing-adversarial/labels.jsonl",
    "examples/task-routing/labels.jsonl",
    "examples/task-routing/labels-described.jsonl",
])
def test_published_datasets_declare_gt1_with_caveats(labels):
    gt = parse_ground_truth(read_dataset_header(str(ROOT / labels)).get("ground_truth"))
    assert gt.tier == "GT-1" and gt.validation == "not_validated"
    assert gt.purpose and len(gt.caveats) >= 2


# --- docs/ground-truth.md: what each tier lets you claim ------------------------

def claim_table(root) -> list[list[str]]:
    text = (root / "docs" / "ground-truth.md").read_text(encoding="utf-8")
    section = text.split("## What each tier lets you claim", 1)[1].split("\n## ", 1)[0]
    return [[c.strip() for c in line.strip().strip("|").split("|")]
            for line in section.splitlines() if line.startswith("| GT-")]


def test_claim_table_rows_are_exactly_the_tiers_in_code(root):
    rows = claim_table(root)
    assert [r[0] for r in rows] == [f"{tier} {label}" for tier, (label, _) in TIERS.items()]
    assert all(len(r) == 4 for r in rows)


def test_claim_table_verdicts(root):
    table = {r[0].split()[0]: r[1:] for r in claim_table(root)}
    assert table["GT-0"] == ["✗", "✗", "✗"]
    # synthetic items say nothing about production, however good their labels
    assert table["GT-1"][2] == "✗" and table["GT-2"][2] == "✗"
    # one annotator: unmeasured label noise moves ECE and blurs comparisons
    assert table["GT-3"][:2] == ["with caveats (label noise)"] * 2
    assert table["GT-5"][2] == "with caveats (only if items are sampled from production)"
    assert table["GT-6"] == ["✓", "✓", "✓"]
    assert [t for t, r in table.items() if r[2] == "✓"] == ["GT-6"]


def test_label_noise_example_in_the_doc_is_what_the_metric_computes(root):
    # ten answers at 0.9, nine right: calibrated against reality ...
    reality = [True] * 9 + [False]
    assert expected_calibration_error([0.9] * 10, reality) == pytest.approx(0.0)
    # ... one right row mislabelled: 8/10 right against the labels, ECE 0.100
    labels = [True] * 8 + [False] * 2
    assert expected_calibration_error([0.9] * 10, labels) == pytest.approx(0.1)
    text = (root / "docs" / "ground-truth.md").read_text(encoding="utf-8")
    assert "ECE 0.000 against reality" in text and "ECE against the labels is 0.100" in text
