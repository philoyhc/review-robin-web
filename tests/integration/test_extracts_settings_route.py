"""Integration tests for ``GET /operator/sessions/{id}/export/settings.csv``
— Segment 12A-1 PR 1.

Covers the route surface (auth, lifecycle, response shape) +
the audit-event emission. Per-row content shape is unit-tested
in ``tests/unit/test_session_config_io.py``.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "exp-r"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Settings Export", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_export_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="filename1")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="filename1_settings.csv"'
    )


def test_export_body_is_well_formed_csv_with_header(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="csvshape")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code == 200

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    assert rows[0] == ["field", "value", "data_type"]
    # Session-level rows lead.
    assert rows[1] == ["session.name", "Settings Export", "string"]
    assert rows[2] == ["session.code", "csvshape", "string"]
    # Header + body row count > 1 even on a freshly-created session
    # (session-level + email override block always emits).
    assert len(rows) > 1


def test_export_emits_audit_event(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="audit-em")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code == 200
    # Drain the streaming body so ``StreamingResponse`` finishes its
    # work. The audit row is written before the response yields, but
    # reading the body is the canonical way to confirm a clean stream.
    response.read()

    db.expire_all()
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.settings_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert len(events) == 1
    detail = cast(dict, events[0].detail)
    assert detail["session_id"] == review_session.id
    assert detail["session_code"] == "audit-em"
    assert detail["counts"] == {"rows": detail["counts"]["rows"]}
    assert detail["counts"]["rows"] > 0


def test_export_unknown_session_rejected(
    client: TestClient, db: Session
) -> None:
    """``require_session_operator`` rejects non-existent IDs without
    distinguishing them from "not yours" — operator gets the same
    403 either way (also matches every other operator route's
    behaviour on a stale URL)."""

    response = client.get("/operator/sessions/99999/export/settings.csv")
    assert response.status_code in (403, 404)


def test_export_rejects_non_operator(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """Per-session permission gate: only the session's operator can
    extract its settings."""

    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="permgate")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code in (403, 404)


def test_export_works_in_every_lifecycle_state(
    client: TestClient, db: Session
) -> None:
    """No lifecycle gate — extraction is read-only and useful in
    draft / validated / ready / closed alike."""

    review_session = _make_session(client, db, code="lifecycle")
    # Draft.
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code == 200

    # Promote to ready: seed roster + assignments + activate.
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    client.get(f"/operator/sessions/{review_session.id}?validated=1")
    activate = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate.status_code == 303

    # Activated — extract still works.
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/settings.csv"
    )
    assert response.status_code == 200
