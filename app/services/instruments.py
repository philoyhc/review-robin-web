from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ReviewSession,
    User,
)
from app.services.audit import write_event

DEFAULT_INSTRUMENT_NAME = "Default"

DEFAULT_RESPONSE_FIELDS: list[dict[str, Any]] = [
    {
        "field_key": "rating",
        "label": "Rating",
        "response_type": "integer",
        "required": True,
        "order": 1,
        "validation": {"min": 1, "max": 5},
    },
    {
        "field_key": "comments",
        "label": "Comments",
        "response_type": "long_text",
        "required": False,
        "order": 2,
        "validation": None,
    },
]

_DEFAULT_DISPLAY_FIELDS: list[dict[str, Any]] = [
    {"source_type": "pair_context", "source_field": "1", "order": 0},
    {"source_type": "pair_context", "source_field": "2", "order": 1},
    {"source_type": "pair_context", "source_field": "3", "order": 2},
]

_DEFAULT_DISPLAY_LABELS: dict[tuple[str, str], str] = {
    ("reviewee", "tag_1"): "Tag 1",
    ("reviewee", "tag_2"): "Tag 2",
    ("reviewee", "tag_3"): "Tag 3",
    ("reviewee", "profile_link"): "Profile",
    ("pair_context", "1"): "Pair context 1",
    ("pair_context", "2"): "Pair context 2",
    ("pair_context", "3"): "Pair context 3",
}

_FIELD_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELD_KEY_MAX_LEN = 64
_VALID_RESPONSE_TYPES = {"integer", "short_text", "long_text", "yes_no"}

_VALID_DISPLAY_SOURCES: frozenset[tuple[str, str]] = frozenset(
    _DEFAULT_DISPLAY_LABELS.keys()
)


class FieldKeyError(ValueError):
    """Raised when a proposed field_key is invalid or duplicates an existing key."""


class ResponsesPresentError(Exception):
    """Raised when delete is attempted on a field with saved responses without confirm."""

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} response(s) exist for this field")
        self.cascaded_response_count = count


class DisplaySourceError(ValueError):
    """Raised when a (source_type, source_field) pair is unknown or already on the instrument."""


def slugify_field_key(label: str) -> str:
    """Derive a default field_key from an operator-typed label.

    Lowercase, replace non-alphanumeric with `_`, collapse repeated `_`,
    strip leading digits / underscores, trim to 64 chars. Returns "" when
    the label has no usable characters (caller should treat as missing).
    """
    if not label:
        return ""
    s = label.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    s = s.lstrip("0123456789_")
    return s[:_FIELD_KEY_MAX_LEN]


def _validate_field_key(field_key: str) -> None:
    if not field_key:
        raise FieldKeyError("Field key is required.")
    if len(field_key) > _FIELD_KEY_MAX_LEN:
        raise FieldKeyError(
            f"Field key must be at most {_FIELD_KEY_MAX_LEN} characters."
        )
    if not _FIELD_KEY_REGEX.match(field_key):
        raise FieldKeyError(
            "Field key must start with a lowercase letter and use only "
            "lowercase letters, digits, or underscores."
        )


def _ordered_fields(
    db: Session, instrument: Instrument
) -> list[InstrumentResponseField]:
    return list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order, InstrumentResponseField.id)
        ).scalars()
    )


def _repack_orders(fields: list[InstrumentResponseField]) -> None:
    for index, field in enumerate(fields):
        if field.order != index:
            field.order = index


def ensure_default_instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    """Return the session's Default Instrument, creating it if missing,
    and ensuring it carries the default response fields."""
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.id)
    ).scalars().first()

    if instrument is None:
        instrument = Instrument(
            session_id=review_session.id,
            name=DEFAULT_INSTRUMENT_NAME,
            order=0,
            accepting_responses=False,
            responses_visible_when_closed=False,
        )
        db.add(instrument)
        db.flush()

    has_fields = (
        db.execute(
            select(InstrumentResponseField.id)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .limit(1)
        ).first()
        is not None
    )

    if not has_fields:
        for spec in DEFAULT_RESPONSE_FIELDS:
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=spec["field_key"],
                    label=spec["label"],
                    response_type=spec["response_type"],
                    required=spec["required"],
                    order=spec["order"],
                    validation=spec["validation"],
                )
            )
        db.flush()

    has_display_fields = (
        db.execute(
            select(InstrumentDisplayField.id)
            .where(InstrumentDisplayField.instrument_id == instrument.id)
            .limit(1)
        ).first()
        is not None
    )

    if not has_display_fields:
        for spec in _DEFAULT_DISPLAY_FIELDS:
            db.add(
                InstrumentDisplayField(
                    instrument_id=instrument.id,
                    label="",
                    source_type=spec["source_type"],
                    source_field=spec["source_field"],
                    order=spec["order"],
                    visible=True,
                )
            )
        db.flush()

    return instrument


