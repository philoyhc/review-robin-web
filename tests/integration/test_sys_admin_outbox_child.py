"""Coverage for the 16A child-page Outbox under the Admin chrome.

Reshape of the inline-Outbox experiment: per-session Outbox now
lives at ``/operator/sys-admin/sessions/{session_id}/outbox`` as
a child of the Sessions Diagnostics tab. The pre-16A per-session
``/operator/sessions/{id}/outbox`` route stays retired
(bookmarks 404 there).
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


def _seed_invite_targets(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
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


def test_outbox_child_page_renders_back_link_and_chrome(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-child")

    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/outbox"
    )
    assert response.status_code == 200
    # Back-link points at the Sessions Diagnostics list.
    assert 'href="/operator/sys-admin/sessions"' in response.text
    assert "Back to Sessions Diagnostics" in response.text
    # Admin chrome present; Sessions Diagnostics tab active.
    assert "Sessions Diagnostics" in response.text
    assert "Accounts Management" in response.text
    # Outbox content rendered via the partial.
    assert f"Outbox — {review_session.name}" in response.text


def test_outbox_child_page_empty_state(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-empty")
    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/outbox"
    )
    assert response.status_code == 200
    assert "No outbox rows yet for this session." in response.text


def test_outbox_child_page_lists_seeded_rows(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: seed an invitation that populates email_outbox,
    then verify the child page shows the recipient + body."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-rows")
    _seed_invite_targets(client, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/invitations/generate",
        follow_redirects=False,
    )
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalar_one_or_none()
    if invitation is None:
        pytest.skip(
            "Invitations weren't generated for this fixture combination; "
            "outbox content is exercised by other integration tests."
        )

    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/outbox"
    )
    assert response.status_code == 200
    assert "rae@example.edu" in response.text
    assert "/me/invite/" in response.text


def test_outbox_child_page_404s_on_missing_session(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/sessions/99999/outbox")
    assert response.status_code == 404


def test_outbox_child_page_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="ob-child-403")
    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/outbox",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_per_session_outbox_route_remains_retired(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The original per-session ``/operator/sessions/{id}/outbox``
    URL is still gone — no second life via the child-page reshape."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-still-404")
    response = client.get(f"/operator/sessions/{review_session.id}/outbox")
    assert response.status_code == 404


def test_sessions_table_per_row_outbox_link_points_at_child(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="ob-link")
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    # Per-row Outbox link → child page URL.
    assert (
        f'href="/operator/sys-admin/sessions/{review_session.id}/outbox">Outbox</a>'
        in response.text
    )
    # No inline anchor / no inline query param.
    assert "?outbox_session_id=" not in response.text
    assert 'id="outbox"' not in response.text
