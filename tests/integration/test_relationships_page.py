"""Integration coverage for the Relationships Setup page
(Segment 15D PR 2).

Pins the page surface, the upload + delete-all routes, and the
chrome integration (nav tab + status pill + Setup card row).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RelPage", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    db.commit()
    return review_session


def _seed_rosters(
    client: TestClient, session_id: int
) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Bob,bob@example.edu\n"
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
                    b"Carol,carol@example.edu\n"
                    b"Dan,dan@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def test_get_relationships_page_renders(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-render")
    response = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    )
    assert response.status_code == 200
    body = response.text
    assert "Upload Relationships" in body
    assert 'id="upload-csv"' in body
    assert "ReviewerEmail" in body
    assert "RevieweeEmail" in body
    assert "PairContextTag1" in body


def test_chrome_nav_includes_relationships_tab(
    client: TestClient, db: Session
) -> None:
    """Setup row reads Reviewers · Reviewees · Relationships ·
    Assignments · Instruments · Email Template (interim until
    PR 6 moves Assignments to Operations)."""

    review_session = _make_session(client, db, code="rel-nav")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/relationships">'
        "Relationships</a>"
    ) in body
    # Tab order: Relationships sits between Reviewees and Assignments.
    reviewees_idx = body.find(">Reviewees</a>")
    relationships_idx = body.find(">Relationships</a>")
    assignments_idx = body.find(">Assignments</a>")
    assert 0 < reviewees_idx < relationships_idx < assignments_idx


def test_relationships_page_marks_active_tab(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-active")
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    # The chrome partial breaks the anchor across two lines (class on
    # one, href on the next). Search by the `nav-tab active` class
    # then confirm the href matches the Relationships URL within the
    # same anchor.
    target = f'href="/operator/sessions/{review_session.id}/relationships"'
    # The active class precedes the href in the rendered markup.
    cut = body.find(target)
    assert cut > 0, "Relationships href not found in chrome"
    preceding = body[max(0, cut - 200):cut]
    assert "nav-tab active" in preceding


def test_status_pill_shows_count(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-pill")
    _seed_rosters(client, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    )
    assert response.status_code == 200
    body = response.text
    # Empty state shows "none" beside the Relationships pill.
    assert "Relationships:" in body
    assert "none" in body.split("Relationships:", 1)[1][:200]

    # After upload, the pill shows the count.
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
                    b"alice@example.edu,carol@example.edu,Mentor\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    after_pill = body.split("Relationships:", 1)[1][:200]
    assert 'class="pill pill-info">1</span>' in after_pill


def test_post_import_inserts_rows_and_redirects(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-upload")
    _seed_rosters(client, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag1,Status\n"
                    b"alice@example.edu,carol@example.edu,Mentor,active\n"
                    b"bob@example.edu,dan@example.edu,COI,inactive\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"].endswith(
        f"/operator/sessions/{review_session.id}/relationships"
    )

    rows = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    assert len(rows) == 2
    by_status = {r.status for r in rows}
    assert by_status == {"active", "inactive"}


def test_post_import_invalid_csv_returns_400(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-bad")
    _seed_rosters(client, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail\n"
                    b"ghost@example.edu,carol@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text
    assert "Unknown reviewer" in body or "ghost@example.edu" in body


def test_post_import_replace_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-confirm")
    _seed_rosters(client, review_session.id)
    # First upload populates the table.
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                b"ReviewerEmail,RevieweeEmail\nalice@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    # Second upload without confirm_replace 400s.
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                b"ReviewerEmail,RevieweeEmail\nbob@example.edu,dan@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    rows_after = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    # Original row preserved.
    assert len(rows_after) == 1

    # With confirm_replace, the upload succeeds.
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        data={"confirm_replace": "true"},
        files={
            "file": (
                "rel.csv",
                b"ReviewerEmail,RevieweeEmail\nbob@example.edu,dan@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_delete_all_wipes_table(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-delete")
    _seed_rosters(client, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                b"ReviewerEmail,RevieweeEmail\nalice@example.edu,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows_after = db.execute(
        select(Relationship).where(
            Relationship.session_id == review_session.id
        )
    ).scalars().all()
    assert rows_after == []


def test_delete_all_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-delete-noconfirm")
    response = client.post(
        f"/operator/sessions/{review_session.id}/relationships/delete-all",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_preview_table_renders_resolved_emails(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rel-preview")
    _seed_rosters(client, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
                    b"alice@example.edu,carol@example.edu,Mentor\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    ).text
    assert "alice@example.edu" in body
    assert "carol@example.edu" in body
    assert "Mentor" in body
    assert 'id="relationships-table"' in body
