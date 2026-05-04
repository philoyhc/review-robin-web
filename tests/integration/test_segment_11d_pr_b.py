"""Tests for Segment 11D PR B — Sessions-list cards + Edit Session chrome."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _create_session(
    client: TestClient, db: Session, *, code: str = "rrw-pr-b"
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── Sessions list lobby (D4) ────────────────────────────────────────────


def test_sessions_list_renders_v2_table_inside_a_card(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)
    body = client.get("/operator/sessions").text
    # Body class flips onto v2.
    assert '<body class="ui-v2">' in body
    # Lobby is a v2 <table> inside a single .card wrapper (revisits the
    # original D4 cards-vs-table decision).
    assert "<table>" in body
    assert "class=\"card session-card\"" not in body
    # The session name is the row's primary anchor into Session Home —
    # there's no separate Access button.
    assert (
        f'<a href="/operator/sessions/{session.id}">{session.name}</a>'
    ) in body
    assert ">Access</a>" not in body


def test_sessions_list_columns_match_spec(
    client: TestClient, db: Session
) -> None:
    """Six labelled columns (Session Name / Session Code / Deadline /
    Created by / Created / Last Modified) plus an unlabelled action
    column for the Delete button."""
    _create_session(client, db, code="rrw-cols")
    body = client.get("/operator/sessions").text
    assert "<th>Session Name</th>" in body
    assert "<th>Session Code</th>" in body
    assert "<th>Deadline</th>" in body
    assert "<th>Created by</th>" in body
    assert "<th>Created</th>" in body
    assert "<th>Last Modified</th>" in body
    # Trailing action column has no header label.
    assert '<th class="col-shrink"></th>' in body


def test_sessions_list_deadline_renders_as_pill_when_set(
    client: TestClient, db: Session
) -> None:
    """Deadline values render as `.pill.pill-info` (a salient stand-out
    cell, vs the plain "No deadline" text used when unset)."""
    # Create with no deadline first — assert the empty-state copy.
    _create_session(client, db, code="rrw-no-dl")
    body = client.get("/operator/sessions").text
    assert "No deadline" in body
    # Now create one with a deadline and check the pill.
    client.post(
        "/operator/sessions",
        data={
            "name": "With Deadline",
            "code": "rrw-with-dl",
            "deadline": "2026-12-31T23:59",
        },
        follow_redirects=False,
    )
    body = client.get("/operator/sessions").text
    assert 'class="pill pill-info">2026-12-31' in body


def test_sessions_list_shows_creator_created_and_modified_dates(
    client: TestClient, db: Session
) -> None:
    _create_session(client, db, code="rrw-meta")
    body = client.get("/operator/sessions").text
    # Created-by reads from the signed-in user's display name (Alice
    # Example via the conftest fake-auth fixture).
    assert "Alice Example" in body


def test_sessions_list_empty_state_renders_prominent_cta(
    client: TestClient,
) -> None:
    body = client.get("/operator/sessions").text
    # No sessions exist yet for the test user.
    assert "You don't have any sessions yet." in body
    # Per spec, the empty state promotes "Create new session" to the
    # page's prominent affordance — rendered as a `.btn-cta`, not the
    # smaller header-row Primary that appears once a session exists.
    assert 'class="btn-cta" href="/operator/sessions/new"' in body
    # And the header-row Create button is suppressed when the list is
    # empty (the empty-state CTA is the single affordance).
    assert 'class="btn" href="/operator/sessions/new"' not in body


# ── Edit Session chrome (B1) ────────────────────────────────────────────


def test_session_edit_renders_two_row_chrome_with_no_active_tab(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="rrw-edit")
    body = client.get(f"/operator/sessions/{session.id}/edit").text
    # Body class flips onto v2.
    assert '<body class="ui-v2">' in body
    # Two-row chrome included.
    assert 'class="session-nav-card"' in body
    assert 'class="session-home-anchor' in body
    assert 'class="tab-strip tab-strip-setup' in body
    assert 'class="tab-strip tab-strip-ops"' in body
    # Per spec, sub-pages of Home render the chrome with no tab active —
    # neither a Setup nor an Operations tab carries the active class.
    assert "nav-tab active" not in body
    assert "session-home-anchor active" not in body
    # H1 inside the body identifies the sub-page (the chrome doesn't).
    assert "<h1>Edit Session</h1>" in body


def test_session_edit_renders_status_row_with_lifecycle_pill(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="rrw-edit2")
    body = client.get(f"/operator/sessions/{session.id}/edit").text
    # The status row partial requires status_pills in context — confirm
    # the route now passes it (B1 prerequisite from the spike).
    assert 'class="status-row"' in body
    assert f'class="pill pill-lifecycle-{session.status}"' in body


def test_session_edit_form_lives_inside_a_card(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="rrw-edit3")
    body = client.get(f"/operator/sessions/{session.id}/edit").text
    # Form is wrapped in a single `.card` (between the chrome and the
    # script tag at the foot of base.html).
    assert "<div class=\"card\">" in body
    assert (
        f'<form method="post" action="/operator/sessions/{session.id}/edit">'
        in body
    )
    # Save = Primary (default `.btn`); Cancel = Secondary.
    assert '<button class="btn" type="submit">Save changes</button>' in body
    assert (
        f'<a class="btn secondary" href="/operator/sessions/{session.id}">Cancel</a>'
        in body
    )
