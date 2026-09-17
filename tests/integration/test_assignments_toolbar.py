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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment

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

    # The class list, not the whole attribute: the row gained the
    # `is-grouped` modifier, and a match anchored on the closing quote
    # would read that as "the chip row left the pane".
    assert 'class="col-chip-row' in left
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


# ── Rung 2: the row expander ───────────────────────────────────────────


def _markup(html: str) -> str:
    """The page with its inline `<style>` removed, as
    `test_reviewers_roster_card_scaffold.py` does it."""
    return re.sub(r"<style\b.*?</style>", "", html, flags=re.S)


def _builder(body: str) -> str:
    """The expander's `build()` body — the string literal that becomes
    the injected panel. Bounded by the function that consumes it."""
    start = body.index('tr.id = "assignments-row-expander"')
    return body[start : body.index("function render()", start)]


def test_the_operator_actions_card_is_gone_from_the_page(
    client: TestClient, db: Session
) -> None:
    """Rung 1 emptied it of the filter; rung 2 empties it entirely.

    The card was the last `.operator-actions-card` in the app — the
    four roster pages gave theirs up across 19P.1-3 — so the class, its
    `bottom-grid` wrapper and `.grid-right` all go with it.
    `.grid-right` had no other caller.
    """
    rs = _seeded(client, db, "asn-exp-card")
    body = _page(client, rs)

    # Markup only: `base.html` names both classes in its inline CSS,
    # in the rules' own comments recording where they went, so a bare
    # substring over the page is true everywhere and asserts nothing —
    # the vacuous check `test_assignments_lifecycle_gate.py` calls out.
    markup = _markup(body)
    assert "operator-actions-card" not in markup
    assert "grid-right" not in markup
    assert 'id="assignments-selected-count"' not in body
    assert 'id="assignments-inactivate-btn"' not in body
    assert 'id="assignments-activate-btn"' not in body
    # The bulk form stays: the checkboxes and the injected buttons both
    # reach the routes through it.
    assert '<form id="assignments-bulk-form"' in body


def test_every_row_carries_the_status_the_panel_reads(
    client: TestClient, db: Session
) -> None:
    """`data-status` is `Assignment.include`, in the vocabulary
    `spec/assignments.md` § *The status filter* already uses for
    `?status=` (`active` = `include IS true`).

    It decides which of `Inactivate` / `Activate` the panel offers, so
    a row whose attribute disagreed with its Include cell would offer
    the button that no-ops. Asserted against the cell rather than
    against the database, because the cell is what the operator reads.
    """
    rs = _seeded(client, db, "asn-exp-status")
    rows = db.execute(
        select(Assignment).where(Assignment.session_id == rs.id)
    ).scalars().all()
    assert rows, "fixture generated no assignments"
    # Flip one so the page is not uniform — a page where every row is
    # `active` cannot tell a correct mapping from a hardcoded one.
    rows[0].include = False
    db.commit()

    body = _page(client, rs)
    for row in rows:
        marker = f'<tr id="assignment-row-{row.id}"'
        assert marker in body, row.id
        fragment = body[body.index(marker) : body.index("</tr>", body.index(marker))]
        expected = "active" if row.include else "inactive"
        assert f'data-status="{expected}"' in fragment, (row.id, expected)
        # The cell the operator reads, in the same fragment.
        assert (">yes<" if row.include else ">no<") in fragment, row.id


def test_the_panel_offers_only_the_action_the_selection_admits(
    client: TestClient, db: Session
) -> None:
    """The behavior change in this rung, not a move.

    The card rendered `Inactivate` **and** `Activate` whenever anything
    was ticked, so a selection of entirely-included rows offered an
    `Activate` that would no-op on every one of them. The roster idiom
    renders only what is actionable, which 19P Item 1 § Semantics
    states: *"A control that would no-op on every selected row is not
    rendered."*

    Asserted on the rule in `statusActions`, which is where the
    decision lives; the browser check that it drives the rendered panel
    is in the PR body.
    """
    rs = _seeded(client, db, "asn-exp-actions")
    body = _page(client, rs)
    rule = body[
        body.index("function statusActions(sel)") : body.index(
            "function visibleColumnCount"
        )
    ]

    assert 'if (hasActive) out.push("Inactivate");' in rule
    assert 'if (hasInactive) out.push("Activate");' in rule
    # Keyed on the row attribute, not on a count or a filter value.
    assert 'row.dataset.status === "active"' in rule

    # And each label posts to its OWN route. Swapping the two branches
    # — so `Inactivate` posts `/bulk-activate` — passed this file's
    # first draft: both route strings were still in the builder and
    # both conditionals still existed, and nothing tied a label to a
    # route. `test_observers_expander.py:197-202` carries the same
    # guard, written after the same mutation survived there.
    builder = _builder(body)
    assert '? "/bulk-inactivate" : "/bulk-activate"' in builder, (
        "the status labels and their routes can disagree"
    )


