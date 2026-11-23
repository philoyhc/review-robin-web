"""Apply Desk's audit trail (segment AD2A; ruling 74): Review Robin's
envelope (`spec/architecture.md`, "Audit-event detail schema"), copied,
since packages import nothing of `app`.

Every mutating service writes one `AuditEvent` through `write_event` with
exactly one payload envelope (`changes`, `snapshot`, `counts` or
`set_changes`) and any of the orthogonal slots `reason`, `refs` (integer
keys ending in `_id`) and `context` (scalars). Each event type's allowed
keys are registered in `EVENT_SCHEMAS`: a new emitter registers its type
there. Under pytest a detail that breaks its schema raises; otherwise the
row writes through and the breach is logged by name, never by value.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, NonNegativeInt, ValidationError, field_validator
from sqlalchemy.orm import Session

from applydesk.models import AuditEvent, Exercise, Person

_log = logging.getLogger(__name__)


def _serialise(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class AuditPayload:
    """One of the four envelopes."""

    def to_dict(self) -> dict[str, Any]:  # pragma: no cover - overridden
        raise NotImplementedError


@dataclass(frozen=True)
class ChangesPayload(AuditPayload):
    pairs: dict[str, list[Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"changes": {k: [_serialise(v[0]), _serialise(v[1])] for k, v in self.pairs.items()}}


@dataclass(frozen=True)
class SnapshotPayload(AuditPayload):
    fields: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot": {k: _serialise(v) for k, v in self.fields.items()}}


@dataclass(frozen=True)
class CountsPayload(AuditPayload):
    values: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {"counts": dict(self.values)}


@dataclass(frozen=True)
class SetChangesPayload(AuditPayload):
    added: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    removed: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    updated: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_changes": {
                "added": list(self.added),
                "removed": list(self.removed),
                "updated": list(self.updated),
            }
        }


def changes(pairs: dict[str, list[Any]]) -> ChangesPayload:
    return ChangesPayload(pairs=pairs)


def snapshot(fields: dict[str, Any]) -> SnapshotPayload:
    return SnapshotPayload(fields=fields)


def counts(**values: int) -> CountsPayload:
    return CountsPayload(values=values)


def set_changes(
    *,
    added: list[dict[str, Any]] | None = None,
    removed: list[dict[str, Any]] | None = None,
    updated: list[dict[str, Any]] | None = None,
) -> SetChangesPayload:
    return SetChangesPayload(added=added or [], removed=removed or [], updated=updated or [])


@dataclass(frozen=True)
class EventSchema:
    """The top-level keys an event type's detail may carry."""

    allows: frozenset[str]


_EXERCISE = frozenset({"exercise_public_id"})

#: Every event type Apply Desk emits, with the keys its detail may carry.
#: `test_every_emitted_event_type_is_registered`
#: (`applydesk/tests/test_people_and_operators.py`) pins this to the emitters.
EVENT_SCHEMAS: dict[str, EventSchema] = {
    # People (applydesk/people.py): made, and bound to an account.
    "person.created": EventSchema(frozenset({"snapshot", "refs", "context"})),
    "person.bound": EventSchema(frozenset({"snapshot", "refs", "context"})),
    "person.signed_in": EventSchema(frozenset({"refs"})),
    # The allowlist (ruling 75), kept by the platform super-admin.
    "person.admitted": EventSchema(frozenset({"refs"})),
    "person.revoked": EventSchema(frozenset({"refs", "reason"})),
    # Admins (segment AD2M), made and unmade by the super-admin.
    "person.promoted": EventSchema(frozenset({"refs"})),
    "person.demoted": EventSchema(frozenset({"refs"})),
    # An exercise's operators (ruling 73).
    "exercise.created": EventSchema(_EXERCISE | {"refs"}),
    "exercise.operator_added": EventSchema(_EXERCISE | {"refs", "context"}),
    "exercise.operator_removed": EventSchema(_EXERCISE | {"refs"}),
    "exercise.ownership_handed_over": EventSchema(_EXERCISE | {"refs"}),
    "exercise.owner_added": EventSchema(_EXERCISE | {"refs"}),
    "exercise.owner_demoted": EventSchema(_EXERCISE | {"refs", "context"}),
    "exercise.operator_left": EventSchema(_EXERCISE | {"refs"}),
    # An exercise's settings recorded from the sample (the seed, AD2B).
    "exercise.settings_recorded": EventSchema(_EXERCISE | {"snapshot"}),
    "exercise.details_changed": EventSchema(_EXERCISE | {"changes", "context"}),
    # Segment AD2C: Process saved whole, replacing the draft.
    "exercise.process_saved": EventSchema(_EXERCISE | {"counts", "context"}),
    # Segment AD2E: Panels saved whole, or a page's new panels adopted.
    "exercise.panels_saved": EventSchema(_EXERCISE | {"counts", "context"}),
    # Segment AD2D: Form saved whole.
    "exercise.form_saved": EventSchema(_EXERCISE | {"counts", "context"}),
    # Candidates (ruling 77): added by search or CSV, removed in the list.
    # The form's moves, Home's next step (ruling 76).
    "exercise.form_opened": EventSchema(_EXERCISE),
    # A published stage reverted to draft by a Process save (ruling 35).
    "exercise.stage_reverted": EventSchema(_EXERCISE | {"refs", "reason"}),
    "exercise.form_closed": EventSchema(_EXERCISE),
    "candidate.added": EventSchema(_EXERCISE | {"refs", "context"}),
    "candidate.removed": EventSchema(_EXERCISE | {"refs"}),
    "exercise.archived": EventSchema(_EXERCISE),
    "exercise.restored": EventSchema(_EXERCISE),
    "exercise.deleted": EventSchema(_EXERCISE),
    "exercise.duplicated": EventSchema(_EXERCISE | {"refs"}),
    # An Admin or the super-admin taking up an exercise as an Owner (AD2M).
    "exercise.adopted": EventSchema(_EXERCISE | {"refs", "context"}),
}


