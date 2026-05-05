from __future__ import annotations

import re
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Response,
    ResponseTypeDefinition,
    Reviewee,
    ReviewSession,
    User,
)
from app.services import session_lifecycle as lifecycle
from app.services.audit import write_event

# Audit-event types that signal "this instrument's field tables were
# saved by the operator" — used by ``saved_state_for_session`` to
# render the per-instrument-card status pill.
_SAVED_STATE_EVENT_TYPES: frozenset[str] = frozenset({
    "instrument.display_fields_saved",
    "instrument.display_field_added",
    "instrument.display_field_updated",
    "instrument.display_field_deleted",
    "instrument.display_field_moved",
    "instrument.field_added",
    "instrument.field_updated",
    "instrument.field_deleted",
    "instrument.fields_reordered",
    "instrument.response_fields_saved",
})


def saved_state_for_session(
    db: Session, *, session_id: int
) -> dict[int, bool]:
    """Map ``instrument_id`` → True if the instrument has any audit
    event indicating an operator-driven save of its field tables; False
    otherwise. Instruments with no qualifying audit history render as
    "not saved" on the operator's status sub-card."""
    rows = db.execute(
        select(AuditEvent.event_type, AuditEvent.detail)
        .where(AuditEvent.session_id == session_id)
        .where(AuditEvent.event_type.in_(_SAVED_STATE_EVENT_TYPES))
    ).all()
    saved: dict[int, bool] = {}
    for event_type, detail in rows:
        if not detail:
            continue
        instrument_id = detail.get("instrument_id")
        if isinstance(instrument_id, int):
            saved[instrument_id] = True
    return saved

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
# guide/instruments.md, ``RevieweeName`` and ``RevieweeEmail``
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

_FIELD_KEY_REGEX = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELD_KEY_MAX_LEN = 64

_VALID_DISPLAY_SOURCES: frozenset[tuple[str, str]] = frozenset(
    _DEFAULT_DISPLAY_LABELS.keys()
)

# Response Type Definitions — the per-session catalog of types
# referenced by ``InstrumentResponseField.response_type_id``. The
# ten rows below are seeded on every session and are fully locked
# (name + data_type + parameters; cannot be deleted). Operator-
# defined rows land in 4b.
_VALID_DATA_TYPES: frozenset[str] = frozenset(
    {"String", "Integer", "Decimal", "List"}
)

SEEDED_RESPONSE_TYPE_DEFINITIONS: list[dict[str, Any]] = [
    {"response_type": "Long_text",  "data_type": "String",  "min": 0,    "max": 2000, "step": None, "list_csv": None},
    {"response_type": "Short_text", "data_type": "String",  "min": 0,    "max": 100,  "step": None, "list_csv": None},
    {"response_type": "Yes_no",     "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Yes, No"},
    {"response_type": "Grade",      "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "A+, A, A-, B+, B, B-, C+, C, D+, D, F"},
    {"response_type": "Likert5",    "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Strongly Disagree, Disagree, Neutral, Agree, Strongly Agree"},
    {"response_type": "100int",     "data_type": "Integer", "min": 0,    "max": 100,  "step": 1,    "list_csv": None},
    {"response_type": "0-to-2int",  "data_type": "Integer", "min": 0,    "max": 2,    "step": 1,    "list_csv": None},
    {"response_type": "1-to-5int",  "data_type": "Integer", "min": 1,    "max": 5,    "step": 1,    "list_csv": None},
    {"response_type": "1-to-5half", "data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.5,  "list_csv": None},
    {"response_type": "1-to-5dec",  "data_type": "Decimal", "min": 1.0,  "max": 5.0,  "step": 0.1,  "list_csv": None},
]


def ensure_default_response_type_definitions(
    db: Session, review_session: ReviewSession
) -> dict[str, ResponseTypeDefinition]:
    """Idempotently seed the ten baseline RTD rows on the given
    session. Returns a dict keyed by ``response_type`` name covering
    every seeded row currently in the DB for the session.

    Re-running on a session that already has the seeds is a no-op.
    Operator-defined rows are left untouched."""
    existing = {
        rtd.response_type: rtd
        for rtd in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == review_session.id
            )
        ).scalars()
    }

    added = False
    for index, spec in enumerate(SEEDED_RESPONSE_TYPE_DEFINITIONS):
        if spec["response_type"] in existing:
            continue
        rtd = ResponseTypeDefinition(
            session_id=review_session.id,
            response_type=spec["response_type"],
            data_type=spec["data_type"],
            min=spec["min"],
            max=spec["max"],
            step=spec["step"],
            list_csv=spec["list_csv"],
            is_seeded=True,
            seed_order=index,
        )
        db.add(rtd)
        existing[spec["response_type"]] = rtd
        added = True

    if added:
        db.flush()

    return existing


