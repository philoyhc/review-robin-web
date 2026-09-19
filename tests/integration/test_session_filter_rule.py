"""The Lobby / Archive filter rule, executed rather than parsed.

19O Item 7 entry 15 rung 2. The rule is inline JS, so the suite's usual
reach ends at `node --check` — `test_inline_scripts_parse.py` proves it
parses and nothing proved what it *does*. The cold read on this rung
named that directly: the three `<datalist>` cases written alongside it
would all have passed with the matching reverted to the concatenated
haystack it replaced.

`node` already runs in CI for the parse gate, so executing one pure
function costs nothing new. `rrwSessionFilterMatches` takes the three
values rather than a DOM row precisely so this is possible; the per-page
wrapper that reads `row.cells[...]` is what remains untested, and it is
three property reads.

Skipped where `node` is absent — and a skip here is worse than a
failure, so read the skip list rather than the exit code (`CLAUDE.md`,
"Where work runs").
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASE = Path("app/web/templates/base.html")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)


def _extract_rule() -> str:
    """The `rrwSessionFilterMatches` source, lifted from `base.html`.

    Anchored on the function header and closed by the first line that
    dedents back to its own indentation, so a body edit cannot silently
    truncate what is tested.
    """
    source = BASE.read_text()
    start = source.index("      function rrwSessionFilterMatches(")
    end = source.index("\n      }\n", start) + len("\n      }\n")
    body = source[start:end]
    assert body.count("{") == body.count("}"), "unbalanced extraction"
    return body


def _run(cases: list[dict]) -> list[bool]:
    script = _extract_rule() + (
        "\nconst cases = " + json.dumps(cases) + ";\n"
        "console.log(JSON.stringify(cases.map(c =>"
        "  rrwSessionFilterMatches(c.name, c.code, c.tags, c.term))));\n"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


SPRING = {"name": "Spring Review", "code": "2026-A", "tags": ["team a"]}


def test_the_rule_is_actually_reachable_and_returns_booleans() -> None:
    """The premise. Without this, every case below could be passing on
    `undefined` and reading as a clean run."""
    got = _run([dict(SPRING, term="")])

    assert got == [True]
    assert isinstance(got[0], bool)


@pytest.mark.parametrize(
    "term,expected,why",
    [
        ("", True, "an empty filter keeps every row"),
        ("spring", True, "substring on the name"),
        ("REVIEW", True, "name matching is case-insensitive"),
        ("2026", True, "substring on the code"),
        ("team a", True, "whole-value match on a tag"),
        ("TEAM A", True, "tag matching is case-insensitive"),
        ("team", False, "a tag prefix is not a tag"),
        ("eam a", False, "a tag substring is not a tag"),
        ("nothing here", False, "no column matches"),
    ],
)
def test_per_column_rules(term: str, expected: bool, why: str) -> None:
    assert _run([dict(SPRING, term=term)]) == [expected], why


def test_a_term_spanning_name_and_code_does_not_match() -> None:
    """Per column means per column, whatever the markup does.

    The concatenating version this replaced was *saved* from matching
    here by the template's indentation rather than by intent — measured
    in Chromium, the joined string read
    `"\\n                Spring Review\\n               2026-A"`, so
    `review 2026` was never in it. Reformat those cells onto one line
    and that version starts matching; this one cannot.
    """
    assert _run([dict(SPRING, term="review 2026")]) == [False]


def test_a_row_with_no_tags_still_matches_on_name() -> None:
    """The tag branch is last, so an empty tag list must not swallow a
    name that already matched — nor throw."""
    assert _run([{"name": "Bare", "code": "b-1", "tags": [], "term": "bare"}]) == [
        True
    ]


def test_tag_values_are_compared_trimmed() -> None:
    """Surrounding whitespace was never a difference on the seven
    server-side filters (`spec/setup_pages.md`), and is not one here."""
    assert _run(
        [{"name": "X", "code": "x-1", "tags": ["  team a  "], "term": "team a"}]
    ) == [True]


def test_the_extraction_is_anchored_to_something_that_exists() -> None:
    """A rename in `base.html` must fail this file loudly rather than
    leaving it green against a stale copy."""
    assert "function rrwSessionFilterMatches(" in BASE.read_text()
    assert re.search(r"rrwSessionFilterMatches\(", _extract_rule())
