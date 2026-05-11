"""Audit log viewer — Segment 16C PR 1.

Translates ``AuditLogRow`` service rows into the dataclass shape
the audit-log child page template iterates over, plus the
keyset-pagination cursor wiring.

Page size + cursor semantics:

- Default page size 50 (locked into the route signature; the
  view adapter accepts whatever the route hands it).
- Newer-first (``AuditEvent.id DESC``). The first row's ``id``
  is irrelevant to the next page; the **last** row's ``id`` is
  the cursor for the next-page link. The viewer renders a
  "Next" anchor only when ``len(rows) == limit`` — the cheap
  approximation for "there might be more."
- "Prev" navigation is intentionally omitted in PR 1 because
  backward cursors require a second query shape; bookmarks +
  browser back are the temporary substitute. PR 2 (filter
  strip) revisits if operator feedback wants it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.audit import AuditLogRow

__all__ = [
    "AuditLogRowsContext",
    "AuditLogTableRow",
    "build_audit_log_rows",
]


@dataclass(frozen=True)
class AuditLogTableRow:
    """One audit-log row as the template renders it.

    Mirrors the CSV exporter's 8-column projection. Strings are
    pre-formatted (datetime → ISO 8601 UTC, missing actor → "")
    so the template stays markup-only.
    """

    id: int
    event_type: str
    severity: str
    summary: str
    actor_email: str
    correlation_id: str
    created_at_iso: str
    detail_json: str


@dataclass(frozen=True)
class AuditLogRowsContext:
    rows: list[AuditLogTableRow]
    next_cursor: int | None
    """Last row's ``id`` when the page filled to ``limit``; ``None``
    means there's no next page."""


def build_audit_log_rows(
    rows: list[AuditLogRow],
    *,
    limit: int,
) -> AuditLogRowsContext:
    table_rows = [
        AuditLogTableRow(
            id=row.id,
            event_type=row.event_type,
            severity=row.severity,
            summary=row.summary,
            actor_email=row.actor_email or "",
            correlation_id=row.correlation_id or "",
            created_at_iso=_isoformat_utc(row.created_at),
            detail_json=_json_or_empty(row.detail),
        )
        for row in rows
    ]
    # Cheap "is there more?" heuristic: full page ⇒ probably more.
    # If the underlying table holds exactly ``limit`` more-recent
    # events for the session, the next page renders empty and the
    # operator sees "No older events." False positive is one
    # wasted click; the alternative is a second COUNT query.
    next_cursor = (
        table_rows[-1].id
        if table_rows and len(table_rows) == limit
        else None
    )
    return AuditLogRowsContext(rows=table_rows, next_cursor=next_cursor)


def _isoformat_utc(value: object) -> str:
    if value is None:
        return ""
    from datetime import datetime, timezone

    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()  # type: ignore[union-attr]


def _json_or_empty(value: object) -> str:
    if value is None:
        return ""
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)