def create_instrument(
    db: Session,
    *,
    review_session: ReviewSession,
    after_instrument_id: int | None = None,
    actor: User,
) -> Instrument:
    """Create a new instrument seeded with default response and display
    fields. If ``after_instrument_id`` is given, slot the new instrument
    immediately after that one and bump subsequent ``order`` values; else
    append at the end.
    """
    existing = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )

    new_order: int
    if after_instrument_id is None:
        new_order = (existing[-1].order + 1) if existing else 0
    else:
        anchor = next(
            (i for i in existing if i.id == after_instrument_id), None
        )
        if anchor is None:
            new_order = (existing[-1].order + 1) if existing else 0
        else:
            new_order = anchor.order + 1
            for inst in existing:
                if inst.order >= new_order:
                    inst.order += 1

    next_num = len(existing) + 1
    instrument = Instrument(
        session_id=review_session.id,
        name=f"instrument_{next_num}",
        order=new_order,
        accepting_responses=False,
        responses_visible_when_closed=False,
    )
    db.add(instrument)
    db.flush()

    for spec in DEFAULT_RESPONSE_FIELDS:
        db.add(
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=spec["field_key"],
                label=spec["label"],
                response_type=spec["response_type"],
                required=spec["required"],
                order=spec["order"],
                validation=spec["validation"],
            )
        )
    for spec in _DEFAULT_DISPLAY_FIELDS:
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type=spec["source_type"],
                source_field=spec["source_field"],
                order=spec["order"],
                visible=True,
            )
        )
    db.flush()

    write_event(
        db,
        event_type="instrument.created",
        summary=f"Created instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session_id=review_session.id,
        detail={
            "instrument_id": instrument.id,
            "session_id": review_session.id,
            "order": new_order,
            "after_instrument_id": after_instrument_id,
        },
    )
    db.commit()
    return instrument


def _instrument_label(instrument: Instrument) -> str:
    return instrument.description.strip() if instrument.description and instrument.description.strip() else instrument.name


def delete_instrument(
    db: Session,
    *,
    instrument: Instrument,
    actor: User,
) -> int:
    """Delete an instrument plus all its dependent rows (display/response
    fields, assignments, responses) via cascade, then re-pack the
    surviving instruments' ``order`` values to ``0..N-1``. Returns the
    deleted instrument's id.
    """
    session_id = instrument.session_id
    deleted_id = instrument.id
    deleted_name = instrument.name
    deleted_order = instrument.order

    db.delete(instrument)
    db.flush()

    remaining = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )
    for idx, inst in enumerate(remaining):
        if inst.order != idx:
            inst.order = idx
    db.flush()

    write_event(
        db,
        event_type="instrument.deleted",
        summary=f"Deleted instrument {deleted_name}",
        actor_user_id=actor.id if actor else None,
        session_id=session_id,
        detail={
            "instrument_id": deleted_id,
            "session_id": session_id,
            "name": deleted_name,
            "order": deleted_order,
        },
    )
    db.commit()
    return deleted_id


def display_field_label(field: InstrumentDisplayField) -> str:
    """Return the operator-typed label, else the inferred default for the source pair."""
    if field.label and field.label.strip():
        return field.label.strip()
    inferred = _DEFAULT_DISPLAY_LABELS.get((field.source_type, field.source_field))
    if inferred is not None:
        return inferred
    return f"{field.source_type}:{field.source_field}"


