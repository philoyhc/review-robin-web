"""Cookie-backed sort on Reviewers + Reviewees Setup tables —
Segment 13B Part 2 PR 6.

Pins:

- Each table renders the sort scaffolding (table marker +
  ``rrw-sortable`` class on sortable headers + per-row
  ``data-sort-value`` cells + ``tbody.rrw-rows`` wrapper).
- The route reads the per-(session, table) cookie and threads
  the decoded spec through ``views.apply_cookie_sort`` so the
  initial HTML lands sorted.
- Malformed cookies are silently dropped (insertion order).
- Stale keys (column the operator doesn't recognise anymore)
  are silently dropped.
"""
from __future__ import annotations

import json
from urllib.parse import quote

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_reviewers(client: TestClient, session_id: int) -> None:
    # Deliberately non-alphabetical insertion order so a sort
    # actually reshuffles.
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Bravo,bravo@example.edu\n"
                    b"Alpha,alpha@example.edu\n"
                    b"Charlie,charlie@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _populate_reviewees(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Bravo,bravo@example.edu\n"
                    b"Alpha,alpha@example.edu\n"
                    b"Charlie,charlie@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


# --- Reviewers --------------------------------------------------------------


def test_reviewers_table_renders_sort_scaffolding(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-scaff")
    _populate_reviewers(client, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    )
    assert response.status_code == 200
    body = response.text
    assert (
        f'data-rrw-sortable="rrw-sort-reviewers-{review_session.id}"'
        in body
    )
    assert '<tbody class="rrw-rows">' in body
    assert 'class="rrw-sortable" data-sort-key="name"' in body
    assert 'class="rrw-sortable" data-sort-key="email"' in body
    assert 'class="rrw-sortable" data-sort-key="status"' in body
    # Segment 15F follow-on — the right-end "Updated" timestamp
    # column is sortable so the operator can surface the
    # most-recently-added / edited rows.
    assert 'class="rrw-sortable" data-sort-key="updated_at"' in body
    assert ">Updated<" in body
    # Refinement (2026-05-12): the click target is a small
    # ``<button class="rrw-sort-btn">`` next to the header label
    # rather than the ``<th>`` itself. Default badge content is
    # ``↕`` so the operator sees the affordance even when the
    # column isn't sorted.
    assert 'class="rrw-sort-btn"' in body
    assert 'aria-label="Sort by Name"' in body
    assert '<span class="rrw-sort-badge">↕</span>' in body
    # Each <td> carries a data-sort-value mirroring the persisted
    # row value.
    assert 'data-sort-value="Alpha"' in body


def test_reviewers_updated_at_sort_surfaces_recent_row(
    db: Session, client: TestClient
) -> None:
    """The right-end ``updated_at`` column is sortable — a more
    recently touched row floats to the top under a desc sort. This
    is the column's reason for existing: surface the most recently
    added / edited rows without busting the 200-row cap."""
    from datetime import datetime

    from app.db.models import Reviewer

    review_session = _make_session(client, db, code="rev-upd-sort")
    _populate_reviewers(client, review_session.id)
    # Stamp Charlie with a far-future ``updated_at`` so the desc
    # sort is deterministic (SQLite ``func.now()`` only has
    # second granularity, too coarse for a real-time edit).
    charlie = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id,
            Reviewer.name == "Charlie",
        )
    ).scalar_one()
    charlie.updated_at = datetime(2099, 1, 1, 12, 0, 0)
    db.commit()

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "updated_at", "dir": "desc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body = body[body.find('id="reviewers-table"') :]
    assert body.find("Charlie") < body.find("Bravo")
    assert body.find("Charlie") < body.find("Alpha")


