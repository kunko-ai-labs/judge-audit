"""The README tables must be the committed JSON, rounded — and the check must notice an edit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import verify_readme as _vr  # noqa: E402
from verify_readme import check, rounded  # noqa: E402

README = _vr.corpus()   # the README and the per-version results pages, checked as one text


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


# ---------- v0.5 findings and the quickstart ----------

@pytest.mark.parametrize(
    "old,new",
    [
        ("BANKING77 test (3,080 rows)", "BANKING77 test (3,081 rows)"),
        ("CLINC150 subset (1,900 rows)", "CLINC150 subset (1,800 rows)"),
        ("4 are resolved (T1, T6, T7, T8)", "5 are resolved (T1, T6, T7, T8)"),
        ("6 match their pre-registered prediction", "7 match their pre-registered prediction"),
        ("of the 5 hypothesis verdicts 2 are supported",
         "of the 5 hypothesis verdicts 3 are supported"),
        ("T2 -0.046 [-0.089, -0.003], Holm p 0.036)", "T2 -0.046 [-0.089, -0.003], Holm p 0.030)"),
        ("(Holm p 0.072)", "(Holm p 0.036)"),
        ("T7 +0.107 [+0.062, +0.151]", "T7 +0.108 [+0.062, +0.151]"),
        ("T8 +0.477 [+0.428, +0.524]", "T8 +0.477 [+0.428, +0.534]"),
        ("T8 re-read +0.001 [-0.037, +0.041]", "T8 re-read +0.001 [-0.036, +0.041]"),
        ("T1 +0.098 [+0.078, +0.119]", "T1 +0.098 [+0.079, +0.119]"),
        ("T2 -0.046 [-0.089, -0.003]", "T2 -0.046 [-0.089, -0.004]"),
        ("T3 -0.070 [-0.091, -0.049]", "T3 -0.071 [-0.091, -0.049]"),
        ("T4 -0.220 [-0.255, -0.184]", "T4 -0.220 [-0.256, -0.184]"),
        ("T5 -0.144 [-0.169, -0.119]", "T5 -0.144 [-0.169, -0.118]"),
        ("T6 +0.363 [+0.318, +0.406]", "T6 +0.363 [+0.319, +0.406]"),
        ("T6 re-read -0.281 [-0.343, -0.215]", "T6 re-read -0.281 [-0.343, -0.216]"),
        ("the BANKING77 gap of T1 is +0.022", "the BANKING77 gap of T1 is +0.023"),
        ("Qwen3-8B k = 10, gemini-3.6-flash k = 5", "Qwen3-8B k = 9, gemini-3.6-flash k = 5"),
        ("in 3 of the 4 tests", "in 4 of the 4 tests"),
        ("41.0 % at ≤ 5 % (37 errors", "42.0 % at ≤ 5 % (37 errors"),
        ("(37 errors / 1263 automated;", "(36 errors / 1263 automated;"),
        ("72.3 % at ≤ 10 % (182 / 2225;", "72.3 % at ≤ 10 % (182 / 2226;"),
        ("27.0 %–45.1 % over seeds", "27.0 %–46.1 % over seeds"),
        ("72.0 %–73.4 % over the same seeds", "72.0 %–74.4 % over the same seeds"),
        ("split seed 2026", "split seed 2027"),
        ("14.3 % at ≤ 5 % (6 errors", "14.3 % at ≤ 5 % (7 errors"),
        ("45.5 % at ≤ 10 % (59 / 1402)", "45.5 % at ≤ 10 % (59 / 1412)"),
        ("441 automated; 7.6 %–30.0 % over", "441 automated; 7.6 %–31.0 % over"),
        ("0 automated; 0.0 %–4.4 % over", "0 automated; 0.0 %–4.5 % over"),
        ("12.5 % at ≤ 10 % (19 / 384)", "12.6 % at ≤ 10 % (19 / 384)"),
        # verdicts and caveats are read too
        ("H2 is supported for Qwen3-8B", "H2 is strongly supported for Qwen3-8B"),
        ("H1-lp is not supported for Qwen3-8B", "H1-lp is supported for Qwen3-8B"),
        ("T8 depends on the scoring rule", "T8 is robust to the scoring rule"),
        ("label noise was not measured", "label noise was measured"),
        ("the held-out slice was not run", "the held-out slice was run"),
        # the quickstart's simulated line and its figure in the prose
        ("safe_automation@10%=65.5% …", "safe_automation@10%=66.5% …"),
        ("its 65.5 % says nothing", "its 64.5 % says nothing"),
        ("safe_automation@5%=none", "safe_automation@5%=12.0%"),
    ],
)
def test_a_one_digit_edit_of_a_v05_figure_is_caught(old, new):
    assert any(f.startswith(("v0.5", "quickstart")) for f in check(edit(old, new)).failures)


def edit_in(opening: str, old: str, new: str) -> str:
    """Edit `old` inside the one paragraph that starts with `opening`."""
    paras = README.split("\n\n")
    (i,) = [i for i, p in enumerate(paras) if p.startswith(opening)]
    assert old in paras[i], (opening, old)
    paras[i] = paras[i].replace(old, new, 1)
    return "\n\n".join(paras)


TESTS, SC, SAFE = ("**Pre-registered confirmatory tests.**",
                   "**Self-consistency against verbalized confidence.**",
                   "**Safe automation rate on BANKING77.**")


@pytest.mark.parametrize(
    "opening,old,new",
    [
        # direction words: the sign of the difference, not just its digits
        (TESTS, "token log-probability beat verbalized",
         "token log-probability lost to verbalized"),
        (TESTS, "lost to it on CLINC150", "beat it on CLINC150"),
        (SC, "ranked errors worse than", "ranked errors better than"),
        # the Holm threshold
        ("A pre-registered study", "Holm-adjusted p below 0.05", "Holm-adjusted p below 0.01"),
        (TESTS, "opposite direction (Holm p < 0.05)", "opposite direction (Holm p < 0.5)"),
        (SC, "Holm p < 0.05", "Holm p < 0.5"),
        # the counts' honest reading
        (TESTS, "count as matched only because", "count as matched because"),
        (TESTS, "not resolved under the re-reading", "resolved under the re-reading"),
        # the dataset years, in every paragraph's caveat
        (TESTS, "BANKING77 (2020)", "BANKING77 (2021)"),
        (SC, "BANKING77 (2020)", "BANKING77 (2021)"),
        (SAFE, "CLINC150 (2019)", "CLINC150 (2018)"),
        # the single-run caveat, in every paragraph
        (TESTS, "each confirmatory run ran once", "each confirmatory run ran three times"),
        (SC, "repeats only for Jev and Qwen3-8B verbalized", "repeats for every run"),
        (SAFE, "each confirmatory run ran once", "every run repeated"),
        (SAFE, "probably in the judges' pretraining data", "not in the judges' pretraining data"),
    ],
)
def test_a_v05_direction_or_criterion_edit_is_caught(opening, old, new):
    assert any(f.startswith("v0.5") for f in check(edit_in(opening, old, new)).failures)


@pytest.mark.parametrize(
    "old,new",
    [
        ("--target 0.10 --min-safe-rate 0.10:0.60\n", "--target 0.10 --min-safe-rate 0.10:0.90\n"),
        ("`check --min-safe-rate 0.10:0.60` exits", "`check --min-safe-rate 0.10:0.90` exits"),
        ("falls below 60 %", "falls below 50 %"),
        ("exits 0 here and exits 1", "exits 1 here and exits 0"),
    ],
)
def test_a_quickstart_gate_edit_is_caught(old, new):
    assert any(f.startswith("quickstart") for f in check(edit(old, new)).failures)


def test_the_gate_threshold_follows_a_fresh_check(monkeypatch):
    import verify_readme

    monkeypatch.setattr(verify_readme, "demo_check", lambda: (1, "(minimum 70.0%)"))
    assert any(f.startswith("quickstart") and "exit" in f for f in check(README).failures)


def test_a_second_copy_of_a_v05_figure_fails():
    ck = check(README + "\nT7 +0.107 [+0.062, +0.151]\n")
    assert any("v0.5" in f and "2 times" in f for f in ck.failures)


def test_a_v05_figure_follows_the_json(monkeypatch):
    import copy

    import verify_readme

    real = verify_readme.load

    def patched(name):
        d = real(name)
        if name == "v05-results.json":
            d = copy.deepcopy(d)
            d["tests"]["strict"]["T7"]["difference"] = 0.2
        return d

    monkeypatch.setattr(verify_readme, "load", patched)
    assert any(f.startswith("v0.5") and "T7" in f for f in check(README).failures)


def patch_v05(monkeypatch, edit_json):
    """Serve a deep copy of docs/v05-results.json edited by `edit_json`."""
    import copy

    import verify_readme

    real = verify_readme.load

    def patched(name):
        d = real(name)
        if name == "v05-results.json":
            d = copy.deepcopy(d)
            edit_json(d)
        return d

    monkeypatch.setattr(verify_readme, "load", patched)


@pytest.mark.parametrize(
    "old,new",
    [
        ('2 carry "depends on the scoring rule"', '1 carries "depends on the scoring rule"'),
        ('2 carry "depends on the scoring rule"', '3 carry "depends on the scoring rule"'),
        ("(H1-sc and H2 for gemini-3.6-flash)", "(H2 for gemini-3.6-flash)"),
        ("one of them, H2 for gemini-3.6-flash, changes verdict",
         "both of them change verdict"),
    ],
)
def test_the_scoring_rule_count_is_the_flag_in_the_json(old, new):
    assert any(f.startswith("v0.5") for f in check(edit_in(TESTS, old, new)).failures)


def test_the_scoring_rule_count_follows_the_flag_not_the_flips(monkeypatch):
    # clearing H1-sc's flag changes no verdict, so a count built from flips would still pass
    def clear(d):
        for v in d["verdicts"]:
            if v["hypothesis"] == "H1-sc":
                v["depends_on_scoring_rule"] = False

    patch_v05(monkeypatch, clear)
    assert any(f.startswith("v0.5") and "scoring rule" in f for f in check(README).failures)


@pytest.mark.parametrize(
    "field",
    ["opposite_sign", "depends_on_scoring_rule", "flips"],
)
def test_an_empty_list_from_the_json_is_a_named_mismatch_not_a_crash(monkeypatch, field):
    def empty(d):
        if field == "opposite_sign":
            for t in d["tests"]["strict"].values():
                t["opposite_sign"] = False
        elif field == "depends_on_scoring_rule":
            for v in d["verdicts"]:
                v["depends_on_scoring_rule"] = False
        else:
            for v in d["verdicts"]:
                v["reread"] = v["strict"]

    patch_v05(monkeypatch, empty)
    failures = check(README).failures   # must not raise
    assert any(f.startswith("v0.5") and "not found word for word" in f for f in failures)


SHORT = "**In short.**"


@pytest.mark.parametrize(
    "old,new",
    [
        ("ranked their errors worse than", "ranked their errors better than"),
        ("in 3 of 4 tests", "in 4 of 4 tests"),
        ("one verdict (H2 for gemini-3.6-flash) changes", "no verdict changes"),
        ("can decide 41.0 % (27.0 %", "can decide 42.0 % (27.0 %"),
        ("(27.0 %–45.1 % over split seeds", "(27.0 %–46.1 % over split seeds"),
        ("verbalized 14.3 % (7.6 %–30.0 %)", "verbalized 14.3 % (7.6 %–31.0 %)"),
        ("none (0.0 %–4.4 %)", "none (0.0 %–5.4 %)"),
        ("(4 of 4 under the re-reading)", "(3 of 4 under the re-reading)"),
        ("one run each, except", "three runs each, except"),
        ("verbalized on BANKING77 (3 runs)", "verbalized on BANKING77 (4 runs)"),
        ("label noise not measured", "label noise measured"),
        ("the held-out slice not run (#106)", "the held-out slice run (#106)"),
        ("gemini-3.6-flash verbalized 14.3 % (7.6", "gemini-3.6-flash verbalized 15.3 % (7.6"),
        ("token log-probability none (", "token log-probability 1.0 % ("),
        ("probably seen in pretraining", "not seen in pretraining"),
    ],
)
def test_the_in_short_summary_is_checked_like_the_findings(old, new):
    assert any(f.startswith("v0.5") for f in check(edit_in(SHORT, old, new)).failures)


def test_the_in_short_none_follows_the_json(monkeypatch):
    # a run that automates something at 5 % must print its share, not "none"
    def automate(d):
        p = d["metrics"]["banking77/logprob-qwen3-8b"]["strict"]["certification"]["0.05"]["pooled"]
        p["covered"], p["coverage"] = 30, 0.01

    patch_v05(monkeypatch, automate)
    assert any(f.startswith("v0.5 findings / **In short.**") for f in check(README).failures)


def test_no_opposite_sign_test_does_not_read_as_worse(monkeypatch):
    # all([]) is True: with no opposite-sign test, the rebuilt sentence must not say "worse"
    def none_opposed(d):
        for t in d["tests"]["strict"].values():
            t["opposite_sign"] = False

    patch_v05(monkeypatch, none_opposed)
    failures = check(README).failures
    assert any("ranked their errors no differently" in f for f in failures)
    assert not any("ranked their errors worse" in f and "in 0 of" in f for f in failures)


@pytest.mark.parametrize(
    "old,new",
    [
        ("| Jev, native probability | **41.0 %** |", "| Jev, native probability | **42.0 %** |"),
        ("| 27.0–45.1 % | 72.3 % |", "| 27.0–46.1 % | 72.3 % |"),
        ("| 7.6–30.0 % | 45.5 % |", "| 7.6–30.0 % | 46.5 % |"),
        ("| Qwen3-8B, token log-probability | **none** |",
         "| Qwen3-8B, token log-probability | **1.0 %** |"),
        ("BANKING77, 3,080 human-labelled", "BANKING77, 3,081 human-labelled"),
    ],
)
def test_the_at_a_glance_table_is_checked_cell_by_cell(old, new):
    assert any(f.startswith("v0.5 at a glance") for f in check(edit(old, new)).failures)


def test_a_dropped_row_of_the_at_a_glance_table_is_caught():
    row = "| gemini-3.6-flash, verbalized | **14.3 %** | 7.6–30.0 % | 45.5 % |\n"
    assert row in README
    assert any("gemini-3.6-flash, verbalized" in f and "0 times" in f
               for f in check(README.replace(row, "")).failures)


@pytest.mark.parametrize(
    "old,new",
    [
        ("| Range over split seeds | At ≤ 10 % error |",
         "| Range over split seeds | At ≤ 20 % error |"),
        ("decided alone at an error of at most 5 %.**",
         "decided alone at an error of at most 10 %.**"),
    ],
)
def test_the_at_a_glance_header_and_caption_are_checked(old, new):
    assert any(f.startswith("v0.5 at a glance") for f in check(edit(old, new)).failures)


def test_the_demo_figures_follow_the_json(monkeypatch, tmp_path):
    import json

    import verify_readme
    src = verify_readme.ROOT / "docs/assets/demo-figures.json"
    demo = json.loads(src.read_text(encoding="utf-8"))
    demo["banking77"]["runs"]["jev"]["coverage_at_5pct"] = 0.42
    fake = tmp_path / "docs/assets"
    fake.mkdir(parents=True)
    (fake / "demo-figures.json").write_text(json.dumps(demo), encoding="utf-8")
    real_root = verify_readme.ROOT
    monkeypatch.setattr(verify_readme, "ROOT", tmp_path)
    monkeypatch.setattr(verify_readme, "load",
                        lambda name: json.loads((real_root / "docs" / name).read_text()))
    monkeypatch.setattr(verify_readme, "simulated_line", lambda target: (
        "SIMULATED · judge=simulated n=200 accuracy=85.5% safe_automation@10%=65.5%"))
    monkeypatch.setattr(verify_readme, "demo_check", lambda: (1, "(minimum 70.0%)"))
    ck = verify_readme.Checker()
    verify_readme.check_demo_figures(ck)
    assert any("demo / jev / rate at 5 %" in f for f in ck.failures)
