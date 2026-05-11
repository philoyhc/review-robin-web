"""Coverage for the Sys Admin audit-log child page — Segment 16C PR 1.

Mirrors the Outbox child-page tests under
``test_sys_admin_outbox_child.py`` — same chrome / back-link /
gate convention.
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


# --- Gate ------------------------------------------------------------------


def test_audit_log_page_403_for_non_admin(
    db: Session,
    client: TestClient,
) -> None:
    """Plain operator (creator of the session, but no sys-admin
    role) cannot reach the audit-log child page — the gate is
    require_sys_admin."""
    review_session = _make_session(client, db, code="audit-page-403")
    response = client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_audit_log_page_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-200")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    # Chrome conventions: back-link + Admin nav + audit-log section
    # heading + Download CSV affordance.
    assert "Back to Sessions Diagnostics" in response.text
    assert "<h1>Admin</h1>" in response.text
    assert "Sessions Diagnostics" in response.text  # tab strip
    assert f"Audit log — {review_session.name}" in response.text
    assert (
        f'href="/operator/sessions/{review_session.id}/export/audit_log.csv"'
        in response.text
    )
    assert "Download CSV" in response.text


def test_audit_log_page_404s_on_missing_session(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    bob_client = make_client(bob)
    response = bob_client.get(
        "/operator/sys-admin/sessions/99999/audit-log",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --- Content + columns -----------------------------------------------------


def test_audit_log_page_renders_seeded_events(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The session creation flow emits a ``session.created`` audit
    event. The child page should render that row + the 8 column
    headers."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-seeded")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    body = response.text
    # All 8 column headers present.
    for header in (
        "Event",
        "Severity",
        "Summary",
        "Actor",
        "Correlation",
        "When",
        "Detail",
    ):
        assert f">{header}<" in body
    # session.created emits during _make_session; should appear.
    assert "session.created" in body
    assert "alice@example.edu" in body


# --- Pagination ------------------------------------------------------------


def test_audit_log_page_renders_next_link_when_page_fills(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the table has more events than the page size (50),
    the "Older events →" anchor renders, carrying the last row's
    id as the cursor."""
    from app.services import audit

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-fill")
    # Seed 55 extra info events so page 1 of 50 fills and there's
    # leftover. Each emits a canonical envelope.
    for i in range(55):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"seed {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert response.status_code == 200
    body = response.text
    assert "Older events" in body
    # Anchor encodes a cursor.
    assert "?cursor=" in body


def test_audit_log_pagination_round_trip(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Page 2 follows ``?cursor=<id>``; its top row is strictly
    older (lower id) than page 1's bottom row."""
    from app.services import audit

    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-page-rt")
    for i in range(60):
        audit.write_event(
            db,
            event_type="session.activated",
            summary=f"rt seed {i}",
            session=review_session,
            payload=audit.counts(i=i),
        )

    bob_client = make_client(bob)
    page1 = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}/audit-log"
    )
    assert page1.status_code == 200
    # Pull the cursor out of the rendered next-page anchor.
    import re

    match = re.search(r"\?cursor=(\d+)", page1.text)
    assert match is not None, "Page 1 should advertise a cursor"
    cursor = int(match.group(1))

    page2 = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}"
        f"/audit-log?cursor={cursor}"
    )
    assert page2.status_code == 200
    # Page 2 should contain events older than the cursor; the
    # specific ``rt seed 0`` row sits near the bottom of the
    # full set and lands on page 2 with 60 seeds (5 leftover) +
    # one creator row.
    assert "rt seed 0" in page2.text
    assert "rt seed 0" not in page1.text


def test_audit_log_page_no_events_renders_empty_copy(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past a cursor that exhausts the table the page renders
    "No audit events ... older than the requested cursor"."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="audit-empty-cursor")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sys-admin/sessions/{review_session.id}"
        f"/audit-log?cursor=1"
    )
    assert response.status_code == 200
    assert "older than the requested cursor" in response.text


# --- Diagnostics row link migration ---------------------------------------


def test_diagnostics_row_audit_log_link_points_at_child_page(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-row Audit log affordance on Sessions Diagnostics
    now opens the child viewer rather than streaming the CSV
    directly."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="audit-row-link")
    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert (
        f'href="/operator/sys-admin/sessions/{review_session.id}/audit-log">Audit log</a>'
        in response.text
    )
    # The old direct-CSV link no longer renders.
    assert (
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
        not in response.text
    )
