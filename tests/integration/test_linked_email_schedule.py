"""Review Robin's schedule sends no email for a session whose linked
application takes the email lock (segment 23F rung 6, the cold read)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent

from ._lookups import detail_of
from .test_linked_sessions import _created


def test_the_schedule_sends_no_email_for_apply_desk(client: TestClient, db: Session) -> None:
    """A due scheduled invite or reminder is skipped, not sent, on a session
    whose application takes the email lock (the cold read of 23F)."""
    from app.services.scheduled_events import _invites, _reminders

    review_session, _ = _created(client, db)
    review_session.linked_app = "applydesk"
    review_session.status = "ready"
    db.commit()
    now = datetime.now(UTC)
    for module, fire, event in (
        (_invites, "_fire_invite_entry", "session.scheduled_invites_skipped"),
        (_reminders, "_fire_reminder_entry", "session.scheduled_reminders_skipped"),
    ):
        getattr(module, fire)(
            db,
            review_session,
            offset_index=0,
            offset_str="-P1D",
            anchor_iso=now.isoformat(),
            scheduled_iso=now.isoformat(),
            now=now,
            correlation_id=None,
            build_invite_url=lambda token: token,
        )
        db.flush()
        skipped = db.scalars(select(AuditEvent).where(AuditEvent.event_type == event)).one()
        assert detail_of(skipped)["reason"] == "linked_app_email_off"
