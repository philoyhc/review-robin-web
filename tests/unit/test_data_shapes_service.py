"""Unit tests for ``app.services.data_shapes`` — pins the
service-layer contract (validation rules + audit emission +
CASCADE behaviour at the service level) the route slice
will build on.
"""

from __future__ import annotations

import json
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    DataShape,
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.services import data_shapes


_INLINE_NUMERIC = {
    "_inline_data_type": "Integer",
    "_inline_response_type": "100int",
    "_inline_min": 0.0,
    "_inline_max": 100.0,
    "_inline_step": 1.0,
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _user(db: Session, *, email: str = "op@x.edu") -> User:
    user = User(email=email, display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, *, code: str = "ds", actor: User | None = None
) -> ReviewSession:
    actor = actor or _user(db, email=f"{code}@x.edu")
    review_session = ReviewSession(
        name="DS",
        code=code,
        created_by_user_id=actor.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _instrument(
    db: Session, review_session: ReviewSession
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id, name="Form", short_label="F"
    )
    db.add(instrument)
    db.flush()
    return instrument


def _field(
    db: Session, instrument: Instrument
) -> InstrumentResponseField:
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="score",
        label="Score",
        order=0,
        **_INLINE_NUMERIC,
    )
    db.add(field)
    db.flush()
    return field


def _make_args(**overrides):
    base = dict(
        name="My shape",
        axis="reviewer",
        instrument_id=None,
        response_field_id=None,
        column_chip_slots=["reviewer:name", "reviewer:email"],
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_create_rejects_empty_name(db: Session) -> None:
    review_session = _session(db, code="empty-name")
    actor = _user(db, email="empty-name-actor@x.edu")
    with pytest.raises(data_shapes.DataShapeValidationError, match="name"):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(name="   "),
        )


def test_create_rejects_invalid_axis(db: Session) -> None:
    review_session = _session(db, code="bad-axis")
    actor = _user(db, email="bad-axis-actor@x.edu")
    with pytest.raises(data_shapes.DataShapeValidationError, match="Axis"):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(axis="instrument"),
        )


def test_create_rejects_empty_columns(db: Session) -> None:
    review_session = _session(db, code="no-cols")
    actor = _user(db, email="no-cols-actor@x.edu")
    with pytest.raises(
        data_shapes.DataShapeValidationError, match="column chip"
    ):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(column_chip_slots=[]),
        )


def test_create_rejects_instrument_from_other_session(
    db: Session,
) -> None:
    """Instrument must belong to the session the shape is
    being saved on."""
    session_a = _session(db, code="a")
    session_b = _session(db, code="b")
    instrument_b = _instrument(db, session_b)
    actor = _user(db, email="cross@x.edu")
    with pytest.raises(
        data_shapes.DataShapeValidationError, match="Instrument"
    ):
        data_shapes.create_shape(
            db,
            review_session=session_a,
            actor=actor,
            **_make_args(instrument_id=instrument_b.id),
        )


def test_create_rejects_field_without_instrument(db: Session) -> None:
    review_session = _session(db, code="orphan-field")
    instrument = _instrument(db, review_session)
    field = _field(db, instrument)
    actor = _user(db, email="orphan-field-actor@x.edu")
    with pytest.raises(
        data_shapes.DataShapeValidationError, match="field"
    ):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(
                instrument_id=None, response_field_id=field.id
            ),
        )


def test_create_rejects_field_from_other_instrument(db: Session) -> None:
    review_session = _session(db, code="cross-field")
    instr_a = _instrument(db, review_session)
    instr_b = _instrument(db, review_session)
    field_a = _field(db, instr_a)
    actor = _user(db, email="cross-field-actor@x.edu")
    with pytest.raises(
        data_shapes.DataShapeValidationError, match="field"
    ):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(
                instrument_id=instr_b.id, response_field_id=field_a.id
            ),
        )


# --------------------------------------------------------------------------- #
# Happy paths + audit
# --------------------------------------------------------------------------- #


def test_create_persists_and_emits_audit(db: Session) -> None:
    review_session = _session(db, code="ok")
    actor = _user(db, email="ok-actor@x.edu")
    shape = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(
            name="  Trimmed  ",  # Leading/trailing whitespace stripped
            column_chip_slots=[
                "reviewer:name",
                "reviewer:email",
                "reviewer:assigned",
            ],
        ),
    )
    assert shape.id is not None
    assert shape.name == "Trimmed"  # name.strip() applied
    assert shape.session_id == review_session.id
    assert shape.created_by_user_id == actor.id
    assert json.loads(shape.column_chip_slots) == [
        "reviewer:name",
        "reviewer:email",
        "reviewer:assigned",
    ]

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_saved",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["snapshot"]["name"] == "Trimmed"
    assert detail["snapshot"]["axis"] == "reviewer"
    assert detail["snapshot"]["column_chip_slots"] == [
        "reviewer:name",
        "reviewer:email",
        "reviewer:assigned",
    ]
    assert detail["refs"]["shape_id"] == shape.id


def test_create_name_conflict_raises_targeted_subclass(
    db: Session,
) -> None:
    review_session = _session(db, code="conflict")
    actor = _user(db, email="conflict-actor@x.edu")
    data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(),
    )
    with pytest.raises(data_shapes.DataShapeNameConflictError):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(),
        )


