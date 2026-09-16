"""The filter strip lives in the preview table's toolbar on Reviewees
and Relationships.

19P.3 rung 2 — the move Reviewers made at 19P.1 rung 2a and Observers at
19P.2 rung 3, carried to the last two roster pages. The filter row,
``Clear``, ``Add`` (relabelled ``Add new``) and ``Search`` leave the
``Operator actions`` card for the right pane of a two-pane toolbar
inside the table card; the column chips, the pager and the count line
are the left pane.

**The card is slimmed, not retired.** It still holds the only working
``Edit`` / ``Inactivate`` / ``Activate`` / ``Delete`` on either page —
rung 3 moves those into the row expander and deletes the card. A guard
that only checked what LEFT would pass just as happily if the whole card
had gone, so the four that stay are asserted too.

**Both pages in one file, parametrized**, for the reason rung 1's file
gives: 19P.3's risk is drift between two pages that should be identical.

**The trap this rung nearly shipped, twice.**

- The table card was gated on the FILTERED row list, so moving the strip
  inside it hid the search box and its ``Clear`` in the one state an
  operator needs them — a filter matching nothing. Reviewers met this at
  19P.1 rung 2a; the gate widens to ``total_row_count > 0``.
- ``Add`` lived inside the card's ``{% if is_editable %}`` and came out
  of it in the move, which left an ``archived`` session rendering a LIVE
  ``Add new`` whose route 409s. ``is_ready`` is only ``status ==
  "ready"``, so the inner gate does not cover it. Caught by writing this
  file, not by the suite: nothing else asserts what a locked roster
  page's toolbar may offer.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

#: ``(page, noun)`` — the two pages this rung moves.
PAGES = [("reviewees", "reviewee"), ("relationships", "relationship")]

TEMPLATES = pathlib.Path("app/web/templates/operator")

#: `_SETUP_DEFAULT_CAP` in `app/web/routes_operator/_shared.py` — one
#: page of a Setup roster. Seeding past it is the only way to render a
#: pager at all.
_PAGE_SIZE = 200


def _markup(html: str) -> str:
    """``base.html`` inlines the whole app's CSS and JS on every page, so
    a page-wide substring assertion matches names in rules and scripts
    that have nothing to do with this page's markup."""
    html = re.sub(r"<style\b.*?</style>", "", html, flags=re.S)
    return re.sub(r"<script\b.*?</script>", "", html, flags=re.S)


def _div_slice(html: str, start: int) -> str:
    """The balanced ``<div>`` beginning at ``start``.

    Substring-to-the-next-``</div>`` would stop at the first nested
    close, which on a pane holding a form is three levels too early.
    """
    depth = 0
    i = start
    while i < len(html):
        nxt_open = html.find("<div", i)
        nxt_close = html.find("</div>", i)
        if nxt_close == -1:
            break
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
            continue
        depth -= 1
        if depth == 0:
            return html[start : nxt_close + 6]
        i = nxt_close + 6
    raise AssertionError("unbalanced div")


def _pane(html: str, which: str) -> str:
    marker = f'<div class="toolbar-pane toolbar-{which}">'
    at = html.find(marker)
    assert at != -1, f"no {which} pane"
    return _div_slice(html, at)


def _actions_card(html: str) -> str:
    at = html.find('<div class="card operator-actions-card">')
    assert at != -1, "the Operator actions card is gone — rung 3 retires it"
    return _div_slice(html, at)


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "R", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    # Relationships is gate-hidden — its routes 404 behind
    # `require_relationships_enabled_session`.
    rs.relationships_enabled = True
    db.commit()
    db.refresh(rs)
    return rs


def _seed(db: Session, sid: int, page: str, n: int = 3) -> list[int]:
    """Rows on whichever page is under test.

    **Every row carries a tag**, because the chip row is gated on some
    row having one and a chipless left pane would let the placement
    assertion pass against a pane that has nothing in it — the way a
    two-row fixture let the Reviewers original prove nothing.
    """
    reviewers = [
        Reviewer(
            session_id=sid, name=f"Rr{i}", email=f"rr{i}@example.org", tag_1=f"T{i}"
        )
        for i in range(n)
    ]
    reviewees = [
        Reviewee(
            session_id=sid,
            name=f"Re{i}",
            email_or_identifier=f"re{i}@example.org",
            tag_1=f"T{i}",
        )
        for i in range(n)
    ]
    db.add_all(reviewers + reviewees)
    db.commit()
    for r in reviewers + reviewees:
        db.refresh(r)

    if page == "reviewees":
        return [r.id for r in reviewees]

    rows = [
        Relationship(
            session_id=sid,
            reviewer_id=reviewers[i].id,
            reviewee_id=reviewees[i].id,
            tag_1=f"T{i}",
        )
        for i in range(n)
    ]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return [r.id for r in rows]


