"""Settings CSV ``email_overrides.responses_received.enabled`` imports
the way the editor's toggle stores it (findings D12, 2026-10-05).

The export always writes the row (``true`` by default), and the import
stored that ``true`` in ``email_template_overrides``, so a session with
no overrides came back with one, and Validate's "custom email
overrides" line reported it. ``set_responses_received_enabled`` keeps
the key only for an explicit opt-out; the import now does the same.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import email_templates
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _session(db: Session, code: str) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _with_enabled(rows: list[Row], value: str) -> list[Row]:
    key = "email_overrides.responses_received.enabled"
    assert any(r.field == key for r in rows), "the export no longer writes it"
    return [
        Row(r.field, value, r.data_type) if r.field == key else r
        for r in rows
    ]


def test_a_session_with_no_overrides_imports_with_none(db: Session) -> None:
    review_session = _session(db, "d12-none")
    assert review_session.email_template_overrides is None
    rows = serialize_session_config(db, review_session)

    result = apply_session_config(db, review_session, rows)

    assert result.errors == []
    assert review_session.email_template_overrides is None
    assert email_templates.responses_received_enabled(review_session) is True


def test_an_opt_out_still_imports_as_off(db: Session) -> None:
    review_session = _session(db, "d12-off")
    rows = _with_enabled(serialize_session_config(db, review_session), "false")

    result = apply_session_config(db, review_session, rows)

    assert result.errors == []
    assert email_templates.responses_received_enabled(review_session) is False
    assert review_session.email_template_overrides == {
        email_templates.RESPONSES_RECEIVED_ENABLED_KEY: False
    }
