"""The row pager on the roster-bearing pages — Segment 19J.5.

Rung 1 landed the surface: the ranges real, the links going nowhere.
Rung 2 wired the four Setup pages, and the inertness assertion expired
exactly as that rung predicted — it now asserts the opposite on those
four, and survives unchanged on the three pages still waiting for
rungs 3 and 4.

What these pin is the operator-visible contract: the strip renders
above and below the table, it disappears while a filter is active, it
stays away when there is nothing to page, and — the point of the whole
item — a row past the first page is reachable.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _import_reviewers(client: TestClient, session_id: int, count: int) -> None:
    rows = b"".join(
        f"Reviewer {i:04d},r{i:04d}@example.edu\n".encode() for i in range(count)
    )
    response = client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": ("r.csv", b"ReviewerName,ReviewerEmail\n" + rows, "text/csv")
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.status_code


def _table(body: str) -> str:
    """Just the rows. The page also renders every reviewer's name into
    the search typeahead's ``<datalist>``, so an unscoped ``in body``
    assertion about a row is answered by the wrong element — and an
    unscoped ``not in`` passes or fails for reasons that have nothing
    to do with paging."""
    return body[body.index('id="reviewers-table"') :]


def test_a_roster_over_one_page_gets_a_pager_above_and_below_the_table(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pager-big")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(f"/operator/sessions/{review_session.id}/reviewers").text

    # Twice: a 200-row table is several screens tall, and a pager only
    # at the top makes the operator scroll back to use it.
    assert body.count('<nav class="table-pager') == 2
    # One of the two carries the bottom modifier. Counted on the
    # rendered element: the bare class name also appears in the CSS
    # ``base.html`` ships on every page.
    assert body.count('<nav class="table-pager table-pager-bottom"') == 1

    # Real ranges, computed from the real roster — not placeholders.
    assert "1–200" in body
    assert "201–400" in body
    assert "401–556" in body


def test_the_pager_is_suppressed_while_a_filter_is_active(
    client: TestClient, db: Session
) -> None:
    """The operator's own partition of the roster wins; the count line
    speaks for that view instead."""
    review_session = _make_session(client, db, code="pager-filtered")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(
        # ``q`` is the search param; ``status`` the filter (the route's
        # own names — ``status_filter`` is aliased to ``status``).
        f"/operator/sessions/{review_session.id}/reviewers?q=Reviewer+01"
    ).text

    # ``table-pager`` alone would match the CSS in ``base.html``, which
    # ships on every page — assert on the rendered element.
    assert "<nav class=\"table-pager" not in body
    # …and the sentence is still there to say what the filter did.
    assert "table-showing-hint" in body


def test_a_roster_that_fits_one_page_gets_no_pager(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pager-small")
    _import_reviewers(client, review_session.id, 12)

    body = client.get(f"/operator/sessions/{review_session.id}/reviewers").text
    assert "<nav class=\"table-pager" not in body


def test_the_setup_pager_links_navigate(client: TestClient, db: Session) -> None:
    """Rung 2. The assertion this replaces read ``"offset=" not in
    body`` — a scaffold test doing its job and then expiring on
    schedule."""
    review_session = _make_session(client, db, code="pager-live")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(f"/operator/sessions/{review_session.id}/reviewers").text
    base = f"/operator/sessions/{review_session.id}/reviewers?offset="
    assert f'href="{base}200"' in body
    assert f'href="{base}400"' in body
    # The page you are on is a marker, not a link back to itself.
    assert 'aria-current="page"' in body


def test_a_row_past_the_first_page_is_reachable(
    client: TestClient, db: Session
) -> None:
    """The item's whole reason for existing: before 19J.5 row 401 of
    556 could not be seen without searching for it."""
    review_session = _make_session(client, db, code="pager-reach")
    _import_reviewers(client, review_session.id, 556)

    first = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    last = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?offset=400"
    ).text

    assert "Reviewer 0555" not in _table(first)
    assert "Reviewer 0555" in _table(last)
    assert "Reviewer 0000" not in _table(last)


def test_an_out_of_range_offset_clamps_rather_than_erroring(
    client: TestClient, db: Session
) -> None:
    """A link that was valid before someone deleted forty rows should
    land on the last page, not on an error."""
    review_session = _make_session(client, db, code="pager-clamp")
    _import_reviewers(client, review_session.id, 556)

    past_end = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?offset=99999"
    )
    assert past_end.status_code == 200
    assert "Reviewer 0555" in _table(past_end.text)

    negative = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?offset=-50"
    )
    assert negative.status_code == 200
    assert "Reviewer 0000" in _table(negative.text)


def test_an_offset_mid_page_snaps_to_its_boundary(
    client: TestClient, db: Session
) -> None:
    """Otherwise two different offsets render overlapping windows and
    the range labels stop describing what is on screen."""
    review_session = _make_session(client, db, code="pager-snap")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?offset=250"
    ).text
    table = _table(body)
    assert "Reviewer 0200" in table
    assert "Reviewer 0399" in table
    assert "Reviewer 0400" not in table


def test_the_pager_carries_no_selection_across_a_page(
    client: TestClient, db: Session
) -> None:
    """Selection is page-local. Carrying a hidden one across a page
    boundary is how an operator deletes something they cannot see."""
    review_session = _make_session(client, db, code="pager-select")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?selected=1&selected=2"
    ).text
    strip_start = body.index('<nav class="table-pager')
    strip = body[strip_start : body.index("</nav>", strip_start)]
    assert "selected=" not in strip


def test_the_pages_still_waiting_for_their_rung_stay_inert(
    client: TestClient, db: Session
) -> None:
    """Assignments, Invitations and Responses keep the scaffold until
    rungs 3 and 4. Their strips render and go nowhere — and because
    they are not paged, they also keep the withheld notice that the
    Setup pages have now dropped."""
    review_session = _make_session(client, db, code="pager-unwired")
    _import_reviewers(client, review_session.id, 12)

    for page in ("invitations", "responses", "assignments"):
        body = client.get(
            f"/operator/sessions/{review_session.id}/{page}"
        ).text
        assert f"{page}?offset=" not in body, page


def test_editing_a_row_lands_on_the_page_that_holds_it(
    client: TestClient, db: Session
) -> None:
    """Before 19J.5 a row being edited from outside the cap was
    prepended to whatever page the operator was on, because there was
    nowhere else to put it. On a paged view there now is — and landing
    there keeps the pager honest about where they are."""
    from sqlalchemy import select

    from app.db.models import Reviewer

    review_session = _make_session(client, db, code="pager-edit")
    _import_reviewers(client, review_session.id, 556)

    # A row on the third page (index 500 of the id-ordered roster).
    target = db.execute(
        select(Reviewer)
        .where(Reviewer.session_id == review_session.id)
        .order_by(Reviewer.id)
    ).scalars().all()[500]

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={target.id}"
    ).text

    table = _table(body)
    # Landed on its page, not page 1 with the row bolted to the top.
    assert "Reviewer 0500" in table
    assert "Reviewer 0000" not in table
    # And the strip says so.
    assert 'aria-current="page">401–556' in body


def test_a_stale_edit_id_drops_edit_mode_rather_than_erroring(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pager-stale-edit")
    _import_reviewers(client, review_session.id, 556)

    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?edit_id=99999999"
    )
    assert response.status_code == 200
    assert "Reviewer 0000" in _table(response.text)
