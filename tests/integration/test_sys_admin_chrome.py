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

import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession, SessionOperator, User
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


def _hand_to_another_owner(db: Session, review_session: ReviewSession) -> None:
    """Re-own a session the signed-in admin created, so its Diagnostics
    row offers Manage; an owned one reads Owned (author, 2026-10-15)."""
    other = User(email="other-owner@example.edu", is_operator=True)
    db.add(other)
    db.flush()
    for row in db.execute(
        select(SessionOperator).where(SessionOperator.session_id == review_session.id)
    ).scalars():
        row.user_id = other.id
    db.commit()


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
    _hand_to_another_owner(db, review_session)

    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert "<h1>Admin</h1>" in response.text
    assert "Sessions Diagnostics" in response.text
    # Sessions table row.
    assert review_session.name in response.text
    # Per-row Outbox link points at the child page under the
    # Sessions Diagnostics tab.
    assert (
        f'href="/operator/sys-admin/sessions/{review_session.public_id}/outbox">Outbox</a>'
        in response.text
    )
    assert (
        f'href="/operator/sys-admin/sessions/{review_session.public_id}/audit-log">Audit log</a>'
        in response.text
    )
    # Manage action (Segment 18S Item 3) — a POST to the adopt route
    # (self-add as owner → open), replacing the old back-door link to
    # /edit now that editing a non-owned session requires ownership.
    assert (
        f'action="/operator/sys-admin/sessions/{review_session.public_id}/adopt"'
        in response.text
    )
    assert ">Manage</button>" in response.text
    # 2026-09-08 — the three per-row actions are canonical Secondary
    # buttons in a `.btn-pair`, not link-styled ones. Pinned because the
    # assertions around them check href and label only, so a revert to
    # `chrome-link` plus inline un-styling would pass every other test on
    # this page (`spec/operator_button_audit.md` §21).
    # The Actions cell is the row's last; Timezone is also col-shrink.
    actions = response.text.split('<div class="btn-pair is-one-line">')[1].split("</td>")[0]
    assert actions.count('class="btn secondary"') == 3
    # Whitespace-independent: the template wraps these across lines, and an
    # assertion coupled to that indentation breaks on a re-wrap while
    # telling you nothing about the roles.
    assert "chrome-link" not in actions
    assert "style=" not in actions
    # Status renders as a lifecycle-coloured pill matching the
    # session_setup_status_row partial used on session-home pages.
    assert (
        '<span class="pill pill-lifecycle-draft">Draft</span>'
        in response.text
    )