def display_field_value(
    field: InstrumentDisplayField, assignment: Assignment
) -> str | None:
    """Resolve a display field's cell value for an assignment row.

    Returns ``None`` when the source is absent, the value is empty / falsy,
    or the (source_type, source_field) pair is not recognised.
    """
    if field.source_type == "pair_context":
        ctx = assignment.context or {}
        value = ctx.get(f"pair_context_{field.source_field}")
        return value or None
    if field.source_type == "reviewee":
        if field.source_field not in {"tag_1", "tag_2", "tag_3", "profile_link"}:
            return None
        value = getattr(assignment.reviewee, field.source_field, None)
        return value or None
    return None


def _ordered_display_fields(
    db: Session, instrument: Instrument
) -> list[InstrumentDisplayField]:
    return list(
        db.execute(
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id == instrument.id)
            .order_by(InstrumentDisplayField.order, InstrumentDisplayField.id)
        ).scalars()
    )


def _repack_display_orders(fields: list[InstrumentDisplayField]) -> None:
    for index, field in enumerate(fields):
        if field.order != index:
            field.order = index


def _display_field_snapshot(field: InstrumentDisplayField) -> dict[str, Any]:
    return {
        "source_type": field.source_type,
        "source_field": field.source_field,
        "label": field.label,
        "order": field.order,
        "visible": field.visible,
    }


def add_display_field(
    db: Session,
    *,
    instrument: Instrument,
    source_type: str,
    source_field: str,
    label: str,
    visible: bool,
    actor: User,
) -> InstrumentDisplayField:
    """Add a display field to an instrument.

    `(source_type, source_field)` must be one of the seven D6 sources and
    must not already exist on this instrument. `label` is normalised via
    strip-on-write; an empty string is allowed and means "use the inferred
    D6 label at render time."
    """
    pair = (source_type, source_field)
    if pair not in _VALID_DISPLAY_SOURCES:
        raise DisplaySourceError(
            f"Unknown display-field source: {source_type}.{source_field}"
        )

    existing = _ordered_display_fields(db, instrument)
    if any(
        (f.source_type, f.source_field) == pair for f in existing
    ):
        raise DisplaySourceError(
            f"Display field {source_type}.{source_field} already exists "
            f"on this instrument."
        )

    new_field = InstrumentDisplayField(
        instrument_id=instrument.id,
        label=(label or "").strip(),
        source_type=source_type,
        source_field=source_field,
        order=len(existing),
        visible=visible,
    )
    db.add(new_field)
    db.flush()

    existing.append(new_field)
    _repack_display_orders(existing)
    db.flush()

    write_event(
        db,
        event_type="instrument.display_field_added",
        summary=(
            f"Added display field {source_type}.{source_field} "
            f"to instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            **_display_field_snapshot(new_field),
        },
    )
    return new_field


def update_display_field(
    db: Session,
    *,
    field: InstrumentDisplayField,
    label: str,
    visible: bool,
    actor: User,
) -> tuple[InstrumentDisplayField, dict[str, list[Any]]]:
    """Edit a display field's label override and visibility.

    `(source_type, source_field)` are immutable post-create. Returns
    `(field, changes)` where `changes` carries only the keys that
    actually changed.
    """
    instrument = field.instrument
    new_label = (label or "").strip()

    changes: dict[str, list[Any]] = {}
    if field.label != new_label:
        changes["label"] = [field.label, new_label]
    if field.visible != visible:
        changes["visible"] = [field.visible, visible]

    field.label = new_label
    field.visible = visible
    db.flush()

    write_event(
        db,
        event_type="instrument.display_field_updated",
        summary=(
            f"Updated display field {field.source_type}.{field.source_field} "
            f"on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "source_type": field.source_type,
            "source_field": field.source_field,
            "changes": changes,
        },
    )
    return field, changes


def delete_display_field(
    db: Session, *, field: InstrumentDisplayField, actor: User
) -> None:
    """Delete a display field. No cascade-confirm — display fields carry
    no per-row dependent data."""
    instrument = field.instrument
    snapshot = _display_field_snapshot(field)
    db.delete(field)
    db.flush()

    remaining = _ordered_display_fields(db, instrument)
    _repack_display_orders(remaining)
    db.flush()

    write_event(
        db,
        event_type="instrument.display_field_deleted",
        summary=(
            f"Deleted display field {snapshot['source_type']}.{snapshot['source_field']} "
            f"from instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "snapshot": snapshot,
        },
    )


