"""Audit event helpers.

`write_event` is the single emitter entrypoint; the typed
`audit.changes(...)` / `audit.snapshot(...)` / `audit.counts(...)`
/ `audit.set_changes(...)` payload constructors enforce the
canonical `detail` shape documented in
``spec/architecture.md`` "Audit-event detail schema".

Every emitted ``detail`` is validated against a per-event-type
schema in ``EVENT_SCHEMAS`` before the row is written. Under
``settings.audit_strict_mode`` (flipped on by ``tests/conftest.py``)
a shape violation raises ``AuditDetailValidationError``; in
production the violation logs a structured warning and the row
writes anyway — auditing is observability, and dropping audit
events because of a shape bug would hide the very mutations
we're auditing.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession


# --------------------------------------------------------------------------- #
# Payload envelopes
# --------------------------------------------------------------------------- #


class AuditPayload:
    """Marker base for the four canonical envelope dataclasses."""

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class ChangesPayload(AuditPayload):
    """`{"changes": {field: [old, new]}}` for scalar-key updates."""

    pairs: dict[str, list[Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"changes": {k: [_serialise(v[0]), _serialise(v[1])] for k, v in self.pairs.items()}}


@dataclass(frozen=True)
class SnapshotPayload(AuditPayload):
    """`{"snapshot": {col: value, ...}}` for full-state capture."""

    fields: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot": {k: _serialise(v) for k, v in self.fields.items()}}


@dataclass(frozen=True)
class CountsPayload(AuditPayload):
    """`{"counts": {label: int}}` for aggregate ops."""

    values: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {"counts": dict(self.values)}


@dataclass(frozen=True)
class SetChangesPayload(AuditPayload):
    """`{"set_changes": {"added": [...], "removed": [...], "updated": [...]}}`."""

    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    updated: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_changes": {
                "added": list(self.added),
                "removed": list(self.removed),
                "updated": list(self.updated),
            }
        }


def changes(pairs: dict[str, list[Any]]) -> ChangesPayload:
    """Wrap a `{field: [old, new]}` dict in the canonical envelope."""
    return ChangesPayload(pairs=pairs)


def snapshot(fields: dict[str, Any]) -> SnapshotPayload:
    """Wrap a column-mirror dict in the canonical envelope."""
    return SnapshotPayload(fields=fields)


def counts(**values: int) -> CountsPayload:
    """Wrap keyword count values in the canonical envelope."""
    return CountsPayload(values=values)


def set_changes(
    *,
    added: list[dict[str, Any]] | None = None,
    removed: list[dict[str, Any]] | None = None,
    updated: list[dict[str, Any]] | None = None,
) -> SetChangesPayload:
    """Wrap an added/removed/updated triple in the canonical envelope."""
    return SetChangesPayload(
        added=list(added) if added else [],
        removed=list(removed) if removed else [],
        updated=list(updated) if updated else [],
    )


# --------------------------------------------------------------------------- #
# write_event
# --------------------------------------------------------------------------- #


_LEGACY_SENTINEL: Any = object()


def write_event(
    db: Session,
    *,
    event_type: str,
    summary: str,
    actor_user_id: int | None = None,
    session: ReviewSession | None | object = _LEGACY_SENTINEL,
    session_id: int | None = None,
    severity: str = "info",
    payload: AuditPayload | None = None,
    reason: str | None = None,
    refs: dict[str, int] | None = None,
    context: dict[str, str | int | bool] | None = None,
    detail: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    """Write an `AuditEvent` row.

    Two calling styles overlap during the Segment 11K migration window.

    Canonical (post-11K, every new emitter): pass `session=` (the row
    or `None`) plus exactly one `payload=` envelope and any combination
    of `reason=` / `refs=` / `context=`. The helper composes the
    canonical ``detail`` shape and derives the FK column + identity
    slots from `session`.

    Legacy (pre-migration): pass `session_id=` (or omit) and `detail=`
    directly; the helper writes the dict as-is. Emits a
    ``DeprecationWarning`` under pytest so unmigrated callsites surface
    in CI.
    """
    using_canonical = (
        session is not _LEGACY_SENTINEL or payload is not None
        or reason is not None or refs is not None or context is not None
    )
    if using_canonical and detail is not None:
        raise TypeError(
            "audit.write_event: pass either `detail=` (legacy) "
            "or `payload=` / `reason=` / `refs=` / `context=` "
            "(canonical), not both"
        )

    if using_canonical:
        canonical_session = session if session is not _LEGACY_SENTINEL else None
        resolved_session_id, resolved_detail = _compose_canonical(
            session=canonical_session,
            payload=payload,
            reason=reason,
            refs=refs,
            context=context,
        )
        if canonical_session is None and session_id is not None:
            resolved_session_id = session_id
    else:
        if detail is not None and _is_test_env():
            warnings.warn(
                f"audit.write_event for {event_type!r} called via legacy "
                "detail= kwarg; migrate to payload= helpers per "
                "spec/architecture.md \"Audit-event detail schema\".",
                DeprecationWarning,
                stacklevel=2,
            )
        resolved_session_id = session_id
        resolved_detail = detail

    try:
        validate_detail(event_type, resolved_detail)
    except AuditDetailValidationError as exc:
        if _audit_strict_mode():
            raise
        warnings.warn(
            f"audit.write_event {exc}; writing the row anyway because "
            f"settings.audit_strict_mode is False",
            stacklevel=2,
        )

    event = AuditEvent(
        event_type=event_type,
        summary=summary,
        severity=severity,
        actor_user_id=actor_user_id,
        session_id=resolved_session_id,
        detail=resolved_detail,
        correlation_id=correlation_id,
    )
    db.add(event)
    db.flush()
    return event


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _compose_canonical(
    *,
    session: ReviewSession | None,
    payload: AuditPayload | None,
    reason: str | None,
    refs: dict[str, int] | None,
    context: dict[str, str | int | bool] | None,
) -> tuple[int | None, dict[str, Any] | None]:
    body: dict[str, Any] = {}
    if session is not None:
        body["session_id"] = session.id
        body["session_code"] = session.code

    if payload is not None:
        body.update(payload.to_dict())
    if reason is not None:
        body["reason"] = reason
    if refs:
        body["refs"] = dict(refs)
    if context:
        body["context"] = dict(context)

    column_session_id = session.id if session is not None else None
    detail = body if body else None
    return column_session_id, detail


def _serialise(value: Any) -> Any:
    """Coerce datetimes / dates to ISO-8601 strings; pass everything else through."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _is_test_env() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get(
        "_", ""
    )


