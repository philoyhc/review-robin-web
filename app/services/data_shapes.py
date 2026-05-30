"""Data shaper saved-shape service.

CRUD helpers for the ``data_shapes`` table — operator-saved
Data shaper shapes that round-trip through the Extract data
tab's Data shaper card. Per the wiring decisions in
``spec/extract_data.md`` "Wiring decisions (resolved
2026-05-29)".

Validation enforced server-side:

* ``axis`` must be one of ``reviewer`` / ``reviewee``.
* ``name`` non-empty after trim.
* ``column_chip_slots`` non-empty list of strings.
* ``instrument_id`` (when set) must point at an instrument
  on the same session.
* ``response_field_id`` (when set) must point at a response
  field on the chosen instrument. If both are null the
  shape applies session-wide.

Database-level constraints handle the rest: ``UNIQUE
(session_id, name)`` blocks duplicate names per session;
CASCADE FKs drop the shape when its anchor session /
instrument / response field disappears.

Audit events emitted:

* ``session.data_shape_saved`` on ``create_shape`` /
  ``update_shape``.
* ``session.data_shape_deleted`` on ``delete_shape``.
* (``session.data_shape_extracted`` lands with the file-gen
  route in PR 4.)
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import audit

__all__ = [
    "DataShapeValidationError",
    "DataShapeNameConflictError",
    "VALID_AXES",
    "VALID_SELF_REVIEW_HANDLING",
    "DEFAULT_SELF_REVIEW_HANDLING",
    "list_shapes",
    "get_shape",
    "create_shape",
    "update_shape",
    "delete_shape",
]


VALID_AXES: frozenset[str] = frozenset({"reviewer", "reviewee"})
# Per-shape Self-review handling chip state — PR B of the chip
# slice per ``guide/extract_data.md`` § *Self-review handling*.
VALID_SELF_REVIEW_HANDLING: frozenset[str] = frozenset(
    {"include_self", "exclude_self", "both"}
)
DEFAULT_SELF_REVIEW_HANDLING = "include_self"


class DataShapeValidationError(ValueError):
    """Raised when one or more fields on a save attempt fail
    server-side validation.

    The route layer maps this to a 422 with the message
    surfaced inline next to the offending input.
    """


class DataShapeNameConflictError(DataShapeValidationError):
    """Raised specifically when a save attempt would violate
    the ``UNIQUE (session_id, name)`` constraint. Split out
    so the route can surface a targeted "name already in
    use" hint on the name input rather than a generic
    validation error."""


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #


def list_shapes(
    db: Session, review_session: ReviewSession
) -> list[DataShape]:
    """Every shape on ``review_session``, sorted by name for
    stable rendering on the page."""
    return list(
        db.execute(
            select(DataShape)
            .where(DataShape.session_id == review_session.id)
            .order_by(DataShape.name)
        ).scalars()
    )


def get_shape(
    db: Session, review_session: ReviewSession, shape_id: int
) -> DataShape | None:
    """Return the shape with ``shape_id`` if it lives on
    ``review_session``; ``None`` otherwise. Used by the
    Download route + the PATCH / DELETE routes to confirm the
    shape belongs to the operator's session before mutating
    or extracting it."""
    return db.execute(
        select(DataShape).where(
            DataShape.id == shape_id,
            DataShape.session_id == review_session.id,
        )
    ).scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _validate(
    db: Session,
    *,
    review_session: ReviewSession,
    name: str,
    axis: str,
    instrument_id: int | None,
    response_field_id: int | None,
    column_chip_slots: list[str],
    self_review_handling: str,
) -> tuple[Instrument | None, InstrumentResponseField | None]:
    """Server-side validation per the wiring decisions.

    Raises ``DataShapeValidationError`` on any failure. Returns
    the resolved ``Instrument`` / ``InstrumentResponseField``
    objects (or ``None`` for either) so the caller doesn't have
    to re-query.
    """
    if not name or not name.strip():
        raise DataShapeValidationError("Shape name is required.")
    if axis not in VALID_AXES:
        raise DataShapeValidationError(
            f"Axis must be one of {sorted(VALID_AXES)}, got {axis!r}."
        )
    if not column_chip_slots:
        raise DataShapeValidationError(
            "A shape needs at least one column chip selected."
        )
    if not all(isinstance(s, str) and s for s in column_chip_slots):
        raise DataShapeValidationError(
            "Column chip slots must be non-empty strings."
        )
    if self_review_handling not in VALID_SELF_REVIEW_HANDLING:
        raise DataShapeValidationError(
            f"Self-review handling must be one of "
            f"{sorted(VALID_SELF_REVIEW_HANDLING)}, got "
            f"{self_review_handling!r}."
        )

    instrument: Instrument | None = None
    response_field: InstrumentResponseField | None = None

    if instrument_id is not None:
        instrument = db.execute(
            select(Instrument).where(
                Instrument.id == instrument_id,
                Instrument.session_id == review_session.id,
            )
        ).scalar_one_or_none()
        if instrument is None:
            raise DataShapeValidationError(
                "Instrument does not belong to this session."
            )

    if response_field_id is not None:
        if instrument is None:
            raise DataShapeValidationError(
                "Response field requires an instrument."
            )
        response_field = db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.id == response_field_id,
                InstrumentResponseField.instrument_id == instrument.id,
            )
        ).scalar_one_or_none()
        if response_field is None:
            raise DataShapeValidationError(
                "Response field does not belong to the selected instrument."
            )

    return instrument, response_field


def _audit_snapshot(shape: DataShape) -> dict[str, Any]:
    """Compose the snapshot envelope payload for a shape —
    same shape on save / delete so the audit log can
    reconstruct what was in the row before the change.

    ``column_chip_slots`` is stored as a JSON string; the
    snapshot decodes it back to a list so the audit detail
    reads naturally.
    """
    try:
        slots = json.loads(shape.column_chip_slots)
    except (json.JSONDecodeError, TypeError):
        slots = shape.column_chip_slots
    return {
        "name": shape.name,
        "axis": shape.axis,
        "instrument_id": shape.instrument_id,
        "response_field_id": shape.response_field_id,
        "column_chip_slots": slots,
        "self_review_handling": shape.self_review_handling,
    }


# --------------------------------------------------------------------------- #
# Mutators
# --------------------------------------------------------------------------- #


def create_shape(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User | None,
    name: str,
    axis: str,
    instrument_id: int | None,
    response_field_id: int | None,
    column_chip_slots: list[str],
    self_review_handling: str = DEFAULT_SELF_REVIEW_HANDLING,
    correlation_id: str | None = None,
) -> DataShape:
    """Persist a new shape on ``review_session`` + emit the
    ``session.data_shape_saved`` audit event.

    Raises ``DataShapeValidationError`` (or its
    ``DataShapeNameConflictError`` subclass) on validation
    failure so the route layer can surface the message
    inline.
    """
    name = name.strip()
    _validate(
        db,
        review_session=review_session,
        name=name,
        axis=axis,
        instrument_id=instrument_id,
        response_field_id=response_field_id,
        column_chip_slots=column_chip_slots,
        self_review_handling=self_review_handling,
    )

    shape = DataShape(
        session_id=review_session.id,
        name=name,
        axis=axis,
        instrument_id=instrument_id,
        response_field_id=response_field_id,
        column_chip_slots=json.dumps(column_chip_slots),
        self_review_handling=self_review_handling,
        created_by_user_id=actor.id if actor else None,
    )
    db.add(shape)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DataShapeNameConflictError(
            f"A shape named {name!r} already exists on this session."
        ) from exc

    audit.write_event(
        db,
        event_type="session.data_shape_saved",
        summary=(
            f"Saved Data shape {name!r} on session "
            f"{review_session.code}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(_audit_snapshot(shape)),
        refs={"shape_id": shape.id},
        correlation_id=correlation_id,
    )
    return shape


def update_shape(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User | None,
    shape: DataShape,
    name: str,
    axis: str,
    instrument_id: int | None,
    response_field_id: int | None,
    column_chip_slots: list[str],
    self_review_handling: str = DEFAULT_SELF_REVIEW_HANDLING,
    correlation_id: str | None = None,
) -> DataShape:
    """Update an existing shape in place + re-emit the
    ``session.data_shape_saved`` audit event.

    ``shape`` is expected to already belong to
    ``review_session`` (the route resolves it via
    ``get_shape``).
    """
    name = name.strip()
    _validate(
        db,
        review_session=review_session,
        name=name,
        axis=axis,
        instrument_id=instrument_id,
        response_field_id=response_field_id,
        column_chip_slots=column_chip_slots,
        self_review_handling=self_review_handling,
    )

    shape.name = name
    shape.axis = axis
    shape.instrument_id = instrument_id
    shape.response_field_id = response_field_id
    shape.column_chip_slots = json.dumps(column_chip_slots)
    shape.self_review_handling = self_review_handling
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DataShapeNameConflictError(
            f"A shape named {name!r} already exists on this session."
        ) from exc

    audit.write_event(
        db,
        event_type="session.data_shape_saved",
        summary=(
            f"Updated Data shape {name!r} on session "
            f"{review_session.code}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(_audit_snapshot(shape)),
        refs={"shape_id": shape.id},
        correlation_id=correlation_id,
    )
    return shape


def delete_shape(
    db: Session,
    *,
    review_session: ReviewSession,
    actor: User | None,
    shape: DataShape,
    correlation_id: str | None = None,
) -> None:
    """Delete ``shape`` + emit the
    ``session.data_shape_deleted`` audit event. The snapshot
    payload mirrors what was in the row pre-delete so the
    audit log can reconstruct it later."""
    snapshot = _audit_snapshot(shape)
    shape_id = shape.id
    shape_name = shape.name
    db.delete(shape)
    db.flush()
    audit.write_event(
        db,
        event_type="session.data_shape_deleted",
        summary=(
            f"Deleted Data shape {shape_name!r} from session "
            f"{review_session.code}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(snapshot),
        refs={"shape_id": shape_id},
        correlation_id=correlation_id,
    )
