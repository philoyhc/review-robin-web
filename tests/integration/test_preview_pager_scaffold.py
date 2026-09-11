"""The pager scaffold on the roster-bearing pages — Segment 19J.5 rung 1.

Rung 1 lands the surface, not the behaviour: the ranges are real and
the links go nowhere. These tests pin the three things that decide
whether the shape is right before anything is wired to it — that it
renders twice, that it is suppressed while a filter is active, and
that it stays away when there is nothing to page.

The inertness assertion is the one that expires: rung 2 wires the
Setup pages and this file changes with it. That is the intended
lifecycle of a scaffold test, not drift.
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


def test_rung_one_links_are_inert(client: TestClient, db: Session) -> None:
    """No ``?offset=`` anywhere yet: the scaffold is the shape, agreed
    before any wiring attaches to it."""
    review_session = _make_session(client, db, code="pager-inert")
    _import_reviewers(client, review_session.id, 556)

    body = client.get(f"/operator/sessions/{review_session.id}/reviewers").text
    assert "offset=" not in body
    assert 'class="table-pager-link" aria-disabled="true"' in body
