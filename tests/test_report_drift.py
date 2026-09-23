"""The drift gate compares like with like: same dataset, same judge, same n."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from judge_audit.report import IncompatibleBaseline, check_drift
from judge_audit.runner import AuditResult


def result(**over) -> AuditResult:
    d = {"judge": "llm:claude-sonnet-4.5", "n": 200, "accuracy": 0.95, "ece": 0.03,
         "run": {"judge": {"name": "llm:claude-sonnet-4.5", "model": "claude-sonnet-4.5"},
                 "dataset": {"path": "labels.jsonl", "rows": 200,
                             "sha256": "aa" * 32, "sha256_rows": "bb" * 32}}}
    d.update(over)
    return AuditResult(**d)


def baseline(tmp_path, **over) -> str:
    d = result().to_dict()
    for key, value in over.items():
        if key in ("judge_name", "model"):
            d["run"]["judge"]["name" if key == "judge_name" else "model"] = value
        elif key in ("sha256", "sha256_rows"):
            d["run"]["dataset"][key] = value
        else:
            d[key] = value
    p = tmp_path / "baseline.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return str(p)


def with_prompt_hash(tmp_path, prompt_sha256: str) -> str:
    """A baseline that recorded the prompt it was measured with."""
    path = Path(baseline(tmp_path))
    d = json.loads(path.read_text(encoding="utf-8"))
    d["run"]["judge"]["prompt_sha256"] = prompt_sha256
    path.write_text(json.dumps(d), encoding="utf-8")
    return str(path)


def test_html_escapes_provenance_strings():
    pytest.importorskip("matplotlib")
    from judge_audit.report import render_html
    r = result()
    r.run["judge"]["model"] = '<script>alert("xss")</script>'
    r.zero_error = {"coverage": 1.0, "n": 200, "threshold": 0.9}
    r.curve = [{"coverage": 1.0, "accuracy": 1.0, "min_confidence": 0.9, "n": 200}]
    r.reliability = [{"bin": "0.9-1.0", "avg_confidence": 0.9, "accuracy": 1.0, "n": 200}]
    page = render_html(r, tag="<b>SIMULATED</b>")
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page and "&lt;b&gt;SIMULATED" in page


JEV_CURVE = [{"coverage": 0.935, "accuracy": 1.0, "n": 187, "min_confidence": 1.0},
             {"coverage": 0.955, "accuracy": 1.0, "n": 191, "min_confidence": 0.98},
             {"coverage": 1.0, "accuracy": 1.0, "n": 200, "min_confidence": 0.89}]
JEV_ROWS = ["| 93.5% | 100.0% | 1.00 | 187 |", "| 95.5% | 100.0% | 0.98 | 191 |",
            "| 100.0% | 100.0% | 0.89 | 200 |"]


def test_markdown_publishes_every_point_of_the_curve():
    # The curve is already one point per real threshold: sampling it (the old `[::4]`,
    # written for a 20-point curve) dropped two of these three. 93.5 % is not 94 %.
    from judge_audit.report import render_markdown
    r = result(curve=JEV_CURVE, zero_error={"coverage": 1.0, "n": 200, "threshold": 0.89})
    md = render_markdown(r)
    table = md.split("## Accuracy vs coverage")[1].split("##")[0]
    assert [line for line in table.splitlines() if line.startswith("| ") and "%" in line] \
        == JEV_ROWS


def test_html_publishes_every_point_of_the_curve():
    pytest.importorskip("matplotlib")
    from judge_audit.report import render_html
    r = result(curve=JEV_CURVE, zero_error={"coverage": 1.0, "n": 200, "threshold": 0.89})
    page = render_html(r)
    table = page.split("<h2>Accuracy vs coverage</h2>")[1].split("</table>")[0]
    assert table.count("<tr><td>") == 3
    for cov, conf, n in (("93.5%", "1.00", 187), ("95.5%", "0.98", 191),
                         ("100.0%", "0.89", 200)):
        assert f"<tr><td>{cov}</td><td>100.0%</td><td>{conf}</td><td>{n}</td></tr>" in table


def test_a_regeneration_is_reported_next_to_the_run_not_in_place_of_it():
    # The run block keeps what the original run said (version, time); the regeneration
    # has its own line, and a tier the old block lacks is read from the regeneration.
    from judge_audit.report import render_markdown
    r = result(curve=JEV_CURVE, zero_error={"coverage": 1.0, "n": 200, "threshold": 0.89})
    r.run = {"judge": {"name": "jev"}, "judge_audit_version": "0.2.0",
             "recomputed_utc": "2026-09-19T09:09:12+00:00"}
    r.regenerated = {"utc": "2026-09-24T10:11:12+00:00", "judge_audit_version": "0.4.0",
                     "script": "scripts/runs_report.py", "checkpoint": "c.ckpt.jsonl",
                     "labels": "l.jsonl", "ground_truth": {"tier": "GT-1"}}
    md = render_markdown(r)
    assert "recomputed 2026-09-19T09:09:12+00:00" in md and "judge-audit 0.2.0" in md
    assert ("_regenerated 2026-09-24T10:11:12+00:00 from `c.ckpt.jsonl` by "
            "`scripts/runs_report.py` · judge-audit 0.4.0_") in md
    assert "Ground truth: GT-1" in md
    assert r.to_dict()["regenerated"] == r.regenerated
    assert "regenerated" not in result().to_dict()


def test_same_run_against_itself_is_compatible_and_has_no_failures(tmp_path):
    assert check_drift(result(), baseline(tmp_path)) == []


def test_a_different_dataset_is_refused(tmp_path):
    with pytest.raises(IncompatibleBaseline) as e:
        check_drift(result(), baseline(tmp_path, sha256="cc" * 32, sha256_rows="dd" * 32))
    assert "sha256" in str(e.value) and "--allow-incompatible" in str(e.value)


def test_a_pre_header_baseline_matches_by_rows_digest(tmp_path):
    """A baseline written before the ground-truth header recorded the whole file;
    that digest is today's rows digest, so it is the same measurement."""
    path = Path(baseline(tmp_path, sha256="bb" * 32))
    d = json.loads(path.read_text(encoding="utf-8"))
    del d["run"]["dataset"]["sha256_rows"]
    path.write_text(json.dumps(d), encoding="utf-8")
    assert check_drift(result(), str(path)) == []


