from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentDisplayField,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.instruments import (
    display_field_label,
    display_field_value,
    ensure_default_instrument,
)


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, *, code: str) -> ReviewSession:
    s = ReviewSession(name="Test", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _make_field(
    *, source_type: str, source_field: str, label: str = ""
) -> InstrumentDisplayField:
    return InstrumentDisplayField(
        instrument_id=0,
        label=label,
        source_type=source_type,
        source_field=source_field,
        order=0,
        visible=True,
    )


def test_display_field_label_returns_operator_typed_label_stripped() -> None:
    field = _make_field(
        source_type="reviewee", source_field="tag_1", label="  Cohort  "
    )
    assert display_field_label(field) == "Cohort"


@pytest.mark.parametrize(
    ("source_type", "source_field", "expected"),
    [
        ("reviewee", "tag_1", "Tag 1"),
        ("reviewee", "tag_2", "Tag 2"),
        ("reviewee", "tag_3", "Tag 3"),
        ("reviewee", "profile_link", "Profile"),
        ("pair_context", "1", "Pair context 1"),
        ("pair_context", "2", "Pair context 2"),
        ("pair_context", "3", "Pair context 3"),
    ],
)
def test_display_field_label_falls_back_to_inferred_for_each_source(
    source_type: str, source_field: str, expected: str
) -> None:
    field = _make_field(source_type=source_type, source_field=source_field)
    assert display_field_label(field) == expected


def test_display_field_label_defensive_fallback_for_unknown_pair() -> None:
    field = _make_field(source_type="mystery", source_field="orb")
    assert display_field_label(field) == "mystery:orb"


@pytest.mark.parametrize("slot", ["1", "2", "3"])
def test_display_field_value_pair_context_reads_assignment_context(slot: str) -> None:
    assignment = Assignment(
        session_id=0,
        reviewer_id=0,
        reviewee_id=0,
        instrument_id=0,
        include=True,
        context={f"pair_context_{slot}": f"slot-{slot}-value"},
    )
    field = _make_field(source_type="pair_context", source_field=slot)
    assert display_field_value(field, assignment) == f"slot-{slot}-value"


def test_display_field_value_pair_context_returns_none_when_missing() -> None:
    assignment = Assignment(
        session_id=0,
        reviewer_id=0,
        reviewee_id=0,
        instrument_id=0,
        include=True,
        context={},
    )
    field = _make_field(source_type="pair_context", source_field="1")
    assert display_field_value(field, assignment) is None


def test_display_field_value_pair_context_returns_none_when_empty() -> None:
    assignment = Assignment(
        session_id=0,
        reviewer_id=0,
        reviewee_id=0,
        instrument_id=0,
        include=True,
        context={"pair_context_1": ""},
    )
    field = _make_field(source_type="pair_context", source_field="1")
    assert display_field_value(field, assignment) is None


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("tag_1", "engineering"),
        ("tag_2", "cohort-7"),
        ("tag_3", "remote"),
        ("profile_link", "https://example.edu/me"),
    ],
)
def test_display_field_value_reviewee_reads_via_getattr(
    db: Session, column: str, value: str
) -> None:
    user = _user(db)
    session = _session(db, user, code=f"rv-{column}")
    reviewee = Reviewee(
        session_id=session.id,
        name="E",
        email_or_identifier="e@example.edu",
        **{column: value},
    )
    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    db.add_all([reviewer, reviewee])
    db.flush()
    instrument = ensure_default_instrument(db, session)
    assignment = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        context={},
    )
    db.add(assignment)
    db.flush()

    field = _make_field(source_type="reviewee", source_field=column)
    assert display_field_value(field, assignment) == value


def test_display_field_value_reviewee_returns_none_when_column_unset(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="rv-none")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu"
    )
    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    db.add_all([reviewer, reviewee])
    db.flush()
    instrument = ensure_default_instrument(db, session)
    assignment = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        context={},
    )
    db.add(assignment)
    db.flush()

    field = _make_field(source_type="reviewee", source_field="tag_1")
    assert display_field_value(field, assignment) is None


def test_ensure_default_instrument_seeds_three_pair_context_display_fields(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-display")

    instrument = ensure_default_instrument(db, session)

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [
        (r.source_type, r.source_field, r.label, r.order, r.visible) for r in rows
    ] == [
        ("pair_context", "1", "", 0, True),
        ("pair_context", "2", "", 1, True),
        ("pair_context", "3", "", 2, True),
    ]


def test_ensure_default_instrument_is_idempotent_for_display_fields(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-idem")

    ensure_default_instrument(db, session)
    ensure_default_instrument(db, session)

    rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id.in_(
                select(InstrumentDisplayField.instrument_id)
            )
        )
    ).scalars().all()
    pair_rows = [r for r in rows if r.source_type == "pair_context"]
    assert len(pair_rows) == 3
