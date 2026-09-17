"""The Assignments table toolbar, split into two panes.

19P.5 rung 1. The page put its filter in an `Operator actions` card a
grid away from the rows it filters, and its chip row and pager straight
into an unsplit `.table-card-toolbar` — the arrangement the four roster
pages left behind across 19P.1-3. `base.html` named Assignments as one
of the three templates still doing so.

What moved: the status / search-by / search selects, `Clear` and the
`Search` submit, into `toolbar-right`; the preview-count line, into
`toolbar-left` beneath the pager, where three specs already say it
belongs. What stayed: the selected-count pill and the bulk buttons,
which are the selection-driven half and go to the row expander at
rung 2.
"""

from __future__ import annotations

import pathlib
import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)
from .test_assignment_routes import _make_session, _seed_roster


def _seeded(client: TestClient, db: Session, code: str):
    rs = _make_session(client, db, code=code)
    _seed_roster(
        client,
        rs.id,
        reviewer_emails=["r0@example.edu", "r1@example.edu"],
        reviewee_idents=["e0@example.edu", "e1@example.edu"],
    )
    pin_full_matrix_on_all_instruments(db, rs.id)
    generate_via_page_button(client, rs.id)
    return rs


def _page(client: TestClient, rs, query: str = "") -> str:
    url = f"/operator/sessions/{rs.id}/assignments"
    return client.get(url + query).text


def _div_depth(markup: str) -> int:
    depth = 0
    for match in re.finditer(r"<div\b|</div>", markup):
        depth += 1 if match.group(0).startswith("<div") else -1
    return depth


RIGHT_PANE = '<div class="toolbar-pane toolbar-right">'


def _pane(body: str, which: str) -> str:
    """One toolbar pane's markup, bounded by a landmark rather than by
    counting `</div>`, which the nesting inside each pane breaks.

    Left ends where the right pane begins; right ends at its form's
    close, the form being the only thing in it.
    """
    start = body.index(f'<div class="toolbar-pane toolbar-{which}">')
    rest = body[start:]
    stop = RIGHT_PANE if which == "left" else "</form>"
    return rest[: rest.index(stop)]


def test_the_toolbar_is_split_and_the_filter_is_in_the_right_pane(
    client: TestClient, db: Session
) -> None:
    rs = _seeded(client, db, "asn-tb-split")
    body = _page(client, rs)

    assert '<div class="table-card-toolbar is-split">' in body
    right = _pane(body, "right")
    for marker in (
        '<select name="status">',
        '<select name="search_by">',
        '<input type="text" name="q"',
        ">Search</button>",
    ):
        assert marker in right, marker
    # Moved, not copied. The card it came from renders ~55 lines above
    # the toolbar and is outside `_pane(body, "left")` entirely, so a
    # `not in` against that slice would pass with the select duplicated
    # in the card. Counting the whole page is the check that means it.
    assert body.count('<select name="search_by">') == 1
    assert body.count('<input type="text" name="q"') == 1


def test_the_chips_pager_and_count_line_are_in_the_left_pane(
    client: TestClient, db: Session
) -> None:
    """The count line rendered just outside the toolbar until this rung.

    `spec/rrw_functional_spec.md:1114` ("the preview-count line sits in
    the toolbar's left pane") and `spec/ui_elements.md:626` ("Left
    pane: … column chips, pager cluster, count line") both put it
    there, under the pager — the order `tests/unit/test_pager.py` pins
    for the pager and the sentence together.

    A third citation rode along with this rung's first draft and is
    struck: `spec/operator_ui_concept.md` describes the two-pane
    toolbar but never mentions the count line at all.
    """
    rs = _seeded(client, db, "asn-tb-left")
    body = _page(client, rs, "?q=r0@example.edu")
    left = _pane(body, "left")
    count_line = '<p class="muted table-showing-hint">'

    assert 'class="col-chip-row"' in left
    assert count_line in left, "the count line is outside the pane"
    # Once, and only in the pane: it used to render below the closing
    # `</div>`, so a move that copied rather than moved would leave two.
    assert body.count(count_line) == 1

    # The pager's place relative to the sentence is pinned by
    # `tests/unit/test_pager.py` and needs 200+ rows to render at all
    # (`views._pager.PAGE_SIZE`), so it is not re-asserted here. What
    # this rung changed is which side of the toolbar's closing tag the
    # sentence falls on.


