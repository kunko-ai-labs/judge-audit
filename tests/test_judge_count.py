"""The README's judge count is the CLI's: two PRs that each add a judge must not both say
"six" once merged."""
from __future__ import annotations

import re
from pathlib import Path

from judge_audit.cli import JUDGES

WORDS = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
README = Path(__file__).resolve().parent.parent / "README.md"


def test_the_readme_names_every_judge_the_cli_accepts_and_counts_them():
    text = README.read_text(encoding="utf-8")
    m = re.search(r"Ships with (\w+): (.+?) Details in", text)
    assert m, "README lost its 'Ships with N: ...' sentence"
    assert m.group(1) == WORDS[len(JUDGES)]
    named = re.findall(r"`(\w+)` \(", m.group(2)) + re.findall(r"and `(\w+)`\.", m.group(2))
    assert sorted(named) == sorted(JUDGES)
