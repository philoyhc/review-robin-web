"""Display Fields slice — per-instrument reviewee-context columns
shown to reviewers (Name / Email / tag_1..3 / profile_link, plus
pair_context_1..3 from assignment imports).

Slice 2 of the §12.A ladder (``guide/major_refactor.md``).

Owns the catalog of valid sources, the locked-row gates (Name +
Email always sit at positions 1 / 2 on every instrument, never
hidden, never deleted, never moved), the operator-side CRUD
(add / update / delete / move) and the lazy-seeding helpers that
fire from CSV imports / assignment imports. Saves emit
``instrument.display_field_added`` / ``.display_field_updated`` /
``.display_field_deleted`` / ``.display_field_moved`` audit events.

Source range in pre-PR-2 ``_legacy.py``: lines 53-100, 107-116,
131-132, and 479-1004 (interleaved with non-display content that
PR 4 carves into ``_instrument_crud.py``).
"""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentDisplayField,
    Reviewee,
    ReviewSession,
    User,
)
from app.services import audit
from app.services import session_lifecycle as lifecycle

from ._state import _instrument_label


_DEFAULT_DISPLAY_LABELS: dict[tuple[str, str], str] = {
    ("reviewee", "name"): "Name",
    ("reviewee", "email_or_identifier"): "Email",
    ("reviewee", "tag_1"): "Tag 1",
    ("reviewee", "tag_2"): "Tag 2",
    ("reviewee", "tag_3"): "Tag 3",
    ("reviewee", "profile_link"): "Profile",
    ("pair_context", "1"): "Pair context 1",
    ("pair_context", "2"): "Pair context 2",
    ("pair_context", "3"): "Pair context 3",
}

# Operator UI vocabulary uses CSV column names; the schema uses
# (source_type, source_field) tuples. This map is the canonical
# translation used by lazy-seeding (Segment 10D / item #14).
_CSV_COL_TO_SOURCE: dict[str, tuple[str, str]] = {
    "RevieweeName": ("reviewee", "name"),
    "RevieweeEmail": ("reviewee", "email_or_identifier"),
    "PhotoLink": ("reviewee", "profile_link"),
    "RevieweeTag1": ("reviewee", "tag_1"),
    "RevieweeTag2": ("reviewee", "tag_2"),
    "RevieweeTag3": ("reviewee", "tag_3"),
    "PairContext1": ("pair_context", "1"),
    "PairContext2": ("pair_context", "2"),
    "PairContext3": ("pair_context", "3"),
}

# Locked rows in the Display Fields table. Per
# spec/instruments.md, ``RevieweeName`` and ``RevieweeEmail``
# always sit at positions 1 and 2 (orders 0 and 1) on every
# instrument. Their visible flag is locked-checked, their order
# is locked, and they cannot be deleted.
_LOCKED_DISPLAY_SOURCES: frozenset[tuple[str, str]] = frozenset({
    ("reviewee", "name"),
    ("reviewee", "email_or_identifier"),
})

_LOCKED_DISPLAY_ORDER: dict[tuple[str, str], int] = {
    ("reviewee", "name"): 0,
    ("reviewee", "email_or_identifier"): 1,
}

_VALID_DISPLAY_SOURCES: frozenset[tuple[str, str]] = frozenset(
    _DEFAULT_DISPLAY_LABELS.keys()
)


def is_locked_display_source(source_type: str, source_field: str) -> bool:
    """Return True for the two Display Fields rows that are locked at
    fixed positions / always-visible (RevieweeName, RevieweeEmail)."""
    return (source_type, source_field) in _LOCKED_DISPLAY_SOURCES


class LockedDisplayFieldError(ValueError):
    """Raised when a locked Display Fields row (Name / Email) is the
    target of an operation that's not permitted on locked rows
    (delete, hide, reorder)."""