def validation_block_for_rtd(
    rtd: ResponseTypeDefinition,
) -> dict[str, Any] | None:
    """Map an RTD row to the JSON shape written to
    ``instrument_response_fields.validation`` per
    ``guide/instruments.md`` "Validation derivation"."""
    if rtd.data_type == "List":
        if not rtd.list_csv:
            return {"choices": []}
        return {
            "choices": [
                item.strip()
                for item in rtd.list_csv.split(",")
                if item.strip()
            ]
        }
    if rtd.data_type == "String":
        block: dict[str, Any] = {}
        if rtd.min is not None:
            block["min_length"] = int(rtd.min)
        if rtd.max is not None:
            block["max_length"] = int(rtd.max)
        return block or None
    if rtd.data_type in ("Integer", "Decimal"):
        cast = int if rtd.data_type == "Integer" else float
        block = {}
        if rtd.min is not None:
            block["min"] = cast(rtd.min)
        if rtd.max is not None:
            block["max"] = cast(rtd.max)
        if rtd.step is not None:
            block["step"] = cast(rtd.step)
        return block or None
    return None


class RTDPrecisionError(ValueError):
    """Raised when an operator-defined RTD's numeric cell violates
    the precision rule for its Data Type. Per
    ``guide/instruments.md`` "Save-time validation rules":

    - ``Integer`` ``Min`` / ``Max`` / ``Step`` must have no
      fractional part.
    - ``Decimal`` ``Min`` / ``Max`` / ``Step`` must have at most
      one decimal place.
    """


def _has_fractional_part(value: float) -> bool:
    return value != int(value)


def _exceeds_one_decimal_place(value: float) -> bool:
    # Guard against float drift: round to one decimal place and
    # compare against ten times the value (which should be an
    # integer if the input had ≤ 1dp).
    scaled = round(value * 10)
    return abs(value * 10 - scaled) > 1e-9


def assert_rtd_precision(
    *, data_type: str, min: float | None, max: float | None, step: float | None
) -> None:
    """Validate the numeric cells on an operator-defined RTD against
    the Data Type's precision rule. No-op for ``String`` and ``List``
    rows; those have their own validation paths. Raises
    ``RTDPrecisionError`` on the first violation."""
    cells = [("Min", min), ("Max", max), ("Step", step)]
    if data_type == "Integer":
        for label, value in cells:
            if value is None:
                continue
            if _has_fractional_part(float(value)):
                raise RTDPrecisionError(
                    f"{label} must be an integer for Integer Response Types "
                    f"(got {value})."
                )
    elif data_type == "Decimal":
        for label, value in cells:
            if value is None:
                continue
            if _exceeds_one_decimal_place(float(value)):
                raise RTDPrecisionError(
                    f"{label} must have at most one decimal place for "
                    f"Decimal Response Types (got {value})."
                )


def get_session_rtds(
    db: Session, *, session_id: int
) -> list[ResponseTypeDefinition]:
    """Return the session's RTDs, sorted: seeded rows first in their
    canonical seed order, then operator-defined rows by id."""
    rows = list(
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == session_id
            )
        ).scalars()
    )
    return sorted(
        rows,
        key=lambda r: (0 if r.is_seeded else 1, r.seed_order, r.id),
    )