def test_sessions_diagnostics_columns_present(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lobby's columns, in its order (author, 2026-10-14): six that
    sort, then Status and Actions, which don't. Last Modified is gone."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _make_session(client, db, code="diag-cols")

    body = client.get("/operator/sys-admin/sessions").text
    head = body.split('id="diagnostics-sessions"', 1)[1].split("</thead>", 1)[0]
    keys = [part.split('"', 1)[0] for part in head.split('data-sort-key="')[1:]]
    assert keys == ["name", "code", "created_by", "created", "deadline", "timezone"]
    labels = re.findall(r"<th(?:\s[^>]*)?>([^<]*)", head)
    assert labels == [
        "Session Name", "Session Code", "Created by", "Created", "Deadline",
        "Timezone", "Status", "Actions",
    ]
    assert head.count("rrw-sort-btn") == 6
    assert "Last Modified" not in body


def test_sessions_diagnostics_lists_every_workspace_session(
    db: Session,
    client: TestClient,
    make_client,
    alice,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sys-admin sees every session in the workspace, including
    ones they didn't create. Alice (creator) and Bob (creator) each
    spin up a session; both rows render for an admin viewer."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    alice_session = _make_session(client, db, code="all-a")

    # ``make_client(bob)`` mutates the global TestClient identity
    # override; create the bob client first to seed his session, then
    # swap back to alice to verify the workspace view.
    bob_client = make_client(bob)
    bob_session = _make_session(bob_client, db, code="all-b")

    alice_client = make_client(alice)
    response = alice_client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert alice_session.name in response.text
    assert bob_session.code in response.text  # also check Bob's row
    assert (
        f'href="/operator/sys-admin/sessions/{bob_session.public_id}/outbox">Outbox</a>'
        in response.text
    )


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
        f"/operator/sys-admin/sessions?return_to=/operator/sessions/{review_session.public_id}"
    )
    assert response.status_code == 200
    assert f'href="/operator/sessions/{review_session.public_id}"' in response.text
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


def test_sessions_diagnostics_renders_live_accounts_tab(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16A PR 6 lit up the Accounts Management tab as a live link
    to /operator/sys-admin/users. Until PR 6 the tab rendered as a
    disabled placeholder; this assertion guards against regressing
    it back to the placeholder."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert "Accounts Management" in response.text
    assert 'href="/operator/sys-admin/users"' in response.text


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
        f"/operator/sessions/{review_session.public_id}/invitations"
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


# --- /sys-admin/system (System Status tab, segment 22G Item 1) ------------


def test_system_status_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/system")
    assert response.status_code == 200
    for card in ("data-system-clock", "data-system-due", "data-system-sending", "data-system-instance"):
        assert card in response.text
    # The tab is active here, and the other two link away.
    assert re.search(
        r'class="nav-tab active"\s+href="/operator/sys-admin/system">System Status', response.text
    )
    assert 'href="/operator/sys-admin/sessions"' in response.text
    assert 'href="/operator/sys-admin/users"' in response.text


def test_system_status_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/operator/sys-admin/system")
    assert response.status_code == 403


def test_every_admin_tab_links_to_system_status(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    for path in ("/operator/sys-admin/sessions", "/operator/sys-admin/users"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'href="/operator/sys-admin/system"' in response.text


def test_system_status_clock_card_reads_the_clock(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.scheduled_events import _clock

    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(settings, "scheduler_interval_seconds", 0)
    response = client.get("/operator/sys-admin/system")
    assert 'data-clock-state="off"' in response.text
    assert "SCHEDULER_INTERVAL_SECONDS is 0" in response.text

    monkeypatch.setattr(settings, "scheduler_interval_seconds", 120)
    monkeypatch.setattr(
        _clock, "_status", _clock.ClockStatus(since=_clock.clock_status().since, running=True, interval_seconds=120)
    )
    response = client.get("/operator/sys-admin/system")
    assert 'data-clock-state="on"' in response.text
    assert "Every 2 min" in response.text
    assert "None yet" in response.text


def test_system_status_due_card_renders_its_rows(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.get("/operator/sys-admin/system")
    assert response.status_code == 200
    for row in ("data-due-start", "data-due-close", "data-due-release", "data-due-now", "data-due-failed"):
        assert row in response.text
    assert "Nothing scheduled" in response.text


def test_system_status_links_a_session_by_its_public_id(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex, #3619: the audit-log route takes the public id, not the
    integer one, so a link built from ``id`` would 404."""
    from datetime import UTC, datetime, timedelta

    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="due-link")
    review_session.scheduled_activate_at = datetime.now(UTC) + timedelta(days=1)
    db.commit()
    response = client.get("/operator/sys-admin/system")
    link = f"/operator/sys-admin/sessions/{review_session.public_id}/audit-log"
    assert f'href="{link}"' in response.text
    assert client.get(link).status_code == 200


def test_system_status_sending_and_instance_cards(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.schema_head import SCHEMA_HEAD

    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(settings, "app_version", "a5aa328")
    monkeypatch.setattr(settings, "scheduled_send", False)
    response = client.get("/operator/sys-admin/system")
    assert "Off (RRW_SCHEDULED_SEND)" in response.text
    assert re.search(r"data-instance-version>a5aa328<", response.text)
    dialect = db.get_bind().dialect.name
    assert f"data-instance-dialect>{dialect}<" in response.text
    if dialect == "sqlite":
        # The SQLite schema is built without Alembic: no revision recorded.
        assert 'data-schema-current="no"' in response.text
        assert f"No revision recorded; this code expects {SCHEMA_HEAD}" in response.text
    else:
        # The Postgres job migrates to head.
        assert 'data-schema-current="yes"' in response.text
        assert f"Current ({SCHEMA_HEAD})" in response.text

    monkeypatch.setattr(settings, "scheduled_send", True)
    response = client.get("/operator/sys-admin/system")
    assert "On: scheduled invites and reminders fire on time" in response.text
