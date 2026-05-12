"""Response Type Definitions (RTDs) — the per-session catalog of types
referenced by ``InstrumentResponseField.response_type_id``.

Slice 1 of the §12.A ladder (``guide/archive/major_refactor.md``).

Owns the ten seeded RTDs and the operator-defined add / edit /
delete flow on the Response Type Definitions card. Saves emit
``response_type.added`` / ``response_type.updated`` /
``response_type.deleted`` audit events; updates also propagate the
recomputed ``validation`` block to every dependent
``instrument_response_fields`` row.

Source range in pre-PR-1 ``_legacy.py``: lines 99-708.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    OperatorResponseTypeDefinition,
    Response,
    ResponseTypeDefinition,
    ReviewSession,
    User,
)
from app.services import audit
from app.services import session_lifecycle as lifecycle


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
    {"response_type": "Likert5",    "data_type": "List",    "min": None, "max": None, "step": None, "list_csv": "Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree"},
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
    ``spec/instruments.md`` "Validation derivation"."""
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
    ``spec/instruments.md`` "Save-time validation rules":

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
    (per ``spec/instruments.md`` "Save-time validation rules"):
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
    ``spec/instruments.md`` for a fresh-or-updated RTD payload."""
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

    audit.write_event(
        db,
        event_type="response_type.added",
        summary=(
            f"Added Response Type '{rtd.response_type}' "
            f"({rtd.data_type}) on session {review_session.code}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(
            {
                "id": rtd.id,
                "response_type": rtd.response_type,
                "data_type": rtd.data_type,
                "min": rtd.min,
                "max": rtd.max,
                "step": rtd.step,
                "list_csv": rtd.list_csv,
            }
        ),
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
    ``spec/instruments.md`` "Locked vs. operator-added rows")."""
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
        audit.write_event(
            db,
            event_type="response_type.updated",
            summary=(
                f"Updated Response Type '{rtd.response_type}' on "
                f"session {rtd.session_id}"
            ),
            actor_user_id=actor.id if actor else None,
            session=rtd.session,
            payload=audit.changes(changes),
            refs={"response_type_id": rtd.id},
            context={
                "response_type": rtd.response_type,
                "data_type": rtd.data_type,
                "propagated_response_fields": propagated,
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

    captured = {
        "id": rtd.id,
        "response_type": rtd.response_type,
        "data_type": rtd.data_type,
        "min": rtd.min,
        "max": rtd.max,
        "step": rtd.step,
        "list_csv": rtd.list_csv,
    }
    review_session = rtd.session
    rtd_id = rtd.id
    db.delete(rtd)
    db.flush()

    audit.write_event(
        db,
        event_type="response_type.deleted",
        summary=(
            f"Deleted Response Type '{captured['response_type']}' on "
            f"session {review_session.id}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.snapshot(captured),
        refs={"response_type_id": rtd_id},
        context={
            "cascaded_response_fields": dependents["response_field_count"],
            "cascaded_instruments": dependents["instrument_count"],
            "cascaded_responses": dependents["response_count"],
            "cascaded_assignments": dependents["assignment_count"],
        },
    )
    db.commit()
    return dependents


def list_operator_rtds(
    db: Session, *, owner_user: User
) -> list[OperatorResponseTypeDefinition]:
    """``owner_user``'s library RTDs, in id order. Used by 15C
    Slice 2's ``materialise_operator_libraries`` to enumerate the
    library entries that should be copied into a newly-created
    session's ``response_type_definitions`` rows."""
    stmt = (
        select(OperatorResponseTypeDefinition)
        .where(OperatorResponseTypeDefinition.owner_user_id == owner_user.id)
        .order_by(OperatorResponseTypeDefinition.id)
    )
    return list(db.execute(stmt).scalars())


class RTDLibraryConflictError(Exception):
    """Raised when an operator tries to ``Save to library`` an RTD whose
    name already exists in their library — the
    ``uq_operator_rtd_owner_name`` constraint would block the insert
    and the route translates the error into a useful banner."""


def list_library_rtds_not_in_session(
    db: Session, *, owner_user: User, session_id: int
) -> list[OperatorResponseTypeDefinition]:
    """``owner_user``'s library RTDs whose ``response_type`` name
    is **not** already present on ``session_id``'s
    ``response_type_definitions``. Drives the Slice 3 "Add from
    library" picker — operators see only library entries they
    haven't already pulled into the session (or that haven't been
    auto-copied via Slice 2)."""
    in_session = set(
        db.execute(
            select(ResponseTypeDefinition.response_type).where(
                ResponseTypeDefinition.session_id == session_id
            )
        ).scalars()
    )
    return [
        row
        for row in list_operator_rtds(db, owner_user=owner_user)
        if row.response_type not in in_session
    ]


def save_session_rtd_to_library(
    db: Session,
    *,
    session_rtd: ResponseTypeDefinition,
    actor: User,
    correlation_id: str | None = None,
) -> OperatorResponseTypeDefinition:
    """Copy a session RTD into the actor's operator library and link
    the session row back via ``library_origin_id``.

    Refuses (``RTDLibraryConflictError``) if the actor's library
    already has a row with the same ``response_type`` name — the
    ``uq_operator_rtd_owner_name`` unique constraint forbids it and
    the operator must rename one or delete the library duplicate.

    Refuses (``RTDLockedError``) on seeded session RTDs — they're
    workspace-shipped and don't belong in any one operator's
    personal library.

    Idempotent in the trivial sense: if ``session_rtd.library_origin_id``
    is already set, returns the linked library row without writing.
    """
    if session_rtd.is_seeded:
        raise RTDLockedError(
            "Seeded Response Types cannot be saved to the operator library"
        )

    if session_rtd.library_origin_id is not None:
        existing = db.execute(
            select(OperatorResponseTypeDefinition).where(
                OperatorResponseTypeDefinition.id
                == session_rtd.library_origin_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        # Origin was deleted via SET NULL; fall through and re-save.

    collision = db.execute(
        select(OperatorResponseTypeDefinition).where(
            OperatorResponseTypeDefinition.owner_user_id == actor.id,
            OperatorResponseTypeDefinition.response_type
            == session_rtd.response_type,
        )
    ).scalar_one_or_none()
    if collision is not None:
        raise RTDLibraryConflictError(
            f"{session_rtd.response_type!r} already exists in your "
            "operator library — rename or remove the library entry "
            "first"
        )

    library_row = OperatorResponseTypeDefinition(
        owner_user_id=actor.id,
        response_type=session_rtd.response_type,
        data_type=session_rtd.data_type,
        min=session_rtd.min,
        max=session_rtd.max,
        step=session_rtd.step,
        list_csv=session_rtd.list_csv,
    )
    db.add(library_row)
    db.flush()
    session_rtd.library_origin_id = library_row.id
    db.flush()

    review_session = session_rtd.session

    audit.write_event(
        db,
        event_type="operator_rtd.created",
        summary=(
            f"Added Response Type {session_rtd.response_type!r} to "
            f"operator library"
        ),
        actor_user_id=actor.id,
        session=None,
        payload=audit.snapshot(
            {
                "id": library_row.id,
                "response_type": library_row.response_type,
                "data_type": library_row.data_type,
            }
        ),
        refs={"operator_rtd_id": library_row.id},
        context={"via": "save_to_library"},
        correlation_id=correlation_id,
    )

    audit.write_event(
        db,
        event_type="response_type_definitions.saved_to_library",
        summary=(
            f"Saved session Response Type {session_rtd.response_type!r}"
            f" to operator library"
        ),
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "response_type": session_rtd.response_type,
                "data_type": session_rtd.data_type,
            }
        ),
        refs={
            "response_type_id": session_rtd.id,
            "operator_rtd_id": library_row.id,
        },
        context={"via": "save_to_library"},
        correlation_id=correlation_id,
    )
    db.commit()
    return library_row


def add_rtd_from_library(
    db: Session,
    *,
    review_session: ReviewSession,
    library_rtd: OperatorResponseTypeDefinition,
    actor: User,
    correlation_id: str | None = None,
) -> ResponseTypeDefinition:
    """Copy an operator-library RTD into ``review_session``'s
    ``response_type_definitions`` table. The session copy carries
    ``library_origin_id`` pointing at the library row.

    Refuses (``RTDValidationError``) if a session RTD with the same
    ``response_type`` name already exists — the
    ``uq_rtd_session_name`` constraint would block the insert.
    """
    if library_rtd.owner_user_id != actor.id:
        raise RTDValidationError(
            "Cannot add another operator's library entry"
        )
    collision = _rtd_by_name(
        db, session_id=review_session.id, name=library_rtd.response_type
    )
    if collision is not None:
        raise RTDValidationError(
            f"Response Type {library_rtd.response_type!r} already "
            "exists on this session"
        )

    session_rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type=library_rtd.response_type,
        data_type=library_rtd.data_type,
        min=library_rtd.min,
        max=library_rtd.max,
        step=library_rtd.step,
        list_csv=library_rtd.list_csv,
        is_seeded=False,
        seed_order=0,
        library_origin_id=library_rtd.id,
    )
    db.add(session_rtd)
    db.flush()

    audit.write_event(
        db,
        event_type="response_type_definitions.added_from_library",
        summary=(
            f"Added Response Type {library_rtd.response_type!r} from "
            f"operator library"
        ),
        actor_user_id=actor.id,
        session=review_session,
        payload=audit.snapshot(
            {
                "response_type": session_rtd.response_type,
                "data_type": session_rtd.data_type,
            }
        ),
        refs={
            "response_type_id": session_rtd.id,
            "operator_rtd_id": library_rtd.id,
        },
        context={"via": "add_from_library"},
        correlation_id=correlation_id,
    )
    db.commit()
    return session_rtd


def count_rtd_session_copies(
    db: Session, *, operator_rtd: OperatorResponseTypeDefinition
) -> int:
    """Count the number of session-tier ``response_type_definitions``
    rows that point at this library RTD via ``library_origin_id``.

    Surfaces on the operator-Settings library list (Slice 5) as the
    "Sessions using N" column — invariant #3 transparency without a
    cascade. Delete is purely the library-side action; the SQL
    ``SET NULL`` on ``response_type_definitions.library_origin_id``
    handles any session rows."""
    return int(
        db.execute(
            select(func.count(ResponseTypeDefinition.id)).where(
                ResponseTypeDefinition.library_origin_id == operator_rtd.id
            )
        ).scalar_one()
    )


def delete_operator_rtd(
    db: Session,
    *,
    operator_rtd: OperatorResponseTypeDefinition,
    actor: User,
    correlation_id: str | None = None,
) -> None:
    """Hard-delete a library RTD from the operator's tier. Session
    copies survive (their ``library_origin_id`` clears to NULL via
    the ``SET NULL`` cascade — invariant #3 of 15C). Emits the
    ``operator_rtd.deleted`` audit event."""
    captured = {
        "id": operator_rtd.id,
        "response_type": operator_rtd.response_type,
        "data_type": operator_rtd.data_type,
    }
    db.delete(operator_rtd)
    db.flush()

    audit.write_event(
        db,
        event_type="operator_rtd.deleted",
        summary=(
            f"Deleted library Response Type {captured['response_type']!r}"
        ),
        actor_user_id=actor.id,
        session=None,
        payload=audit.snapshot(captured),
        refs={"operator_rtd_id": captured["id"]},
        context={"via": "operator_settings"},
        correlation_id=correlation_id,
    )
    db.commit()
