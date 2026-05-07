"""Audit event helpers.

`write_event` is the single emitter entrypoint; the typed
`audit.changes(...)` / `audit.snapshot(...)` / `audit.counts(...)`
/ `audit.set_changes(...)` payload constructors enforce the
canonical `detail` shape documented in
``spec/architecture.md`` "Audit-event detail schema".

The legacy ``detail=`` kwarg path is preserved during the
Segment 11K migration window and emits a ``DeprecationWarning``
when called from the test environment so drift surfaces in CI;
PR 8 of Segment 11K replaces the warning with a Pydantic
write-validation gate.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

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
