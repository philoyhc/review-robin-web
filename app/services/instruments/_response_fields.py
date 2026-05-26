"""Response Fields slice — per-instrument response columns the
reviewer fills in (Rating / Comments and any operator-added rows
hooked up to a Response Type Definition).

Slice 3 of the §12.A ladder (``guide/archive/major_refactor.md``).

Owns the field-key vocabulary, the row-level CRUD
(add / update / delete / move), the consolidated bulk-save handler
that interleaves display + response field updates from a single
form, and the seeded ``DEFAULT_RESPONSE_FIELDS`` shape used by
``ensure_default_instrument`` / ``create_instrument``.

Saves emit ``instrument.field_added`` / ``.field_updated`` /
``.field_deleted`` / ``.fields_reordered`` /
``.response_fields_saved`` / ``.display_fields_saved`` audit events
(the last two from the bulk-save path).

Source range in pre-PR-3 ``_legacy.py``: lines 42-122
(constants + classes + slug/order helpers) and 402-1055
(``bulk_save_fields`` through ``move_response_field``).
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
    User,
)
from app.services import audit
from app.services import session_lifecycle as lifecycle
from app.services.instruments._display_fields import (
    _LOCKED_DISPLAY_ORDER,
    _ordered_display_fields,
    _repack_display_orders,
    is_locked_display_source,
)
from app.services.instruments._state import _instrument_label


# Segment 18J Wave 2 PR iii-b2 — default response fields now carry
# inline bound info directly. Pre-iii-b2 they pointed at the seeded
# ``1-to-5int`` + ``Long_text`` RTDs; all seeded RTDs retire in
# this PR so the defaults can't depend on them anymore.
# ``response_type`` is the analytical-export name; bounds populate
# ``data_type`` / ``min`` / ``max`` / ``step`` inline.
# ``response_type_id`` lands NULL on every default field.
DEFAULT_RESPONSE_FIELDS: list[dict[str, Any]] = [
    {
        "field_key": "rating",
        "label": "Rating",
        "data_type": "Integer",
        "response_type": "1-to-5int",
        "min": 1.0,
        "max": 5.0,
        "step": 1.0,
        "list_csv": None,
        "required": True,
        "order": 1,
    },
    {
        "field_key": "comments",
        "label": "Comments",
        "data_type": "String",
        "response_type": "Long_text",
        "min": 0.0,
        "max": 2000.0,
        "step": None,
        "list_csv": None,
        "required": False,
        "order": 2,
    },
]


def _inline_kwargs_from_default_spec(
    spec: dict[str, Any],
) -> dict[str, Any]:
    """Lift inline-bound kwargs out of a DEFAULT_RESPONSE_FIELDS
    entry so creators can splat them into an
    InstrumentResponseField constructor."""
    return {
        "_inline_data_type": spec["data_type"],
        "_inline_response_type": spec["response_type"],
        "_inline_min": spec.get("min"),
        "_inline_max": spec.get("max"),
        "_inline_step": spec.get("step"),
        "_inline_list_csv": spec.get("list_csv"),
    }


def _validation_block_from_default_spec(
    spec: dict[str, Any],
) -> dict[str, Any] | None:
    """Build the ``instrument_response_fields.validation`` JSON for
    a DEFAULT_RESPONSE_FIELDS entry. Mirrors
    :func:`validation_block_for_rtd` shape but reads the inline
    spec instead of an RTD instance."""
    data_type = spec["data_type"]
    if data_type == "String":
        block: dict[str, Any] = {}
        if spec.get("min") is not None:
            block["min_length"] = int(spec["min"])
        if spec.get("max") is not None:
            block["max_length"] = int(spec["max"])
        return block or None
    if data_type in ("Integer", "Decimal"):
        cast = int if data_type == "Integer" else float
        block = {}
        if spec.get("min") is not None:
            block["min"] = cast(spec["min"])
        if spec.get("max") is not None:
            block["max"] = cast(spec["max"])
        if spec.get("step") is not None:
            block["step"] = cast(spec["step"])
        return block or None
    return None

_FIELD_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELD_KEY_MAX_LEN = 64


class FieldKeyError(ValueError):
    """Raised when a proposed field_key is invalid or duplicates an existing key."""


class ResponsesPresentError(Exception):
    """Raised when delete is attempted on a field with saved responses without confirm."""

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} response(s) exist for this field")
        self.cascaded_response_count = count


class ResponseFieldShapeChangeError(Exception):
    """Raised when an operator tries to change a response field's data
    type or numeric / list bounds while the field already has saved
    responses (Wave 3 PR ii — sibling of ResponsesPresentError).
    The contract: operator must clear the responses first before
    re-shaping the field, so existing response data doesn't end up
    silently mis-typed (e.g. Integer → String leaving stray "abc"
    values un-flagged) or out-of-bounds (e.g. tightening max=5 below
    a saved "999")."""

    def __init__(
        self,
        *,
        field_label: str,
        count: int,
        changed_attrs: list[str],
    ) -> None:
        super().__init__(
            f"{count} response(s) exist for {field_label!r}; "
            f"cannot change {', '.join(changed_attrs)}"
        )
        self.field_label = field_label
        self.cascaded_response_count = count
        self.changed_attrs = changed_attrs


class InvalidResponseFieldShapeError(Exception):
    """Raised when an operator-authored response field has a
    nonsensical authoring shape (Wave 3 PR ii) — max < min, step
    ≤ 0, empty List options, or max_length ≤ 0 for String. The
    Band 3 ✓ button is client-side-gated against the same checks;
    this exception is defence-in-depth for direct API hits."""

    def __init__(self, errors: list[tuple[str, str]]) -> None:
        super().__init__("; ".join(f"{label}: {msg}" for label, msg in errors))
        self.errors = errors


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
        # ``row.get("label")`` retired in Segment 15A Slice 2.
        # The per-instrument label override is no longer in the
        # resolver chain, so the bulk-save POST no longer accepts
        # a value for this field. Any stray ``label`` value in
        # the payload is silently ignored; ``field.label`` is
        # preserved as dead data.
        new_visible = bool(row.get("visible", field.visible))
        # Locked rows (RevieweeName, RevieweeEmail) are forced
        # ``visible=True`` on save regardless of submitted state. The
        # operator UI suppresses the checkbox + arrows for these rows;
        # this is a server-side defense in case a forged form ever
        # arrives.
        #
        # Segment 13C: a group-scoped instrument has no locked rows —
        # the RevieweeName row's Include is operator-choosable
        # (unticking it omits the member-name list from the composed
        # group identity), so the force does not apply there.
        if (
            is_locked_display_source(field.source_type, field.source_field)
            and instrument.group_kind is None
        ):
            new_visible = True
        per_row_changes: dict[str, list[Any]] = {}
        if field.visible != new_visible:
            per_row_changes["visible"] = [field.visible, new_visible]
        old_order = field.order
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

    # The per-session ``response_type_definitions`` table retired
    # 2026-05-26 — ``response_type`` is now an opaque label stored
    # verbatim into ``_inline_response_type``. New rows default to
    # the Rating Integer 1-5 shape (matching ``DEFAULT_RESPONSE_FIELDS[0]``);
    # the operator edits the inline data_type / bounds via the Band 3
    # row UI after creation if a different shape is wanted.
    default_spec = DEFAULT_RESPONSE_FIELDS[0]
    inline_kwargs = _inline_kwargs_from_default_spec(default_spec)
    inline_kwargs["_inline_response_type"] = response_type
    validation_block = _validation_block_from_default_spec(default_spec)

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
        required=required,
        order=len(fields),
        validation=validation_block,
        help_text=(help_text or None),
        help_text_visible=help_text_visible,
        **inline_kwargs,
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
                "required": new_field.required,
                "order": new_field.order,
                "validation": new_field.validation,
                "help_text": new_field.help_text,
                "help_text_visible": new_field.help_text_visible,
            }
        ),
        refs={"instrument_id": instrument.id},
        context={"response_type": response_type},
    )
    db.commit()

    return new_field


def add_default_response_field(
    db: Session,
    *,
    instrument: Instrument,
    after_field_id: int | None = None,
    label: str | None = None,
    field_key: str | None = None,
    required: bool | None = None,
    actor: User,
) -> InstrumentResponseField:
    """Append a fresh response field to an instrument.

    Auto-generates ``Rating{N}`` label + ``rating{N}`` field_key,
    ``required=True``, with the Rating-Integer-1-5 inline shape
    (matching ``DEFAULT_RESPONSE_FIELDS[0]``). Operator edits the
    Type / bounds via the Band 3 row UI after creation.

    Overrides:
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

    default_spec = DEFAULT_RESPONSE_FIELDS[0]
    field_kwargs: dict[str, Any] = {
        "validation": _validation_block_from_default_spec(default_spec),
        **_inline_kwargs_from_default_spec(default_spec),
    }
    audit_response_type: str = default_spec["response_type"]

    new_field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key=candidate,
        label=new_label,
        required=is_required,
        order=new_order,
        help_text=None,
        help_text_visible=True,
        **field_kwargs,
    )
    db.add(new_field)
    db.flush()

    default_add_refs: dict[str, int] = {"instrument_id": instrument.id}
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
                "required": new_field.required,
                "order": new_order,
            }
        ),
        refs=default_add_refs,
        context={"response_type": audit_response_type},
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