def test_the_search_lands_on_the_table_card(
    client: TestClient, db: Session
) -> None:
    """A `GET` submission replaces the query and leaves the action's
    fragment alone, so a search arrives at the card's top edge exactly
    as a page turn does (19J.8). From its old home in the card the form
    carried no fragment and the reload landed at the document top.

    Verified in Chromium as well as here: the browser scrolls to the
    anchor, capped by the page's own height.
    """
    rs = _seeded(client, db, "asn-tb-anchor")
    body = _page(client, rs)
    right = _pane(body, "right")

    anchored = f"/operator/sessions/{rs.id}/assignments#assignments-table-card"
    assert f'action="{anchored}"' in right

    # `Clear` takes the same anchor, so clearing lands where searching
    # does. It only renders with a filter active, hence the query.
    cleared = _pane(_page(client, rs, "?q=r0@example.edu"), "right")
    assert ">Clear</a>" in cleared
    assert f'href="{anchored}"' in cleared


def test_the_no_match_state_closes_every_div_it_opens(
    client: TestClient, db: Session
) -> None:
    """A real defect this rung inherited, not a hypothetical.

    `<div class="table-card-toolbar">` opened above the
    `{% if not pair_sample %}` and closed inside its `{% else %}`, so a
    search matching nothing emitted an unclosed `<div>`. Measured
    before the rung: a net `<div>` depth of **2** on the no-match page
    against **1** on the same page with rows, and 1 on every other
    operator page. The toolbar renders unconditionally now and the
    message sits below it, where the rows would be.
    """
    rs = _seeded(client, db, "asn-tb-empty")
    rows = _page(client, rs)
    empty = _page(client, rs, "?q=nosuchterm")

    assert "No assignments match the search." in empty
    # Absolute, not relative: `==` alone passes if both pages drift to
    # the same wrong depth. 1 is what every operator page measures,
    # this one included once it has rows.
    assert _div_depth(rows) == 1
    assert _div_depth(empty) == 1
    # The filter is still reachable, with the term kept, so the operator
    # can clear it — the reason the toolbar cannot be inside the branch.
    assert 'value="nosuchterm"' in empty
    assert ">Clear</a>" in empty
    assert '<div class="table-card-toolbar is-split">' in empty


def test_no_split_toolbar_chip_row_carries_an_inline_margin() -> None:
    """`base.html:1742` is `.toolbar-left > * { margin: 0 }`, written
    for exactly this pane. An inline style outrules it.

    Assignments carried `style="margin: 0 0 12px 0;"` on its chip row
    from its unsplit-toolbar days and kept it through the first draft of
    this rung, which put 12px on top of `.toolbar-left`'s 16px `gap` —
    28px where the rosters have 16. The three roster pages that made
    this same move all dropped the attribute; a cold read caught that
    this one had not, and nothing was pinning it either way.

    Asserted from source across every page carrying the modifier, not
    from one render: the defect is a template attribute, and it is only
    visible in a browser when the chip row has a sibling in the pane —
    which needs a filter or 200+ rows.
    """
    offenders = {}
    for path in sorted(
        pathlib.Path("app/web/templates/operator").glob("session_*.html")
    ):
        text = path.read_text()
        if "table-card-toolbar is-split" not in text:
            continue
        for line in text.splitlines():
            if "col-chip-row" in line and "<p" in line and "style=" in line:
                offenders[path.name] = line.strip()

    assert offenders == {}, offenders
    # And the base rule the pages rely on instead is still there.
    base = pathlib.Path("app/web/templates/base.html").read_text()
    assert "body.ui-v2 .toolbar-left > * { margin: 0; }" in base
