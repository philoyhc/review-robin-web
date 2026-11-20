"""``CLAUDE.md`` "Where work runs" names the browser-gated tests by a
rule, ``tests/browser/`` and every ``*_browser.py``, so that a reader
of a skip list knows which skips a missing Chromium explains (segment
23H, rung 9). A list of files went stale: it named 7 of 20. The rule
stays true only if every test file that drives a browser follows it,
and this checks that, from what each file imports."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE = "`tests/browser/` and every `*_browser.py`"
PLAYWRIGHT = re.compile(r"^\s*(?:from|import)\s+playwright\b", re.M)


def _tracked_tests() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*test_*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [row for row in out.splitlines() if "/tests/" in f"/{row}"]


def _gated(path: str) -> bool:
    return path.startswith("tests/browser/") or path.endswith("_browser.py")


def test_claude_md_states_the_rule() -> None:
    assert RULE in (ROOT / "CLAUDE.md").read_text(), (
        f"CLAUDE.md no longer names the browser-gated tests as {RULE}"
    )


def test_every_browser_driving_test_follows_the_rule() -> None:
    files = _tracked_tests()
    assert any(f.endswith("_browser.py") for f in files), "found no browser tests"
    strays = [f for f in files if not _gated(f) and PLAYWRIGHT.search((ROOT / f).read_text())]
    assert not strays, (
        "these tests import playwright but are neither under tests/browser/ "
        f"nor named *_browser.py, so CLAUDE.md's rule misses them: {strays}"
    )
