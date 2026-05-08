"""Legacy container holding every instruments-service function not
yet sliced. See ``guide/major_refactor.md`` §12.A — this file
shrinks once per slice PR and is deleted in PR 4.
"""

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
    ResponseTypeDefinition,
    ReviewSession,
    User,
)
from app.services import session_lifecycle as lifecycle
from app.services import audit
from app.services.instruments._display_fields import (
    _LOCKED_DISPLAY_ORDER,
    _ordered_display_fields,
    _repack_display_orders,
    is_locked_display_source,
)
from app.services.instruments._rtds import (
    _rtd_by_id,
    _rtd_by_name,
    ensure_default_response_type_definitions,
    validation_block_for_rtd,
)
from app.services.instruments._state import _instrument_label

DEFAULT_INSTRUMENT_NAME = "Default"

DEFAULT_RESPONSE_FIELDS: list[dict[str, Any]] = [
    {
        "field_key": "rating",
        "label": "Rating",
        "rtd_name": "1-to-5int",
        "required": True,
        "order": 1,
    },
    {
        "field_key": "comments",
        "label": "Comments",
        "rtd_name": "Long_text",
        "required": False,
        "order": 2,
    },
]

_FIELD_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELD_KEY_MAX_LEN = 64


class FieldKeyError(ValueError):
    """Raised when a proposed field_key is invalid or duplicates an existing key."""