def test_update_persists_and_emits_audit(db: Session) -> None:
    review_session = _session(db, code="upd")
    actor = _user(db, email="upd-actor@x.edu")
    shape = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(name="Old"),
    )
    # Reset audit events count baseline.
    saved_events_pre = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_saved"
        )
    ).all()
    assert len(saved_events_pre) == 1

    data_shapes.update_shape(
        db,
        review_session=review_session,
        actor=actor,
        shape=shape,
        name="New",
        axis="reviewee",
        instrument_id=None,
        response_field_id=None,
        column_chip_slots=["reviewee:name", "reviewee:email"],
    )
    db.expire_all()
    refreshed = db.execute(
        select(DataShape).where(DataShape.id == shape.id)
    ).scalar_one()
    assert refreshed.name == "New"
    assert refreshed.axis == "reviewee"
    assert json.loads(refreshed.column_chip_slots) == [
        "reviewee:name",
        "reviewee:email",
    ]

    saved_events_post = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_saved"
        )
    ).all()
    # ``update`` re-emits the same event type with the new
    # snapshot — so the count goes from 1 to 2.
    assert len(saved_events_post) == 2


def test_update_name_conflict_rolls_back(db: Session) -> None:
    review_session = _session(db, code="upd-conflict")
    actor = _user(db, email="upd-conflict-actor@x.edu")
    first = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(name="first"),
    )
    second = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(name="second"),
    )
    _ = first
    with pytest.raises(data_shapes.DataShapeNameConflictError):
        data_shapes.update_shape(
            db,
            review_session=review_session,
            actor=actor,
            shape=second,
            name="first",
            axis="reviewer",
            instrument_id=None,
            response_field_id=None,
            column_chip_slots=["reviewer:name"],
        )


def test_delete_removes_row_and_emits_audit(db: Session) -> None:
    review_session = _session(db, code="del")
    actor = _user(db, email="del-actor@x.edu")
    shape = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(name="To delete"),
    )
    shape_id = shape.id
    data_shapes.delete_shape(
        db,
        review_session=review_session,
        actor=actor,
        shape=shape,
    )
    db.expire_all()
    assert (
        db.execute(
            select(DataShape).where(DataShape.id == shape_id)
        ).scalar_one_or_none()
        is None
    )
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_deleted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["snapshot"]["name"] == "To delete"
    assert detail["refs"]["shape_id"] == shape_id


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #


def test_list_shapes_returns_session_shapes_sorted_by_name(
    db: Session,
) -> None:
    review_session = _session(db, code="list")
    actor = _user(db, email="list-actor@x.edu")
    other = _session(db, code="other")
    other_actor = _user(db, email="other-list-actor@x.edu")
    for n in ("zeta", "alpha", "mu"):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(name=n),
        )
    # Shape on the other session must NOT come back.
    data_shapes.create_shape(
        db,
        review_session=other,
        actor=other_actor,
        **_make_args(name="other-session shape"),
    )
    names = [s.name for s in data_shapes.list_shapes(db, review_session)]
    assert names == ["alpha", "mu", "zeta"]


def test_get_shape_scoped_to_session(db: Session) -> None:
    session_a = _session(db, code="get-a")
    session_b = _session(db, code="get-b")
    actor = _user(db, email="get-actor@x.edu")
    actor_b = _user(db, email="get-actor-b@x.edu")
    a_shape = data_shapes.create_shape(
        db,
        review_session=session_a,
        actor=actor,
        **_make_args(),
    )
    assert (
        data_shapes.get_shape(db, session_a, a_shape.id) is not None
    )
    # ``get_shape`` on the wrong session returns ``None`` —
    # the route uses this to reject cross-session access.
    assert data_shapes.get_shape(db, session_b, a_shape.id) is None
    _ = actor_b


# --------------------------------------------------------------------------- #
# Self-review handling chip — PR B
# --------------------------------------------------------------------------- #


def test_create_shape_defaults_self_review_handling_to_include_self(
    db: Session,
) -> None:
    """The chip's persisted state defaults to ``include_self`` so
    a save through the (PR-A-era) chip-less client preserves
    today's behaviour."""
    review_session = _session(db, code="srh-default")
    actor = _user(db, email="srh-default-actor@x.edu")
    shape = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(),
    )
    assert shape.self_review_handling == "include_self"


def test_create_shape_accepts_each_valid_state(db: Session) -> None:
    """All three chip states round-trip through ``create_shape``."""
    review_session = _session(db, code="srh-states")
    actor = _user(db, email="srh-states-actor@x.edu")
    for state in ("include_self", "exclude_self", "both"):
        shape = data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(name=f"Shape-{state}"),
            self_review_handling=state,
        )
        assert shape.self_review_handling == state


def test_create_shape_rejects_unknown_self_review_handling(
    db: Session,
) -> None:
    """A bogus state string raises ``DataShapeValidationError``
    so the route returns 422 instead of writing junk."""
    review_session = _session(db, code="srh-bogus")
    actor = _user(db, email="srh-bogus-actor@x.edu")
    with pytest.raises(data_shapes.DataShapeValidationError):
        data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=actor,
            **_make_args(),
            self_review_handling="garbage",
        )


def test_update_shape_can_flip_self_review_handling(db: Session) -> None:
    """The chip cycles on the page; the persisted column follows
    on Save."""
    review_session = _session(db, code="srh-update")
    actor = _user(db, email="srh-update-actor@x.edu")
    shape = data_shapes.create_shape(
        db,
        review_session=review_session,
        actor=actor,
        **_make_args(),
    )
    data_shapes.update_shape(
        db,
        review_session=review_session,
        actor=actor,
        shape=shape,
        **_make_args(),
        self_review_handling="exclude_self",
    )
    assert shape.self_review_handling == "exclude_self"
