"""Audit-events extract — Segment 12B PR 1.

Streams the session's ``audit_events`` rows as a wide CSV
for downstream analysis / recordkeeping. Per the 12B plan,
the export is read-only with no import counterpart —
audit events are system-emitted (not operator-typed) so
there is no porting use case.

The 8-column shape carries the operator-meaningful slots
plus the canonical detail envelope (per Segment 11K) as a
JSON-encoded string. Different ``event_type`` values carry
different envelope keys, so one-column-per-key would
produce a sparse table; the JSON string preserves the full
typed envelope for downstream re-parse.

Streamed via ``yield_per(1000)`` cursor so memory stays
flat on sessions with thousands of events (mirrors the
Responses extract in 12A-1 PR 4).

Plan: ``guide/segment_12B_audit_retention.md``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User

if TYPE_CHECKING:
    from app.services.audit import AuditFilters

__all__ = ["HEADER", "serialize_audit_events"]


HEADER: tuple[str, ...] = (
    "EventType",
    "Severity",
    "Summary",
    "ActorEmail",
    "CorrelationId",
    "CreatedAt",
    "DetailJson",
)


def serialize_audit_events(
    db: Session,
    review_session: ReviewSession,
    *,
    filters: "AuditFilters | None" = None,
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s audit events.

    First yield is ``HEADER``; subsequent yields are one
    tuple per ``AuditEvent`` row in ``(created_at ASC,
    id ASC)`` order.

    ``ActorEmail`` joins through ``actor_user_id`` (LEFT
    JOIN — system-emitted events with no actor render an
    empty cell). ``CreatedAt`` is ISO 8601 with timezone
    offset; naive readbacks (SQLite) are normalised to UTC
    so the cell shape is dialect-stable. ``DetailJson`` is
    ``json.dumps(detail, sort_keys=True)`` for stable
    byte-identical re-exports; ``None`` collapses to empty
    cell.

    Optional ``filters`` (Segment 16C PR 2) narrow the row set
    to match the in-app viewer's filter strip. Composes with
    the same predicate set the viewer uses; an unset filter is
    a no-op.
    """
    from app.services.audit import _apply_filters

    yield HEADER

    stmt = (
        select(AuditEvent, User.email)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.session_id == review_session.id)
    )
    stmt = _apply_filters(stmt, filters, User)
    stmt = (
        stmt.order_by(AuditEvent.created_at, AuditEvent.id)
        .execution_options(yield_per=1000)
    )
    for event, actor_email in db.execute(stmt):
        yield (
            event.event_type,
            event.severity,
            event.summary or "",
            actor_email or "",
            event.correlation_id or "",
            _isoformat_utc(event.created_at),
            _json_or_empty(event.detail),
        )


def _isoformat_utc(value: object) -> str:
    """ISO 8601 representation of a datetime, normalised
    to UTC when tzinfo is missing on readback.

    SQLite's ``DateTime`` column drops tzinfo on readback;
    Postgres preserves it. Forcing UTC on naive values
    keeps the export shape stable across both dialects."""

    if value is None:
        return ""
    from datetime import datetime, timezone

    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()  # type: ignore[union-attr]


def _json_or_empty(value: object) -> str:
    """Compact, key-stable JSON of ``value``.
    ``None`` ⇒ empty cell."""

    if value is None:
        return ""
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