def test_reviewers_cookie_drives_ssr_initial_order(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-cookie-asc")
    _populate_reviewers(client, review_session.id)

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "name", "dir": "asc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Slice from the table marker so the Segment 15F search-autocomplete
    # `<datalist>` options above the table don't interfere.
    body = body[body.find('id="reviewers-table"') :]
    # Alphabetical ascending.
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


def test_reviewers_cookie_desc_order(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-cookie-desc")
    _populate_reviewers(client, review_session.id)

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "name", "dir": "desc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body = body[body.find('id="reviewers-table"') :]
    assert body.find("Charlie") < body.find("Bravo") < body.find("Alpha")


def test_reviewers_percent_encoded_cookie_drives_ssr_order(
    db: Session, client: TestClient
) -> None:
    """The browser primitive writes the sort cookie percent-encoded
    (``encodeURIComponent``); Starlette doesn't percent-decode
    cookie values, so the SSR decoder must ``unquote`` before
    parsing. Without it the server silently falls back to insertion
    order while the JS badge still shows the column sorted."""
    review_session = _make_session(client, db, code="rev-cookie-enc")
    _populate_reviewers(client, review_session.id)

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        quote(json.dumps([{"key": "name", "dir": "asc"}])),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body = body[body.find('id="reviewers-table"') :]
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


def test_reviewers_malformed_cookie_falls_back_to_insertion_order(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-cookie-bad")
    _populate_reviewers(client, review_session.id)

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        "not-json{",
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body = body[body.find('id="reviewers-table"') :]
    # Insertion order: Bravo, Alpha, Charlie.
    assert body.find("Bravo") < body.find("Alpha") < body.find("Charlie")


def test_reviewers_stale_cookie_key_dropped(
    db: Session, client: TestClient
) -> None:
    """A cookie referencing a column the route doesn't recognise
    (e.g. an old ``tag_5``) is silently dropped — the rest of the
    spec still applies."""
    review_session = _make_session(client, db, code="rev-cookie-stale")
    _populate_reviewers(client, review_session.id)

    cookie_name = f"rrw-sort-reviewers-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([
            {"key": "tag_5", "dir": "asc"},
            {"key": "name", "dir": "asc"},
        ]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    body = body[body.find('id="reviewers-table"') :]
    # tag_5 drops; name asc still applies.
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


# --- Reviewees --------------------------------------------------------------


def test_reviewees_table_renders_sort_scaffolding(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ree-scaff")
    _populate_reviewees(client, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    )
    assert response.status_code == 200
    body = response.text
    assert (
        f'data-rrw-sortable="rrw-sort-reviewees-{review_session.id}"'
        in body
    )
    assert '<tbody class="rrw-rows">' in body
    assert 'class="rrw-sortable" data-sort-key="name"' in body
    assert 'class="rrw-sortable" data-sort-key="email_or_identifier"' in body
    assert 'data-sort-value="Alpha"' in body


def test_reviewees_cookie_drives_ssr_initial_order(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="ree-cookie-asc")
    _populate_reviewees(client, review_session.id)

    cookie_name = f"rrw-sort-reviewees-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "name", "dir": "asc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewees"
    ).text
    assert body.find("Alpha") < body.find("Bravo") < body.find("Charlie")


# --- Relationships ---------------------------------------------------------


def _populate_relationships(
    client: TestClient, session_id: int
) -> None:
    """Three reviewers paired with one reviewee via the
    Relationships CSV. Insertion order is Bravo / Alpha / Charlie
    so a name sort actually reshuffles."""
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"B Rev,bravo@example.edu\n"
                    b"A Rev,alpha@example.edu\n"
                    b"C Rev,charlie@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nM,m@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail\n"
                    b"bravo@example.edu,m@example.edu\n"
                    b"alpha@example.edu,m@example.edu\n"
                    b"charlie@example.edu,m@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def test_relationships_table_renders_sort_scaffolding(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-scaff")
    _populate_relationships(client, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert (
        f'data-rrw-sortable="rrw-sort-relationships-{review_session.id}"'
        in body
    )
    assert '<tbody class="rrw-rows">' in body
    assert 'class="rrw-sortable" data-sort-key="reviewer"' in body
    assert 'class="rrw-sortable" data-sort-key="reviewee"' in body
    # Segment 15F PR 5 stage 2 — the reviewer / reviewee cells sort
    # on the rendered name, not the email.
    assert 'data-sort-value="A Rev"' in body


def test_relationships_cookie_sort_by_reviewer_asc(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-by-rev")
    _populate_relationships(client, review_session.id)

    cookie_name = f"rrw-sort-relationships-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewer", "dir": "asc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    body = body[body.find('id="relationships-table"') :]
    # Reviewer column sorts on email — alphabetical: alpha,
    # bravo, charlie.
    assert (
        body.find("alpha@example.edu")
        < body.find("bravo@example.edu")
        < body.find("charlie@example.edu")
    )


def test_relationships_cookie_sort_desc(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-desc")
    _populate_relationships(client, review_session.id)

    cookie_name = f"rrw-sort-relationships-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewer", "dir": "desc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    body = body[body.find('id="relationships-table"') :]
    assert (
        body.find("charlie@example.edu")
        < body.find("bravo@example.edu")
        < body.find("alpha@example.edu")
    )


def test_relationships_stale_cookie_key_dropped(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rel-stale")
    _populate_relationships(client, review_session.id)

    cookie_name = f"rrw-sort-relationships-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([
            {"key": "not_a_column", "dir": "asc"},
            {"key": "reviewer", "dir": "asc"},
        ]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    body = body[body.find('id="relationships-table"') :]
    assert (
        body.find("alpha@example.edu")
        < body.find("bravo@example.edu")
        < body.find("charlie@example.edu")
    )