def _rtd_by_id(
    db: Session, *, session_id: int, rtd_id: int
) -> ResponseTypeDefinition | None:
    return db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == rtd_id,
            ResponseTypeDefinition.session_id == session_id,
        )
    ).scalar_one_or_none()


def _rtd_by_name(
    db: Session, *, session_id: int, name: str
) -> ResponseTypeDefinition | None:
    return db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == session_id,
            ResponseTypeDefinition.response_type == name,
        )
    ).scalar_one_or_none()


# --- Slice 4b: operator add / edit / delete on RTD card --------------

class RTDValidationError(ValueError):
    """Raised when an operator-defined RTD violates a save-time rule
    (per ``guide/instruments.md`` "Save-time validation rules"):
    empty list, Min > Max, Step doesn't evenly divide (Max − Min),
    incomplete row, etc. ``RTDPrecisionError`` is the more specific
    subclass for the precision rules."""


class RTDLockedError(Exception):
    """Raised when an operator attempts to mutate a seeded RTD row
    (rename / re-data-type / delete) — those are spec-locked."""


class RTDInUseError(Exception):
    """Raised when delete is attempted on an operator-defined RTD that
    has dependent ``instrument_response_fields`` rows without the
    operator confirming the cascade preview."""

    def __init__(self, dependents: dict[str, Any]) -> None:
        super().__init__(
            f"{dependents['response_field_count']} response field(s) "
            f"reference this Response Type"
        )
        self.dependents = dependents


class RTDDeleteWouldEmptyInstrumentError(Exception):
    """Raised when a cascade-delete on an operator-defined RTD would
    leave at least one instrument with **zero** Response Fields rows.
    The route translates this into a hard-block banner naming the
    affected instrument(s); operator must add a non-ODT row to that
    instrument first. Slice 4d Gap 3."""

    def __init__(self, would_empty: list[dict[str, Any]]) -> None:
        names = ", ".join(f"#{e['instrument_number']}" for e in would_empty)
        super().__init__(
            f"Cascade would leave instrument(s) {names} with no Response Fields"
        )
        self.would_empty = would_empty


def count_rtd_dependents(
    db: Session, *, rtd: ResponseTypeDefinition
) -> dict[str, Any]:
    """Count the rows that would be cascade-dropped if this RTD is
    deleted, plus the list of instruments that would be left with
    zero Response Fields rows after the cascade. Used by the
    operator-delete confirmation dialog and the hard-block check."""
    rf_rows = list(
        db.execute(
            select(InstrumentResponseField.id, InstrumentResponseField.instrument_id)
            .where(InstrumentResponseField.response_type_id == rtd.id)
        )
    )
    rf_ids = [r[0] for r in rf_rows]
    instrument_ids = {r[1] for r in rf_rows}

    if not rf_ids:
        response_count = 0
        assignment_count = 0
    else:
        response_count = int(
            db.execute(
                select(func.count(Response.id)).where(
                    Response.response_field_id.in_(rf_ids)
                )
            ).scalar_one()
        )
        assignment_count = int(
            db.execute(
                select(func.count(func.distinct(Response.assignment_id))).where(
                    Response.response_field_id.in_(rf_ids)
                )
            ).scalar_one()
        )

    # For each instrument that has any RF row referencing this RTD,
    # count the *other* RF rows on that instrument (rows not
    # referencing this RTD). If zero, the cascade would empty it.
    would_empty: list[dict[str, Any]] = []
    if instrument_ids:
        instruments_in_session = list(
            db.execute(
                select(Instrument)
                .where(Instrument.session_id == rtd.session_id)
                .order_by(Instrument.order, Instrument.id)
            ).scalars()
        )
        position_by_id = {inst.id: idx for idx, inst in enumerate(instruments_in_session, start=1)}
        for instrument_id in instrument_ids:
            other_rf_count = int(
                db.execute(
                    select(func.count(InstrumentResponseField.id)).where(
                        InstrumentResponseField.instrument_id == instrument_id,
                        InstrumentResponseField.response_type_id != rtd.id,
                    )
                ).scalar_one()
            )
            if other_rf_count == 0:
                would_empty.append({
                    "instrument_id": instrument_id,
                    "instrument_number": position_by_id.get(instrument_id, 0),
                })
        # Sort by on-screen number so the banner reads in card order.
        would_empty.sort(key=lambda e: e["instrument_number"])

    return {
        "response_field_count": len(rf_ids),
        "instrument_count": len(instrument_ids),
        "response_count": response_count,
        "assignment_count": assignment_count,
        "would_empty_instruments": would_empty,
    }