def _base(sid: int, page: str) -> str:
    return f"/operator/sessions/{sid}/{page}"


# ── Where the controls are ────────────────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_filter_strip_renders_in_the_toolbars_right_pane(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Not merely "on the page": the slimmed card still holds a form of
    the same class and comes first in source, so a page-wide find would
    match the one that did NOT move."""
    rs = _make_session(client, db, f"tb-r-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page)).text)

    assert '<div class="table-card-toolbar is-split">' in html
    right = _pane(html, "right")
    assert 'name="q"' in right, "the search box did not move"
    assert 'class="filter-status"' in right, "the status select did not move"
    assert ">Search</button>" in right
    assert ">Add new</a>" in right, "Add did not move, or kept its old label"


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_left_pane_holds_the_chips_and_the_count_line(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Unlike Observers, whose left pane is deliberately chipless, both
    of these pages have tag columns to toggle — so the pane is populated
    and its contents are assertable.

    **The pager is not in this test's reach, by construction.** It and
    the count line are alternatives, not neighbours: `_setup_row_window`
    sets `pager = None` whenever the view is filtered
    (`app/web/routes_operator/_shared.py:533`), and `preview_count_line`
    returns `None` when it is not. This request is filtered, so naming
    the pager here would promise a claim the fixture makes unreachable —
    which an earlier draft of this test did. The pager has its own test
    below, on an unfiltered roster past the page cap.
    """
    rs = _make_session(client, db, f"tb-l-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + "?q=Re0").text)

    left = _pane(html, "left")
    assert 'class="col-chip-row"' in left, "the chip row is not in the left pane"
    assert "table-showing-hint" in left, "the count line is not in the left pane"
    # Source order, which `tests/unit/test_pager.py` pins page-wide;
    # asserted here too because the move could have reversed it inside
    # the pane while leaving the page-wide order intact.
    assert left.index("col-chip-row") < left.index("table-showing-hint")


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_pager_is_in_the_left_pane_too(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The third tenant, on the only kind of view that renders it: an
    unfiltered roster with more rows than one page holds.

    Seeding past the cap is what makes this falsifiable. A three-row
    fixture renders no pager at all, so an assertion written against one
    would pass with the pager anywhere on the page — or nowhere.
    """
    rs = _make_session(client, db, f"tb-p-{page[:4]}")
    _seed(db, rs.id, page, n=_PAGE_SIZE + 5)
    html = _markup(client.get(_base(rs.id, page)).text)

    left = _pane(html, "left")
    assert "table-pager-cluster" in left, "the pager is not in the left pane"
    # The bottom copy is outside the toolbar and must stay there.
    assert "table-pager-cluster-bottom" not in left


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_chip_row_carries_no_inline_margin_in_the_pane(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`.toolbar-left > * { margin: 0 }` sets the spacing and the pane's
    own `gap` does the rest. An inline `style=` beats both, so the chip
    row kept a 12px tail its sibling panes on Reviewers do not have."""
    rs = _make_session(client, db, f"tb-m-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page)).text)

    chip_row = re.search(r'<p class="col-chip-row"[^>]*>', html)
    assert chip_row, "no chip row"
    assert "style=" not in chip_row.group(0), chip_row.group(0)


# (`test_the_slimmed_card_keeps_the_four_it_still_owns` stood here. The
# card it guarded is retired at 19P.3 rung 3, and the four controls it
# named are in the row expander — where
# `test_roster_expander.py::test_the_panel_carries_all_four_actions` and
# its neighbours pin them. Deleted rather than re-aimed in place: a test
# named for a card cannot be the one that guards a panel.)


# ── The trap: the states where the strip must still be reachable ──────


@pytest.mark.parametrize("page,noun", PAGES)
def test_a_filter_matching_nothing_still_renders_the_strip(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The card was gated on the FILTERED list. Moving the strip inside
    it therefore hid the search box and its `Clear` in exactly the state
    that needs them — no way out but the URL bar."""
    rs = _make_session(client, db, f"tb-n-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + "?q=zzzznomatch").text)

    right = _pane(html, "right")
    assert ">Clear</a>" in right, "no way out of a filter matching nothing"
    assert 'name="q"' in right

    # The sentence is inside the same card as the filter that produced
    # it, not a separate card below — which is what made the strip
    # vanish with the table in the first place.
    card_at = html.find('<div class="card table-pager-anchored"')
    assert card_at != -1
    card = _div_slice(html, card_at)
    assert f"No {page} match the current filter." in card
    assert "toolbar-pane toolbar-right" in card


@pytest.mark.parametrize("page,noun", PAGES)
def test_an_empty_roster_still_offers_a_LIVE_add_new(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Gating the card on the roster having rows would hide the only
    `Add new` on the page from the one operator who most needs it.

    **A live one.** `>Add new</a>` matches the disabled variant just as
    happily, and on Relationships an empty roster is exactly when the
    disabled variant renders: with no reviewer and no reviewee there is
    no pair to make, so `can_add_relationship` is False. An earlier draft
    asserted the bare string and passed on that page against a control
    the operator cannot use — the opposite of what the docstring claims.

    So "empty roster" means empty of THIS page's rows: Relationships
    seeds the two rosters it pairs and no relationships.
    """
    rs = _make_session(client, db, f"tb-e-{page[:4]}")
    if page == "relationships":
        _seed(db, rs.id, "reviewees", n=2)
    html = _markup(client.get(_base(rs.id, page)).text)

    assert '<div class="table-card-toolbar is-split">' in html, (
        "the whole card went with the empty table"
    )
    right = _pane(html, "right")
    assert re.search(r'<a class="btn secondary"\s+[^>]*\?add=1', right), (
        f"no LIVE Add new on an empty {page} roster: {right[-600:]}"
    )
    assert f"No {page} yet." in html


@pytest.mark.parametrize("page,noun", PAGES)
def test_a_locked_session_offers_no_add_new_at_all(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`Add` came out of the card's `{% if is_editable %}` in the move.
    `is_ready` is only `status == "ready"`, so the inner gate leaves
    `expired` and `archived` rendering a LIVE link whose route 409s —
    the page offering a control its route will refuse.

    Both locked states, not just one: the first draft of this test read
    `archived` alone, and `expired` is the state an operator actually
    arrives in by waiting.
    """
    for status in ("expired", "archived"):
        rs = _make_session(client, db, f"tb-{status[:3]}-{page[:4]}")
        _seed(db, rs.id, page)
        rs.status = status
        db.commit()
        html = _markup(client.get(_base(rs.id, page)).text)

        right = _pane(html, "right")
        assert ">Add new</a>" not in right, (status, page)
        assert "?add=1" not in right, (status, page)
        # Reading a locked roster is legitimate, so the filter stays.
        assert 'name="q"' in right, (status, page)
        assert ">Search</button>" in right, (status, page)


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_moved_filter_locks_while_a_row_is_being_edited(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`is-locked` greyed the strip out from `.operator-actions-main`,
    which the strip no longer sits in. It rides the moved form now, with
    a rule scoped to `.toolbar-right` that actually reaches it."""
    rs = _make_session(client, db, f"tb-k-{page[:4]}")
    ids = _seed(db, rs.id, page)
    response = client.get(_base(rs.id, page) + f"?edit_id={ids[0]}")
    html = response.text

    # Vacuity guard: a typo'd `edit_id` is ignored silently.
    assert "Save</button>" in _markup(html), "edit mode did not engage"

    moved = re.search(
        r'<div class="toolbar-pane toolbar-right">\s*(?:<!--.*?-->\s*)*'
        r"<form[^>]*?class=\"(operator-actions-filter[^\"]*)\"",
        _markup(html),
        re.S,
    )
    assert moved, "moved filter form not found in the toolbar"
    assert "is-locked" in moved.group(1), "the moved filter does not lock"
    assert re.search(
        r"\.toolbar-right \.operator-actions-filter\.is-locked \{", html
    ), "`is-locked` on the moved filter matches no rule"

    # `is-locked` greys the pane; it does not disable the link inside it.
    # `Add new` mid-edit must be the DISABLED variant, or an operator one
    # click from a half-typed row loses it. Nothing pinned this: a
    # mutation making the disabled branch live passed the whole suite.
    right = _pane(_markup(html), "right")
    assert '<a class="btn secondary disabled" aria-disabled="true">Add new</a>' in right
    assert "?add=1" not in right, "a live Add new while a row is being edited"


# ── What the moved controls must keep ─────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_filter_and_clear_keep_the_landing_fragment(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Every control in this pane reloads the page, and without a
    fragment the reload lands at the very top — throwing the operator
    away from the rows they were filtering. The pager solved this at
    19J.8 and these take the same anchor."""
    rs = _make_session(client, db, f"tb-f-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + "?q=Re0").text)

    anchor = f"{page}-table-card"
    right = _pane(html, "right")
    assert re.search(rf'<form[^>]*action="[^"]*/{page}#{anchor}"', right), right[:400]
    # `method="get"` is what puts the filter in the query string and what
    # keeps the action's fragment; the route behind it accepts GET only.
    # Unpinned until now — flipping it to `post` passed the whole suite.
    assert re.search(r'<form method="get"', right), "the moved filter is not a GET"
    assert re.search(rf'href="[^"]*/{page}#{anchor}">Clear</a>', right)


@pytest.mark.parametrize("page,noun", PAGES)
def test_add_new_still_carries_the_active_filter_and_lands_on_the_row(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Rung 1's contract, which the move must not drop: without the
    filter on this link the intervening GET rebuilds the page at the
    defaults and `create`'s round-trip carries nothing.

    The fragment arrived at rung 3, when the editor became a row. Until
    then the Add / Edit form was a card at the top of the page and a
    fragment would have scrolled the operator past it. Where the fragment
    LANDS is `test_roster_expander.py`'s claim; what this test adds is
    that carrying it did not cost the filter round-trip.
    """
    rs = _make_session(client, db, f"tb-a-{page[:4]}")
    _seed(db, rs.id, page)
    html = _markup(client.get(_base(rs.id, page) + "?status=active&q=Re0").text)

    link = re.search(r'href="([^"]*\?add=1[^"]*)"', _pane(html, "right"))
    assert link, "no live Add new link"
    href = link.group(1).replace("&amp;", "&")
    assert "status=active" in href, href
    assert "q=Re0" in href, href
    assert href.endswith(f"#{page}-row-editor"), href


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_landing_anchor_id_is_on_exactly_one_element(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Rung 1 put the id on two mutually exclusive branches — the table
    card and a separate "no matches" card. The branches merged here, so
    the id has one home and cannot be lost by a branch that forgets it.
    Checked in both states, because one card per state is the claim.
    """
    rs = _make_session(client, db, f"tb-i-{page[:4]}")
    _seed(db, rs.id, page)
    for query in ("", "?q=zzzznomatch"):
        html = _markup(client.get(_base(rs.id, page) + query).text)
        assert html.count(f'id="{page}-table-card"') == 1, (query, page)


# ── Read from source: the shape that must hold on both ────────────────


#: ``page -> how many ``Add new`` spellings its template holds``. Both
#: pages render exactly one of them per request; the count is of
#: BRANCHES. Reviewees has two — disabled (`is_ready or edit_mode`) and
#: live. Relationships has three: it also refuses when the session has
#: no reviewer or no reviewee to pair, because a relationship needs
#: both.
ADD_NEW_BRANCHES = {"reviewees": 2, "relationships": 3}


def test_both_templates_moved_and_neither_kept_a_second_strip() -> None:
    """One filter row per template. A move that copies a block rather
    than cutting it leaves two search boxes posting the same parameter,
    and the page still looks right in every rendered assertion above —
    only the source count sees it.

    The `Add new` counts are exact rather than "at least one": a branch
    lost in the move is a state that silently stops offering the
    control, and a branch gained is one that offers it where it should
    not.
    """
    for page, branches in ADD_NEW_BRANCHES.items():
        source = (TEMPLATES / f"session_{page}.html").read_text()
        assert source.count('<div class="filter-row">') == 1, page
        assert source.count('class="table-card-toolbar is-split"') == 1, page
        assert source.count(">Add new</a>") == branches, page
        assert ">Add</a>" not in source, f"{page} kept the old label somewhere"
