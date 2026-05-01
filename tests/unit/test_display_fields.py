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
    seed_display_fields_from_assignments,
    seed_display_fields_from_reviewees,
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


def test_ensure_default_instrument_seeds_no_display_fields(
    db: Session,
) -> None:
    """Per item #14, display fields are now seeded lazily from import data,
    not unconditionally on session creation."""
    user = _user(db)
    session = _session(db, user, code="seed-display")

    instrument = ensure_default_instrument(db, session)

    rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert rows == []


def test_ensure_default_instrument_does_not_revive_deleted_display_fields(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-idem")

    ensure_default_instrument(db, session)
    ensure_default_instrument(db, session)

    rows = db.execute(select(InstrumentDisplayField)).scalars().all()
    assert rows == []


def test_seed_display_fields_from_reviewees_creates_rows_for_populated_slots(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-rev")
    instrument = ensure_default_instrument(db, session)
    db.add(
        Reviewee(
            session_id=session.id,
            name="E1",
            email_or_identifier="e1@example.edu",
            tag_1="alpha",
            tag_3="gamma",
            profile_link="https://example.edu/e1",
        )
    )
    db.add(
        Reviewee(
            session_id=session.id,
            name="E2",
            email_or_identifier="e2@example.edu",
        )
    )
    db.flush()

    created = seed_display_fields_from_reviewees(db, session)
    assert created == 3

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field, r.label, r.visible) for r in rows]
    assert pairs == [
        ("reviewee", "profile_link", "", True),
        ("reviewee", "tag_1", "", True),
        ("reviewee", "tag_3", "", True),
    ]


def test_seed_display_fields_from_reviewees_is_idempotent(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-rev-idem")
    instrument = ensure_default_instrument(db, session)
    db.add(
        Reviewee(
            session_id=session.id,
            name="E",
            email_or_identifier="e@example.edu",
            tag_1="alpha",
        )
    )
    db.flush()

    seed_display_fields_from_reviewees(db, session)
    second_call_created = seed_display_fields_from_reviewees(db, session)
    assert second_call_created == 0

    rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert len(rows) == 1


def test_seed_display_fields_from_reviewees_preserves_operator_label(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-rev-preserve")
    instrument = ensure_default_instrument(db, session)
    existing = InstrumentDisplayField(
        instrument_id=instrument.id,
        label="Cohort",
        source_type="reviewee",
        source_field="tag_1",
        order=0,
        visible=False,
    )
    db.add(existing)
    db.add(
        Reviewee(
            session_id=session.id,
            name="E",
            email_or_identifier="e@example.edu",
            tag_1="alpha",
            tag_2="beta",
        )
    )
    db.flush()

    seed_display_fields_from_reviewees(db, session)

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_field, r.label, r.visible) for r in rows]
    assert pairs == [
        ("tag_1", "Cohort", False),
        ("tag_2", "", True),
    ]


def test_seed_display_fields_from_assignments_creates_pair_context_rows(
    db: Session,
) -> None:
    from app.db.models import Reviewer
    user = _user(db)
    session = _session(db, user, code="seed-asgn")
    instrument = ensure_default_instrument(db, session)
    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Assignment(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            context={"pair_context_1": "morning", "pair_context_3": "cohort"},
        )
    )
    db.flush()

    created = seed_display_fields_from_assignments(db, session)
    assert created == 2

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    pairs = [(r.source_type, r.source_field) for r in rows]
    assert pairs == [("pair_context", "1"), ("pair_context", "3")]


def test_seed_display_fields_from_assignments_no_op_for_full_matrix(
    db: Session,
) -> None:
    """Full-matrix assignments carry ``context=None``; no pair_context rows
    should be seeded."""
    from app.db.models import Reviewer
    user = _user(db)
    session = _session(db, user, code="seed-asgn-fm")
    instrument = ensure_default_instrument(db, session)
    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Assignment(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=True,
            context=None,
        )
    )
    db.flush()

    created = seed_display_fields_from_assignments(db, session)
    assert created == 0

    rows = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert rows == []
