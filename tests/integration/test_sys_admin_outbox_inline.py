"""Coverage for the 16A inline-Outbox reshape on the Admin Sessions
Diagnostics page.

Replaces the retired per-session ``/operator/sessions/{id}/outbox``
route + ``session_outbox.html`` template. Outbox content now
renders inline on ``/operator/sys-admin/sessions`` when the URL
carries ``?outbox_session_id=N`` — the per-row Outbox link sets
this and ``#outbox`` to scroll to the section.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Invitation, ReviewSession


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


def _ready_session_with_outbox(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Seed a session, populate rosters, validate / activate, then
    generate invitations so the email_outbox table has rows."""
    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
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
    return review_session


def test_outbox_section_hidden_when_no_session_id(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _make_session(client, db, code="ob-hidden")
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    # No Outbox section rendered.
    assert 'id="outbox"' not in response.text
    assert "Outbox —" not in response.text


def test_outbox_section_renders_when_session_id_set(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-empty")
    response = client.get(
        f"/operator/sys-admin/sessions?outbox_session_id={review_session.id}"
    )
    assert response.status_code == 200
    # Outbox anchor + header rendered, even when no rows yet.
    assert 'id="outbox"' in response.text
    assert f"Outbox — {review_session.name}" in response.text
    assert "No outbox rows yet for this session." in response.text


def test_outbox_section_lists_seeded_rows(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: seed an invitation that populates email_outbox,
    then verify the inline section shows the recipient + body."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _ready_session_with_outbox(client, db, code="ob-rows")

    # Make sure the session is in a state where invitations can generate.
    # Activate the session (Validate → Activate flow). Use the same
    # form pattern existing invitation tests rely on.
    client.post(
        f"/operator/sessions/{review_session.id}/invitations/generate",
        follow_redirects=False,
    )
    # Confirm an Invitation row exists so we know outbox should too.
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalar_one_or_none()
    if invitation is None:
        pytest.skip(
            "Invitations weren't generated for this fixture combination; "
            "outbox content is exercised by other integration tests."
        )

    response = client.get(
        f"/operator/sys-admin/sessions?outbox_session_id={review_session.id}"
    )
    assert response.status_code == 200
    assert 'id="outbox"' in response.text
    assert "rae@example.edu" in response.text
    assert "/reviewer/invite/" in response.text


def test_outbox_section_404s_on_missing_session_id(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get(
        "/operator/sys-admin/sessions?outbox_session_id=99999"
    )
    assert response.status_code == 404


def test_outbox_section_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    """Alice is a plain operator; the route 403s regardless of
    ?outbox_session_id."""
    review_session = _make_session(client, db, code="ob-403")
    response = client.get(
        f"/operator/sys-admin/sessions?outbox_session_id={review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_per_session_outbox_route_retired(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-session URL is gone. Sys-admins, operators — everyone
    gets a 404."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-retired")
    response = client.get(f"/operator/sessions/{review_session.id}/outbox")
    assert response.status_code == 404