def bulk_save_fields(
    db: Session,
    *,
    instrument: Instrument,
    rows: list[dict[str, Any]],
    actor: User,
) -> dict[str, bool]:
    """Apply order + (display-only) visibility / label across a single
    interleaved payload covering both display and response fields.

    Per Segment 10B-2 D7: rows missing from the payload are left alone
    (deletion goes through the row-level Delete POST). Per-table orders
    are repacked to ``0..N-1`` independently in submission order. Adds
    + deletes are not handled here — those are row-level POSTs.

    Returns ``{"display_changed": bool, "response_order_changed": bool}``.
    """
    display_payload: list[dict[str, Any]] = []
    response_payload: list[dict[str, Any]] = []
    for row in rows:
        kind = row.get("kind")
        if kind == "display":
            display_payload.append(row)
        elif kind == "response":
            response_payload.append(row)

    # Sort by operator-submitted `order` so changing a numeric reranks
    # the row; the position in the form is incidental.
    display_payload.sort(key=lambda r: int(r.get("order", 0)))
    response_payload.sort(key=lambda r: int(r.get("order", 0)))

    existing_display_list = _ordered_display_fields(db, instrument)
    existing_response_list = _ordered_fields(db, instrument)
    existing_display = {f.id: f for f in existing_display_list}
    existing_response = {f.id: f for f in existing_response_list}

    # Old ranks: position in current ordered listing (0..N-1).
    response_old_rank = {f.id: i for i, f in enumerate(existing_response_list)}
    display_old_rank = {f.id: i for i, f in enumerate(existing_display_list)}

    display_updated: list[dict[str, Any]] = []

    new_display_order: list[InstrumentDisplayField] = []
    for row in display_payload:
        field = existing_display.get(row.get("id"))
        if field is None:
            continue
        new_label = (row.get("label") or "").strip()
        new_visible = bool(row.get("visible", field.visible))
        per_row_changes: dict[str, list[Any]] = {}
        if field.label != new_label:
            per_row_changes["label"] = [field.label, new_label]
        if field.visible != new_visible:
            per_row_changes["visible"] = [field.visible, new_visible]
        old_order = field.order
        field.label = new_label
        field.visible = new_visible
        new_display_order.append(field)
        display_updated.append(
            {
                "source_type": field.source_type,
                "source_field": field.source_field,
                "_old_order": old_order,
                "changes": per_row_changes,
            }
        )

    new_response_order: list[InstrumentResponseField] = []
    for row in response_payload:
        field = existing_response.get(row.get("id"))
        if field is None:
            continue
        new_response_order.append(field)

    # Rank-based change detection: compare each submitted row's prior
    # rank (position in the existing ordered listing) to its new rank
    # (position in the submitted-and-sorted listing). This lets the
    # bulk save normalise non-contiguous order values (e.g. 1, 2 → 0, 1
    # from a fresh seed) without spuriously emitting a reorder event.
    response_new_rank = {f.id: i for i, f in enumerate(new_response_order)}
    display_new_rank = {f.id: i for i, f in enumerate(new_display_order)}

    _repack_display_orders(new_display_order)
    _repack_orders(new_response_order)
    db.flush()

    # finalise per-row changes with rank deltas + drop no-op rows
    final_display_updated: list[dict[str, Any]] = []
    for entry, field in zip(display_updated, new_display_order):
        old_order = entry.pop("_old_order")
        old_rank = display_old_rank.get(field.id)
        new_rank = display_new_rank.get(field.id)
        if old_rank != new_rank:
            entry["changes"]["order"] = [old_order, field.order]
        if entry["changes"]:
            final_display_updated.append(entry)

    response_order_changed = any(
        response_old_rank.get(f.id) != response_new_rank.get(f.id)
        for f in new_response_order
    )
    display_changed = bool(final_display_updated)

    if response_order_changed:
        # Re-query to capture the post-mutation ordered key list for the
        # audit event; this includes any unsubmitted rows in their
        # current positions.
        new_response_keys = [
            f.field_key for f in _ordered_fields(db, instrument)
        ]
        old_order_keys = [f.field_key for f in existing_response_list]
        write_event(
            db,
            event_type="instrument.fields_reordered",
            summary=f"Reordered fields on instrument {_instrument_label(instrument)}",
            actor_user_id=actor.id if actor else None,
            session_id=instrument.session_id,
            detail={
                "instrument_id": instrument.id,
                "session_id": instrument.session_id,
                "old_order": old_order_keys,
                "new_order": new_response_keys,
            },
        )

    if display_changed:
        write_event(
            db,
            event_type="instrument.display_fields_saved",
            summary=(
                f"Saved display-field order / visibility on "
                f"instrument {_instrument_label(instrument)}"
            ),
            actor_user_id=actor.id if actor else None,
            session_id=instrument.session_id,
            detail={
                "instrument_id": instrument.id,
                "session_id": instrument.session_id,
                "added": [],
                "removed": [],
                "updated": final_display_updated,
            },
        )

    return {
        "display_changed": display_changed,
        "response_order_changed": response_order_changed,
    }