def _validate_rtd_payload(
    *,
    response_type: str,
    data_type: str,
    min: float | None,
    max: float | None,
    step: float | None,
    list_csv: str | None,
) -> None:
    """Apply the save-time validation rules from
    ``guide/instruments.md`` for a fresh-or-updated RTD payload."""
    cleaned_name = (response_type or "").strip()
    if not cleaned_name:
        raise RTDValidationError("Response Type name is required.")
    if data_type not in _VALID_DATA_TYPES:
        raise RTDValidationError(
            f"Unknown Data Type: {data_type!r} (expected one of "
            f"{sorted(_VALID_DATA_TYPES)})."
        )

    if data_type == "List":
        if not list_csv or not [
            item.strip() for item in list_csv.split(",") if item.strip()
        ]:
            raise RTDValidationError("List requires at least one item.")
        return

    if data_type == "String":
        if min is None or max is None:
            raise RTDValidationError(
                "String Response Types require Min and Max."
            )
        if min > max:
            raise RTDValidationError("Min cannot exceed Max.")
        return

    # Integer / Decimal
    if min is None or max is None or step is None:
        raise RTDValidationError(
            f"{data_type} Response Types require Min, Max, and Step."
        )
    assert_rtd_precision(
        data_type=data_type, min=min, max=max, step=step
    )
    if min > max:
        raise RTDValidationError("Min cannot exceed Max.")
    span = max - min
    # Float-safe divisibility check: scale by 10 (one-dp) for Decimal
    # since the precision rule above already constrains decimal places.
    scaled_span = round(span * 10)
    scaled_step = round(step * 10)
    if scaled_step <= 0:
        raise RTDValidationError("Step must be positive.")
    if scaled_span % scaled_step != 0:
        raise RTDValidationError(
            f"Step must evenly divide (Max − Min) = {span}; got {step}."
        )


