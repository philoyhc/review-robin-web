"""Coverage for the Segment 16A PR 4 ``require_sys_admin_or_session_operator``
relaxation on the per-session Audit log CSV route.

The Admin Sessions Diagnostics table lets a sys-admin click any
session's Audit log button regardless of ``session_operators``
membership. The per-session route previously gated strictly on
``require_session_operator``; PR 4 swaps it to the unified
``require_sys_admin_or_session_operator`` dependency so sys-admins
bypass membership while everyone else continues to hit the
standard per-session check.

The Outbox tests moved to ``test_sys_admin_outbox_inline.py`` once
the per-session ``/operator/sessions/{id}/outbox`` route retired
and Outbox content moved inline onto the Admin page.
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


# --- Audit log CSV — gate relaxation (16A PR 4) ----------------------------


def test_session_creator_can_download_audit_log(
    db: Session,
    client: TestClient,
) -> None:
    """Baseline: the operator who created the session is automatically
    a session_operators member and reaches the audit-log CSV normally."""
    review_session = _make_session(client, db, code="audit-base")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


def test_non_member_plain_operator_cannot_download_audit_log(
    db: Session,
    client: TestClient,
    make_client,
    bob,
) -> None:
    """Bob is on the workspace operator allowlist but isn't a
    session_operators member of alice's session. He still gets a 403
    on the audit-log CSV (the standard per-session gate path)."""
    review_session = _make_session(client, db, code="audit-403")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_sys_admin_non_member_can_download_audit_log(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bob is a sys-admin (env var seeded BEFORE first sign-in) but
    isn't a session_operators member of alice's session. The
    require_sys_admin_or_session_operator gate lets him download."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-sa-200")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


def test_sys_admin_non_member_404s_on_missing_audit_log_session(
    db: Session,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even sys-admins get a 404 when the session_id doesn't exist."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    bob_client = make_client(bob)
    response = bob_client.get(
        "/operator/sessions/99999/export/audit_log.csv", follow_redirects=False
    )
    assert response.status_code == 404
