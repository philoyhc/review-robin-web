"""A client-side sort drops the injected selection panel — 19O Item 4.

``_rrwApplySort`` re-sorts **every child** of ``tbody.rrw-rows``. An
injected ``.session-expander`` panel is one of those children, carries a
single ``colspan`` cell and no ``data-sort-value``, so ``_rrwCellValue``
returns ``null`` for every column and the null-last rule parks it at the
bottom of the table, detached from the row it brackets.

The second effect is quieter and worse. The same pass stamps
``rrwOriginalIndex`` once per row, which is what ``state.length === 0``
restores when the operator clears the sort. A panel present at stamping
time occupies an index, so **every row after it is stamped one too
high** and "unsorted" stops restoring the server's order.

**There is no JS runtime in this suite**, so these are structural
assertions over the shipped source, in the idiom of
``test_column_visibility_primitive.py``. They pin the mechanism — the
removal, its position relative to the stamp, the dispatch, and a
listener per owner — because the browser half is confirmed on the dev
slot and nothing here can reach it.

The ordering assertion is the load-bearing one. A removal that ran
*after* the stamp would leave the index corruption in place while
looking correct in a grep, which is exactly the class of guard 19P kept
having to re-aim: one that proves less than it claims.
"""
from __future__ import annotations

from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"
BASE = TEMPLATES / "base.html"
OPERATOR = TEMPLATES / "operator"

#: The pages migrated to the shared signal — **not** the set that
#: injects a panel. Measured at HEAD: seven templates inject a
#: `.session-expander`, six of them also sort, and three still carry
#: 19P.1's per-page capture-phase handler (`session_reviewees`,
#: `session_relationships`, `session_assignments`). They are correct
#: today — their handler runs before the inline sort handler, so
#: `_rrwApplySort` finds nothing to remove — and migrating them is
#: filed as 19O Item 6.
#:
#: The plan's own blast radius said *three* injecting pages, measured
#: at `820d5d6`, which is not this branch's base: 19P.2-3 and 19P.5
#: added four more between that measurement and this item being built.
#: A measurement carries its commit for exactly this reason.
MIGRATED_PAGES = [
    "sessions_list.html",
    "sessions_archived.html",
    "session_reviewers.html",
]

#: Still on the per-page handler. Listed so this file states the whole
#: picture rather than the part it checks — a reader who deletes one of
#: these workarounds on the strength of the shared fix gets a panel
#: that vanishes on sort, because these pages have no listener.
UNMIGRATED_PAGES = [
    "session_reviewees.html",
    "session_relationships.html",
    "session_assignments.html",
]


def _strip_line_comments(js: str) -> str:
    """Blank out ``//`` comment text, keeping every byte's position.

    Written after this module's own first run failed: the ordering
    assertion matched ``rrwOriginalIndex`` inside the *comment* that
    explains the fix, 400 characters ahead of the code it describes.
    That is the same defect 19P kept re-aiming guards for — an
    assertion satisfied by prose the page happens to contain. Padding
    with spaces rather than deleting keeps every surviving index
    comparable to the raw source, so a failure message still points at
    a real offset.
    """
    out = []
    i = 0
    while i < len(js):
        if js.startswith("//", i):
            end = js.find("\n", i)
            if end == -1:
                end = len(js)
            out.append(" " * (end - i))
            i = end
        else:
            out.append(js[i])
            i += 1
    return "".join(out)


def _apply_sort_body() -> str:
    """``_rrwApplySort``'s source, brace to brace, comments blanked.

    Counted rather than regexed: the function contains nested braces in
    both its loops and its comparator, so a non-greedy match to the
    first ``}`` would stop inside the first ``if`` and a greedy one
    would run to the end of the file. Either would let a real
    regression pass.
    """
    src = _strip_line_comments(BASE.read_text(encoding="utf-8"))
    start = src.index("function _rrwApplySort(")
    open_brace = src.index("{", start)
    depth = 0
    for i in range(open_brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_brace : i + 1]
    raise AssertionError("_rrwApplySort is not brace-balanced")


