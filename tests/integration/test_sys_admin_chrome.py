"""Coverage for the Segment 16A PR 2 Sys Admin gate + workspace-level
Admin entry point.

Exercises F2:
- ``require_sys_admin`` returns the user on hit; raises 403 on miss.
- ``GET /operator/sys-admin`` 200s for sys-admins and 403s for plain
  operators.
- The base-chrome top bar renders the "Admin" link for sys-admins
  (between Settings and About) and suppresses it for plain
  operators. The link carries ``?return_to=`` per the Settings /
  About pattern.
- The Admin page itself renders a "← Back to {label}" affordance
  resolved from the ``return_to`` query param.
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


def test_sys_admin_landing_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])

    response = client.get("/operator/sys-admin", follow_redirects=False)
    assert response.status_code == 200
    assert "<h1>Admin</h1>" in response.text


def test_sys_admin_landing_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    """Alice is a plain operator (conftest autouse seeds her into
    operator_emails but not sys_admin_emails); the route must 403."""
    response = client.get("/operator/sys-admin", follow_redirects=False)
    assert response.status_code == 403
    assert "sys_admin required" in response.text


def test_sys_admin_landing_renders_back_link_from_return_to(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="sa-rt")

    response = client.get(
        f"/operator/sys-admin?return_to=/operator/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert (
        f'href="/operator/sessions/{review_session.id}"'
        in response.text
    )
    assert "Back to Spring" in response.text


def test_sys_admin_landing_back_link_falls_back_to_sessions_lobby(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``return_to=`` query param ⇒ resolve_return_to falls back
    to /operator/sessions ("Sessions")."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin", follow_redirects=False)
    assert response.status_code == 200
    assert 'href="/operator/sessions"' in response.text
    assert "Back to Sessions" in response.text


# --- Top-bar Admin link visibility (F2) ------------------------------------


def test_chrome_admin_link_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The base.html top bar renders an Admin link for sys-admins,
    carrying ``?return_to=<current path>``. Verify on the sessions
    lobby (any operator page works)."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    assert "/operator/sys-admin?return_to=" in response.text
    # The link text reads "Admin".
    assert ">Admin</a>" in response.text


def test_chrome_admin_link_suppressed_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    """Alice is a plain operator; the Admin link must not render."""
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    assert "/operator/sys-admin" not in response.text
    assert ">Admin</a>" not in response.text


def test_chrome_admin_link_hides_itself_on_admin_page(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """While the user is already on /operator/sys-admin, the Admin
    link self-suppresses (matches the Settings / About self-hiding
    pattern)."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin")
    assert response.status_code == 200
    # The href doesn't recur in the page chrome.
    assert "/operator/sys-admin?return_to=" not in response.text


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
