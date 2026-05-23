"""Display Fields slice — per-instrument reviewee-context columns
shown to reviewers (Name / Email / tag_1..3 / profile_link, plus
pair_context_1..3 from assignment imports).

Slice 2 of the §12.A ladder (``guide/archive/major_refactor.md``).

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
    Relationship,
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


def display_field_label(
    field: InstrumentDisplayField,
    session: ReviewSession | None = None,
) -> str:
    """Return the friendly label for a display-field cell header.

    Segment 15A Slice 2 collapsed the chain to three steps:

    1. ``field_labels.resolve(...)`` — session-wide override
    2. Built-in default in ``_DEFAULT_LABELS``
       (mirrored locally as ``_DEFAULT_DISPLAY_LABELS`` for the
       no-session fallback path below)
    3. ``f"{source_type}:{source_field}"`` last-resort fallback

    The per-instrument ``InstrumentDisplayField.label`` override
    was retired — the column stays in the schema as dead data
    pending a follow-on cleanup segment, but is no longer
    consulted.

    ``session`` is optional for backward compat: callers that
    haven't been migrated yet still get a usable label via the
    built-in default. New callers (operator template globals,
    reviewer-surface view-build) should always pass ``session``
    so session-wide overrides flow through.
    """
    if session is not None:
        # Local import to avoid a circular at module load.
        from app.services import field_labels

        return field_labels.resolve(
            session, field.source_type, field.source_field
        )
    inferred = _DEFAULT_DISPLAY_LABELS.get((field.source_type, field.source_field))
    if inferred is not None:
        return inferred
    return f"{field.source_type}:{field.source_field}"


def display_field_value(
    field: InstrumentDisplayField,
    assignment: Assignment,
    *,
    pair_context_lookup: dict[tuple[int, int], Relationship] | None = None,
) -> str | None:
    """Resolve a display field's cell value for an assignment row.

    Returns ``None`` when the source is absent, the value is empty / falsy,
    or the (source_type, source_field) pair is not recognised.

    ``pair_context_lookup`` is a
    ``(reviewer_id, reviewee_id) -> Relationship`` map the caller
    pre-loads to avoid N+1 queries when rendering many rows. Passing
    ``None`` makes pair_context cells resolve to ``None`` (the safe
    fallback for callers that don't yet pass the lookup); production
    callers should always pass it. Inactive ``Relationship`` rows
    are skipped (their tag values stay hidden — same skip-at-lookup
    semantic as ``app/services/rules/fields.py``).
    """
    if field.source_type == "pair_context":
        if pair_context_lookup is None:
            return None
        relationship = pair_context_lookup.get(
            (assignment.reviewer_id, assignment.reviewee_id)
        )
        if relationship is None:
            return None
        if getattr(relationship, "status", None) != "active":
            return None
        attribute = f"tag_{field.source_field}"
        value = getattr(relationship, attribute, None)
        if isinstance(value, str) and value.strip() == "":
            return None
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


def reorder_display_fields(
    db: Session,
    *,
    instrument: Instrument,
    ordered_ids: list[int],
    actor: User,
) -> None:
    """Apply a bulk reorder of an instrument's non-locked display
    fields. ``ordered_ids`` must be a permutation of every non-locked
    display field id on the instrument — duplicates, unknown ids, or
    locked ids raise ``ValueError`` / ``LockedDisplayFieldError``.

    The two locked fields (RevieweeName, RevieweeEmail) keep their
    pinned positions (orders 0 and 1); the non-locked fields take
    orders 2..N+1 in the sequence ``ordered_ids`` describes. The
    Band 2 drag-and-drop pill reorder writes through this helper.

    No-op saves (the requested order matches the current order)
    skip the audit + lifecycle side effects.
    """
    if len(set(ordered_ids)) != len(ordered_ids):
        raise ValueError("ordered_ids contains duplicates")
    fields = _ordered_display_fields(db, instrument)
    locked: list[InstrumentDisplayField] = []
    unlocked_by_id: dict[int, InstrumentDisplayField] = {}
    for f in fields:
        if is_locked_display_source(f.source_type, f.source_field):
            locked.append(f)
        else:
            unlocked_by_id[f.id] = f
    if set(ordered_ids) != set(unlocked_by_id):
        raise ValueError(
            "ordered_ids must enumerate every non-locked display field "
            f"on instrument {instrument.id} exactly once"
        )
    new_order = locked + [unlocked_by_id[fid] for fid in ordered_ids]
    current_order_ids = [f.id for f in fields]
    desired_order_ids = [f.id for f in new_order]
    if current_order_ids == desired_order_ids:
        return
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_display_fields_reordered",
    )
    _repack_display_orders(new_order)
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.fields_reordered",
        summary=(
            f"Reordered display fields on instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(
            {"display_field_order": [current_order_ids, desired_order_ids]}
        ),
        refs={"instrument_id": instrument.id},
    )


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
    """Create pair_context display fields for any populated relationship slots.

    Inspects the session's ``relationships`` table for non-empty
    ``tag_N`` values (post-15D PR 6b — pre-15D the data lived on
    ``Assignment.context.pair_context_N``); for each instrument in
    the session, idempotently adds an ``InstrumentDisplayField`` row
    for each populated slot. Returns the total number of new
    display-field rows created.
    """
    pair_present = {1: False, 2: False, 3: False}
    for slot in (1, 2, 3):
        col = getattr(Relationship, f"tag_{slot}")
        found = db.execute(
            select(Relationship.id)
            .where(Relationship.session_id == review_session.id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
            pair_present[slot] = True

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

    for slot in (1, 2, 3):
        col = getattr(Relationship, f"tag_{slot}")
        found = db.execute(
            select(Relationship.id)
            .where(Relationship.session_id == review_session.id)
            .where(col.is_not(None))
            .where(col != "")
            .limit(1)
        ).first()
        if found is not None:
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


# ---------------------------------------------------------------------------
# Sort spec (Segment 13B PR 1)
# ---------------------------------------------------------------------------


# Canonical value shape per ``spec/sort_by_reviewee.md``:
# ``[{"display_field_id": int, "dir": "asc"|"desc"}, ...]``. Up to
# 3 entries. NULL or ``[]`` = "no operator default" (the reviewer-
# surface render falls back to insertion order).
_VALID_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})
_MAX_SORT_KEYS: int = 3


class SortSpecError(ValueError):
    """Service-layer rejection of an invalid sort spec.

    ``code`` is a stable machine identifier the route layer can
    translate to a banner / form error; ``message`` is the
    human-readable explanation.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def set_sort_display_fields(
    db: Session,
    *,
    instrument: Instrument,
    fields: list[tuple[int, str]] | list[dict[str, Any]],
    actor: User,
    correlation_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]] | None]:
    """Persist the per-instrument operator-default sort spec.

    ``fields`` accepts either the canonical
    ``[{"display_field_id": N, "dir": "asc|desc"}, ...]`` shape or
    a list of ``(display_field_id, dir)`` tuples (convenience for
    the route handler that just parsed form data). Normalises to
    the canonical dict shape on the way in.

    Returns ``(new_value, old_value)`` so route handlers can
    short-circuit the audit emit on no-op saves. ``old_value`` is
    ``None`` when the column was previously unset (NULL).

    Validation (raises ``SortSpecError``):

    - ``too_many``: length > 3.
    - ``unknown_dir``: ``dir`` not in ``{"asc", "desc"}``.
    - ``duplicate_id``: same ``display_field_id`` appears twice.
    - ``cross_instrument``: ``display_field_id`` is not one of
      this instrument's display fields.

    Lifecycle-invalidates if the session was previously validated
    (sort spec is a setup-shape change, not a runtime knob).
    Emits ``instrument.sort_fields_updated`` with the canonical
    ``changes`` envelope on diff; no emit on no-op save.
    """
    normalised = _normalise_sort_spec(fields)
    # Query display-field IDs directly rather than relying on the
    # relationship cache — callers may have added display fields
    # earlier in the same transaction without expiring it.
    valid_ids = set(
        db.execute(
            select(InstrumentDisplayField.id).where(
                InstrumentDisplayField.instrument_id == instrument.id
            )
        ).scalars()
    )
    seen: set[int] = set()
    for entry in normalised:
        if entry["display_field_id"] in seen:
            raise SortSpecError(
                code="duplicate_id",
                message=(
                    f"Display field {entry['display_field_id']} appears "
                    "more than once in the sort spec."
                ),
            )
        if entry["display_field_id"] not in valid_ids:
            raise SortSpecError(
                code="cross_instrument",
                message=(
                    f"Display field {entry['display_field_id']} is not "
                    f"on instrument {_instrument_label(instrument)}."
                ),
            )
        seen.add(entry["display_field_id"])

    old_value = instrument.sort_display_fields
    if old_value == normalised:
        # No-op save — skip lifecycle invalidation + audit emit.
        return normalised, old_value

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_sort_fields_updated",
    )
    instrument.sort_display_fields = normalised
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.sort_fields_updated",
        summary=(
            f"Updated sort spec on instrument {_instrument_label(instrument)} "
            f"({len(normalised)} key{'s' if len(normalised) != 1 else ''})"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"sort_display_fields": [old_value, normalised]}),
        refs={"instrument_id": instrument.id},
        correlation_id=correlation_id,
    )
    db.commit()
    return normalised, old_value


def _normalise_sort_spec(
    fields: list[tuple[int, str]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(fields) > _MAX_SORT_KEYS:
        raise SortSpecError(
            code="too_many",
            message=(
                f"Sort spec has {len(fields)} entries; the maximum is "
                f"{_MAX_SORT_KEYS}."
            ),
        )
    out: list[dict[str, Any]] = []
    for entry in fields:
        if isinstance(entry, tuple):
            field_id_raw, dir_raw = entry
        else:
            field_id_raw = entry.get("display_field_id")
            dir_raw = entry.get("dir")
        try:
            field_id = int(field_id_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise SortSpecError(
                code="bad_id",
                message=(
                    f"Sort spec entry has non-integer display_field_id "
                    f"{field_id_raw!r}."
                ),
            ) from exc
        direction = str(dir_raw or "").lower()
        if direction not in _VALID_SORT_DIRS:
            raise SortSpecError(
                code="unknown_dir",
                message=(
                    f"Sort spec direction {dir_raw!r} is not one of "
                    f"{sorted(_VALID_SORT_DIRS)}."
                ),
            )
        out.append({"display_field_id": field_id, "dir": direction})
    return out