def add_response_type_definition(
    db: Session,
    *,
    review_session: ReviewSession,
    response_type: str,
    data_type: str,
    min: float | None,
    max: float | None,
    step: float | None,
    list_csv: str | None,
    actor: User,
) -> ResponseTypeDefinition:
    """Add a fresh operator-defined RTD on the session. Validates per
    the save-time rules; raises ``RTDValidationError`` /
    ``RTDPrecisionError`` on a bad payload, or ``RTDValidationError``
    if the name collides with an existing row on the session."""
    lifecycle.invalidate_if_validated(
        db, review_session=review_session, user=actor, reason="response_type_added"
    )
    cleaned_name = response_type.strip()
    _validate_rtd_payload(
        response_type=cleaned_name,
        data_type=data_type,
        min=min,
        max=max,
        step=step,
        list_csv=list_csv,
    )
    if _rtd_by_name(
        db, session_id=review_session.id, name=cleaned_name
    ) is not None:
        raise RTDValidationError(
            f"A Response Type named {cleaned_name!r} already exists on "
            f"this session."
        )

    rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type=cleaned_name,
        data_type=data_type,
        min=min if data_type != "List" else None,
        max=max if data_type != "List" else None,
        step=step if data_type in ("Integer", "Decimal") else None,
        list_csv=list_csv if data_type == "List" else None,
        is_seeded=False,
        seed_order=0,
    )
    db.add(rtd)
    db.flush()

    write_event(
        db,
        event_type="response_type.added",
        summary=(
            f"Added Response Type '{rtd.response_type}' "
            f"({rtd.data_type}) on session {review_session.code}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=review_session.id,
        detail={
            "response_type_id": rtd.id,
            "session_id": review_session.id,
            "response_type": rtd.response_type,
            "data_type": rtd.data_type,
            "min": rtd.min,
            "max": rtd.max,
            "step": rtd.step,
            "list_csv": rtd.list_csv,
        },
    )
    db.commit()
    return rtd


def update_response_type_definition(
    db: Session,
    *,
    rtd: ResponseTypeDefinition,
    min: float | None,
    max: float | None,
    step: float | None,
    list_csv: str | None,
    actor: User,
) -> ResponseTypeDefinition:
    """Update an operator-defined RTD's parameters. Name + Data Type
    are spec-locked. Propagates the new ``validation`` block to every
    Response Fields row that references this RTD (per
    ``guide/instruments.md`` "Locked vs. operator-added rows")."""
    if rtd.is_seeded:
        raise RTDLockedError(
            f"Seeded Response Type {rtd.response_type!r} cannot be edited."
        )
    _validate_rtd_payload(
        response_type=rtd.response_type,
        data_type=rtd.data_type,
        min=min,
        max=max,
        step=step,
        list_csv=list_csv,
    )

    lifecycle.invalidate_if_validated(
        db, review_session=rtd.session, user=actor, reason="response_type_updated"
    )

    changes: dict[str, list[Any]] = {}
    if rtd.data_type == "List":
        new_min = new_max = new_step = None
        new_list = list_csv
    elif rtd.data_type == "String":
        new_min, new_max = min, max
        new_step = None
        new_list = None
    else:
        new_min, new_max, new_step = min, max, step
        new_list = None

    if rtd.min != new_min:
        changes["min"] = [rtd.min, new_min]
        rtd.min = new_min
    if rtd.max != new_max:
        changes["max"] = [rtd.max, new_max]
        rtd.max = new_max
    if rtd.step != new_step:
        changes["step"] = [rtd.step, new_step]
        rtd.step = new_step
    if rtd.list_csv != new_list:
        changes["list_csv"] = [rtd.list_csv, new_list]
        rtd.list_csv = new_list

    db.flush()

    # Propagate the new validation block to every dependent RF row
    # (per spec). Do this regardless of whether ``changes`` is empty —
    # if some upstream code wrote an out-of-sync block, this re-syncs.
    new_block = validation_block_for_rtd(rtd)
    dependent_rfs = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.response_type_id == rtd.id
            )
        ).scalars()
    )
    propagated = 0
    for rf in dependent_rfs:
        if rf.validation != new_block:
            rf.validation = new_block
            propagated += 1
    if propagated:
        db.flush()

    if changes or propagated:
        write_event(
            db,
            event_type="response_type.updated",
            summary=(
                f"Updated Response Type '{rtd.response_type}' on "
                f"session {rtd.session_id}"
            ),
            actor_user_id=actor.id if actor else None,
            session_id=rtd.session_id,
            detail={
                "response_type_id": rtd.id,
                "session_id": rtd.session_id,
                "response_type": rtd.response_type,
                "data_type": rtd.data_type,
                "changes": changes,
                "propagated_response_field_count": propagated,
            },
        )
    db.commit()
    return rtd


