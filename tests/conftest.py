from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OFFLINE = Path(__file__).resolve().parent / "offline"
sys.path.insert(0, str(OFFLINE))

import offline_guard  # noqa: E402

# --- the suite runs offline (#169) -------------------------------------------------------------
# Installed when this file is imported, before any test or fixture runs, and inherited by every
# Python process a test starts (PYTHONPATH reaches `tests/offline/sitecustomize.py`). A test
# fails when the log gained a line while it ran, even if the code under test caught the error.

_LOG = os.path.join(tempfile.mkdtemp(prefix="judge-audit-offline-"), "attempts.log")
open(_LOG, "w").close()
os.environ[offline_guard.LOG_VAR] = _LOG
os.environ["PYTHONPATH"] = os.pathsep.join(
    p for p in (str(OFFLINE), os.environ.get("PYTHONPATH", "")) if p)
offline_guard.install(_LOG)
_seen = 0


def _new_attempts() -> list[str]:
    global _seen
    with open(_LOG, encoding="utf-8") as f:
        lines = f.read().splitlines()
    new, _seen = lines[_seen:], len(lines)
    return new


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    before = _new_attempts()          # this test's fixtures, or the previous test's teardown
    result = yield
    if attempts := before + _new_attempts():
        pytest.fail("tests run offline, and this one reached for the network: "
                    + "; ".join(attempts[:5]), pytrace=False)
    return result


def pytest_sessionfinish(session):
    if attempts := _new_attempts():                   # from a fixture's setup or teardown
        print("\ntests run offline, and a fixture reached for the network: "
              + "; ".join(attempts[:5]), file=sys.stderr)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture
def labels_path(tmp_path: Path) -> Path:
    rows = [
        {"state": f"email {i}: please send a quote for {i} units",
         "questions": [{"name": "category", "type": "choice", "instructions": "classify",
                        "options": ["quote_request", "spam"]}],
         "labels": {"category": "quote_request"},
         "_meta": {"synthetic": True}}
        for i in range(12)
    ]
    p = tmp_path / "labels.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p



# Every family's environment prefix: the over-length warning of one family names none of the
# others' (a decider run must never be told to raise LAYA_MAX_LEN).
FAMILY_VARIABLES = ("LAYA_", "DECIDER_", "STRANDS_", "CLEF_", "DECISION2_")


@pytest.fixture
def over_length_warning():
    """judge -> the NotSentWarning of a one-row run whose only question it withholds, and
    the family prefixes it names."""
    from judge_audit.runner import NotSentWarning, run_audit
    rows = [{"state": "long", "labels": {"route": "billing"},
             "questions": [{"name": "route", "type": "choice", "instructions": "Which team?",
                            "options": ["billing", "sales"]}]}]

    def warning_of(judge) -> tuple[str, set[str]]:
        with pytest.warns(NotSentWarning) as caught:
            result = run_audit(judge, rows, ci=False)
        assert result.not_sent == 1
        (w,) = [w for w in caught if w.category is NotSentWarning]
        message = str(w.message)
        return message, {v for v in FAMILY_VARIABLES if v in message}
    return warning_of
