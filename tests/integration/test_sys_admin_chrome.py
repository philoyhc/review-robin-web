"""Coverage for the Segment 16A PR 2 Sys Admin gate + chrome scaffold.

Exercises F2:
- ``require_sys_admin`` returns the user on hit; raises 403 on miss.
- ``GET /operator/sessions/{id}/sys-admin`` 200s for sys-admins and
  403s for plain operators.
- The session chrome partial renders the "Sys Admin" row for
  sys-admins and suppresses it for plain operators.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, User
from app.web.deps import require_sys_admin


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


# --- /sys-admin route gate (F2) --------------------------------------------


def test_sys_admin_page_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote alice via the env-var bootstrap (set BEFORE her first
    sign-in so first-sign-in flips is_sys_admin=True). Alice creates
    the session, so she also passes the per-session operator check.
    """
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="sa-200")

    response = client.get(
        f"/operator/sessions/{review_session.id}/sys-admin",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "<h1>Sys Admin</h1>" in response.text


def test_sys_admin_page_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    """Alice is a plain operator (conftest autouse seeds her into
    operator_emails but not sys_admin_emails); the route must 403."""
    review_session = _make_session(client, db, code="sa-403")

    response = client.get(
        f"/operator/sessions/{review_session.id}/sys-admin",
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert "sys_admin required" in response.text


# --- Chrome partial tab visibility (F2) ------------------------------------


def test_chrome_renders_sys_admin_row_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="sa-tab-on")

    response = client.get(f"/operator/sessions/{review_session.id}")
    assert response.status_code == 200
    assert 'class="session-nav-grid has-admin"' in response.text
    assert (
        f'href="/operator/sessions/{review_session.id}/sys-admin"'
        in response.text
    )


def test_chrome_suppresses_sys_admin_row_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="sa-tab-off")
    response = client.get(f"/operator/sessions/{review_session.id}")
    assert response.status_code == 200
    # The ``has-admin`` token shows up in the inline base.html CSS;
    # check for the rendered grid markup instead.
    assert 'class="session-nav-grid has-admin"' not in response.text
    assert 'class="session-nav-grid"' in response.text
    assert (
        f"/operator/sessions/{review_session.id}/sys-admin"
        not in response.text
    )


# --- require_sys_admin dependency (unit-style) -----------------------------


def test_require_sys_admin_returns_user_on_hit(db: Session) -> None:
    user = User(
        email="admin@example.edu",
        display_name="Admin",
        is_operator=True,
        is_sys_admin=True,
    )
    db.add(user)
    db.commit()
    assert require_sys_admin(user=user) is user


def test_require_sys_admin_raises_on_miss(db: Session) -> None:
    user = User(
        email="operator@example.edu",
        display_name="Operator",
        is_operator=True,
        is_sys_admin=False,
    )
    db.add(user)
    db.commit()
    with pytest.raises(HTTPException) as excinfo:
        require_sys_admin(user=user)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail == "sys_admin required"