def add_response_field(
    db: Session,
    *,
    instrument: Instrument,
    field_key: str,
    label: str,
    response_type: str,
    required: bool,
    validation: dict[str, Any] | None,
    help_text: str | None,
    help_text_visible: bool,
    actor: User,
) -> InstrumentResponseField:
    _validate_field_key(field_key)
    if response_type not in _VALID_RESPONSE_TYPES:
        raise ValueError(f"Unknown response_type: {response_type}")
    if not label or not label.strip():
        raise ValueError("Label is required.")

    fields = _ordered_fields(db, instrument)
    if any(existing.field_key == field_key for existing in fields):
        raise FieldKeyError(
            f"A field with key '{field_key}' already exists on this instrument."
        )

    new_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label.strip(),
        response_type=response_type,
        required=required,
        order=len(fields),
        validation=validation,
        help_text=(help_text or None),
        help_text_visible=help_text_visible,
    )
    db.add(new_field)
    db.flush()

    fields.append(new_field)
    _repack_orders(fields)

    write_event(
        db,
        event_type="instrument.field_added",
        summary=(
            f"Added field '{new_field.label}' ({new_field.field_key}) "
            f"to instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "field_key": new_field.field_key,
            "label": new_field.label,
            "response_type": new_field.response_type,
            "required": new_field.required,
            "validation": new_field.validation,
            "help_text": new_field.help_text,
            "help_text_visible": new_field.help_text_visible,
        },
    )

    return new_field


def _count_now_missing_required(
    db: Session, *, instrument: Instrument, field: InstrumentResponseField
) -> int:
    """Count assignments under this instrument whose Response row for the
    field is missing or blank — i.e. reviewer rows that would be incomplete
    if the field flips required."""
    field_response = (
        select(Response.assignment_id, Response.value)
        .join(
            Assignment,
            Assignment.id == Response.assignment_id,
        )
        .where(
            Assignment.instrument_id == instrument.id,
            Response.response_field_id == field.id,
        )
        .subquery()
    )

    total_assignments = db.execute(
        select(func.count(Assignment.id)).where(
            Assignment.instrument_id == instrument.id
        )
    ).scalar_one()

    rows_with_value = db.execute(
        select(func.count())
        .select_from(field_response)
        .where(field_response.c.value.is_not(None))
        .where(func.length(func.coalesce(field_response.c.value, "")) > 0)
    ).scalar_one()

    return max(int(total_assignments) - int(rows_with_value), 0)


def update_response_field(
    db: Session,
    *,
    field: InstrumentResponseField,
    label: str,
    required: bool,
    validation: dict[str, Any] | None,
    help_text: str | None,
    help_text_visible: bool,
    actor: User,
) -> tuple[InstrumentResponseField, int]:
    """Edit a response field. Returns (field, required_warning_count)."""
    if not label or not label.strip():
        raise ValueError("Label is required.")

    instrument = field.instrument
    new_label = label.strip()
    new_help_text = help_text or None

    changes: dict[str, list[Any]] = {}
    if field.label != new_label:
        changes["label"] = [field.label, new_label]
    if field.required != required:
        changes["required"] = [field.required, required]
    if field.validation != validation:
        changes["validation"] = [field.validation, validation]
    if field.help_text != new_help_text:
        changes["help_text"] = [field.help_text, new_help_text]
    if field.help_text_visible != help_text_visible:
        changes["help_text_visible"] = [field.help_text_visible, help_text_visible]

    required_warning_count = 0
    if not field.required and required:
        required_warning_count = _count_now_missing_required(
            db, instrument=instrument, field=field
        )

    field.label = new_label
    field.required = required
    field.validation = validation
    field.help_text = new_help_text
    field.help_text_visible = help_text_visible
    db.flush()

    write_event(
        db,
        event_type="instrument.field_updated",
        summary=f"Updated field '{field.label}' on instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "field_key": field.field_key,
            "changes": changes,
        },
    )

    return field, required_warning_count


