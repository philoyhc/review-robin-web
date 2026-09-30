"""19T Item 17 — the intro's help-card split (`views.intro_split_index`).

The intro is two column stacks: the heading card over the first k help
cards, the visibility card over the rest, in field order. `k` is the split that
ends the two columns closest in height, ties to the heavier left column.
The browser's copy, `rrwIntroSplitIndex` in `base.html`, is held to the
same answers by `tests/integration/test_inline_scripts_parse.py`.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.web.views import estimated_intro_split, intro_split_index
from app.web.views._instruments import InstrumentHeading

GAP = 12


@pytest.mark.parametrize(
    ("left_top", "right_top", "heights", "expected"),
    [
        # The author's example: a shrunk heading, the visibility card, three
        # help cards — two go left, one right.
        (89, 154, [80, 60, 55], 2),
        (89, 154, [], 0),  # no help cards
        (89, 154, [46], 1),  # one: whichever side ends closer
        (500, 154, [46, 46], 0),  # a very long description: all go right
        (None, 154, [46, 46], 2),  # no heading: the left column is help cards
        (89, None, [46, 46], 0),  # no visibility card: the right is help cards
        (None, None, [46], 1),  # a tie goes to the heavier left
        (100, 100, [50, 50], 1),  # symmetric: one each
    ],
)
def test_the_split_balances_the_columns(left_top, right_top, heights, expected):
    assert intro_split_index(left_top, right_top, heights, GAP) == expected


def test_a_long_first_card_takes_the_left_alone() -> None:
    # A shortest-column-first placement would send the short cards after
    # it left too; the split keeps field order, so only the first goes.
    assert intro_split_index(60, 150, [200, 30, 30, 30], GAP) == 1


def test_the_gap_decides_between_near_splits() -> None:
    # A 40 then three 10s: with the gap between cards counted (20 here)
    # the best split is 40 + 10 against 10 + 10; a copy that ignored the
    # gap, or fixed it at 12, answers 1.
    assert intro_split_index(None, None, [40, 10, 10, 10], 20) == 2
    assert intro_split_index(None, None, [40, 10, 10, 10], 0) == 1
    # With no gap three 10s balance a 20 top; at 12 the gaps tip it to 2.
    assert intro_split_index(None, 20, [10, 10, 10], 0) == 3
    assert intro_split_index(None, 20, [10, 10, 10], 12) == 2


def test_the_estimate_counts_a_long_title() -> None:
    # A lone instrument whose description is its title (no subtitle).
    rows = [object(), object()]
    short = [SimpleNamespace(label="A", help_text="a"), SimpleNamespace(label="B", help_text="b")]
    assert estimated_intro_split(InstrumentHeading(title="Short", subtitle=None), rows, short) == 2
    long_title = InstrumentHeading(title="t" * 400, subtitle=None)
    assert estimated_intro_split(long_title, rows, short) == 0


def test_the_estimate_follows_text_length() -> None:
    heading = InstrumentHeading(title="#1: Group Peer Review", subtitle="Short.")
    rows = [object(), object()]

    def item(label: str, text: str) -> SimpleNamespace:
        return SimpleNamespace(label=label, help_text=text)

    short = [item("Familiarity", "0 to 3."), item("Rating", "1 to 5."), item("Comments", "Optional.")]
    assert estimated_intro_split(heading, rows, short) == 2
    # A description long enough to outgrow the visibility card sends them right.
    long_heading = InstrumentHeading(title="#1", subtitle="x" * 800)
    assert estimated_intro_split(long_heading, rows, short) == 0
    # No help cards: nothing to split.
    assert estimated_intro_split(heading, rows, []) == 0
