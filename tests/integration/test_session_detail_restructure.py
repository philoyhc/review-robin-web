"""Tests for the Segment 9.4B session-detail restructure.

Covers:
- Setup-row view helper output.
- Four-card layout on ``GET /operator/sessions/{id}``.
- Inline validate-summary card via ``?validated=1``.
- ``/validate`` page activate-form removed.
- ``POST /delete-data`` wipes responses, preserves setup, audits, and is
  allowed in ``ready``.
- Edit-lock visibility on the Session card and Danger zone.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Reviewee,
    Reviewer,
    Response,
    ReviewSession,
)
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str = "restruct-test"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair(
    client: TestClient, db: Session, *, code: str, reviewer_email: str
) -> ReviewSession:
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    return review_session


def _activate(client: TestClient, db: Session, review_session: ReviewSession) -> None:
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    response = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(review_session)


# ---------------------------------------------------------------------------
# Slice 1 — view helper + four-card render
# ---------------------------------------------------------------------------


def test_build_setup_rows_returns_expected_shape(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="rows", reviewer_email="r@example.edu"
    )

    rows = views.build_setup_rows(db, review_session)
    by_label = {r.label: r for r in rows}

    assert list(by_label.keys()) == [
        "Reviewers",
        "Reviewees",
        "Instruments",
        "Assignments",
        "Set up invites",
    ]
    assert by_label["Reviewers"].value == "1"
    assert by_label["Reviewers"].manage_url.endswith("/reviewers")
    assert by_label["Reviewers"].manage_disabled is False
    assert by_label["Instruments"].manage_disabled is False
    assert by_label["Instruments"].manage_url.endswith("/instruments")
    assert by_label["Set up invites"].manage_disabled is False
    assert by_label["Set up invites"].manage_url.endswith("/setupinvite")
    assert by_label["Assignments"].value == "1"


def test_session_detail_renders_four_cards(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="four-cards")

    response = client.get(f"/operator/sessions/{review_session.id}")
    body = response.text

    assert response.status_code == 200
    assert "<h2>Session</h2>" in body
    assert "<h2>Session setup</h2>" in body
    assert "<h2>Run Session</h2>" in body
    assert "Danger zone" in body  # heading uses inline color, not exact match
    assert 'id="danger-zone"' in body
    # Legacy ad-hoc layout markers are gone:
    assert "Run setup validation" not in body
    assert "Validate &amp; activate" not in body
    assert "Validate & activate" not in body


def test_setup_table_renders_manage_links(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="disabled-manage")

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # All five Manage buttons are real anchors after 9.4C
    assert (
        f'href="/operator/sessions/{review_session.id}/reviewers"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/reviewees"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/assignments"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/instruments"' in body
    )
    assert (
        f'href="/operator/sessions/{review_session.id}/setupinvite"' in body
    )


# ---------------------------------------------------------------------------
# Slice 2 — inline validate-summary via ?validated=1
# ---------------------------------------------------------------------------


def test_session_detail_no_validate_summary_by_default(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="no-summary")
    body = client.get(f"/operator/sessions/{review_session.id}").text
    assert 'id="validation-summary"' not in body
    assert "Validation summary" not in body


def test_session_detail_renders_validate_summary_with_query(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="with-summary", reviewer_email="r@example.edu"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}?validated=1"
    ).text

    assert 'id="validation-summary"' in body
    assert "Validation summary" in body
    # Counts pills present
    assert "0 errors" in body
    # View detailed validation button targets /validate
    assert (
        f'href="/operator/sessions/{review_session.id}/validate"' in body
    )
    # Activate form is on the card when can_activate
    assert (
        f'action="/operator/sessions/{review_session.id}/activate"' in body
    )


def test_validate_summary_lost_on_refresh_without_query(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="lose-summary", reviewer_email="r@example.edu"
    )
    with_query = client.get(
        f"/operator/sessions/{review_session.id}?validated=1"
    ).text
    assert "Validation summary" in with_query

    without_query = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert "Validation summary" not in without_query


def test_validate_page_activate_form_removed(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="no-activate-form", reviewer_email="r@example.edu"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/validate"
    ).text
    assert (
        f'action="/operator/sessions/{review_session.id}/activate"'
        not in body
    )
    # Page still renders counts + validation results
    assert "0 errors" in body
    # The Activate hint about the inline summary card is present
    assert "inline summary card" in body


# ---------------------------------------------------------------------------
# Slice 3 — Delete Data
# ---------------------------------------------------------------------------


def _seed_responses(client: TestClient, db: Session) -> tuple[ReviewSession, int]:
    """Activate the seeded session and have the reviewer save a draft.

    Returns ``(review_session, response_count)``.
    """
    review_session = _seed_pair(
        client, db, code="del-data", reviewer_email="rae@example.edu"
    )
    _activate(client, db, review_session)

    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae",
        provider="aad",
    )

    from app.auth.identity import get_current_user
    from app.db.session import get_db
    from app.main import app

    def override_user() -> AuthenticatedUser:
        return rae

    def override_db():
        yield db

    # Swap in the reviewer's identity for the save call only.
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        rae_client = TestClient(app)
        assignment = db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalar_one()
        response = rae_client.post(
            f"/reviewer/sessions/{review_session.id}/save",
            data={
                f"response[{assignment.id}][rating]": "4",
                f"response[{assignment.id}][comments]": "ok",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    finally:
        # Restore the operator override so the rest of the test sees alice.
        app.dependency_overrides.clear()

    response_count = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    return review_session, len(response_count)


def test_delete_data_wipes_responses_and_preserves_setup(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, count_before = _seed_responses(operator, db)
    assert count_before > 0

    # Re-arm the operator client after _seed_responses cleared overrides.
    operator = make_client(alice)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Responses gone for this session
    remaining = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    assert remaining == []

    # Setup intact
    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == review_session.id)
        ).first()
        is not None
    )
    assert (
        db.execute(
            select(Reviewee).where(Reviewee.session_id == review_session.id)
        ).first()
        is not None
    )
    assert (
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).first()
        is not None
    )

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.deleted_all")
    ).scalar_one()
    assert audit.detail == {"deleted_count": count_before}
    assert audit.session_id == review_session.id


def test_delete_data_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="confirm-req", reviewer_email="r@example.edu"
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 400

    # No audit event written
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "responses.deleted_all"
        )
    ).all()
    assert rows == []


def test_delete_data_allowed_in_ready_status(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session, count_before = _seed_responses(operator, db)
    db.refresh(review_session)
    assert review_session.status == "ready"

    operator = make_client(alice)
    response = operator.post(
        f"/operator/sessions/{review_session.id}/delete-data",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "responses.deleted_all")
    ).scalar_one()
    assert audit.detail == {"deleted_count": count_before}


# ---------------------------------------------------------------------------
# Edit-lock visibility on Session card / Danger zone
# ---------------------------------------------------------------------------


def test_session_card_buttons_when_draft(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="draft-buttons")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Edit details button shown
    assert (
        f'href="/operator/sessions/{review_session.id}/edit">Edit details'
        in body
    )
    # Revert to draft form NOT present
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"' not in body
    )
    # Delete Data form present
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"' in body
    )
    # Delete Session form present (not locked)
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"' in body
    )


def test_session_card_buttons_when_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair(
        client, db, code="ready-buttons", reviewer_email="r@example.edu"
    )
    _activate(client, db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}").text

    # Edit details button hidden
    assert (
        f'href="/operator/sessions/{review_session.id}/edit">Edit details'
        not in body
    )
    # Revert to draft form present
    assert (
        f'action="/operator/sessions/{review_session.id}/revert"' in body
    )
    # Delete Data form still present (allowed in ready)
    assert (
        f'action="/operator/sessions/{review_session.id}/delete-data"' in body
    )
    # Delete Session form ABSENT (locked while ready)
    assert (
        f'action="/operator/sessions/{review_session.id}/delete"' not in body
        or 'Delete session' not in body  # belt-and-suspenders
    )
    assert "Session deletion is locked while status is" in body