class _SetChangesShape(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []


class _CanonicalDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_public_id: str | None = None
    changes: dict[str, list[Any]] | None = None
    snapshot: dict[str, Any] | None = None
    counts: dict[str, NonNegativeInt] | None = None
    set_changes: _SetChangesShape | None = None
    reason: str | None = None
    refs: dict[str, int] | None = None
    context: Mapping[str, str | int | bool] | None = None

    @field_validator("refs")
    @classmethod
    def _ref_keys_end_in_id(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is not None:
            bad = sorted(k for k in value if not k.endswith("_id"))
            if bad:
                raise ValueError(f"refs keys must end in _id: {bad}")
        return value


class AuditDetailValidationError(ValueError):
    """A detail that breaks its event type's schema. `loggable` names the
    breach without any value from the payload."""

    def __init__(self, event_type: str, message: str, loggable: str) -> None:
        super().__init__(f"{event_type}: {message}")
        self.event_type = event_type
        self.loggable = f"{event_type}: {loggable}"


def validate_detail(event_type: str, detail: dict[str, Any]) -> None:
    try:
        _CanonicalDetail.model_validate(detail)
    except ValidationError as exc:
        where = sorted({(str(e["loc"][0]) if e["loc"] else "", e["type"]) for e in exc.errors()})
        raise AuditDetailValidationError(
            event_type, f"shape: {where!r}", f"shape: {where!r}"
        ) from exc
    schema = EVENT_SCHEMAS.get(event_type)
    if schema is None:
        raise AuditDetailValidationError(
            event_type, "not registered in EVENT_SCHEMAS", "not registered"
        )
    extra = sorted(set(detail) - schema.allows)
    if extra:
        raise AuditDetailValidationError(
            event_type, f"keys {extra!r} not allowed", f"keys {extra!r} not allowed"
        )


def _strict() -> bool:
    """Strict under pytest, so drift fails a test (as Review Robin's)."""
    return "PYTEST_CURRENT_TEST" in os.environ


def write_event(
    session: Session,
    *,
    event_type: str,
    actor: Person | None,
    exercise: Exercise | None = None,
    payload: AuditPayload | None = None,
    reason: str | None = None,
    refs: dict[str, int] | None = None,
    context: Mapping[str, str | int | bool] | None = None,
) -> AuditEvent:
    """Add one audit row to `session` (flushed, not committed: the
    caller's transaction holds it with the change it records)."""
    detail: dict[str, Any] = {}
    if exercise is not None:
        detail["exercise_public_id"] = exercise.public_id
    if payload is not None:
        detail.update(payload.to_dict())
    if reason is not None:
        detail["reason"] = reason
    if refs:
        detail["refs"] = dict(refs)
    if context:
        detail["context"] = dict(context)
    try:
        validate_detail(event_type, detail)
    except AuditDetailValidationError as exc:
        if _strict():
            raise
        # As Review Robin's (`app/services/audit.py`): the event and the
        # type as fields the host's JSON log keeps, never a payload value.
        _log.warning(
            "applydesk audit %s; written anyway",
            exc.loggable,
            extra={"event": "audit.detail_schema_violation", "event_type": event_type},
        )
    event = AuditEvent(
        event_type=event_type,
        actor_id=actor.id if actor is not None else None,
        exercise_id=exercise.id if exercise is not None else None,
        detail=detail,
    )
    session.add(event)
    session.flush()
    return event