# --------------------------------------------------------------------------- #
# Shape validation (Segment 11K PR 8)
# --------------------------------------------------------------------------- #


class AuditDetailValidationError(ValueError):
    """Raised when a written ``detail`` doesn't match the canonical
    envelope schema for its ``event_type``.

    Strict-mode-only by default — production lenient mode logs a
    structured warning and lets the write proceed (auditing is
    observability; dropping events would hide mutations).
    """

    def __init__(
        self, event_type: str, detail: dict[str, Any] | None, message: str
    ) -> None:
        super().__init__(f"{event_type}: {message}")
        self.event_type = event_type
        self.detail = detail


class _SetChangesShape(BaseModel):
    """Inner shape for the ``set_changes`` envelope."""

    model_config = ConfigDict(extra="forbid")
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []


class _CanonicalDetail(BaseModel):
    """Top-level structural shape of ``AuditEvent.detail``.

    ``extra="forbid"`` catches drift back into the pre-canonical
    idiosyncratic dicts (e.g. a top-level ``instrument_id`` would
    fail here — instrument IDs go in ``refs``). Each key carries
    its own value-shape validation; the per-event-type allowlist
    (``EVENT_SCHEMAS``) then narrows which keys may appear for a
    given emitter.
    """

    model_config = ConfigDict(extra="forbid")
    session_id: int | None = None
    session_code: str | None = None
    changes: dict[str, list[Any]] | None = None
    snapshot: dict[str, Any] | None = None
    counts: dict[str, int] | None = None
    set_changes: _SetChangesShape | None = None
    reason: str | None = None
    refs: dict[str, int] | None = None
    context: dict[str, str | int | bool] | None = None


