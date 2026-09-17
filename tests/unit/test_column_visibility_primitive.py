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

import re

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
    # Unquoted: the card gained ``table-pager-anchored`` at 19J.8, and
    # this probe means "the enclosing card's open tag", not "a card with
    # exactly one class".
    card_open = src.rindex('<div class="card', 0, chips)
    card_end = src.index("</table>", chips)
    assert card_open < chips < card_end
    assert "<h2" not in src[card_open:card_end]


def test_the_retired_assignments_heading_stays_retired() -> None:
    src = (OPERATOR / "session_assignments.html").read_text()
    assert "Assignments preview" not in src


def test_assignments_keeps_its_three_groups_on_one_row() -> None:
    """The nine slots come from three different sources, so the labels
    stay — but all three groups sit on **one** chip row (author,
    2026-09-10), each in its own ``.chip-group`` box so a narrow
    viewport wraps between groups rather than stranding a label from
    its chips.

    One ``data-col-toggles-for`` and one ``<p class="col-chip-row">``:
    before this the template rendered the row three times in a loop.
    """
    src = (OPERATOR / "session_assignments.html").read_text()
    assert src.count(CHIP_ROW) == 1
    # The class list, not the whole attribute: 19P.5 added the
    # `is-grouped` modifier here, and a match anchored on the closing
    # quote would read that as "the row is gone".
    assert src.count('<p class="col-chip-row') == 1
    assert 'class="col-chip-row is-grouped"' in src
    assert src.count('<span class="chip-group">') == 1  # one loop
    for label in ("Show reviewers", "Show reviewees", "Show relationships"):
        assert label in src


def test_the_assignments_search_card_and_its_grid_rule_are_both_gone() -> None:
    """19I Item 12 rung 1 left this card a lone child of a ``1fr 1fr``
    grid, which put it in the *left* column; the author asked for it
    back at half width flush right (2026-09-10) and ``.grid-right``
    did that.

    **19P.5 took the card in two steps** — rung 1 the filter strip to
    the table toolbar, rung 2 the selected count and bulk buttons to
    the row expander — so there is no lone child and no card. This
    page had the rule's only caller, so the rule went too rather than
    waiting in `base.html` for a second one.
    """
    # Markup, not prose: the template's comment names both classes to
    # record where they went, which a bare substring would trip on.
    src = (OPERATOR / "session_assignments.html").read_text()
    classes = re.findall(r'class="([^"]*)"', src)
    assert not [c for c in classes if "operator-actions-card" in c], classes
    assert not [c for c in classes if "grid-right" in c], classes
    assert ".bottom-grid > .grid-right {" not in BASE.read_text()


def test_no_template_renders_a_fields_with_data_card() -> None:
    """Rung 1 moved the chips out of the card; rung 4 retired the card.
    Its pills named the columns holding any value, which the chips now
    say — and say better, since a chip both reports the fact and acts
    on it.

    The bare string, not the rendered markup: this asserts no template
    is building one again, and the only mentions left anywhere are the
    comments recording why it went."""
    for name in sorted(p.name for p in OPERATOR.glob("*.html")):
        src = (OPERATOR / name).read_text()
        assert "Fields with data:" not in src, name


def test_the_primitive_carries_no_disabled_chip_branch() -> None:
    """Segment 19I Item 12 rung 3 retired the struck "no data in this
    column" chip: a slot with no data renders neither chip nor
    column, so there is nothing for the primitive to grey out and no
    empty column left for it to hide.

    Pinned structurally because the branch is *behaviorally* dead —
    a mutation restoring it changed no rendered page and passed every
    integration test in the suite. Only the source says it is gone.

    ``base.html`` still carries a ``.tag-chip.is-disabled`` CSS rule,
    which stays: ``instruments_index.html`` renders that class for
    its Band 1 link chips, a different mechanism entirely.
    """
    src = BASE.read_text()
    start = src.index('data-rrw-col-toggles"')
    iife = src[start : src.index("</script>", start)]
    assert "is-disabled" not in iife


# The three Operations tables outgrow their card and wrap their
# overflow; the three Setup rosters measure inside theirs and do not.
# Written as all six on a first pass and corrected by running it —
# the Setup pages never had the wrapper, and asserting they did was a
# claim, not a measurement.
SCROLL_WRAPPED = [
    "session_assignments.html",
    "session_invitations.html",
    "session_responses.html",
]


@pytest.mark.parametrize("name", SCROLL_WRAPPED)
def test_the_wide_chip_tables_sit_inside_a_table_scroll_wrapper(
    name: str,
) -> None:
    """Overflow belongs inside the card, not on the page.

    Item 11 gave Invitations and Responses the wrapper and measured
    why: 1496px of table against a ~1396px page cap, scrolling the
    whole document sideways at every width up to 1920. Assignments was
    left out and is the worst of the three — with all nine tag slots
    populated it renders **14 columns**, a 1508px table in a 1360px
    card, pushing the document 126px past a 1440 viewport.

    The three Setup rosters are deliberately absent: measured at 1324px
    inside a 1360px card, they fit.
    """
    src = (OPERATOR / name).read_text()
    table = src.index('<table id="')
    assert src.rfind('<div class="table-scroll">', 0, table) != -1, name


def test_chip_groups_are_separated_by_a_gap_not_a_margin() -> None:
    """A wrapped group must not start its line indented.

    `.chip-group + .chip-group { margin-left }` separated the groups
    while they shared one line and was wrong the moment they stopped:
    the second group wraps, starts a new line, and carries the margin
    with it — 16px of indent against the group above. 19P.5 rung 1 made
    that reachable by moving the chip row into the half-width
    `.toolbar-left` pane, where Assignments' groups no longer fit on
    one line.

    A `column-gap` is between-items-on-a-line by definition, so it
    cannot do that. It is a modifier because the roster chip rows put
    their label and chips directly in `.col-chip-row`, where a wider
    column-gap would space a label from its own chips.
    """
    base = BASE.read_text()

    assert ".chip-group + .chip-group" not in base, (
        "the adjacent-sibling margin is back; it indents wrapped groups"
    )
    assert "body.ui-v2 .col-chip-row.is-grouped {" in base
    grouped = base[base.index("body.ui-v2 .col-chip-row.is-grouped {") :]
    assert "column-gap: var(--space-4);" in grouped[: grouped.index("}")]


def test_only_chip_rows_built_from_groups_are_marked_grouped() -> None:
    """The modifier and the markup it describes cannot drift apart:
    every row carrying `.chip-group` children takes `is-grouped`, and
    no row without them does."""
    for path in sorted(OPERATOR.glob("*.html")) + sorted(
        (OPERATOR / "partials").glob("*.html")
    ):
        text = path.read_text()
        for row in re.findall(r'<p class="col-chip-row[^"]*"[^>]*>', text):
            after = text[text.index(row) + len(row) :]
            body = after[: after.index("</p>")]
            has_groups = '<span class="chip-group">' in body
            marked = "is-grouped" in row
            assert has_groups == marked, (path.name, row.strip())
