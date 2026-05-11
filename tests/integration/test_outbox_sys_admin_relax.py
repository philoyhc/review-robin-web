"""Coverage for the audit-log CSV route gate.

Pre-16C: the route was gated by
``require_sys_admin_or_session_operator`` so a session creator
(automatically a ``session_operators`` member) could download the
CSV directly. 16C PR 1 retires that affordance — the only entry
point now is the Sys Admin → Sessions Diagnostics → Audit log
child page, which itself owns a Download CSV button. The CSV
route therefore tightens to ``require_sys_admin``; session
operators who aren't sys-admins now 403.

The companion Outbox tests moved to
``test_sys_admin_outbox_inline.py`` once the per-session
``/operator/sessions/{id}/outbox`` route retired and Outbox
content moved to a child page under Sessions Diagnostics.
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


# --- Audit log CSV — gate tightened to require_sys_admin (16C PR 1) --------


def test_session_creator_cannot_download_audit_log_without_sys_admin(
    db: Session,
    client: TestClient,
) -> None:
    """Pre-16C, the session creator could download the CSV directly
    via the relaxed gate. Post-16C, the route requires sys-admin —
    plain operators (incl. the session creator) 403."""
    review_session = _make_session(client, db, code="audit-403-creator")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_non_member_plain_operator_cannot_download_audit_log(
    db: Session,
    client: TestClient,
    make_client,
    bob,
) -> None:
    """Bob is on the workspace operator allowlist but isn't a
    session_operators member of alice's session. He still 403s —
    the gate is now sys-admin-only."""
    review_session = _make_session(client, db, code="audit-403")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_sys_admin_can_download_audit_log(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sys-admin reaches the CSV regardless of session_operators
    membership. The route now keys on is_sys_admin only."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-sa-200")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")


def test_sys_admin_404s_on_missing_audit_log_session(
    db: Session,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even sys-admins get a 404 when the session_id doesn't exist."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    bob_client = make_client(bob)
    response = bob_client.get(
        "/operator/sessions/99999/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 404
