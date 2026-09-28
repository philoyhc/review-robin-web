"""19T Item 12 — range conditions.

``branch_is_open`` and the reviewer script's ``isOpen`` read the four range
tokens over a ``low to high`` value (rung 2); ``condition_label`` reads them
with symbols. ``BRANCH_OPS`` and ``condition_error`` accept them from rung 3,
when the builder can show a range (Codex on #2657)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.responses import (
    BRANCH_OPS,
    RANGE_OPS,
    branch_is_open,
    condition_error,
    condition_label,
    parse_range,
)

SURFACE = (
    Path(__file__).resolve().parents[2] / "app/web/templates/reviewer/review_surface.html"
)


def _parent(op: str, value: str) -> SimpleNamespace:
    return SimpleNamespace(label="Rating", branch_op=op, branch_value=value)


# Every token around both ends of 2 to 4, plus the ends between.
ANSWERS = ["1", "1.99", "2", "2.01", "3", "3.99", "4", "4.01", "5"]
EXPECTED = {
    "in_inc": [False, False, True, True, True, True, True, False, False],
    "in_exc": [False, False, False, True, True, True, False, False, False],
    "out_inc": [True, True, True, False, False, False, True, True, True],
    "out_exc": [True, True, False, False, False, False, False, True, True],
}


@pytest.mark.parametrize("op", sorted(EXPECTED))
def test_each_range_opens_at_and_around_its_ends(op: str) -> None:
    parent = _parent(op, "2 to 4")
    assert [branch_is_open(parent, a) for a in ANSWERS] == EXPECTED[op]


def test_inclusive_outside_is_the_complement_of_exclusive_within() -> None:
    """The author's ruling: inclusive on outside counts the ends as outside."""
    for answer in ANSWERS:
        assert branch_is_open(_parent("out_inc", "2 to 4"), answer) is not (
            branch_is_open(_parent("in_exc", "2 to 4"), answer)
        )
        assert branch_is_open(_parent("out_exc", "2 to 4"), answer) is not (
            branch_is_open(_parent("in_inc", "2 to 4"), answer)
        )


@pytest.mark.parametrize(
    ("value", "bounds"),
    [
        ("2 to 4", (2.0, 4.0)),
        ("-5 to -1", (-5.0, -1.0)),
        (" 1.5 to 3 ", (1.5, 3.0)),
        ("1. to 3", (1.0, 3.0)),
        # Low must be strictly below high (the author's ruling).
        ("4 to 2", None),
        ("2 to 2", None),
        # Exactly two plain numbers, joined by " to ".
        ("2to4", None),
        ("2 - 4", None),
        ("2 to 4 to 6", None),
        ("a to 4", None),
        ("2 to inf", None),
        ("4", None),
        ("", None),
    ],
)
def test_a_range_is_two_plain_numbers_low_below_high(value, bounds) -> None:
    assert parse_range(value) == bounds


def test_a_bad_range_or_answer_closes_the_branch() -> None:
    for value in ("4 to 2", "2 to 2", "2-4", "", "x to 4"):
        assert branch_is_open(_parent("in_inc", value), "3") is False
    for answer in ("", "  ", "three", "1_000", None):
        assert branch_is_open(_parent("out_inc", "2 to 4"), answer) is False


@pytest.mark.parametrize(
    ("op", "label"),
    [
        ("in_inc", "Rating ≥ 2 and ≤ 4.50"),
        ("in_exc", "Rating > 2 and < 4.50"),
        ("out_inc", "Rating ≤ 2 or ≥ 4.50"),
        ("out_exc", "Rating < 2 or > 4.50"),
    ],
)
def test_a_range_reads_with_symbols_and_its_ends_as_typed(op, label) -> None:
    assert condition_label(_parent(op, "2 to 4.50")) == label


def test_ranges_are_accepted_from_rung_3() -> None:
    """Save and the settings CSV take the four tokens once the builder can
    show them (19T Item 12 rung 3), and name the end at fault."""
    assert RANGE_OPS <= BRANCH_OPS
    assert all(len(op) <= 8 for op in RANGE_OPS)  # branch_op is String(8)
    for op in RANGE_OPS:
        assert condition_error("Integer", None, op, "2 to 4") is None
        assert condition_error("Decimal", None, op, "-1.5 to 0.5") is None
    cases = {
        "4": "The branch condition needs a range: a low and a high number.",
        "2 to 4 to 6": "The branch condition needs a range: a low and a high number.",
        " to 4": "The range's low end needs a number.",
        "x to 4": "The range's low end needs a number.",
        "2 to ": "The range's high end needs a number.",
        "2 to": "The range's high end needs a number.",
        "to 4": "The range's low end needs a number.",
        "to": "The range's low end needs a number.",
        "2 to inf": "The range's high end needs a number.",
        "4 to 2": "The range's low end must be below its high end.",
        "2 to 2": "The range's low end must be below its high end.",
    }
    for value, message in cases.items():
        assert condition_error("Integer", None, "in_inc", value) == message, value
    # A single-value operator refuses a range; a List refuses a range token.
    assert condition_error("Integer", None, "ge", "2 to 4") == (
        "The branch condition needs a number."
    )
    assert condition_error("List", "a,b", "in_inc", "2 to 4") is not None


def _is_open_source() -> str:
    text = SURFACE.read_text()
    start = text.index("function isOpen(op, value, raw) {")
    return text[start : text.index("function sync(", start)]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_reviewer_script_agrees_with_the_service() -> None:
    """``isOpen`` run in node against ``branch_is_open`` on every range token,
    at and around both ends, over good and bad values and answers."""
    values = ["2 to 4", "-5 to -1", "1.5 to 3", " 2 to 4 ", "4 to 2", "2 to 2",
              "2to4", "2 to 4 to 6", "a to 4", "1_000 to 2000", "4", ""]
    answers = ANSWERS + ["-5", "-3", "-1", "0", "1.5", "", " 3 ", "1_000", "x", "1e0"]
    cases = [
        [op, value, answer]
        for op in sorted(RANGE_OPS) + ["ge", "eq"]
        for value in values
        for answer in answers
    ]
    script = (
        _is_open_source()
        + "\nconst cases = JSON.parse(process.argv[1]);\n"
        + "console.log(JSON.stringify(cases.map(c => isOpen(c[0], c[1], c[2]))));\n"
    )
    out = subprocess.run(
        ["node", "-e", script, json.dumps(cases)],
        capture_output=True, text=True, check=True,
    ).stdout
    js = json.loads(out)
    py = [branch_is_open(_parent(op, value), answer) for op, value, answer in cases]
    mismatches = [c for c, a, b in zip(cases, js, py) if a != b]
    assert not mismatches, mismatches[:10]