def delete_response_type_definition(
    db: Session,
    *,
    rtd: ResponseTypeDefinition,
    confirm: bool,
    actor: User,
) -> dict[str, Any]:
    """Delete an operator-defined RTD. Seeded rows are spec-locked
    (raises ``RTDLockedError``). When the cascade would leave at
    least one instrument with zero Response Fields rows, raises
    ``RTDDeleteWouldEmptyInstrumentError`` (Slice 4d Gap 3) — this
    preempts the in-use check and is *not* overridable via
    ``confirm`` (the operator must add a non-ODT row to the
    affected instrument first). When the row has dependent
    Response Fields rows and ``confirm`` is False, raises
    ``RTDInUseError`` so the route can render the cascade-preview
    confirmation. The actual cascade fires through the FK
    ``ON DELETE CASCADE`` from Slice 4a."""
    if rtd.is_seeded:
        raise RTDLockedError(
            f"Seeded Response Type {rtd.response_type!r} cannot be deleted."
        )

    dependents = count_rtd_dependents(db, rtd=rtd)
    if dependents["would_empty_instruments"]:
        raise RTDDeleteWouldEmptyInstrumentError(
            dependents["would_empty_instruments"]
        )
    if dependents["response_field_count"] > 0 and not confirm:
        raise RTDInUseError(dependents)

    lifecycle.invalidate_if_validated(
        db, review_session=rtd.session, user=actor, reason="response_type_deleted"
    )

    snapshot = {
        "response_type": rtd.response_type,
        "data_type": rtd.data_type,
        "min": rtd.min,
        "max": rtd.max,
        "step": rtd.step,
        "list_csv": rtd.list_csv,
    }
    session_id = rtd.session_id
    rtd_id = rtd.id
    db.delete(rtd)
    db.flush()

    write_event(
        db,
        event_type="response_type.deleted",
        summary=(
            f"Deleted Response Type '{snapshot['response_type']}' on "
            f"session {session_id}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=session_id,
        detail={
            "response_type_id": rtd_id,
            "session_id": session_id,
            "snapshot": snapshot,
            "cascaded": dependents,
        },
    )
    db.commit()
    return dependents


def is_locked_display_source(source_type: str, source_field: str) -> bool:
    """Return True for the two Display Fields rows that are locked at
    fixed positions / always-visible (RevieweeName, RevieweeEmail)."""
    return (source_type, source_field) in _LOCKED_DISPLAY_SOURCES


class LockedDisplayFieldError(ValueError):
    """Raised when a locked Display Fields row (Name / Email) is the
    target of an operation that's not permitted on locked rows
    (delete, hide, reorder)."""


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
            "cloned_assignments": cloned_assignments,
        },
    )
    db.commit()
    return instrument


def _instrument_label(instrument: Instrument) -> str:
    """Operator-facing label for audit-event copy.

    Prefers ``short_label`` (the operator-set reviewer-facing framing
    added in Segment 11L) over ``description.strip()`` over the
    auto-generated ``name`` system handle. Lets ``"Updated description
    on instrument Skills"`` read better than ``"…on instrument
    instrument_3"`` once an operator has set a short label.
    """
    short = (instrument.short_label or "").strip()
    if short:
        return short
    desc = (instrument.description or "").strip()
    if desc:
        return desc
    return instrument.name


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
    lifecycle.invalidate_if_validated(
        db, review_session=instrument.session, user=actor, reason="instrument_deleted"
    )
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

    write_event(
        db,
        event_type="instrument.display_field_moved",
        summary=(
            f"Moved display field {field.source_type}.{field.source_field} "
            f"{direction} on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
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

    response_changed = bool(response_updated)
    if response_changed:
        write_event(
            db,
            event_type="instrument.response_fields_saved",
            summary=(
                f"Saved response-field labels / required on "
                f"instrument {_instrument_label(instrument)}"
            ),
            actor_user_id=actor.id if actor else None,
            session_id=instrument.session_id,
            detail={
                "instrument_id": instrument.id,
                "session_id": instrument.session_id,
                "updated": response_updated,
            },
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
            "response_type": rtd.response_type,
            "response_type_id": rtd.id,
            "required": new_field.required,
            "validation": new_field.validation,
            "help_text": new_field.help_text,
            "help_text_visible": new_field.help_text_visible,
        },
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
            "response_type": chosen_rtd.response_type,
            "response_type_id": chosen_rtd.id,
            "required": new_field.required,
            "order": new_order,
            "after_field_id": after_field_id,
        },
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
    write_event(
        db,
        event_type="instrument.short_label_updated",
        summary=(
            f"Updated short_label on instrument {_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session_id=instrument.session_id,
        detail={
            "instrument_id": instrument.id,
            "session_id": instrument.session_id,
            "short_label": [old_value, new_value],
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
