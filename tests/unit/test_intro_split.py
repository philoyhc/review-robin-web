"""19T Item 17 — the intro's help-card split (`views.intro_split_index`).

The intro is two column stacks: the heading card over the first k help
cards, the visibility card over the rest, in field order. `k` is the split that
ends the two columns closest in height, ties to the heavier left column;
a near tie leans left too, when the columns without the card at the split
end within the lean (one line of help text) of each other.
The browser's copy, `rrwIntroSplitIndex` in `base.html`, is held to the
same answers by `tests/integration/test_inline_scripts_parse.py`.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.web.views import estimated_intro_split, intro_split_index
from app.web.views._instruments import INTRO_LEAN_PX, InstrumentHeading

GAP = 12
LEAN = INTRO_LEAN_PX


@pytest.mark.parametrize(
    ("left_top", "right_top", "heights", "expected"),
    [
        # The author's example: a shrunk heading, the visibility card, three
        # help cards — two go left, one right.
        (89, 154, [80, 60, 55], 2),
        (89, 154, [], 0),  # no help cards
        (89, 154, [46], 1),  # one: whichever side ends closer (no near tie)
        (500, 154, [46, 46], 0),  # a very long description: all go right
        (None, 154, [46, 46], 2),  # no heading: the left column is help cards
        # No visibility card: the right is help cards. (Without the first
        # help card the columns end 89 / 46px, 43px apart: no lean.)
        (89, None, [46, 46], 0),
        (None, None, [46], 1),  # a tie goes to the heavier left
        (100, 100, [50, 50], 1),  # symmetric: one each
    ],
)
def test_the_split_balances_the_columns(left_top, right_top, heights, expected):
    assert intro_split_index(left_top, right_top, heights, GAP, LEAN) == expected


def test_a_long_first_card_takes_the_left_alone() -> None:
    # A shortest-column-first placement would send the short cards after
    # it left too; the split keeps field order, so only the first goes.
    assert intro_split_index(60, 150, [200, 30, 30, 30], GAP, LEAN) == 1


def test_the_gap_decides_between_near_splits() -> None:
    # No lean here, so only the gap decides. A 40 then three 10s: with the
    # gap between cards counted (20 here) the best split is 40 + 10
    # against 10 + 10; a copy that ignored the gap, or fixed it at 12,
    # answers 1.
    assert intro_split_index(None, None, [40, 10, 10, 10], 20, 0) == 2
    assert intro_split_index(None, None, [40, 10, 10, 10], 0, 0) == 1
    # With no gap three 10s balance a 20 top; at 12 the gaps tip it to 2.
    assert intro_split_index(None, 20, [10, 10, 10], 0, 0) == 3
    assert intro_split_index(None, 20, [10, 10, 10], 12, 0) == 2


def test_a_near_tie_leans_left() -> None:
    # The author's screenshot (2026-09-30): a title-only heading, the
    # visibility card, Familiarity and Rating. Rating alone under the
    # visibility card is 6px nearer balanced, but without it the columns
    # end 3px apart, so it follows Familiarity down the left.
    assert intro_split_index(75, 146, [62, 62], GAP, 0) == 1
    assert intro_split_index(75, 146, [62, 62], GAP, LEAN) == 2
    # The lean is inclusive: 24px apart leans, 25px does not.
    assert intro_split_index(96, 146, [62, 62], GAP, LEAN) == 2
    assert intro_split_index(97, 146, [62, 62], GAP, LEAN) == 1


def test_one_help_card_leans_left_on_a_near_tie() -> None:
    # The two top cards end 10px apart, so the lone help card goes left
    # although the right would end closer (48px against 68px).
    assert intro_split_index(80, 70, [46], GAP, 0) == 0
    assert intro_split_index(80, 70, [46], GAP, LEAN) == 1


def test_the_lean_moves_the_card_at_the_split() -> None:
    # Three cards, best k = 1: without the second card (the first on the
    # right) the columns end 162 / 158px, 4px apart, so it goes left and
    # the third stays right. Moving the last card instead would answer 3;
    # leaning only when one card is on the right would answer 1.
    assert intro_split_index(80, 96, [70, 40, 50], GAP, 0) == 1
    assert intro_split_index(80, 96, [70, 40, 50], GAP, LEAN) == 2


def test_the_browsers_lean_is_the_servers() -> None:
    # A text check, here rather than beside the node parity test, so it
    # runs where node is absent.
    import re
    from pathlib import Path

    base = (
        Path(__file__).resolve().parents[2] / "app/web/templates/base.html"
    ).read_text()
    match = re.search(r"var RRW_INTRO_LEAN_PX = (\d+);", base)
    assert match and int(match.group(1)) == INTRO_LEAN_PX


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