@dataclass(frozen=True)
class EventSchema:
    """Per-event-type allowlist of canonical detail keys.

    ``allows`` is the set of top-level keys that may appear in
    ``detail`` for this event type. Present keys must be a subset
    of ``allows``; not all allowed keys need to appear (e.g.
    ``instrument.closed`` allows ``context`` for the deadline path
    but the manual path doesn't carry it).
    """

    allows: frozenset[str]


_IDENTITY: frozenset[str] = frozenset({"session_id", "session_code"})

# Registry of every event_type the codebase emits. Adding a new
# emitter requires adding its entry here so PR 8's validation gate
# can confirm the shape; ``test_every_event_type_has_a_schema``
# pins the registry to the actual emitters.
EVENT_SCHEMAS: dict[str, EventSchema] = {
    # PR 1 — session lifecycle
    "session.created": EventSchema(_IDENTITY | {"snapshot"}),
    "session.updated": EventSchema(_IDENTITY | {"changes"}),
    "session.deleted": EventSchema(frozenset({"snapshot"})),
    "session.validated": EventSchema(_IDENTITY | {"counts"}),
    "session.invalidated": EventSchema(_IDENTITY | {"reason"}),
    "session.activated": EventSchema(_IDENTITY | {"counts", "context"}),
    "session.reverted_to_draft": EventSchema(_IDENTITY | {"counts"}),
    "instrument.opened": EventSchema(_IDENTITY | {"refs"}),
    "instrument.closed": EventSchema(_IDENTITY | {"refs", "reason", "context"}),
    # PR 2 — instruments
    "response_type.added": EventSchema(_IDENTITY | {"snapshot"}),
    "response_type.updated": EventSchema(
        _IDENTITY | {"changes", "refs", "context"}
    ),
    "response_type.deleted": EventSchema(
        _IDENTITY | {"snapshot", "refs", "context"}
    ),
    "instrument.created": EventSchema(_IDENTITY | {"snapshot", "refs", "context"}),
    "instrument.deleted": EventSchema(_IDENTITY | {"snapshot", "refs"}),
    "instrument.display_field_added": EventSchema(
        _IDENTITY | {"snapshot", "refs"}
    ),
    "instrument.display_field_updated": EventSchema(
        _IDENTITY | {"changes", "refs", "context"}
    ),
    "instrument.display_field_deleted": EventSchema(
        _IDENTITY | {"snapshot", "refs", "context"}
    ),
    "instrument.display_field_moved": EventSchema(
        _IDENTITY | {"refs", "context"}
    ),
    "instrument.sort_fields_updated": EventSchema(
        _IDENTITY | {"changes", "refs"}
    ),
    "instrument.field_added": EventSchema(
        _IDENTITY | {"snapshot", "refs", "context"}
    ),
    "instrument.field_updated": EventSchema(
        _IDENTITY | {"changes", "refs", "context"}
    ),
    "instrument.field_deleted": EventSchema(
        _IDENTITY | {"snapshot", "refs", "context"}
    ),
    "instrument.fields_reordered": EventSchema(_IDENTITY | {"changes", "refs"}),
    "instrument.display_fields_saved": EventSchema(
        _IDENTITY | {"set_changes", "refs"}
    ),
    "instrument.response_fields_saved": EventSchema(
        _IDENTITY | {"set_changes", "refs"}
    ),
    "instrument.described": EventSchema(_IDENTITY | {"changes", "refs"}),
    "instrument.short_label_updated": EventSchema(
        _IDENTITY | {"changes", "refs"}
    ),
    "instruments.bulk_accepting_responses": EventSchema(
        _IDENTITY | {"set_changes", "context"}
    ),
    "instruments.bulk_visibility_when_closed": EventSchema(
        _IDENTITY | {"set_changes", "context"}
    ),
    # PR 3 — invitations
    "invitations.generated": EventSchema(_IDENTITY | {"set_changes"}),
    "invitation.regenerated": EventSchema(_IDENTITY | {"refs"}),
    "invitations.regenerated": EventSchema(_IDENTITY | {"set_changes"}),
    "invitation.sent": EventSchema(_IDENTITY | {"refs"}),
    "invitation.opened": EventSchema(_IDENTITY | {"refs"}),
    "reminders.sent": EventSchema(_IDENTITY | {"set_changes", "context"}),
    # PR 4 — responses
    "responses.saved": EventSchema(_IDENTITY | {"counts", "refs"}),
    "responses.submitted": EventSchema(_IDENTITY | {"counts", "refs"}),
    "responses.cleared": EventSchema(_IDENTITY | {"counts", "refs"}),
    "responses.deleted_all": EventSchema(_IDENTITY | {"counts"}),
    # PR 5 — assignments
    "assignments.generated": EventSchema(
        _IDENTITY | {"counts", "context", "refs"}
    ),
    "assignments.deleted_all": EventSchema(_IDENTITY | {"counts"}),
    "assignments.self_reviews_active_set": EventSchema(
        _IDENTITY | {"counts", "context"}
    ),
    # Segment 13A PR 5a — RuleSet library mutation events. Workspace-
    # scoped (no session identity), so the schema omits ``session_id``
    # / ``session_code`` from the allowed slot set.
    "rule_set.created": EventSchema(frozenset({"snapshot", "refs", "context"})),
    # Segment 13A PR 6 — in-place Save / Rename / Delete.
    "rule_set.updated": EventSchema(frozenset({"changes", "refs", "context"})),
    "rule_set.deleted": EventSchema(frozenset({"snapshot", "refs", "context"})),
    # PR 7 — settings
    "reviewers.imported": EventSchema(_IDENTITY | {"counts", "context"}),
    "reviewees.imported": EventSchema(_IDENTITY | {"counts", "context"}),
    "relationships.imported": EventSchema(_IDENTITY | {"counts", "context"}),
    "relationships.migrated_from_assignment_context": EventSchema(
        _IDENTITY | {"counts"}
    ),
    "reviewers.deleted_all": EventSchema(_IDENTITY | {"counts"}),
    "reviewees.deleted_all": EventSchema(_IDENTITY | {"counts"}),
    "relationships.deleted_all": EventSchema(_IDENTITY | {"counts"}),
    "operator_email_settings.updated": EventSchema(frozenset({"changes"})),
    "operator_email_settings.cleared": EventSchema(frozenset()),
    # Segment 15A Slice 1 — per-session friendly-label resolver mutations.
    "session_field_label.set": EventSchema(
        _IDENTITY | {"changes", "context"}
    ),
    "session_field_label.cleared": EventSchema(
        _IDENTITY | {"snapshot", "context"}
    ),
    "email_template.updated": EventSchema(_IDENTITY | {"changes", "context"}),
    "email_template.reset": EventSchema(_IDENTITY | {"changes", "context"}),
    # Segment 12A-1 — Extract Data card downloads (read-only).
    "session.settings_extracted": EventSchema(_IDENTITY | {"counts"}),
    "session.reviewers_extracted": EventSchema(_IDENTITY | {"counts"}),
    "session.reviewees_extracted": EventSchema(_IDENTITY | {"counts"}),
    "session.responses_extracted": EventSchema(_IDENTITY | {"counts"}),
    # Segment 12A-3 PR 1 — Relationships export.
    "session.relationships_extracted": EventSchema(_IDENTITY | {"counts"}),
    # Segment 12A-3 PR 3 — Settings importer.
    "session.settings_imported": EventSchema(_IDENTITY | {"counts"}),
    # Segment 12B PR 1 — Audit-events export.
    "session.audit_log_extracted": EventSchema(_IDENTITY | {"counts", "context"}),
    # Segment 16A PR 6 — workspace user-role management.
    # Workspace-scoped (no session identity); the actor is on the
    # audit row's ``actor_user_id`` slot, the target user goes
    # through ``refs.target_user_id``.
    "workspace.user_invited": EventSchema(frozenset({"snapshot", "refs"})),
    "workspace.operator_admitted": EventSchema(frozenset({"changes", "refs"})),
    "workspace.operator_revoked": EventSchema(frozenset({"changes", "refs"})),
    "workspace.user_removed": EventSchema(frozenset({"snapshot", "refs"})),
    "sys_admin.role_promoted": EventSchema(frozenset({"changes", "refs"})),
    "sys_admin.role_demoted": EventSchema(frozenset({"changes", "refs"})),
    # Segment 16B PR 2 — per-session owner management.
    # Session-scoped; carries ``refs.target_user_id`` for the
    # added / removed owner.
    "session.owner_added": EventSchema(_IDENTITY | {"snapshot", "refs"}),
    "session.owner_removed": EventSchema(_IDENTITY | {"snapshot", "refs"}),
}


