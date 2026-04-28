from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def write_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor_user_id: int | None = None,
    session_id: int | None = None,
    severity: str = "info",
    detail: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        summary=summary,
        severity=severity,
        actor_user_id=actor_user_id,
        session_id=session_id,
        detail=detail,
        correlation_id=correlation_id,
    )
    db.add(event)
    db.flush()
    return event