def test_the_panel_is_removed_before_it_is_rebuilt(
    client: TestClient, db: Session
) -> None:
    """`render()` runs on every tick, so without the remove the page
    accumulates one panel per change instead of moving one.

    A source assertion, and a weak one — it pins the line rather than
    the behavior, which only a browser can show. The Chromium pass in
    the PR body is what actually demonstrates a single panel across
    tick, untick, mixed and select-all. It is here because the
    mutation that deletes this line survived the whole suite.
    """
    rs = _seeded(client, db, "asn-exp-remove")
    body = _page(client, rs)
    render = body[
        body.index("function render()") : body.index(
            "body.addEventListener", body.index("function render()")
        )
    ]

    assert "if (panel) { panel.remove(); panel = null; }" in render
    # Removed FIRST, before anything reads the selection.
    assert render.index("panel.remove()") < render.index("selectedRows()")


def test_the_panel_spans_the_columns_that_are_actually_shown(
    client: TestClient, db: Session
) -> None:
    """Nine tag columns are chip-toggled and the row-select column
    follows `can_edit`, so a fixed `colSpan` would leave the panel
    short or overhanging. (`Include` is *not* toggleable — it carries
    no `col-*` class and no chip; the first draft of this docstring
    said it was.)

    Two assertions, because the builder and the counter are in
    different scopes: `build()` must call it, and the counter must
    count laid-out headers rather than all of them — which the first
    draft claimed while reading only the builder's slice.
    """
    rs = _seeded(client, db, "asn-exp-colspan")
    body = _page(client, rs)

    assert "td.colSpan = visibleColumnCount();" in _builder(body)
    counter = body[
        body.index("function visibleColumnCount()") : body.index(
            "function build(sel)"
        )
    ]
    assert "th.offsetParent !== null" in counter
    assert 'table.querySelectorAll("thead th")' in counter


def test_the_panel_survives_a_sort(
    client: TestClient, db: Session
) -> None:
    """The table declares `data-rrw-sortable`, and `_rrwApplySort`
    slices `tbody.children` — the injected panel among them. It reads
    `a.children[col]`, gets `undefined` for a row whose only cell is
    the panel, sorts it null-last, and strands it at the foot of the
    table while the selected rows keep their rails where they are.

    Measured in Chromium before the guard: panel at row 30 of 31 with
    the selection at 18. With it: 19, adjacent. All three *sortable*
    roster pages carry the same capture-phase guard; Observers is the
    one that does not, and the one that does not sort.
    """
    rs = _seeded(client, db, "asn-exp-sort")
    body = _page(client, rs)

    assert 'data-rrw-sortable="rrw-sort-assignments-' in body, (
        "the guard below is only needed because this table sorts"
    )
    # Bounded by a fixed window from the guard's own first line, not
    # by searching forward for `}, true);` — another inline script on
    # the page ends that way, so an unbounded slice swallows it and a
    # capture-phase mutation survives. It did.
    start = body.index('if (!event.target.closest(".rrw-sort-btn")')
    guard = body[start : start + 220]
    assert "panel.remove()" in guard
    assert "setTimeout(render, 0)" in guard
    # Capture phase, so it runs before the header's inline handler.
    assert "}, true);" in guard, guard


def test_a_partial_selection_reads_as_a_dash(
    client: TestClient, db: Session
) -> None:
    """`selectAll.indeterminate`, which the card script this replaced
    never set and this file's first draft inherited the omission of.

    Without it a mixed selection announces as unchecked — a box
    claiming nothing is selected while the panel below says otherwise.
    All four roster pages set it.
    """
    rs = _seeded(client, db, "asn-exp-indeterminate")
    body = _page(client, rs)

    assert "selectAll.indeterminate = (n > 0 && n < all.length);" in body