def validate_detail(
    event_type: str, detail: dict[str, Any] | None
) -> None:
    """Raise ``AuditDetailValidationError`` if ``detail`` doesn't
    conform to the canonical schema for ``event_type``.

    ``detail = None`` (legitimately empty events) always passes.
    """
    if detail is None:
        return
    try:
        _CanonicalDetail.model_validate(detail)
    except ValidationError as exc:
        raise AuditDetailValidationError(
            event_type, detail, f"shape: {exc.errors()!r}"
        ) from exc

    schema = EVENT_SCHEMAS.get(event_type)
    if schema is None:
        raise AuditDetailValidationError(
            event_type,
            detail,
            f"event_type {event_type!r} is not registered in "
            f"EVENT_SCHEMAS in app/services/audit.py",
        )

    extra = set(detail.keys()) - schema.allows
    if extra:
        raise AuditDetailValidationError(
            event_type,
            detail,
            f"keys {sorted(extra)!r} are not allowed for event_type "
            f"{event_type!r}; allowed keys are {sorted(schema.allows)!r}",
        )


def _audit_strict_mode() -> bool:
    """True when shape violations should fail-loud.

    Tests flip the settings flag via ``tests/conftest.py`` so CI
    catches drift before deploy. Production stays lenient.
    """
    return bool(settings.audit_strict_mode)


