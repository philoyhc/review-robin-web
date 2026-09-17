"""Invitations and Responses take the split table toolbar.

19P.5 rung 3, the last two of the seven. Each kept its filter in a
`filter-card` beside the info card in a `bottom-grid`, and put its chip
row and pager straight into an unsplit `.table-card-toolbar`.

Three changes that had to land together, because the grid makes them
one: the filter moves into `toolbar-right`, the info card is left the
grid's only child (so the grid goes and the card is full width), and
the submit stops saying `Apply`.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from .test_invitations import _ready_session

OPERATOR = pathlib.Path("app/web/templates/operator")
PAGES = ("invitations", "responses")
#: `_ready_session` seeds reviewer Rae and reviewee Carol, and each
#: page searches its own side of the pair — so one term cannot serve
#: both. A term matching nothing would empty the left pane and make
#: the count-line assertion below pass vacuously.
MATCHING_TERM = {"invitations": "rae", "responses": "carol"}


def _page(client: TestClient, session, page: str, query: str = "") -> str:
    return client.get(
        f"/operator/sessions/{session.id}/{page}{query}"
    ).text


def _markup(html: str) -> str:
    """Without inline `<style>`. `base.html`'s CSS comments contain
    both `class="` and the class names these tests assert are absent,
    so a regex over the raw page runs straight through them — the
    vacuity `test_assignments_lifecycle_gate.py` warns about."""
    return re.sub(r"<style\b.*?</style>", "", html, flags=re.S)


def _pane(body: str, which: str) -> str:
    start = body.index(f'<div class="toolbar-pane toolbar-{which}">')
    rest = body[start:]
    stop = '<div class="toolbar-pane toolbar-right">' if which == "left" else "</form>"
    return rest[: rest.index(stop)]


@pytest.mark.parametrize("page", PAGES)
def test_the_filter_is_in_the_toolbar_and_the_submit_says_search(
    client: TestClient, db: Session, page: str
) -> None:
    """`Apply` against `Search` was the drift: five surfaces said one
    thing and these two said the other. The minority renames."""
    rs = _ready_session(client, db, code=f"ops-tb-{page[:3]}")
    body = _page(client, rs, page)

    assert '<div class="table-card-toolbar is-split">' in body
    right = _pane(body, "right")
    assert '<select name="status">' in right
    assert '<input type="text"' in right and 'name="q"' in right
    assert ">Search</button>" in right
    assert ">Apply<" not in body

    # The card it came from is gone from this page (Validate keeps the
    # class, which is why the class itself stays in `base.html`).
    assert "filter-card" not in _markup(body)


@pytest.mark.parametrize("page", PAGES)
def test_the_search_lands_on_the_table_card(
    client: TestClient, db: Session, page: str
) -> None:
    """A `GET` submission replaces the query and leaves the action's
    fragment alone, so a search scrolls to the table card exactly as a
    page turn does (19J.8) rather than landing at the document top.

    From its old home in a card above the table the form carried no
    fragment, and did not need one — it was already at the top. It
    needs one now. Nothing pinned this on either page until a mutation
    dropping the anchor survived the whole suite, twice.
    """
    rs = _ready_session(client, db, code=f"ops-an-{page[:3]}")
    body = _page(client, rs, page)
    anchored = f"/operator/sessions/{rs.id}/{page}#{page}-table-card"

    assert f'action="{anchored}"' in _pane(body, "right")

    # `Clear` takes the same anchor, so clearing lands where searching
    # does. It only renders with a filter active.
    cleared = _pane(_page(client, rs, page, "?q=nosuchterm"), "right")
    assert f'href="{anchored}"' in cleared


@pytest.mark.parametrize("page", PAGES)
def test_the_count_line_moved_into_the_left_pane(
    client: TestClient, db: Session, page: str
) -> None:
    """It rendered just outside the toolbar, where neither
    `spec/rrw_functional_spec.md:1114` nor `spec/ui_elements.md:626`
    puts it. Once, not twice: a move that copied would leave both."""
    rs = _ready_session(client, db, code=f"ops-cl-{page[:3]}")
    body = _page(client, rs, page, f"?q={MATCHING_TERM[page]}")
    count_line = '<p class="muted table-showing-hint">'

    left = _pane(body, "left")
    assert count_line in left, left
    assert body.count(count_line) == 1


@pytest.mark.parametrize("page", PAGES)
def test_the_filter_survives_a_search_that_matches_nothing(
    client: TestClient, db: Session, page: str
) -> None:
    """The reason the toolbar cannot sit inside `{% if rows %}`.

    The table card used to, which was fine while the filter was a
    separate card above it — and became a trap the moment the filter
    moved in: a search matching nothing would take away the only way
    to clear it. The message sits below the toolbar now, where the
    rows would be.
    """
    rs = _ready_session(client, db, code=f"ops-nm-{page[:3]}")
    body = _page(client, rs, page, "?q=nosuchterm")

    assert '<div class="table-card-toolbar is-split">' in body
    assert 'value="nosuchterm"' in body
    assert ">Clear</a>" in _pane(body, "right")
    noun = "reviewers" if page == "invitations" else "reviewees"
    assert f"No {noun} match the current filter." in body


@pytest.mark.parametrize("page", PAGES)
def test_the_info_card_is_no_longer_half_a_grid(
    client: TestClient, db: Session, page: str
) -> None:
    """One move, two visible effects. The info card and the filter card
    were the two children of one `bottom-grid`, so taking the filter
    out would strand the info card at half width in the LEFT column —
    a card that reads as having failed to fill the row.

    The wrapper goes rather than the card gaining a width class: a
    `1fr 1fr` grid with one child is not a grid. Measured in Chromium
    at 1280px — info card 1200px, the same as the table card.
    """
    # Class attributes, not the raw text: the template's comment names
    # the grid to record where it went, and `base.html` carries the
    # class in its inline CSS.
    src = _markup((OPERATOR / f"session_{page}.html").read_text())
    assert not [
        c for c in re.findall(r'class="([^"]*)"', src) if "bottom-grid" in c
    ], page
    assert f'id="{page}-info-card"' in src

    rs = _ready_session(client, db, code=f"ops-ic-{page[:3]}")
    body = _markup(_page(client, rs, page))
    assert not [
        c for c in re.findall(r'class="([^"]*)"', body) if "bottom-grid" in c
    ], page


def test_all_seven_table_toolbars_are_split() -> None:
    """The set this segment has been closing one page at a time.
    Asserted from source because three of the seven need a session in a
    particular state to render a table at all."""
    carriers = {
        path.name: path.read_text()
        for path in sorted(OPERATOR.glob("session_*.html"))
        if '"table-card-toolbar' in path.read_text()
    }
    assert len(carriers) == 7, sorted(carriers)
    assert [
        name for name, text in carriers.items()
        if "table-card-toolbar is-split" not in text
    ] == []
