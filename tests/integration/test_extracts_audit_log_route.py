"""Integration tests for ``GET
/operator/sessions/{id}/export/audit_log.csv`` —
Segment 12B PR 1 (gate tightened to ``require_sys_admin`` in
Segment 16C PR 1).

Covers route surface (auth, response shape, filename + audit
emission). Per-row content shape is unit-tested in
``tests/unit/test_audit_events_extract.py``.
"""

from __future__ import annotations

import csv
import io
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "al"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "AuditLog", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


@pytest.fixture(autouse=True)
def _seed_alice_as_sys_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """The audit-log CSV route gates on ``require_sys_admin`` since
    16C PR 1. Seeding alice as a sys-admin keeps the existing
    ``client``-fixture-based tests working — her first sign-in (via
    ``_make_session`` POST) lights up ``is_sys_admin``."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


def test_audit_log_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="al-fname")

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="al-fname_audit_log.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "EventType",
        "Severity",
        "Summary",
        "ActorEmail",
        "CorrelationId",
        "CreatedAt",
        "DetailJson",
    ]


def test_audit_log_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    """The act of downloading the audit log goes into the audit
    log. The body_count reflects pre-download rows; the
    just-written event captures next time."""

    review_session = _make_session(client, db, code="al-audit")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.audit_log_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    # At least the ``session.created`` event was present at
    # download time.
    assert detail["counts"]["rows"] >= 1


def test_audit_log_route_returns_session_events(
    client: TestClient, db: Session
) -> None:
    """A freshly-created session has a ``session.created``
    event; the download surfaces it as a row."""

    review_session = _make_session(client, db, code="al-rows")

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv"
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    # Header + at least one row (session.created).
    assert len(rows) >= 2
    event_types = [row[0] for row in rows[1:]]
    assert "session.created" in event_types


def test_audit_log_route_rejects_non_sys_admin(
    db: Session,
    alice: object,
    bob: object,
    make_client: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bob is a plain operator (not a sys-admin) — even though he's
    on the workspace operator allowlist he can't reach the CSV
    route since 16C PR 1's gate tightening."""
    # Override the autouse fixture: alice still needs to create
    # the session (operator-only path), bob then hits the gate.
    monkeypatch.setattr(settings, "sys_admin_emails", [])
    alice_client = make_client(alice)  # type: ignore[operator]
    review_session = _make_session(alice_client, db, code="al-perm")

    bob_client = make_client(bob)  # type: ignore[operator]
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/audit_log.csv",
        follow_redirects=False,
    )
    assert response.status_code == 403