# --------------------------------------------------------------------------- #
# Reader — Segment 16C PR 1 (per-session in-app audit log viewer)
#          + PR 2 (filter strip + filtered CSV download)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuditLogRow:
    """One row of the in-app audit log table.

    Mirrors the CSV exporter's 8-column projection
    (``app/services/extracts/audit_events_extract.py``) plus the
    primary key so the viewer can cursor on ``id DESC`` (newer
    first).
    """

    id: int
    event_type: str
    severity: str
    summary: str
    actor_email: str | None
    correlation_id: str | None
    created_at: datetime
    detail: dict[str, Any] | None


@dataclass(frozen=True)
class AuditFilters:
    """Filter set for the per-session audit log viewer (16C PR 2).

    Each slot is independent; empty / unset slots are no-ops.
    Multiple slots compose with AND. Empty-list semantics:
    ``event_types=[]`` and ``severities=[]`` both mean "no filter on
    this dimension" (matches the URL-param contract where an absent
    param leaves the dimension wide open). To match nothing, drop
    the dimension from the URL entirely — the viewer doesn't model
    "select zero options" because that's never useful.
    """

    event_types: tuple[str, ...] = ()
    severities: tuple[str, ...] = ()
    actor_email: str | None = None
    created_from: date | None = None
    created_to: date | None = None

    @property
    def is_active(self) -> bool:
        return bool(
            self.event_types
            or self.severities
            or self.actor_email
            or self.created_from
            or self.created_to
        )

    def as_audit_context(self) -> dict[str, str | int | bool]:
        """Serialise the active filter for the
        ``session.audit_log_extracted`` audit event's ``context``
        slot.

        Canonical ``context`` values are scalars only
        (``dict[str, str | int | bool]``) per the Segment 11K
        envelope spec. Multi-value slots (event_types,
        severities) flatten to comma-joined strings so they fit
        the scalar contract; round-trip back to lists at read
        time via ``.split(",")``. Inactive slots collapse out so
        the audit row stays compact.
        """
        out: dict[str, str | int | bool] = {}
        if self.event_types:
            out["event_types"] = ",".join(self.event_types)
        if self.severities:
            out["severities"] = ",".join(self.severities)
        if self.actor_email:
            out["actor_email"] = self.actor_email
        if self.created_from:
            out["created_from"] = self.created_from.isoformat()
        if self.created_to:
            out["created_to"] = self.created_to.isoformat()
        return out


