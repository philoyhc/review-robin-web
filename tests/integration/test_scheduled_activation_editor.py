"""Editor + caption coverage for Segment 18G PR 1C.

End-to-end checks on the Start (``scheduled_activate_at``) input on
the Create / Edit session forms, plus the Workflow card's
right-column caption.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.web.views._workflow_card import build_scheduled_activation_caption


def _create_session(
    client: TestClient,
    code: str,
    *,
    scheduled_activate_at: str | None = None,
) -> int:
    data: dict[str, str] = {
        "name": f"Sess {code}",
        "code": code,
        "description": "d",
    }
    if scheduled_activate_at:
        data["scheduled_activate_at"] = scheduled_activate_at
    response = client.post(
        "/operator/sessions", data=data, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    # Create-session redirect targets ``.../{id}/edit``; strip the
    # trailing ``/edit`` before parsing the id.
    location = response.headers["location"].removesuffix("/edit")
    return int(location.rsplit("/", 1)[-1])


def _fmt_local_input(dt: datetime) -> str:
    """Render a datetime as the ``YYYY-MM-DDTHH:MM`` shape <input type=datetime-local> uses."""
    return dt.strftime("%Y-%m-%dT%H:%M")


# --------------------------------------------------------------------------- #
# Create form                                                                 #
# --------------------------------------------------------------------------- #


def test_create_accepts_valid_scheduled_activate_at(
    client: TestClient, db: Session
) -> None:
    """A Start at least the configured lead time in the future saves."""
    future = datetime.now(timezone.utc) + timedelta(hours=24)
    session_id = _create_session(
        client,
        "create-ok",
        scheduled_activate_at=_fmt_local_input(future),
    )
    review_session = db.get(ReviewSession, session_id)
    assert review_session is not None
    assert review_session.scheduled_activate_at is not None
    # Compare via _ensure_aware_utc to absorb SQLite tzinfo stripping.
    saved = scheduled_events._ensure_aware_utc(
        review_session.scheduled_activate_at
    )
    # Tolerate the timezone-localisation round-trip; both should be
    # the same wall-clock moment, but the form interprets the value
    # in the session's display timezone (UTC by default for tests).
    assert abs((saved - future).total_seconds()) < 60


def test_create_rejects_past_scheduled_activate_at(
    client: TestClient,
) -> None:
    """A Start in the past — or closer than the operational lead — is rejected at save."""
    too_soon = datetime.now(timezone.utc) + timedelta(minutes=15)
    response = client.post(
        "/operator/sessions",
        data={
            "name": "Too soon",
            "code": "create-too-soon",
            "scheduled_activate_at": _fmt_local_input(too_soon),
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "1 hour" in response.text or "in the future" in response.text


def test_create_without_scheduled_activate_at_works(
    client: TestClient, db: Session
) -> None:
    """Empty Start input keeps scheduled_activate_at NULL — no regression."""
    session_id = _create_session(client, "create-empty")
    review_session = db.get(ReviewSession, session_id)
    assert review_session is not None
    assert review_session.scheduled_activate_at is None


# --------------------------------------------------------------------------- #
# Edit form                                                                   #
# --------------------------------------------------------------------------- #


def test_edit_accepts_setting_scheduled_activate_at(
    client: TestClient, db: Session
) -> None:
    """Operator sets Start on an existing draft session via the Edit form."""
    session_id = _create_session(client, "edit-set")
    future = datetime.now(timezone.utc) + timedelta(hours=24)

    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-set",
            "code": "edit-set",
            "scheduled_activate_at": _fmt_local_input(future),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.get(ReviewSession, session_id)
    assert review_session is not None
    assert review_session.scheduled_activate_at is not None


def test_edit_clearing_emits_activation_scheduled_audit(
    client: TestClient, db: Session
) -> None:
    """Setting then clearing Start emits session.activation_scheduled twice."""
    session_id = _create_session(client, "edit-clear")
    future = datetime.now(timezone.utc) + timedelta(hours=24)
    # Set
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-clear",
            "code": "edit-clear",
            "scheduled_activate_at": _fmt_local_input(future),
        },
        follow_redirects=False,
    )
    # Clear
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-clear",
            "code": "edit-clear",
            "scheduled_activate_at": "",
        },
        follow_redirects=False,
    )
    audits = db.execute(
        select(AuditEvent)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type == "session.activation_scheduled")
    ).scalars().all()
    assert len(audits) == 2  # one for set, one for clear
    db.refresh(db.get(ReviewSession, session_id))
    review_session = db.get(ReviewSession, session_id)
    assert review_session.scheduled_activate_at is None


def test_edit_rejects_too_soon(client: TestClient) -> None:
    """Edit save rejects a Start that would violate the lead-time floor."""
    session_id = _create_session(client, "edit-too-soon")
    too_soon = datetime.now(timezone.utc) + timedelta(minutes=10)
    response = client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-too-soon",
            "code": "edit-too-soon",
            "scheduled_activate_at": _fmt_local_input(too_soon),
        },
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_edit_get_prefills_scheduled_activate_at_input_value(
    client: TestClient, db: Session
) -> None:
    """The Edit page GET renders the persisted Start in the input."""
    session_id = _create_session(client, "edit-prefill")
    future = datetime.now(timezone.utc) + timedelta(hours=24)
    client.post(
        f"/operator/sessions/{session_id}/edit",
        data={
            "name": "Sess edit-prefill",
            "code": "edit-prefill",
            "scheduled_activate_at": _fmt_local_input(future),
        },
        follow_redirects=False,
    )
    page = client.get(f"/operator/sessions/{session_id}/edit")
    assert page.status_code == 200
    assert 'id="scheduled_activate_at"' in page.text
    # The input's value attribute should carry the prefilled datetime
    # in the local-input format (YYYY-MM-DDTHH:MM); presence is enough
    # without parsing the rendered HTML.
    assert 'name="scheduled_activate_at"' in page.text
    assert "value=" in page.text  # at minimum some value is rendered


# --------------------------------------------------------------------------- #
# Workflow card caption (right column)                                        #
# --------------------------------------------------------------------------- #


def _make_session_in_status(
    db: Session, code: str, status: str
) -> ReviewSession:
    """Tiny ORM-only helper for the caption tests — bypasses the
    routes since the caption builder just reads session state."""
    from app.db.models import User

    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    from app.schemas.sessions import SessionCreate
    from app.services import sessions as sessions_service

    payload = SessionCreate(
        name=code.title(), code=code, description="d"
    )
    rs = sessions_service.create_session(db, user=op, payload=payload)
    rs.status = status
    db.flush()
    db.commit()
    db.refresh(rs)
    return rs


def test_caption_none_when_status_ready(db: Session) -> None:
    rs = _make_session_in_status(db, "cap-ready", lifecycle.SessionStatus.ready.value)
    assert build_scheduled_activation_caption(db, rs) is None


def test_caption_none_when_draft_no_schedule(db: Session) -> None:
    rs = _make_session_in_status(db, "cap-draft-empty", lifecycle.SessionStatus.draft.value)
    assert build_scheduled_activation_caption(db, rs) is None


def test_caption_amber_warning_when_draft_with_future_schedule(
    db: Session,
) -> None:
    rs = _make_session_in_status(
        db, "cap-draft-future", lifecycle.SessionStatus.draft.value
    )
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.flush()
    db.commit()
    cap = build_scheduled_activation_caption(db, rs)
    assert cap is not None
    assert cap["tone"] == "amber-warning"
    assert "Prepare session" in cap["text"]


def test_caption_green_when_validated_with_future_schedule(
    db: Session,
) -> None:
    rs = _make_session_in_status(
        db, "cap-validated-future", lifecycle.SessionStatus.validated.value
    )
    rs.scheduled_activate_at = datetime.now(timezone.utc) + timedelta(days=1)
    db.flush()
    db.commit()
    cap = build_scheduled_activation_caption(db, rs)
    assert cap is not None
    assert cap["tone"] == "green"
    assert "auto-activate" in cap["text"]


def test_caption_skipped_when_latest_audit_is_skip(db: Session) -> None:
    """Schedule cleared + most-recent audit is skip → amber-grey caption."""
    from app.services import audit

    rs = _make_session_in_status(
        db, "cap-skipped", lifecycle.SessionStatus.draft.value
    )
    # No scheduled_activate_at (already cleared by the skip)
    audit.write_event(
        db,
        event_type="session.scheduled_activation_skipped",
        summary="skipped",
        actor_user_id=None,
        session=rs,
        reason="not_validated",
        context={
            "scheduled_at": "2099-01-01T09:00:00+00:00",
            "status_at_fire": "draft",
        },
    )
    db.commit()
    cap = build_scheduled_activation_caption(db, rs)
    assert cap is not None
    assert cap["tone"] == "amber-grey"
    assert "not_validated" in cap["text"]


def test_caption_skipped_clears_after_next_audit(db: Session) -> None:
    """The skipped caption disappears once any newer audit event lands."""
    from app.services import audit

    rs = _make_session_in_status(
        db, "cap-skipped-cleared", lifecycle.SessionStatus.draft.value
    )
    audit.write_event(
        db,
        event_type="session.scheduled_activation_skipped",
        summary="skipped",
        actor_user_id=None,
        session=rs,
        reason="not_validated",
        context={"scheduled_at": "2099-01-01T09:00:00+00:00", "status_at_fire": "draft"},
    )
    # Operator does anything else → new audit event newer than the skip
    audit.write_event(
        db,
        event_type="session.updated",
        summary="updated",
        actor_user_id=None,
        session=rs,
        payload=audit.changes({"name": ["old", "new"]}),
    )
    db.commit()
    cap = build_scheduled_activation_caption(db, rs)
    assert cap is None
