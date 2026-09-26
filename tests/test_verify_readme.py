"""The README tables must be the committed JSON, rounded — and the check must notice an edit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_readme import ROOT, check, rounded  # noqa: E402

README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_the_committed_readme_matches_its_json():
    ck = check(README)
    assert ck.failures == []
    assert ck.checked > 250  # three tables, every numeric cell


def edit(old: str, new: str) -> str:
    assert README.count(old) >= 1, old
    return README.replace(old, new, 1)


@pytest.mark.parametrize(
    "old,new",
    [
        ("| Gemini 3 Flash | verbalized | 97.0%", "| Gemini 3 Flash | verbalized | 97.1%"),
        ("| DeepSeek R1 | verbalized | 80.5% [74.8, 85.6] | 0.127",
         "| DeepSeek R1 | verbalized | 80.5% [74.8, 85.6] | 0.128"),
        ("| Llama 3.3 70B | verbalized | 90.5% [86.1, 94.5]",
         "| Llama 3.3 70B | verbalized | 90.5% [86.1, 94.6]"),
    ],
)
def test_a_one_digit_edit_is_caught(old, new):
    assert check(edit(old, new)).failures


def test_a_dropped_exact_interval_mark_is_caught():
    row = ("| Gemini 3 Flash | verbalized | 97.0% [94.5, 99.0] | 0.015 [0.002, 0.040] "
           "| **0%** [0.0, 1.8]†")
    failures = check(edit(row, row[:-1])).failures
    assert any("Gemini" in f and "†" in f for f in failures)


def test_an_unknown_row_is_an_error_not_a_skip():
    row = "| Gemini 3 Flash | verbalized |"
    failures = check(edit(row, "| Gemini 9 Ultra | verbalized |")).failures
    assert any("unknown judge row 'Gemini 9 Ultra'" in f for f in failures)


@pytest.mark.parametrize(
    "value,shown,pct,ok",
    [
        (0.97, "97.0%", True, True),
        (0.9712, "97.1%", True, True),
        (0.9704, "97.1%", True, False),
        (0.0149, "0.015", False, True),
        (0.0149, "0.014", False, False),
    ],
)
def test_rounding_accepts_only_the_printed_precision(value, shown, pct, ok):
    text = shown.rstrip("%")
    assert (text in rounded(value, text, pct)) is ok


@pytest.mark.parametrize(
    "old,new",
    [
        ("(0 %, interval up to 90.9 %)", "(0 %, interval up to 80.9 %)"),
        ("(200 emails, 189 distinct texts", "(200 emails, 200 distinct texts"),
        ("Jev 73 % [67.0, 94.0]", "Jev 73 % [69.0, 94.0]"),
        ("(0 %, exact upper bound 1.8 %)", "(0 %, exact upper bound 1.2 %)"),
    ],
)
def test_the_hero_caption_is_checked_too(old, new):
    assert check(edit(old, new)).failures


def test_a_caption_that_drops_a_figure_fails():
    assert check(edit("interval up to 90.9 %", "a wide interval")).failures


def drop_line(start: str) -> str:
    lines = README.split("\n")
    hit = [i for i, line in enumerate(lines) if line.startswith(start)]
    assert len(hit) == 1, start
    return "\n".join(lines[:hit[0]] + lines[hit[0] + 1:])


def dup_line(start: str) -> str:
    lines = README.split("\n")
    (i,) = [i for i, line in enumerate(lines) if line.startswith(start)]
    return "\n".join(lines[:i + 1] + [lines[i]] + lines[i + 1:])


@pytest.mark.parametrize("start", ["| Claude Sonnet 4.5 | verbalized", "| DeepSeek R1 | verbalized",
                                   "| Router, bare labels |", "| Business emails, 10 categories"])
def test_a_deleted_row_is_caught(start):
    assert any("appears 0 times" in f for f in check(drop_line(start)).failures)


def test_a_duplicated_row_is_caught():
    assert any("appears 2 times" in f for f in check(dup_line("| Gemini 3 Flash |")).failures)


@pytest.mark.parametrize(
    "old,new",
    [
        # Sonnet's interval overlaps Jev's: calling it separated is stronger than the data
        ("it is **not** separated from Claude Sonnet 4.5 (0 %, interval up to 90.9 %), ",
         "and from Claude Sonnet 4.5 (0 %, interval up to 90.9 %); it is **not** separated from "),
        # a separated judge left out of the caption
        ("Gemini 3 Flash, Llama 3.3 70B, DeepSeek R1, gemma4 and llama3.2 (0 %",
         "Gemini 3 Flash, DeepSeek R1, gemma4 and llama3.2 (0 %"),
        # run 1 is above Jev, not below
        ("run 1 (97 % [94.4, 99.0]) above it", "run 1 (97 % [94.4, 99.0]) below it"),
        ("social engineering: 0 successes", "social engineering: 3 successes"),
        # coarser rounding hides a change
        ("| 95.5% [92.5, 98.0] | 0.039 [", "| 96% [92.5, 98.0] | 0.039 ["),
        ("| 95.5% [92.5, 98.0] | 0.039 [", "| 95.5% [92.5, 98.0] | 0.04 ["),
    ],
)
def test_the_prose_claims_are_read_not_assumed(old, new):
    assert check(edit(old, new)).failures


def test_a_reworded_cell_is_a_named_mismatch_not_a_crash():
    ck = check(edit("Prompt injection flips 7/40 decisions", "Prompt injection changes 7 of 40"))
    assert any("audit-jev-adversarial" in f or "Same emails under attack" in f
               for f in ck.failures)


def test_a_judge_new_to_the_arena_json_must_appear_in_the_readme(monkeypatch):
    import verify_readme

    real = verify_readme.load

    def with_extra(name):
        d = real(name)
        if name == "arena-2026-09.json":
            d = {**d, "new-judge": d["jev"]}
        return d

    monkeypatch.setattr(verify_readme, "load", with_extra)
    assert any("'new-judge' appears 0 times" in f for f in check(README).failures)


@pytest.mark.parametrize(
    "old,new",
    [
        ("Gemini 3 Flash is 97.0 % accurate", "Gemini 3 Flash is 97.5 % accurate"),
        ("averages 0.98 confidence", "averages 0.99 confidence"),
        ("(95 % upper bound 1.8 %)", "(95 % upper bound 1.2 %)"),
        ("Jev: 73 % [67.0, 94.0].**", "Jev: 83 % [67.0, 94.0].**"),
        ("Jev: 73 % [67.0, 94.0].**", "Jev: 73 % [60.0, 94.0].**"),
        ("On 200 synthetic emails", "On 200 emails"),                  # the caveat dropped
        ("Jev: 73 % [67.0, 94.0].**", "Jev: 73 %.**"),                  # the interval dropped
        # a claim slipped in between the figures
        ("whether it is right or wrong. Share",
         "whether it is right or wrong. No other tool measures this. Share"),
    ],
)
def test_the_first_screen_headline_is_checked(old, new):
    assert check(edit(old, new)).failures


def test_a_second_copy_of_the_headline_fails():
    head = next(line for line in README.split("\n") if line.startswith("**On 200 synthetic"))
    assert any("appears 2 times" in f for f in check(README + "\n" + head + "\n").failures)


@pytest.mark.parametrize(
    "judge,field,value,expect",
    [
        ("jev", "zero_error_coverage_ci", [0.01, 0.94], "intervals overlap"),
        ("gemini-3-flash", "mean_conf_wrong", 0.90, "mean confidence when wrong"),
        ("gemini-3-flash", "zero_error_coverage_ci_method", "bootstrap", "exact interval"),
    ],
)
def test_the_headline_fails_when_the_data_stop_supporting_it(monkeypatch, judge, field, value,
                                                              expect):
    import copy

    import verify_readme

    real = verify_readme.load

    def patched(name):
        d = real(name)
        if name == "arena-2026-09.json":
            d = copy.deepcopy(d)
            d[judge]["datasets"]["email-adversarial"][field] = value
        return d

    monkeypatch.setattr(verify_readme, "load", patched)
    assert any(expect in f for f in check(README).failures if f.startswith("headline"))


@pytest.mark.parametrize("name,path,value", [
    ("repeats-2026-09.json", ("P3", "held"), False),
    ("robustness-distinct-2026-09.json", ("headline", "separated"), False),
])
def test_the_robustness_verdicts_are_read_from_their_reports(monkeypatch, name, path, value):
    import copy

    import verify_readme

    real = verify_readme.load

    def patched(n):
        d = real(n)
        if n == name:
            d = copy.deepcopy(d)
            if name.startswith("repeats"):
                next(p for p in d["predictions"] if p["id"] == path[0])[path[1]] = value
            else:
                d[path[0]][path[1]] = value
        return d

    monkeypatch.setattr(verify_readme, "load", patched)
    assert any(f.startswith("robustness") for f in check(README).failures)


def test_rewording_the_robustness_sentence_fails_instead_of_skipping():
    assert any("robustness" in f for f in check(edit(
        "Two robustness checks back the Jev–Gemini gap", "Two checks back the gap")).failures)