class DisplaySourceError(ValueError):
    """Raised when a (source_type, source_field) pair is unknown or already on the instrument."""


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
        if field.source_field not in {
            "name",
            "email_or_identifier",
            "tag_1",
            "tag_2",
            "tag_3",
            "profile_link",
        }:
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

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_display_field_added",
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

    audit.write_event(
        db,
        event_type="instrument.display_field_added",
        summary=(
            f"Added display field {source_type}.{source_field} "
            f"to instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.snapshot(_display_field_snapshot(new_field)),
        refs={"instrument_id": instrument.id, "display_field_id": new_field.id},
    )
    db.commit()
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

    Locked rows (`RevieweeName`, `RevieweeEmail`) cannot have
    ``visible`` flipped to False. Their label is freely editable.
    """
    if (
        is_locked_display_source(field.source_type, field.source_field)
        and not visible
    ):
        raise LockedDisplayFieldError(
            f"Display field {field.source_type}.{field.source_field} "
            f"is always shown to reviewers and cannot be hidden."
        )
    instrument = field.instrument
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_display_field_updated",
    )
    new_label = (label or "").strip()

    changes: dict[str, list[Any]] = {}
    if field.label != new_label:
        changes["label"] = [field.label, new_label]
    if field.visible != visible:
        changes["visible"] = [field.visible, visible]

    field.label = new_label
    field.visible = visible
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.display_field_updated",
        summary=(
            f"Updated display field {field.source_type}.{field.source_field} "
            f"on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(changes),
        refs={"instrument_id": instrument.id, "display_field_id": field.id},
        context={
            "source_type": field.source_type,
            "source_field": field.source_field,
        },
    )
    db.commit()
    return field, changes


def delete_display_field(
    db: Session, *, field: InstrumentDisplayField, actor: User
) -> None:
    """Delete a display field. No cascade-confirm — display fields carry
    no per-row dependent data.

    Locked rows (`RevieweeName`, `RevieweeEmail`) cannot be deleted.
    """
    if is_locked_display_source(field.source_type, field.source_field):
        raise LockedDisplayFieldError(
            f"Display field {field.source_type}.{field.source_field} "
            f"is locked and cannot be deleted."
        )
    instrument = field.instrument
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_display_field_deleted",
    )
    captured = _display_field_snapshot(field)
    db.delete(field)
    db.flush()

    remaining = _ordered_display_fields(db, instrument)
    _repack_display_orders(remaining)
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.display_field_deleted",
        summary=(
            f"Deleted display field {captured['source_type']}.{captured['source_field']} "
            f"from instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.snapshot(captured),
        refs={"instrument_id": instrument.id},
        context={
            "source_type": captured["source_type"],
            "source_field": captured["source_field"],
        },
    )
    db.commit()


def move_display_field(
    db: Session,
    *,
    field: InstrumentDisplayField,
    direction: Literal["up", "down"],
    actor: User,
) -> None:
    """Swap a display field with its neighbour. Locked rows
    (RevieweeName, RevieweeEmail) cannot be moved; their neighbours
    can be moved but never *into* the locked region (i.e. a
    non-locked row's ``up`` is rejected if the row above it is
    locked)."""
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    if is_locked_display_source(field.source_type, field.source_field):
        raise LockedDisplayFieldError(
            f"Display field {field.source_type}.{field.source_field} "
            f"is locked and cannot be reordered."
        )

    instrument = field.instrument
    fields = _ordered_display_fields(db, instrument)
    index = next((i for i, f in enumerate(fields) if f.id == field.id), None)
    if index is None:
        raise ValueError("Display field not found on instrument")

    swap_with = index - 1 if direction == "up" else index + 1
    if swap_with < 0 or swap_with >= len(fields):
        return  # at boundary; no-op
    target = fields[swap_with]
    if is_locked_display_source(target.source_type, target.source_field):
        # Cannot swap with a locked row.
        raise LockedDisplayFieldError(
            "Cannot move into the locked region of the Display Fields table."
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_display_field_moved",
    )

    fields[index], fields[swap_with] = fields[swap_with], fields[index]
    _repack_display_orders(fields)
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.display_field_moved",
        summary=(
            f"Moved display field {field.source_type}.{field.source_field} "
            f"{direction} on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        refs={"instrument_id": instrument.id, "display_field_id": field.id},
        context={
            "source_type": field.source_type,
            "source_field": field.source_field,
            "direction": direction,
        },
    )
    db.commit()


def _seed_display_fields_for_instrument(
    db: Session,
    *,
    instrument: Instrument,
    sources: list[tuple[str, str]],
) -> int:
    """Idempotently add display-field rows for the given sources.

    Skips any (source_type, source_field) pair already on the instrument.
    Returns the number of new rows created. New rows append after any
    existing rows preserving operator-typed labels and order.
    """
    if not sources:
        return 0
    existing = _ordered_display_fields(db, instrument)
    existing_pairs = {(f.source_type, f.source_field) for f in existing}
    next_order = len(existing)
    created = 0
    for source_type, source_field in sources:
        if (source_type, source_field) in existing_pairs:
            continue
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type=source_type,
                source_field=source_field,
                order=next_order,
                visible=True,
            )
        )
        next_order += 1
        created += 1
    if created:
        db.flush()
    return created


def _instruments_for_session(
    db: Session, review_session: ReviewSession
) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )


def seed_display_fields_from_reviewees(
    db: Session, review_session: ReviewSession
) -> int:
    """Create reviewee-side display fields for any populated import slots.

    Inspects the session's reviewees for non-empty ``profile_link`` and
    ``tag_1/2/3`` values; for each instrument in the session, idempotently
    adds an ``InstrumentDisplayField`` row for each populated slot.
    Returns the total number of new display-field rows created.
    """
    sources: list[tuple[str, str]] = []
    has_profile = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == review_session.id)
        .where(Reviewee.profile_link.is_not(None))
        .where(Reviewee.profile_link != "")
        .limit(1)
    ).first()
    if has_profile is not None:
        sources.append(("reviewee", "profile_link"))
    for slot in (1, 2, 3):
        col = getattr(Reviewee, f"tag_{slot}")
        found = db.execute(
            select(Reviewee.id)
            .where(Reviewee.session_id == review_session.id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            sources.append(("reviewee", f"tag_{slot}"))

    if not sources:
        return 0
    total = 0
    for instrument in _instruments_for_session(db, review_session):
        total += _seed_display_fields_for_instrument(
            db, instrument=instrument, sources=sources
        )
    return total


def seed_display_fields_from_assignments(
    db: Session, review_session: ReviewSession
) -> int:
    """Create pair_context display fields for any populated assignment slots.

    Inspects the session's assignments for non-empty ``pair_context_N``
    values; for each instrument in the session, idempotently adds an
    ``InstrumentDisplayField`` row for each populated slot. Returns the
    total number of new display-field rows created.
    """
    pair_present = {1: False, 2: False, 3: False}
    for (ctx,) in db.execute(
        select(Assignment.context).where(
            Assignment.session_id == review_session.id
        )
    ).all():
        if not ctx:
            continue
        for slot in (1, 2, 3):
            if ctx.get(f"pair_context_{slot}"):
                pair_present[slot] = True
        if all(pair_present.values()):
            break

    sources = [
        ("pair_context", str(slot))
        for slot, present in pair_present.items()
        if present
    ]
    if not sources:
        return 0
    total = 0
    for instrument in _instruments_for_session(db, review_session):
        total += _seed_display_fields_for_instrument(
            db, instrument=instrument, sources=sources
        )
    return total


def _populated_display_sources_for_session(
    db: Session, review_session: ReviewSession
) -> set[tuple[str, str]]:
    """Return the set of ``(source_type, source_field)`` pairs that
    currently have at least one populated value across the session's
    reviewees + assignments. Locked rows (Name + Email) are always
    counted as populated."""
    populated: set[tuple[str, str]] = set(_LOCKED_DISPLAY_SOURCES)

    has_profile = db.execute(
        select(Reviewee.id)
        .where(Reviewee.session_id == review_session.id)
        .where(Reviewee.profile_link.is_not(None))
        .where(Reviewee.profile_link != "")
        .limit(1)
    ).first()
    if has_profile is not None:
        populated.add(("reviewee", "profile_link"))
    for slot in (1, 2, 3):
        col = getattr(Reviewee, f"tag_{slot}")
        found = db.execute(
            select(Reviewee.id)
            .where(Reviewee.session_id == review_session.id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            populated.add(("reviewee", f"tag_{slot}"))

    pair_present = {1: False, 2: False, 3: False}
    for (ctx,) in db.execute(
        select(Assignment.context).where(
            Assignment.session_id == review_session.id
        )
    ).all():
        if not ctx:
            continue
        for slot in (1, 2, 3):
            if ctx.get(f"pair_context_{slot}"):
                pair_present[slot] = True
        if all(pair_present.values()):
            break
    for slot, present in pair_present.items():
        if present:
            populated.add(("pair_context", str(slot)))

    return populated


def prune_unpopulated_display_fields(
    db: Session, review_session: ReviewSession
) -> int:
    """Drop Display Fields rows whose underlying data source has no
    populated value across the session — except locked rows (Name,
    Email), which are always kept regardless of data presence.
    Repacks the remaining rows' ``order`` to ``0..N-1`` per
    instrument. Returns the total number of rows dropped across all
    instruments in the session.

    Used by the ``instruments_index`` route on every GET to keep the
    Display Fields surface in sync with the actual reviewee /
    assignment data; if an operator deletes reviewees or re-imports
    assignments and a slot loses its data, the corresponding row
    disappears from the table.
    """
    populated = _populated_display_sources_for_session(db, review_session)
    dropped = 0
    for instrument in _instruments_for_session(db, review_session):
        deleted_any = False
        for f in list(instrument.display_fields):
            pair = (f.source_type, f.source_field)
            if pair in populated:
                continue
            db.delete(f)
            deleted_any = True
            dropped += 1
        if deleted_any:
            db.flush()
            remaining = _ordered_display_fields(db, instrument)
            _repack_display_orders(remaining)
            db.flush()
    return dropped
