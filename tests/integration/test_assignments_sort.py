"""Cookie-backed sort on the Operations Assignments table —
Segment 13B Part 2 PR 8.

Pins the table marker + per-row scaffolding + cookie-driven SSR
order on ``/operator/sessions/{id}/assignments``.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


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


def _populate_full_matrix(
    client: TestClient, db: Session, session_id: int
) -> None:
    """Three reviewers × three reviewees → 9 (or 6 with self-review
    excluded) assignments. Names are deliberately non-alphabetical
    so a sort actually reshuffles."""
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Bravo R,bravo@example.edu\n"
                    b"Alpha R,alpha@example.edu\n"
                    b"Charlie R,charlie@example.edu\n"
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
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Bravo E,bravoe@example.edu\n"
                    b"Alpha E,alphae@example.edu\n"
                    b"Charlie E,charliee@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def test_assignments_table_renders_sort_scaffolding(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="asn-scaff")
    _populate_full_matrix(client, db, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    )
    assert response.status_code == 200
    body = response.text
    # Table marker + tbody wrapper.
    assert (
        f'data-rrw-sortable="rrw-sort-assignments-{review_session.id}"'
        in body
    )
    assert '<tbody class="rrw-rows">' in body
    # Every sortable header carries its data-sort-key. The tag
    # columns are conditional since 19I Item 12 rung 3 — a slot with
    # no data anywhere renders no column, so no header and no sort
    # key — and this seed imports no tags at all.
    for key in ("reviewer", "reviewee", "include", "instrument"):
        assert f'data-sort-key="{key}"' in body
    for key in ("reviewer_tag_1", "reviewee_tag_1", "pair_tag_1"):
        assert f'data-sort-key="{key}"' not in body
    # Each <td> carries a data-sort-value mirroring the rendered
    # value.
    assert 'data-sort-value="Alpha R"' in body
    assert 'data-sort-value="Charlie R"' in body


def test_a_populated_tag_column_carries_its_sort_key(
    db: Session, client: TestClient
) -> None:
    """The other side of the conditional above: give a tag slot data
    and its column, header and sort key all come back. Without this
    the test above would pass just as well if tag columns had been
    deleted outright."""
    review_session = _make_session(client, db, code="asn-scaff-tag")
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
                    b"Bravo R,bravo@example.edu,Team B\n"
                    b"Alpha R,alpha@example.edu,Team A\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Alpha E,alphae@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert 'data-sort-key="reviewer_tag_1"' in body
    assert 'data-col-toggle="rt1"' in body
    # The reviewee and pair-context slots are still empty.
    assert 'data-sort-key="reviewee_tag_1"' not in body
    assert 'data-sort-key="pair_tag_1"' not in body


def test_assignments_cookie_sort_by_reviewer_asc(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="asn-asc")
    _populate_full_matrix(client, db, review_session.id)
    cookie_name = f"rrw-sort-assignments-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewer", "dir": "asc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Reviewer column sorts on name — Alpha R, Bravo R, Charlie R
    # in row order.
    assert (
        _rows(body).find("Alpha R")
        < _rows(body).find("Bravo R")
        < _rows(body).find("Charlie R")
    )


def _rows(body: str) -> str:
    """The preview table only.

    These assertions compare where names appear in the document, and
    Segment 19I Item 9 added a `<datalist>` of `"Name (handle)"`
    labels that renders **before** the table and is sorted
    alphabetically. Against the whole body, `find()` returns the
    datalist hit: the descending test failed, and — worse — the
    ascending ones would have passed whatever order the table was in.
    Scoping to the table restores exactly what they were checking.
    """
    return body[body.index('<table id="assignments-table"'):]


def test_assignments_cookie_sort_by_reviewer_desc(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="asn-desc")
    _populate_full_matrix(client, db, review_session.id)
    cookie_name = f"rrw-sort-assignments-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([{"key": "reviewer", "dir": "desc"}]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    assert (
        _rows(body).find("Charlie R")
        < _rows(body).find("Bravo R")
        < _rows(body).find("Alpha R")
    )


def test_assignments_cookie_sort_by_reviewee(
    db: Session, client: TestClient
) -> None:
    """Cascade: reviewer asc primary, reviewee desc secondary —
    tie on reviewer falls through to reviewee desc."""
    review_session = _make_session(client, db, code="asn-cascade")
    _populate_full_matrix(client, db, review_session.id)
    cookie_name = f"rrw-sort-assignments-{review_session.id}"
    client.cookies.set(
        cookie_name,
        json.dumps([
            {"key": "reviewer", "dir": "asc"},
            {"key": "reviewee", "dir": "desc"},
        ]),
        path=f"/operator/sessions/{review_session.id}",
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    # Within Alpha R's rows (the first reviewer alphabetically),
    # reviewees sort desc: Charlie E before Alpha E.
    # (Self-review for Alpha R/Alpha E is excluded by the
    # ``exclude_self_review=true`` flag in _populate_full_matrix.)
    rows = _rows(body)
    alpha_r = rows.find("Alpha R")
    bravo_r = rows.find("Bravo R")
    # Look only inside Alpha R's row range for ordering check.
    alpha_segment = rows[alpha_r:bravo_r]
    assert alpha_segment.find("Charlie E") < alpha_segment.find("Bravo E")


def test_assignments_malformed_cookie_falls_back(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="asn-bad")
    _populate_full_matrix(client, db, review_session.id)
    cookie_name = f"rrw-sort-assignments-{review_session.id}"
    client.cookies.set(
        cookie_name,
        "not-json{",
        path=f"/operator/sessions/{review_session.id}",
    )
    response = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    )
    assert response.status_code == 200
    # Page renders; assertion that no sort badges appear is too
    # brittle (the JS hydration runs in browser but not in this
    # test). Just confirm no 500.
