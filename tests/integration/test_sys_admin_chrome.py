"""Coverage for the Segment 16A Sys Admin chrome + workspace-level
Admin landing.

PR 2 / 2b shipped the workspace-level URL + the top-bar "Admin"
link. PR 3 turns ``/operator/sys-admin`` into a 303 redirect to
``/operator/sys-admin/sessions`` (the first tab), which renders
the workspace sessions table with per-row Outbox links. This
file covers:

- 200 for sys-admins / 403 for plain operators on the Sessions
  Diagnostics page.
- ``/operator/sys-admin`` redirects (303) to the default tab,
  preserving ``?return_to=``.
- The base-chrome top-bar Admin link renders for sys-admins
  (between Settings and About) and suppresses on every
  ``/operator/sys-admin*`` page.
- Sessions Diagnostics renders one row per session with a
  per-row outbox link.
- ``require_sys_admin`` returns user / raises 403.

A separate file (`test_outbox_sys_admin_relax.py`) covers the
``require_sys_admin_or_session_operator`` relaxation that lets a
sys-admin reach a per-session outbox they aren't a
``session_operators`` member of.
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


# --- /sys-admin redirect (PR 3) --------------------------------------------


def test_sys_admin_root_redirects_to_sessions_tab(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sys-admin/sessions"


def test_sys_admin_root_preserves_return_to(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get(
        "/operator/sys-admin?return_to=/operator/sessions/7",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        "/operator/sys-admin/sessions?return_to=/operator/sessions/7"
    )


def test_sys_admin_root_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/operator/sys-admin", follow_redirects=False)
    assert response.status_code == 403


# --- /sys-admin/sessions (Sessions Diagnostics tab) ------------------------


def test_sessions_diagnostics_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="diag-1")

    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert "<h1>Admin</h1>" in response.text
    assert "Sessions Diagnostics" in response.text
    # Sessions table row.
    assert review_session.name in response.text
    # Per-row outbox link.
    assert (
        f'href="/operator/sessions/{review_session.id}/outbox"'
        in response.text
    )
    assert ">View outbox</a>" in response.text


def test_sessions_diagnostics_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/operator/sys-admin/sessions", follow_redirects=False)
    assert response.status_code == 403


def test_sessions_diagnostics_empty_state(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    # No sessions in this workspace yet.
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert "No sessions in this workspace yet." in response.text


def test_sessions_diagnostics_back_link_resolves_return_to(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="diag-rt")

    response = client.get(
        f"/operator/sys-admin/sessions?return_to=/operator/sessions/{review_session.id}"
    )
    assert response.status_code == 200
    assert f'href="/operator/sessions/{review_session.id}"' in response.text
    assert "Back to Spring" in response.text


def test_sessions_diagnostics_back_link_falls_back_to_lobby(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert 'href="/operator/sessions"' in response.text
    assert "Back to Sessions" in response.text


def test_sessions_diagnostics_renders_accounts_tab_as_disabled(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    # Accounts Management tab present but disabled.
    assert "Accounts Management" in response.text
    assert 'aria-disabled="true"' in response.text
    # No live link to the future PR 6 URL.
    assert 'href="/operator/sys-admin/users"' not in response.text


# --- Top-bar Admin link visibility ----------------------------------------


def test_chrome_admin_link_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    assert "/operator/sys-admin?return_to=" in response.text
    assert ">Admin</a>" in response.text


def test_chrome_admin_link_suppressed_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    assert "/operator/sys-admin" not in response.text
    assert ">Admin</a>" not in response.text


def test_chrome_admin_link_hides_itself_on_sessions_diagnostics(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Admin link suppresses on any /operator/sys-admin* path."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert "/operator/sys-admin?return_to=" not in response.text


# --- Manage Invitations: outbox button retired (F10) -----------------------


def test_manage_invitations_no_longer_renders_view_outbox_button(
    db: Session,
    client: TestClient,
) -> None:
    """The 'View outbox' Primary Outline button on Manage Invitations
    retired in 16A PR 3 — Outbox is reached via the Admin chrome
    instead. Existing per-session URL stays reachable directly."""
    review_session = _make_session(client, db, code="inv-no-outbox")
    response = client.get(
        f"/operator/sessions/{review_session.id}/invitations"
    )
    assert response.status_code == 200
    # The button (an <a class="btn ..." href="...outbox">View outbox</a>)
    # is gone; check for the distinctive ">View outbox</a>" tail.
    assert ">View outbox</a>" not in response.text


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
