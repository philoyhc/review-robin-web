"""Coverage for the Segment 16A PR 3 ``require_sys_admin_or_session_operator``
relaxation on the per-session Outbox route.

The Admin Sessions Diagnostics table (16A PR 3) lets a sys-admin
click "View outbox" on any session in the workspace, including
sessions they aren't a ``session_operators`` member of. The
existing per-session ``GET /operator/sessions/{id}/outbox`` route
used to gate strictly on ``require_session_operator``; PR 3 swaps
it to the unified ``require_sys_admin_or_session_operator``
dependency so sys-admins bypass membership while everyone else
continues to hit the standard per-session check.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
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


def test_session_creator_can_view_their_outbox(
    db: Session,
    client: TestClient,
) -> None:
    """Baseline: the operator who created the session is automatically
    a session_operators member and reaches the outbox normally."""
    review_session = _make_session(client, db, code="outbox-base")
    response = client.get(f"/operator/sessions/{review_session.id}/outbox")
    assert response.status_code == 200


def test_non_member_plain_operator_cannot_view_outbox(
    db: Session,
    client: TestClient,
    make_client,
    bob,
) -> None:
    """Bob is on the workspace operator allowlist but isn't a
    session_operators member of alice's session. He still gets a 403
    on the outbox (the standard per-session gate path)."""
    review_session = _make_session(client, db, code="outbox-403")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/outbox",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_sys_admin_non_member_can_view_outbox(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bob is a sys-admin (env var seeded BEFORE first sign-in) but
    isn't a session_operators member of alice's session. The
    require_sys_admin_or_session_operator gate lets him through."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])

    review_session = _make_session(client, db, code="outbox-sa-200")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/outbox",
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_sys_admin_non_member_404s_on_missing_session(
    db: Session,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even sys-admins get a 404 when the session_id doesn't exist."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    bob_client = make_client(bob)
    response = bob_client.get(
        "/operator/sessions/99999/outbox", follow_redirects=False
    )
    assert response.status_code == 404
