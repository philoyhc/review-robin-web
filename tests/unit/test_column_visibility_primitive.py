"""One column-visibility implementation, not five — Segment 19I Item 11.

Four operator templates carried a byte-for-byte copy of the same
IIFE, differing only in a storage key and a table id: 224 lines
between them. Porting the mechanism to Invitations and Responses
would have made six copies, so it moved to ``base.html`` on the same
declarative shape the sort primitive already uses.

These are structural assertions over the template sources. They exist
because the failure mode is silent: a sixth copy would work fine, and
nothing else in the suite would notice.
"""
from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
BASE = TEMPLATES / "base.html"
OPERATOR = TEMPLATES / "operator"

# The pages that drive column-visibility chips today. Invitations and
# Responses joined in rung 3 — through the primitive, which is the
# point of having extracted it in rung 1.
CHIP_PAGES = [
    "session_reviewers.html",
    "session_reviewees.html",
    "session_relationships.html",
    "session_assignments.html",
    "session_invitations.html",
    "session_responses.html",
]

# The storage key each page has always used. Renaming one silently
# resets every operator's saved columns on that page, so the keys are
# pinned rather than merely documented.
STORAGE_KEYS = {
    "session_reviewers.html": "rrw-reviewer-tag-visibility",
    "session_reviewees.html": "rrw-reviewee-tag-visibility",
    "session_relationships.html": "rrw-relationship-tag-visibility",
    "session_assignments.html": "rrw-assignment-col-visibility",
    "session_invitations.html": "rrw-invitation-tag-visibility",
    "session_responses.html": "rrw-response-tag-visibility",
}

# The line that actually hides a column. Exactly one implementation of
# it may exist, and it must be the shared one.
TOGGLE = 'classList.toggle("col-hidden-"'


def test_base_html_carries_the_only_implementation() -> None:
    assert BASE.read_text().count(TOGGLE) == 1


@pytest.mark.parametrize(
    "name", sorted(p.name for p in OPERATOR.glob("*.html"))
)
def test_no_operator_template_reimplements_the_toggle(name: str) -> None:
    """The assertion that would fail on a fifth copy."""
    assert TOGGLE not in (OPERATOR / name).read_text()


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_each_chip_page_declares_the_primitive(name: str) -> None:
    src = (OPERATOR / name).read_text()
    key = STORAGE_KEYS[name]
    # The key rides on the table...
    assert f'data-rrw-col-toggles="{key}"' in src
    # ...and every chip row points at a table.
    assert 'data-col-toggles-for="' in src
    # ...and the chips themselves are unchanged.
    assert "data-col-toggle=" in src


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_storage_keys_are_unchanged(name: str) -> None:
    """Pinned deliberately: a rename is invisible in review and resets
    every operator's saved column state on that page."""
    assert STORAGE_KEYS[name] in (OPERATOR / name).read_text()


def test_the_shared_sketch_cannot_collide_with_real_markup() -> None:
    """``base.html`` ships its own comment into every rendered
    document. The sketch therefore uses placeholder slot and table
    names — an earlier version used real ones and broke an unscoped
    assertion in ``test_reviewers_profile_link.py``, which searched the
    whole page for a CSS class name.
    """
    base = BASE.read_text()
    for real in STORAGE_KEYS.values():
        assert real not in base
    for real_slot in ("tag-1", "tag-2", "tag-3", "rt1", "et1", "p1"):
        assert f'data-col-toggle="{real_slot}"' not in base


# --------------------------------------------------------------------------- #
# Where the chip row sits — Segment 19I Item 12 rung 1.
#
# Invitations and Responses have had their chips inside the table
# card since Item 11; the other four kept theirs in a card of their
# own, a grid away from the rows they govern. The author preferred
# the newer shape, so all six now agree.
#
# These are ordering assertions over the template source. They exist
# because the failure mode is silent: a chip row rendered in the
# wrong card still works, and nothing else in the suite would notice
# it drifting back.
# --------------------------------------------------------------------------- #

CHIP_ROW = 'data-col-toggles-for="'
COUNT_LINE = "operator/partials/_preview_count_line.html"


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_chips_sit_above_the_count_line_and_the_table(name: str) -> None:
    """chips → count line → table, in that order, on every page."""
    src = (OPERATOR / name).read_text()
    chips = src.index(CHIP_ROW)
    count = src.index(COUNT_LINE)
    table = src.index('<table id="')
    assert chips < count < table, (
        f"{name}: chips@{chips} count@{count} table@{table}"
    )


@pytest.mark.parametrize("name", CHIP_PAGES)
def test_no_preview_card_carries_a_heading(name: str) -> None:
    """Assignments was the only preview-table card in the app with an
    ``<h2>`` (``Assignments preview``). Nothing in that card may be a
    heading — the page's chrome already says what the table is.

    Both ends of the slice were wrong once, and each was found by a
    mutation rather than by reading:

    - it started at the chip row, so a heading placed *above* the
      chips — exactly where the retired one sat — was outside it;
    - it ended at ``src.index("</table>")``, the **first** table in
      the file. On Assignments that is the per-instrument status
      table near the top, so the slice ran backwards and was empty,
      and the assertion held whatever the card contained.
    """
    src = (OPERATOR / name).read_text()
    chips = src.index(CHIP_ROW)
    card_open = src.rindex('<div class="card"', 0, chips)
    card_end = src.index("</table>", chips)
    assert card_open < chips < card_end
    assert "<h2" not in src[card_open:card_end]


def test_the_retired_assignments_heading_stays_retired() -> None:
    src = (OPERATOR / "session_assignments.html").read_text()
    assert "Assignments preview" not in src


def test_assignments_keeps_its_three_chip_rows() -> None:
    """The move is about *where* the control sits, not how it is
    grouped: the nine slots come from three different sources and one
    flat row would lose that."""
    src = (OPERATOR / "session_assignments.html").read_text()
    assert src.count(CHIP_ROW) == 1  # one loop, three renders
    for label in ("Show reviewers", "Show reviewees", "Show relationships"):
        assert label in src


def test_the_fields_with_data_card_no_longer_holds_chips() -> None:
    """Rung 1 leaves the card standing — rung 4 retires it — but the
    chips are out of it. Asserted by position: the pill row comes
    first in the file, the chip row much later, in the table card."""
    for name in (
        "session_reviewers.html",
        "session_reviewees.html",
        "session_relationships.html",
    ):
        src = (OPERATOR / name).read_text()
        assert src.index("Fields with data:") < src.index(CHIP_ROW)
