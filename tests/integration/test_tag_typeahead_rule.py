"""The tag typeahead's option rule, executed rather than parsed.

19S Item 7. The typeahead completes each tag in a comma-separated box,
past the first one and after every comma (author's ruling, 2026-09-23),
by rewriting a ``<datalist>`` on every keystroke. What the options are
is ``rrwTagOptions(value, vocabulary)`` in
``operator/partials/_tag_typeahead.html``, a pure function precisely so
this file can run it under node, as ``test_session_filter_rule.py`` does
for the lobby filter. The browser's popup itself is not observable
headless and is checked on the dev slot.

Skipped where ``node`` is absent — and a skip here is worse than a
failure, so read the skip list rather than the exit code (``CLAUDE.md``,
"Where work runs").
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.session_tags import normalize_tag

PARTIAL = Path("app/web/templates/operator/partials/_tag_typeahead.html")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)

VOCABULARY = ["2026", "alpha", "beta", "betamax", "legacy", "pilot"]


def _extract_rule() -> str:
    """The ``rrwTagOptions`` source, lifted from the partial.

    Anchored on the function header and closed by the first line that
    dedents back to its own indentation, so a body edit cannot silently
    truncate what is tested.
    """
    source = PARTIAL.read_text()
    start = source.index("  function rrwTagOptions(")
    end = source.index("\n  }\n", start) + len("\n  }\n")
    body = source[start:end]
    assert body.count("{") == body.count("}"), "unbalanced extraction"
    return body


def _options(value: str, vocabulary: list[str] = VOCABULARY) -> list[str]:
    script = _extract_rule() + (
        "\nconsole.log(JSON.stringify(rrwTagOptions("
        + json.dumps(value)
        + ", "
        + json.dumps(vocabulary)
        + ")));\n"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_an_empty_box_offers_the_whole_vocabulary() -> None:
    """The premise: the rule is reachable and returns the list, so no
    case below can pass on ``undefined``."""
    assert _options("") == VOCABULARY


@pytest.mark.parametrize(
    "value,expected,why",
    [
        ("b", ["beta", "betamax"], "the first tag completes"),
        (
            "alpha, be",
            ["alpha, beta", "alpha, betamax"],
            "a tag after a comma completes, and the tags before it are kept",
        ),
        (
            "alpha,b",
            ["alpha,beta", "alpha,betamax"],
            "no space after the comma: the option keeps what was typed",
        ),
        (
            "alpha, beta, ",
            ["alpha, beta, 2026", "alpha, beta, betamax",
             "alpha, beta, legacy", "alpha, beta, pilot"],
            "after a comma, every tag not already in the box",
        ),
        (
            "Be",
            ["Beta", "Betamax"],
            "the typed part keeps its case, so the browser's match "
            "cannot miss on case",
        ),
        ("beta", ["betamax"], "a finished tag is not offered again"),
        ("x", [], "no match, no options"),
        ("PILOT, al", ["PILOT, alpha"], "a tag already in the box is "
         "matched case-insensitively"),
    ],
)
def test_the_options_for_a_box(value: str, expected: list[str], why: str) -> None:
    assert _options(value) == expected, why


def test_a_tag_already_in_the_box_is_not_offered() -> None:
    assert "alpha, beta, alpha" not in _options("alpha, beta, a")
    assert _options("alpha, beta, a") == []


def test_an_empty_vocabulary_offers_nothing() -> None:
    """A first session, no tags anywhere."""
    assert _options("", []) == []
    assert _options("pi", []) == []


def test_every_option_stores_as_a_vocabulary_tag() -> None:
    """Suggestions and storage agree: whatever casing an option carries,
    ``normalize_tag`` — what every editor stores through — turns each
    of its tags into one the vocabulary already holds."""
    for value in ("Be", "alpha, Pi", "2026,LE"):
        for option in _options(value):
            for tag in option.split(","):
                assert normalize_tag(tag) in VOCABULARY, (value, option)