class ResponsesPresentError(Exception):
    """Raised when delete is attempted on a field with saved responses without confirm."""

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} response(s) exist for this field")
        self.cascaded_response_count = count



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
    and ensuring it carries the default response fields and the locked
    Name / Email Display Fields rows."""
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

    rtds_by_name = ensure_default_response_type_definitions(db, review_session)

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
            rtd = rtds_by_name[spec["rtd_name"]]
            db.add(
                InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=spec["field_key"],
                    label=spec["label"],
                    response_type_id=rtd.id,
                    required=spec["required"],
                    order=spec["order"],
                    validation=validation_block_for_rtd(rtd),
                )
            )
        db.flush()

    ensure_locked_display_fields(db, instrument=instrument)

    return instrument


def ensure_locked_display_fields(
    db: Session, *, instrument: Instrument
) -> int:
    """Idempotently seed the two locked Display Fields rows
    (RevieweeName, RevieweeEmail) on the given instrument. Returns the
    number of new rows created (0, 1, or 2). Rows that already exist
    are left alone — including their operator-typed labels."""
    existing_pairs = {
        (f.source_type, f.source_field) for f in instrument.display_fields
    }
    created = 0
    if ("reviewee", "name") not in existing_pairs:
        # New locked rows shift any existing rows up by 2 (or 1 if only
        # one is missing) so Name / Email always sit at the top.
        for f in instrument.display_fields:
            f.order = f.order + 1
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="reviewee",
                source_field="name",
                order=0,
                visible=True,
            )
        )
        created += 1
    if ("reviewee", "email_or_identifier") not in existing_pairs:
        for f in instrument.display_fields:
            if (f.source_type, f.source_field) != ("reviewee", "name"):
                f.order = f.order + 1
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="reviewee",
                source_field="email_or_identifier",
                order=1,
                visible=True,
            )
        )
        created += 1
    if created:
        db.flush()
        db.refresh(instrument)
    return created


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
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor, reason="instrument_added"
    )
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

    rtds_by_name = ensure_default_response_type_definitions(db, review_session)
    for spec in DEFAULT_RESPONSE_FIELDS:
        rtd = rtds_by_name[spec["rtd_name"]]
        db.add(
            InstrumentResponseField(
                instrument_id=instrument.id,
                field_key=spec["field_key"],
                label=spec["label"],
                response_type_id=rtd.id,
                required=spec["required"],
                order=spec["order"],
                validation=validation_block_for_rtd(rtd),
            )
        )
    db.flush()
    ensure_locked_display_fields(db, instrument=instrument)

    # Replicate assignment rows from any existing instrument so the
    # new instrument joins the matrix on every (reviewer, reviewee)
    # pair that's already assigned. Without this, full-matrix +
    # instrument.add leaves the new instrument with zero
    # assignments — the reviewer surface then hides its Page button
    # because it has nothing to render. Pick the lowest-ordered
    # existing instrument as the source so the clone is
    # deterministic; the (reviewer, reviewee, include, context)
    # tuples are identical across instruments today, so any source
    # would yield the same rows.
    cloned_assignments = 0
    if existing:
        source_instrument = existing[0]
        source_rows = list(
            db.execute(
                select(Assignment)
                .where(Assignment.session_id == review_session.id)
                .where(Assignment.instrument_id == source_instrument.id)
            ).scalars()
        )
        for source in source_rows:
            db.add(
                Assignment(
                    session_id=review_session.id,
                    reviewer_id=source.reviewer_id,
                    reviewee_id=source.reviewee_id,
                    instrument_id=instrument.id,
                    include=source.include,
                    context=source.context,
                    created_by_mode=source.created_by_mode,
                )
            )
            cloned_assignments += 1
        db.flush()

    created_refs: dict[str, int] = {"instrument_id": instrument.id}
    if after_instrument_id is not None:
        created_refs["after_instrument_id"] = after_instrument_id
    audit.write_event(
        db,
        event_type="instrument.created",
        summary=f"Created instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": instrument.id,
                "name": instrument.name,
                "order": new_order,
                "description": instrument.description,
                "short_label": instrument.short_label,
            }
        ),
        refs=created_refs,
        context={"cloned_assignments": cloned_assignments},
    )
    db.commit()
    return instrument


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
    review_session = instrument.session
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor, reason="instrument_deleted"
    )
    deleted_id = instrument.id
    deleted_name = instrument.name
    deleted_order = instrument.order

    db.delete(instrument)
    db.flush()

    remaining = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )
    for idx, inst in enumerate(remaining):
        if inst.order != idx:
            inst.order = idx
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.deleted",
        summary=f"Deleted instrument {deleted_name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {"id": deleted_id, "name": deleted_name, "order": deleted_order}
        ),
        refs={"instrument_id": deleted_id},
    )
    db.commit()
    return deleted_id


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
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_fields_saved",
    )
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
        # Locked rows (RevieweeName, RevieweeEmail) are forced
        # ``visible=True`` on save regardless of submitted state. The
        # operator UI suppresses the checkbox + arrows for these rows;
        # this is a server-side defense in case a forged form ever
        # arrives.
        if is_locked_display_source(field.source_type, field.source_field):
            new_visible = True
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

    # Locked rows (Name + Email) must always sit at the top in
    # (Name, Email) order regardless of what the form submitted, and
    # rows missing from the display payload must keep their relative
    # order below. Rebuild the post-save display order from scratch:
    #
    #   1. All locked rows on the instrument, in canonical order.
    #   2. Submitted non-locked rows, in submitted order.
    #   3. Any non-locked rows missing from the payload, in their
    #      pre-save order.
    submitted_ids = {f.id for f in new_display_order}
    locked_existing = sorted(
        [
            f for f in existing_display_list
            if is_locked_display_source(f.source_type, f.source_field)
        ],
        key=lambda f: _LOCKED_DISPLAY_ORDER[(f.source_type, f.source_field)],
    )
    payload_non_locked = [
        f for f in new_display_order
        if not is_locked_display_source(f.source_type, f.source_field)
    ]
    unsubmitted_non_locked = [
        f for f in existing_display_list
        if f.id not in submitted_ids
        and not is_locked_display_source(f.source_type, f.source_field)
    ]
    rebuilt_display_order = (
        locked_existing + payload_non_locked + unsubmitted_non_locked
    )

    new_response_order: list[InstrumentResponseField] = []
    response_updated: list[dict[str, Any]] = []
    for row in response_payload:
        field = existing_response.get(row.get("id"))
        if field is None:
            continue
        per_row_changes: dict[str, list[Any]] = {}
        if "label" in row:
            new_label = (row.get("label") or "").strip()
            if new_label and field.label != new_label:
                per_row_changes["label"] = [field.label, new_label]
                field.label = new_label
        if "required" in row:
            new_required = bool(row["required"])
            if field.required != new_required:
                per_row_changes["required"] = [field.required, new_required]
                field.required = new_required
        if "help_text" in row:
            new_help_text = row.get("help_text") or ""
            new_help_text = new_help_text.strip() or None
            if (field.help_text or None) != new_help_text:
                per_row_changes["help_text"] = [field.help_text, new_help_text]
                field.help_text = new_help_text
        if "help_text_visible" in row:
            new_help_visible = bool(row["help_text_visible"])
            if field.help_text_visible != new_help_visible:
                per_row_changes["help_text_visible"] = [
                    field.help_text_visible, new_help_visible,
                ]
                field.help_text_visible = new_help_visible
        if per_row_changes:
            response_updated.append(
                {
                    "field_key": field.field_key,
                    "changes": per_row_changes,
                }
            )
        new_response_order.append(field)

    # Rank-based change detection: compare each submitted row's prior
    # rank (position in the existing ordered listing) to its new rank
    # (position in the rebuilt listing). This lets the bulk save
    # normalise non-contiguous order values (e.g. 1, 2 → 0, 1 from a
    # fresh seed) without spuriously emitting a reorder event.
    response_new_rank = {f.id: i for i, f in enumerate(new_response_order)}
    display_new_rank = {f.id: i for i, f in enumerate(rebuilt_display_order)}

    _repack_display_orders(rebuilt_display_order)
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
        audit.write_event(
            db,
            event_type="instrument.fields_reordered",
            summary=f"Reordered fields on instrument {_instrument_label(instrument)}",
            actor_user_id=actor.id if actor else None,
            session=instrument.session,
            payload=audit.changes({"order": [old_order_keys, new_response_keys]}),
            refs={"instrument_id": instrument.id},
        )

    if display_changed:
        audit.write_event(
            db,
            event_type="instrument.display_fields_saved",
            summary=(
                f"Saved display-field order / visibility on "
                f"instrument {_instrument_label(instrument)}"
            ),
            actor_user_id=actor.id if actor else None,
            session=instrument.session,
            payload=audit.set_changes(updated=final_display_updated),
            refs={"instrument_id": instrument.id},
        )

    response_changed = bool(response_updated)
    if response_changed:
        audit.write_event(
            db,
            event_type="instrument.response_fields_saved",
            summary=(
                f"Saved response-field labels / required on "
                f"instrument {_instrument_label(instrument)}"
            ),
            actor_user_id=actor.id if actor else None,
            session=instrument.session,
            payload=audit.set_changes(updated=response_updated),
            refs={"instrument_id": instrument.id},
        )

    db.commit()
    return {
        "display_changed": display_changed,
        "response_changed": response_changed,
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
    help_text: str | None,
    help_text_visible: bool,
    actor: User,
) -> InstrumentResponseField:
    _validate_field_key(field_key)
    if not label or not label.strip():
        raise ValueError("Label is required.")

    rtd = _rtd_by_name(
        db, session_id=instrument.session_id, name=response_type
    )
    if rtd is None:
        raise ValueError(f"Unknown response_type: {response_type}")

    fields = _ordered_fields(db, instrument)
    if any(existing.field_key == field_key for existing in fields):
        raise FieldKeyError(
            f"A field with key '{field_key}' already exists on this instrument."
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_field_added",
    )

    new_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=field_key,
        label=label.strip(),
        response_type_id=rtd.id,
        required=required,
        order=len(fields),
        validation=validation_block_for_rtd(rtd),
        help_text=(help_text or None),
        help_text_visible=help_text_visible,
    )
    db.add(new_field)
    db.flush()

    fields.append(new_field)
    _repack_orders(fields)

    audit.write_event(
        db,
        event_type="instrument.field_added",
        summary=(
            f"Added field '{new_field.label}' ({new_field.field_key}) "
            f"to instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.snapshot(
            {
                "id": new_field.id,
                "field_key": new_field.field_key,
                "label": new_field.label,
                "response_type_id": rtd.id,
                "required": new_field.required,
                "order": new_field.order,
                "validation": new_field.validation,
                "help_text": new_field.help_text,
                "help_text_visible": new_field.help_text_visible,
            }
        ),
        refs={"instrument_id": instrument.id, "response_type_id": rtd.id},
        context={"response_type": rtd.response_type},
    )
    db.commit()

    return new_field


def add_default_response_field(
    db: Session,
    *,
    instrument: Instrument,
    after_field_id: int | None = None,
    rtd_id: int | None = None,
    label: str | None = None,
    field_key: str | None = None,
    required: bool | None = None,
    actor: User,
) -> InstrumentResponseField:
    """Append a fresh response field to an instrument.

    Default behaviour (no overrides) preserves the Slice 2 contract:
    auto-generated ``Rating{N}`` label, ``rating{N}`` field_key,
    ``required=True``, pointing at the seeded ``1-to-5int`` RTD.

    Slice 4c overrides:
    - ``rtd_id`` — operator-picked RTD from the session catalog. Must
      belong to ``instrument.session``; falls back to ``1-to-5int`` if
      the id is unknown.
    - ``label`` — operator-typed Friendly Label. Stripped of leading /
      trailing whitespace; non-empty wins over the auto default.
    - ``field_key`` — explicit key. When omitted, derives via
      ``slugify_field_key(label)`` if the operator typed a label,
      otherwise the auto ``rating{N}`` series. Conflicts with existing
      keys on the instrument get an ascending numeric suffix.
    - ``required`` — explicit override of the default ``True``.

    If ``after_field_id`` is given, the new field slots immediately
    after that one and bumps subsequent ``order`` values; otherwise
    appends at the end."""
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_field_added",
    )
    fields = _ordered_fields(db, instrument)

    rtds_by_name = ensure_default_response_type_definitions(
        db, instrument.session
    )
    chosen_rtd: ResponseTypeDefinition | None = None
    if rtd_id is not None:
        chosen_rtd = _rtd_by_id(
            db, session_id=instrument.session_id, rtd_id=rtd_id
        )
    if chosen_rtd is None:
        chosen_rtd = rtds_by_name["1-to-5int"]

    cleaned_label = (label or "").strip()
    base_num = len(fields) + 1
    auto_label = f"Rating{base_num}"
    auto_key = f"rating{base_num}"
    existing_keys = {f.field_key for f in fields}

    new_label = cleaned_label or auto_label
    if field_key:
        candidate = field_key.strip()
    elif cleaned_label:
        candidate = slugify_field_key(cleaned_label) or auto_key
    else:
        candidate = auto_key
    # Bump the trailing number until we find an unused key.
    if candidate in existing_keys:
        suffix = 2
        base = candidate
        while f"{base}{suffix}" in existing_keys:
            suffix += 1
        candidate = f"{base}{suffix}"
    if not candidate:
        candidate = auto_key

    new_order: int
    if after_field_id is None:
        new_order = len(fields)
    else:
        anchor = next((f for f in fields if f.id == after_field_id), None)
        if anchor is None:
            new_order = len(fields)
        else:
            new_order = anchor.order + 1
            for f in fields:
                if f.order >= new_order:
                    f.order += 1

    is_required = True if required is None else bool(required)

    new_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=candidate,
        label=new_label,
        response_type_id=chosen_rtd.id,
        required=is_required,
        order=new_order,
        validation=validation_block_for_rtd(chosen_rtd),
        help_text=None,
        help_text_visible=True,
    )
    db.add(new_field)
    db.flush()

    default_add_refs: dict[str, int] = {
        "instrument_id": instrument.id,
        "response_type_id": chosen_rtd.id,
    }
    if after_field_id is not None:
        default_add_refs["after_field_id"] = after_field_id
    audit.write_event(
        db,
        event_type="instrument.field_added",
        summary=(
            f"Added field '{new_field.label}' ({new_field.field_key}) "
            f"to instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.snapshot(
            {
                "id": new_field.id,
                "field_key": new_field.field_key,
                "label": new_field.label,
                "response_type_id": chosen_rtd.id,
                "required": new_field.required,
                "order": new_order,
            }
        ),
        refs=default_add_refs,
        context={"response_type": chosen_rtd.response_type},
    )
    db.commit()
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
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_field_updated",
    )
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

    audit.write_event(
        db,
        event_type="instrument.field_updated",
        summary=f"Updated field '{field.label}' on instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes(changes),
        refs={"instrument_id": instrument.id, "response_field_id": field.id},
        context={"field_key": field.field_key},
    )
    db.commit()

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

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_field_deleted",
    )

    captured = {
        "id": field.id,
        "field_key": field.field_key,
        "label": field.label,
        "response_type_id": field.response_type_id,
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

    audit.write_event(
        db,
        event_type="instrument.field_deleted",
        summary=f"Deleted field '{label_for_summary}' from instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.snapshot(captured),
        refs={"instrument_id": instrument.id},
        context={
            "field_key": captured["field_key"],
            "cascaded_responses": response_count,
        },
    )
    db.commit()


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

    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_fields_reordered",
    )

    fields[index], fields[swap_with] = fields[swap_with], fields[index]
    _repack_orders(fields)
    db.flush()

    new_keys = [f.field_key for f in fields]
    audit.write_event(
        db,
        event_type="instrument.fields_reordered",
        summary=f"Reordered fields on instrument {_instrument_label(instrument)}",
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"order": [old_keys, new_keys]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()


def update_instrument_description(
    db: Session,
    *,
    instrument: Instrument,
    description: str | None,
    actor: User,
) -> Instrument:
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_described",
    )
    cleaned = description.strip() if isinstance(description, str) else None
    new_value = cleaned or None
    old_value = instrument.description
    instrument.description = new_value
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.described",
        summary=f"Updated description on instrument {instrument.name}",
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"description": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
    return instrument


def update_short_label(
    db: Session,
    *,
    instrument: Instrument,
    short_label: str | None,
    actor: User,
) -> Instrument:
    """Update an instrument's reviewer-facing short label (Segment 11L).

    Trims whitespace; persists ``None`` when the trimmed value is
    empty (so the reviewer surface's "no friendly label set" fallback
    kicks in). Raises ``ValueError`` when the trimmed value exceeds
    32 chars — the HTML5 ``maxlength`` attribute on the operator-side
    input is the user-visible guardrail, but the server-side cap is
    the bedrock guard. Emits an ``instrument.short_label_updated``
    audit event only when the stored value actually changes
    (no-op edits don't write events or invalidate ``validated``).

    Mirrors the shape of :func:`update_instrument_description` so
    the two read as siblings.
    """
    cleaned = short_label.strip() if isinstance(short_label, str) else None
    new_value = cleaned or None
    if new_value is not None and len(new_value) > 32:
        raise ValueError(
            f"short_label exceeds 32 chars: {len(new_value)}"
        )
    if instrument.short_label == new_value:
        return instrument  # no-op; no audit, no invalidate
    lifecycle.invalidate_if_validated(
        db,
        review_session=instrument.session,
        user=actor,
        reason="instrument_short_label_updated",
    )
    old_value = instrument.short_label
    instrument.short_label = new_value
    db.flush()
    audit.write_event(
        db,
        event_type="instrument.short_label_updated",
        summary=(
            f"Updated short_label on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=instrument.session,
        payload=audit.changes({"short_label": [old_value, new_value]}),
        refs={"instrument_id": instrument.id},
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
        audit.write_event(
            db,
            event_type="instruments.bulk_accepting_responses",
            summary=(
                f"Set accepting_responses={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session=review_session,
            payload=audit.set_changes(
                updated=[{"instrument_id": i} for i in changed]
            ),
            context={"target": bool(target)},
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
    # #16 — visibility-when-closed is a display flag, not part of the
    # validation snapshot. Deliberately does NOT call
    # ``lifecycle.invalidate_if_validated``. See ``docs/status.md`` and
    # ``test_invalidation_on_setup_mutation.py`` for the regression test.
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
        audit.write_event(
            db,
            event_type="instruments.bulk_visibility_when_closed",
            summary=(
                f"Set responses_visible_when_closed={target} on "
                f"{len(changed)} instrument(s)"
            ),
            actor_user_id=actor.id if actor else None,
            session=review_session,
            payload=audit.set_changes(
                updated=[{"instrument_id": i} for i in changed]
            ),
            context={"target": bool(target)},
        )
        db.commit()
    return changed