def test_the_panel_is_removed_before_the_rows_are_stamped() -> None:
    """The ordering, which is the whole fix.

    Removal after the stamp would still strand the panel visually and
    would still corrupt `rrwOriginalIndex` — the defect this item exists
    for. Asserting only that a removal exists somewhere would pass on
    that broken arrangement.
    """
    body = _apply_sort_body()

    # The *removal*, not the selector. The first version of this test
    # indexed `.session-expander`, which pins where the panel is
    # `querySelectorAll`-ed and says nothing about where it leaves the
    # DOM. A cold read split the two statements — selector early,
    # `removeChild` after the stamp — and all four assertions passed
    # against an implementation that left the index corruption live and
    # re-appended the panel at the bottom from the stale `rows` array.
    removal = body.index("removeChild")
    collect = body.index("tbody.children")
    stamp = body.index("rrwOriginalIndex")

    assert removal < collect, (
        "the panel must leave the DOM before `tbody.children` is "
        "collected — otherwise it is sorted as a row"
    )
    assert removal < stamp, (
        "the panel must leave the DOM before `rrwOriginalIndex` is "
        "stamped — otherwise every row after it is stamped one too high "
        "and the unsorted restore order is corrupted"
    )


def test_the_panel_is_removed_rather_than_hidden() -> None:
    """A hidden row still occupies an `rrwOriginalIndex`.

    Aimed at what is removed, not merely that a `removeChild` appears:
    the bare-substring version would have passed on a `removeChild` of
    anything at all.
    """
    body = _apply_sort_body()

    # Ordering, not distance. A first draft asserted the `removeChild`
    # sat within 200 characters of the selector, which was a number
    # picked from the current 102 rather than derived from anything —
    # and `_strip_line_comments` pads comments with spaces, so three
    # explanatory lines inserted between the two would have failed the
    # test with a message about "removing something else" that was not
    # true. What actually matters is that the selector precedes the
    # removal and the removal precedes the stamp; the sibling test
    # above owns the second half.
    assert body.index(".session-expander") < body.index("removeChild"), (
        "the `removeChild` must act on the panels this function "
        "selected, so the selector comes first"
    )
    assert "style.display" not in body, (
        "the panel must leave the DOM; hiding it keeps its index"
    )


def test_the_sort_signals_after_the_rows_land() -> None:
    """A listener re-anchors against a row, so it needs the final order."""
    body = _apply_sort_body()

    dispatch = body.index('"rrw:sorted"')
    reappend = body.index("tbody.appendChild")

    assert reappend < dispatch, (
        "`rrw:sorted` must fire after the rows are re-appended, or a "
        "listener re-anchors against the pre-sort order"
    )


@pytest.mark.parametrize("page", MIGRATED_PAGES)
def test_every_migrated_page_listens(page: str) -> None:
    """The dispatch is only half a fix without an owner on the other end."""
    src = (OPERATOR / page).read_text(encoding="utf-8")
    assert 'addEventListener("rrw:sorted"' in src, (
        f"{page} injects a selection panel and sorts, so it must "
        "re-anchor on `rrw:sorted`"
    )


@pytest.mark.parametrize("page", UNMIGRATED_PAGES)
def test_every_unmigrated_page_still_defends_itself(page: str) -> None:
    """Never zero mechanisms — which is the half that matters.

    This is the assertion that makes the split safe to ship. Deleting a
    page's capture-phase handler without giving it a listener leaves it
    with neither: the panel is dropped by `_rrwApplySort` and nothing
    puts it back. Pinning the workaround's *presence* here means that
    mistake fails a test instead of shipping.

    Deliberately `or`, not `!=`. A page carrying both during a
    migration is redundant rather than broken, and failing it would
    force the two halves of a move into one commit.
    """
    src = (OPERATOR / page).read_text(encoding="utf-8")
    has_workaround = 'closest(".rrw-sort-btn")' in src
    has_listener = 'addEventListener("rrw:sorted"' in src
    assert has_workaround or has_listener, (
        f"{page} injects a selection panel into a sortable table and "
        "has neither the per-page handler nor the shared listener, so "
        "its panel disappears on sort"
    )


def test_the_per_page_workaround_is_gone() -> None:
    """Two mechanisms for one bug is how one of them rots unnoticed.

    19P.1 rung 1 shipped a capture-phase click handler on Reviewers that
    removed the panel before the inline sort handler ran. It worked, and
    it was deliberately local so that slice would not change lobby
    behavior — but the lobby's copy of the bug stayed live, and 19P.2-3
    would have made it five copies against one function.
    """
    src = (OPERATOR / "session_reviewers.html").read_text(encoding="utf-8")
    assert 'closest(".rrw-sort-btn")' not in src, (
        "the local workaround is superseded by the shared fix in "
        "`_rrwApplySort`; leaving both means one of them rots"
    )