def test_a_different_dataset_file_is_refused_when_only_sha256_is_recorded(tmp_path):
    # A baseline written before sha256_rows existed still pins the file.
    path = Path(baseline(tmp_path, sha256="cc" * 32))
    d = json.loads(path.read_text(encoding="utf-8"))
    del d["run"]["dataset"]["sha256_rows"]
    path.write_text(json.dumps(d), encoding="utf-8")
    cur = result()
    del cur.run["dataset"]["sha256_rows"]
    with pytest.raises(IncompatibleBaseline) as e:
        check_drift(cur, str(path))
    assert "sha256" in str(e.value)


def test_a_different_judge_is_refused(tmp_path):
    with pytest.raises(IncompatibleBaseline) as e:
        check_drift(result(), baseline(tmp_path, judge_name="llm:gemini-3-flash-preview"))
    assert "judge" in str(e.value)


def test_a_different_model_is_refused(tmp_path):
    with pytest.raises(IncompatibleBaseline) as e:
        check_drift(result(), baseline(tmp_path, model="claude-sonnet-5"))
    assert "model" in str(e.value)


def test_a_different_n_is_refused(tmp_path):
    with pytest.raises(IncompatibleBaseline) as e:
        check_drift(result(), baseline(tmp_path, n=120))
    assert "n" in str(e.value)


def test_allow_incompatible_compares_anyway(tmp_path):
    path = baseline(tmp_path, n=120, judge_name="other", sha256_rows="cc" * 32)
    assert check_drift(result(), path, allow_incompatible=True) == []


def test_a_baseline_that_declares_nothing_is_compared(tmp_path):
    # The committed `baseline-strict.json` shape: only ece and accuracy. Unknown is not
    # a mismatch — there is nothing to compare — so the gate still gates.
    p = tmp_path / "strict.json"
    p.write_text(json.dumps({"ece": 0.0, "accuracy": 1.0}), encoding="utf-8")
    failures = check_drift(result(), str(p))
    assert len(failures) == 2  # ECE rose and accuracy dropped


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_baseline_numbers_are_refused(tmp_path, bad):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"ece": bad, "accuracy": 0.9}), encoding="utf-8")
    with pytest.raises(ValueError, match="finite"):
        check_drift(result(), str(p))


def test_non_finite_current_numbers_are_refused(tmp_path):
    with pytest.raises(ValueError, match="finite"):
        check_drift(result(ece=math.nan), baseline(tmp_path))


def test_a_different_prompt_hash_warns_but_does_not_refuse(tmp_path):
    # A changed prompt is not drift in the judge; it is a different question being asked.
    # The reader has to know, but the gate is not the place to fail the build.
    path = with_prompt_hash(tmp_path, "11" * 32)
    cur = result()
    cur.run["judge"]["prompt_sha256"] = "22" * 32
    with pytest.warns(UserWarning, match="prompt"):
        assert check_drift(cur, path) == []


def test_the_same_prompt_hash_does_not_warn(tmp_path, recwarn):
    path = with_prompt_hash(tmp_path, "11" * 32)
    cur = result()
    cur.run["judge"]["prompt_sha256"] = "11" * 32
    assert check_drift(cur, path) == []
    assert not [w for w in recwarn if issubclass(w.category, UserWarning)]