def delete_response_field(
    db: Session,
    *,
    field: InstrumentResponseField,
    confirm: bool,
    actor: User,
) -> None:
    instrument = field.instrument
    response_count = db.execute(
        select(func.count(Response.id)).where(
            Response.response_field_id == field.id
        )
    ).scalar_one()
    response_count = int(response_count)

    if response_count > 0 and not confirm:
        raise ResponsesPresentError(response_count)

    snapshot = {
        "field_key": field.field_key,
        "label": field.label,
        "response_type": field.response_type,
        "required": field.required,
        "order": field.order,
        "validation": field.validation,
        "help_text": field.help_text,
        "help_text_visible": field.help_text_visible,
    }
    label_for_summary = field.label
    db.delete(field)
    db.flush()

    remaining = _ordered_fields(db, instrument)
    _repack_orders(remaining)
    db.flush()

    write_event(
        db,
        event_type="instrument.field_deleted",
        summary=f"Deleted field '{label_for_summary}' from instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "field_key": snapshot["field_key"],
            "snapshot": snapshot,
            "cascaded_response_count": response_count,
        },
    )


def move_response_field(
    db: Session,
    *,
    field: InstrumentResponseField,
    direction: Literal["up", "down"],
    actor: User,
) -> None:
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")

    instrument = field.instrument
    fields = _ordered_fields(db, instrument)
    old_keys = [f.field_key for f in fields]
    index = next((i for i, f in enumerate(fields) if f.id == field.id), None)
    if index is None:
        raise ValueError("Field not found on instrument")

    swap_with = index - 1 if direction == "up" else index + 1
    if swap_with < 0 or swap_with >= len(fields):
        return  # at boundary; no-op (route returns 400)

    fields[index], fields[swap_with] = fields[swap_with], fields[index]
    _repack_orders(fields)
    db.flush()

    new_keys = [f.field_key for f in fields]
    write_event(
        db,
        event_type="instrument.fields_reordered",
        summary=f"Reordered fields on instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "old_order": old_keys,
            "new_order": new_keys,
        },
    )


def update_instrument_description(
    db: Session,
    *,
    instrument: Instrument,
    description: str | None,
    actor: User,
) -> Instrument:
    cleaned = description.strip() if isinstance(description, str) else None
    new_value = cleaned or None
    old_value = instrument.description
    instrument.description = new_value
    db.flush()

    write_event(
        db,
        event_type="instrument.described",
        summary=f"Updated description on instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "description": [old_value, new_value],
        },
    )
    db.commit()
    return instrument


def bulk_set_accepting(
    db: Session,
    *,
    review_session: ReviewSession,
    target: bool,
    actor: User,
) -> list[int]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    changed: list[int] = []
    for instrument in instruments:
        if instrument.accepting_responses != target:
            instrument.accepting_responses = target
            changed.append(instrument.id)
    if changed:
        db.flush()
        write_event(
            db,
            event_type="instruments.bulk_accepting_responses",
            summary=(
                f"Set accepting_responses={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session_id=review_session.id,
            detail={
                "session_id": review_session.id,
                "target": target,
                "changed_instrument_ids": changed,
            },
        )
        db.commit()
    return changed


def bulk_set_visibility(
    db: Session,
    *,
    review_session: ReviewSession,
    target: bool,
    actor: User,
) -> list[int]:
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    changed: list[int] = []
    for instrument in instruments:
        if instrument.responses_visible_when_closed != target:
            instrument.responses_visible_when_closed = target
            changed.append(instrument.id)
    if changed:
        db.flush()
        write_event(
            db,
            event_type="instruments.bulk_visibility_when_closed",
            summary=(
                f"Set responses_visible_when_closed={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session_id=review_session.id,
            detail={
                "session_id": review_session.id,
                "target": target,
                "changed_instrument_ids": changed,
            },
        )
        db.commit()
    return changed
