"""Integration tests for GET /operator/sessions/{id}/preview (Segment 10B-3)."""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid",
        email="r@example.edu",
        name="R Reviewer",
        provider="aad",
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


def _populate_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _generate_full_matrix(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )


def _activate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")
    client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )


def test_preview_renders_banner_in_draft_status(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-draft")

    response = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    )

    assert response.status_code == 200
    body = response.text
    assert "Preview" in body
    assert "not visible to reviewers" in body
    assert f"<h1>{review_session.name}</h1>" in body


def test_preview_works_in_validated_and_ready_status(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-states")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    # validated state
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    db.refresh(review_session)
    assert review_session.status == "validated"
    response = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    )
    assert response.status_code == 200
    assert "not visible to reviewers" in response.text

    # ready state
    _activate(client, db, review_session.id)
    db.refresh(review_session)
    assert review_session.status == "ready"

    response = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    )
    assert response.status_code == 200
    assert "not visible to reviewers" in response.text

    # Preview is read-only: no instrument.opened audit event is emitted
    # by the GET (D9 — read-only).
    opened_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.opened",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    # The activate call may emit instrument.opened; what we want to assert
    # is that the preview GET itself doesn't emit one. Snapshot count
    # before + after.
    before = len(opened_events)
    client.get(f"/operator/sessions/{review_session.id}/preview")
    after = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.opened",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(after) == before


def test_preview_returns_403_for_non_operator(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="prev-403")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)

    # rae is an active reviewer in the session — but not an operator
    other_client = make_client(reviewer_user)
    response = other_client.get(
        f"/operator/sessions/{review_session.id}/preview"
    )
    assert response.status_code == 403


def test_preview_body_has_no_reviewer_write_path_forms(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-forms")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _activate(client, db, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text

    # No reviewer write-path action attributes should appear in preview.
    assert (
        f'action="/reviewer/sessions/{review_session.id}/save"' not in body
    )
    assert (
        f'action="/reviewer/sessions/{review_session.id}/submit"' not in body
    )
    assert (
        f'action="/reviewer/sessions/{review_session.id}/clear"' not in body
    )
    # And no formaction= overrides on Submit buttons.
    assert "formaction=" not in body


def test_preview_inputs_render_disabled(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="prev-disabled")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    ).text

    # Every input / textarea / select-tagged element should carry
    # the disabled attribute. Use a permissive regex that matches the
    # opening tag and asserts disabled appears before the closing >.
    pattern = re.compile(
        r"<(input|textarea|select)\b([^>]*)>", re.IGNORECASE | re.DOTALL
    )
    for match in pattern.finditer(body):
        opening_attrs = match.group(2)
        assert (
            re.search(r"\bdisabled\b", opening_attrs) is not None
        ), f"input-like tag missing disabled: {match.group(0)!r}"


def test_preview_does_not_observe_deadline_side_effect(
    client: TestClient, db: Session
) -> None:
    """Bypassing deadline observation per D9 means an expired deadline
    does NOT trigger the lazy-close path on a preview GET."""
    from datetime import datetime, timedelta, timezone

    review_session = _make_session(client, db, code="prev-deadline")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)
    _activate(client, db, review_session.id)
    db.refresh(review_session)

    # Set a deadline in the past after activation
    review_session.deadline = datetime.now(timezone.utc) - timedelta(hours=1)
    db.flush()

    response = client.get(
        f"/operator/sessions/{review_session.id}/preview"
    )
    assert response.status_code == 200

    # No deadline-driven instrument.closed event should be written by
    # the preview GET.
    deadline_close = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.closed",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    for ev in deadline_close:
        # Any lazy-close events should not reference the preview path.
        assert ev.detail.get("reason") != "deadline"


def test_reviewer_side_surface_still_renders_write_path(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Regression guard for Slice 3's {% if not preview_mode %} wrappers —
    the reviewer's normal /reviewer/sessions/{id} surface must still
    render Save / Submit / Cancel / Clear (and no preview banner)."""
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="rev-regress")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, review_session.id)
    _activate(operator, db, review_session.id)

    reviewer_client = make_client(reviewer_user)
    body = reviewer_client.get(
        f"/reviewer/sessions/{review_session.id}"
    ).text

    assert "Preview — not visible to reviewers" not in body
    assert "Save draft" in body
    assert (
        f'formaction="/reviewer/sessions/{review_session.id}/submit"' in body
    )
    assert "Cancel — discard unsaved edits" in body
    assert (
        f'action="/reviewer/sessions/{review_session.id}/save"' in body
    )


def test_preview_anchor_rendered_on_session_detail(
    client: TestClient, db: Session
) -> None:
    """The See previews secondary button renders in the Next action
    card's button row once the session is validated. Per
    spec/session_home.md, draft and ready states intentionally omit
    the See previews button (nothing meaningful to preview in
    draft; operators monitor live responses, not previews, while
    Activated)."""

    review_session = _make_session(client, db, code="prev-anchor-detail")
    _populate_rosters(client, review_session.id)
    _generate_full_matrix(client, review_session.id)

    body = client.get(
        f"/operator/sessions/{review_session.id}?validated=1"
    ).text

    assert (
        f'href="/operator/sessions/{review_session.id}/preview"' in body
    )
    assert ">See previews</a>" in body