def _apply_filters(stmt: Any, filters: AuditFilters | None, user_table: Any) -> Any:
    """Compose ``filters`` into ``stmt`` (a SELECT against
    ``AuditEvent`` + ``users.email`` via LEFT JOIN). Returns the
    augmented statement."""
    if filters is None or not filters.is_active:
        return stmt
    if filters.event_types:
        stmt = stmt.where(AuditEvent.event_type.in_(filters.event_types))
    if filters.severities:
        stmt = stmt.where(AuditEvent.severity.in_(filters.severities))
    if filters.actor_email:
        # Case-insensitive exact match — operators pick from a
        # typeahead populated with this session's distinct actor
        # emails, so substring search isn't useful here.
        from sqlalchemy import func as _func

        stmt = stmt.where(
            _func.lower(user_table.email) == filters.actor_email.lower()
        )
    if filters.created_from:
        from datetime import datetime as _dt, time as _time, timezone as _tz

        start = _dt.combine(filters.created_from, _time.min, tzinfo=_tz.utc)
        stmt = stmt.where(AuditEvent.created_at >= start)
    if filters.created_to:
        # Inclusive upper bound: include the whole "to" day.
        from datetime import datetime as _dt, time as _time, timedelta as _td, timezone as _tz

        end = _dt.combine(
            filters.created_to, _time.min, tzinfo=_tz.utc
        ) + _td(days=1)
        stmt = stmt.where(AuditEvent.created_at < end)
    return stmt


def list_events_for_session(
    db: Session,
    review_session: ReviewSession,
    *,
    cursor: int | None = None,
    limit: int = 50,
    filters: AuditFilters | None = None,
) -> list[AuditLogRow]:
    """Read up to ``limit`` ``audit_events`` rows for this session,
    newest first, with keyset pagination on ``id DESC``.

    The CSV exporter (``serialize_audit_events``) walks the table
    chronologically (``created_at ASC, id ASC``) because spreadsheet
    readers want oldest-first. The in-app viewer flips the order —
    the operator's first question is usually "what changed last?"
    Pagination cursors are the last visible row's ``id``; the next
    page asks for ``id < cursor``.

    The reader reuses the CSV exporter's LEFT-JOIN-``users``
    plumbing to surface the actor's email alongside each row.
    """
    from app.db.models import User as _User

    stmt = (
        select(AuditEvent, _User.email)
        .outerjoin(_User, _User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.session_id == review_session.id)
    )
    stmt = _apply_filters(stmt, filters, _User)
    if cursor is not None:
        stmt = stmt.where(AuditEvent.id < cursor)
    stmt = stmt.order_by(AuditEvent.id.desc()).limit(limit)
    return [
        AuditLogRow(
            id=event.id,
            event_type=event.event_type,
            severity=event.severity,
            summary=event.summary or "",
            actor_email=actor_email,
            correlation_id=event.correlation_id,
            created_at=event.created_at,
            detail=event.detail,
        )
        for event, actor_email in db.execute(stmt).all()
    ]


def list_distinct_actor_emails(
    db: Session, review_session: ReviewSession
) -> list[str]:
    """Distinct actor emails on this session's audit events, sorted.

    Drives the actor-email typeahead `<datalist>` on the filter
    strip. System-emitted events (no actor) collapse out of the
    result; the operator can't usefully filter on "no actor"
    anyway."""
    from app.db.models import User as _User

    stmt = (
        select(_User.email)
        .join(AuditEvent, AuditEvent.actor_user_id == _User.id)
        .where(AuditEvent.session_id == review_session.id)
        .where(_User.email.is_not(None))
        .distinct()
        .order_by(_User.email)
    )
    return [row[0] for row in db.execute(stmt).all()]
