"""Audit log viewer — Segment 16C PR 1 + PR 2.

Translates ``AuditLogRow`` service rows into the dataclass shape
the audit-log child page template iterates over, plus the
keyset-pagination cursor wiring + filter-strip form state.

Page size + cursor semantics:

- Default page size 50 (locked into the route signature; the
  view adapter accepts whatever the route hands it).
- Newer-first (``AuditEvent.id DESC``). The first row's ``id``
  is irrelevant to the next page; the **last** row's ``id`` is
  the cursor for the next-page link. The viewer renders a
  "Next" anchor only when ``len(rows) == limit`` — the cheap
  approximation for "there might be more."
- "Prev" navigation is intentionally omitted because backward
  cursors require a second query shape; bookmarks + browser
  back are the substitute.

Filter strip semantics (PR 2):

- Filter state lives in URL query params so bookmarks +
  back/forward stay deterministic.
- ``event_type`` and ``severity`` use repeated query params
  (`?event_type=A&event_type=B`) — the natural HTML form
  shape for `<select multiple>` and checkbox lists.
- ``actor`` is a single email string (typeahead-picked).
- ``from`` / ``to`` are ISO date strings (``YYYY-MM-DD``).
- Empty / missing slots are no-ops; multiple slots AND.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from app.services.audit import AuditFilters, AuditLogRow
from app.services.date_formatting import format_datetime

__all__ = [
    "AuditDetailChangeRow",
    "AuditDetailKVRow",
    "AuditDetailRender",
    "AuditDetailSection",
    "AuditDetailSetChanges",
    "AuditLogFilterFormContext",
    "AuditLogRowsContext",
    "AuditLogTableRow",
    "build_audit_log_filter_form",
    "build_audit_log_rows",
    "filters_querystring",
    "format_audit_detail",
    "parse_audit_log_filters",
]


_VALID_SEVERITIES: tuple[str, ...] = ("info", "warning", "error")


@dataclass(frozen=True)
class AuditLogTableRow:
    """One audit-log row as the template renders it.

    Mirrors the CSV exporter's 8-column projection. Strings are
    pre-formatted (datetime → ISO 8601 UTC, missing actor → "")
    so the template stays markup-only. ``detail`` is the
    structured pretty-printer render (Segment 16C PR 3);
    ``detail_json`` stays available as the always-on raw payload
    fallback inside the expander.
    """

    id: int
    event_type: str
    severity: str
    summary: str
    actor_email: str
    correlation_id: str
    created_at_display: str
    detail_json: str
    detail: AuditDetailRender


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
            # Intentionally UTC (no display zone): the audit log is a
            # UTC-based forensic surface — its date filter and the
            # "When (UTC)" column header say so. Don't localise.
            created_at_display=format_datetime(row.created_at),
            detail_json=_json_or_empty(row.detail),
            detail=format_audit_detail(row.event_type, row.detail),
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


@dataclass(frozen=True)
class AuditLogFilterFormContext:
    """Render-state for the filter strip on the audit-log child page.

    Pre-formatted strings + per-option flags so the template stays
    markup-only.
    """

    event_type_options: list[tuple[str, bool]]
    severity_options: list[tuple[str, bool]]
    actor_options: list[str]
    actor_email_value: str
    created_from_value: str
    created_to_value: str
    cleared_url: str
    download_csv_url: str
    is_active: bool


def parse_audit_log_filters(
    *,
    event_types: list[str] | None,
    severities: list[str] | None,
    actor: str | None,
    from_: str | None,
    to: str | None,
) -> AuditFilters:
    """Build an ``AuditFilters`` from raw query-string inputs.

    Unknown event-type or severity tokens silently drop — the
    operator can't filter on event types that don't exist, and
    propagating a 400 here would be a UX papercut on a stale
    bookmark. Date parsing tolerates ``""`` (treats as None) but
    fails-loud on malformed non-empty strings via
    ``date.fromisoformat`` so a bad bookmark surfaces the typo.
    """
    from app.services.audit import EVENT_SCHEMAS

    valid_event_types = set(EVENT_SCHEMAS.keys())
    event_type_tuple = tuple(
        et for et in (event_types or []) if et in valid_event_types
    )
    severity_tuple = tuple(
        s for s in (severities or []) if s in _VALID_SEVERITIES
    )
    actor_email = (actor or "").strip() or None
    created_from = _parse_date(from_)
    created_to = _parse_date(to)
    return AuditFilters(
        event_types=event_type_tuple,
        severities=severity_tuple,
        actor_email=actor_email,
        created_from=created_from,
        created_to=created_to,
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def build_audit_log_filter_form(
    filters: AuditFilters,
    *,
    distinct_actor_emails: list[str],
    base_url: str,
    csv_base_url: str,
) -> AuditLogFilterFormContext:
    """Translate the active filter set + the per-session actor pool
    into the dataclass the template iterates over.

    ``base_url`` is the canonical viewer path (without query
    string); the "Clear filters" link resets to it. ``csv_base_url``
    is the matching CSV-route path; the Download button carries
    the same filter query string so the spreadsheet honours the
    filter strip.
    """
    from app.services.audit import EVENT_SCHEMAS

    event_type_options = sorted(
        ((et, et in filters.event_types) for et in EVENT_SCHEMAS.keys()),
        key=lambda pair: pair[0],
    )
    severity_options = [
        (sev, sev in filters.severities) for sev in _VALID_SEVERITIES
    ]

    filter_qs = _filters_querystring(filters)
    csv_url = (
        f"{csv_base_url}?{filter_qs}" if filter_qs else csv_base_url
    )
    return AuditLogFilterFormContext(
        event_type_options=event_type_options,
        severity_options=severity_options,
        actor_options=distinct_actor_emails,
        actor_email_value=filters.actor_email or "",
        created_from_value=(
            filters.created_from.isoformat() if filters.created_from else ""
        ),
        created_to_value=(
            filters.created_to.isoformat() if filters.created_to else ""
        ),
        cleared_url=base_url,
        download_csv_url=csv_url,
        is_active=filters.is_active,
    )


def _filters_querystring(filters: AuditFilters) -> str:
    """Encode an ``AuditFilters`` into a stable URL query string.

    Uses ``urlencode(doseq=True)`` so multi-value slots
    (``event_types`` / ``severities``) render as repeated params
    — matching how the template's ``<select multiple>`` + checkbox
    list submit naturally."""
    pairs: list[tuple[str, str]] = []
    for et in filters.event_types:
        pairs.append(("event_type", et))
    for sev in filters.severities:
        pairs.append(("severity", sev))
    if filters.actor_email:
        pairs.append(("actor", filters.actor_email))
    if filters.created_from:
        pairs.append(("from", filters.created_from.isoformat()))
    if filters.created_to:
        pairs.append(("to", filters.created_to.isoformat()))
    return urlencode(pairs)


def filters_querystring(filters: AuditFilters) -> str:
    """Public alias so route layers can build pagination URLs that
    carry the filter state forward."""
    return _filters_querystring(filters)


# ---------------------------------------------------------------------------
# Detail-JSON pretty-printer (Segment 16C PR 3)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditDetailKVRow:
    """One key/value row for the snapshot / counts / refs / context
    payload renderers."""

    label: str
    value: str


@dataclass(frozen=True)
class AuditDetailChangeRow:
    """A single field-level change in the ``changes`` envelope."""

    label: str
    before: str
    after: str


@dataclass(frozen=True)
class AuditDetailSetChanges:
    """Pre-formatted lists for the ``set_changes`` envelope."""

    added: list[str]
    removed: list[str]
    updated: list[str]


@dataclass(frozen=True)
class AuditDetailSection:
    """One labelled section of a rendered audit-event detail.

    The template branches on ``kind`` to choose the right markup.
    Empty payload slots collapse out before rendering — every
    section in ``AuditDetailRender.sections`` has content.
    """

    kind: str
    """One of: ``"changes"`` / ``"snapshot"`` / ``"counts"`` /
    ``"set_changes"`` / ``"reason"`` / ``"refs"`` / ``"context"`` /
    ``"fallback"``."""

    label: str
    kv_rows: tuple[AuditDetailKVRow, ...] = ()
    change_rows: tuple[AuditDetailChangeRow, ...] = ()
    set_changes: AuditDetailSetChanges | None = None
    text: str = ""


@dataclass(frozen=True)
class AuditDetailRender:
    sections: tuple[AuditDetailSection, ...]
    raw_json: str
    is_empty: bool


_PAYLOAD_KEYS: tuple[str, ...] = ("changes", "snapshot", "counts", "set_changes")
_ORTHOGONAL_KEYS: tuple[str, ...] = ("reason", "refs", "context")
_IDENTITY_KEYS: tuple[str, ...] = ("session_id", "session_code")


def format_audit_detail(
    event_type: str,
    detail: dict[str, object] | None,
) -> AuditDetailRender:
    """Translate one canonical envelope into structured sections
    the template can iterate over.

    Recognises the four canonical payload envelopes
    (``changes`` / ``snapshot`` / ``counts`` / ``set_changes``) plus
    the three orthogonal slots (``reason`` / ``refs`` / ``context``).
    Identity slots (``session_id`` / ``session_code``) drop out —
    they're already first-class columns on the row.

    Unknown / non-canonical detail (legacy rows from pre-11K era,
    or new envelopes added without renderer support) falls through
    to a sorted-keys ``<dl>`` so the operator can still inspect
    the payload.
    """
    import json

    if not detail:
        return AuditDetailRender(sections=(), raw_json="", is_empty=True)

    raw_json = json.dumps(detail, separators=(",", ":"), sort_keys=True)
    sections: list[AuditDetailSection] = []

    payload_rendered = False
    if isinstance(detail.get("changes"), dict):
        sections.append(_render_changes(detail["changes"]))
        payload_rendered = True
    if isinstance(detail.get("snapshot"), dict):
        sections.append(_render_kv("snapshot", "Snapshot", detail["snapshot"]))
        payload_rendered = True
    if isinstance(detail.get("counts"), dict):
        sections.append(_render_kv("counts", "Counts", detail["counts"]))
        payload_rendered = True
    if isinstance(detail.get("set_changes"), dict):
        sections.append(_render_set_changes(detail["set_changes"]))
        payload_rendered = True

    if isinstance(detail.get("reason"), str):
        sections.append(
            AuditDetailSection(
                kind="reason", label="Reason", text=detail["reason"]
            )
        )
    if isinstance(detail.get("refs"), dict):
        sections.append(_render_kv("refs", "Refs", detail["refs"]))
    if isinstance(detail.get("context"), dict):
        sections.append(_render_kv("context", "Context", detail["context"]))

    # Fallback: any keys the renderer didn't recognise (legacy
    # pre-11K shapes, or unrecognised additions) — render them all
    # as a single "Other" section so the operator can still see
    # the payload.
    recognised = set(_PAYLOAD_KEYS) | set(_ORTHOGONAL_KEYS) | set(_IDENTITY_KEYS)
    unknown = {k: v for k, v in detail.items() if k not in recognised}
    if unknown:
        sections.append(_render_kv("fallback", "Other", unknown))
    # Legacy detail with no recognised envelope and no identity
    # slots — render the whole thing as fallback so the operator
    # isn't left with an empty expander.
    if not payload_rendered and not sections:
        sections.append(_render_kv("fallback", "Detail", detail))

    return AuditDetailRender(
        sections=tuple(sections),
        raw_json=raw_json,
        is_empty=False,
    )


def _render_changes(changes: dict) -> AuditDetailSection:
    rows = tuple(
        AuditDetailChangeRow(
            label=field,
            before=_format_scalar(pair[0] if len(pair) > 0 else None),
            after=_format_scalar(pair[1] if len(pair) > 1 else None),
        )
        for field, pair in sorted(changes.items())
        if isinstance(pair, list)
    )
    return AuditDetailSection(
        kind="changes",
        label="Changes",
        change_rows=rows,
    )


def _render_kv(kind: str, label: str, data: dict) -> AuditDetailSection:
    rows = tuple(
        AuditDetailKVRow(label=k, value=_format_scalar(v))
        for k, v in sorted(data.items(), key=lambda kv: str(kv[0]))
    )
    return AuditDetailSection(kind=kind, label=label, kv_rows=rows)


def _render_set_changes(data: dict) -> AuditDetailSection:
    import json

    def _fmt_items(items: object) -> list[str]:
        if not isinstance(items, list):
            return []
        return [
            json.dumps(item, separators=(",", ":"), sort_keys=True)
            if not isinstance(item, str)
            else item
            for item in items
        ]

    return AuditDetailSection(
        kind="set_changes",
        label="Set changes",
        set_changes=AuditDetailSetChanges(
            added=_fmt_items(data.get("added", [])),
            removed=_fmt_items(data.get("removed", [])),
            updated=_fmt_items(data.get("updated", [])),
        ),
    )


def _format_scalar(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _json_or_empty(value: object) -> str:
    if value is None:
        return ""
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)
