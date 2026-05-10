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
def test_display_field_value_pair_context_reads_relationship(slot: str) -> None:
    """15D PR 6b: pair_context cells now read from the relationships
    table via the eager lookup the route handler builds. Inactive
    rows are skipped."""

    from app.db.models import Relationship

    assignment = Assignment(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        instrument_id=0,
        include=True,
    )
    relationship = Relationship(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        **{f"tag_{slot}": f"slot-{slot}-value"},
        status="active",
    )
    lookup = {(1, 10): relationship}
    field = _make_field(source_type="pair_context", source_field=slot)
    assert (
        display_field_value(field, assignment, pair_context_lookup=lookup)
        == f"slot-{slot}-value"
    )


def test_display_field_value_pair_context_returns_none_when_no_lookup() -> None:
    """Without a lookup, pair_context cells resolve to None — the
    safe fallback for callers that haven't been updated."""

    assignment = Assignment(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        instrument_id=0,
        include=True,
    )
    field = _make_field(source_type="pair_context", source_field="1")
    assert display_field_value(field, assignment) is None


def test_display_field_value_pair_context_returns_none_when_pair_missing() -> None:
    assignment = Assignment(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        instrument_id=0,
        include=True,
    )
    field = _make_field(source_type="pair_context", source_field="1")
    assert display_field_value(field, assignment, pair_context_lookup={}) is None


def test_display_field_value_pair_context_skips_inactive_relationship() -> None:
    """Skip-at-lookup: ``status='inactive'`` rows hide their tag
    values (mirrors ``app/services/rules/fields.py``)."""

    from app.db.models import Relationship

    assignment = Assignment(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        instrument_id=0,
        include=True,
    )
    relationship = Relationship(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        tag_1="hidden",
        status="inactive",
    )
    lookup = {(1, 10): relationship}
    field = _make_field(source_type="pair_context", source_field="1")
    assert (
        display_field_value(field, assignment, pair_context_lookup=lookup)
        is None
    )


def test_display_field_value_pair_context_returns_none_when_empty_string() -> None:
    from app.db.models import Relationship

    assignment = Assignment(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        instrument_id=0,
        include=True,
    )
    relationship = Relationship(
        session_id=0,
        reviewer_id=1,
        reviewee_id=10,
        tag_1="",
        status="active",
    )
    lookup = {(1, 10): relationship}
    field = _make_field(source_type="pair_context", source_field="1")
    assert (
        display_field_value(field, assignment, pair_context_lookup=lookup)
        is None
    )


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

    )
    db.add(assignment)
    db.flush()

    field = _make_field(source_type="reviewee", source_field="tag_1")
    assert display_field_value(field, assignment) is None


def test_ensure_default_instrument_seeds_locked_name_and_email_only(
    db: Session,
) -> None:
    """Per item #14 + Segment 10D Slice 1: display fields for tags /
    profile / pair_context are seeded lazily from import data, but the
    two locked rows (RevieweeName, RevieweeEmail) are seeded
    unconditionally on session creation so they're always at the top."""
    user = _user(db)
    session = _session(db, user, code="seed-display")

    instrument = ensure_default_instrument(db, session)

    rows = db.execute(
        select(InstrumentDisplayField)
        .where(InstrumentDisplayField.instrument_id == instrument.id)
        .order_by(InstrumentDisplayField.order)
    ).scalars().all()
    assert [(r.source_type, r.source_field, r.order, r.visible) for r in rows] == [
        ("reviewee", "name", 0, True),
        ("reviewee", "email_or_identifier", 1, True),
    ]


def test_ensure_default_instrument_idempotent_for_locked_rows(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-idem")

    ensure_default_instrument(db, session)
    ensure_default_instrument(db, session)

    rows = db.execute(select(InstrumentDisplayField)).scalars().all()
    pairs = sorted((r.source_type, r.source_field) for r in rows)
    assert pairs == [
        ("reviewee", "email_or_identifier"),
        ("reviewee", "name"),
    ]


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
    # The two locked rows (Name + Email) sit at the top from
    # ensure_default_instrument; the lazy-seeded rows append after.
    pairs = [(r.source_type, r.source_field) for r in rows]
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("reviewee", "profile_link"),
        ("reviewee", "tag_1"),
        ("reviewee", "tag_3"),
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
    # 2 locked rows + 1 tag_1 lazy seed = 3.
    assert len(rows) == 3


def test_seed_display_fields_from_reviewees_preserves_operator_label(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="seed-rev-preserve")
    instrument = ensure_default_instrument(db, session)
    # Manually insert a tag_1 row with an operator-typed label after
    # the locked Name + Email rows; lazy seed should leave it alone.
    existing = InstrumentDisplayField(
        instrument_id=instrument.id,
        label="Cohort",
        source_type="reviewee",
        source_field="tag_1",
        order=2,
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
    by_source = {r.source_field: (r.label, r.visible) for r in rows}
    assert by_source["tag_1"] == ("Cohort", False)
    assert by_source["tag_2"] == ("", True)
    # Locked rows still present.
    assert "name" in by_source
    assert "email_or_identifier" in by_source


def test_seed_display_fields_from_assignments_creates_pair_context_rows(
    db: Session,
) -> None:
    """15D PR 6b: pair_context display-field seeding now scans the
    relationships table for populated tag slots, not the retired
    ``Assignment.context`` column."""

    from app.db.models import Relationship, Reviewer

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
        )
    )
    db.add(
        Relationship(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            tag_1="morning",
            tag_3="cohort",
            status="active",
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
    # Locked rows seed first, pair_context rows appended.
    assert pairs == [
        ("reviewee", "name"),
        ("reviewee", "email_or_identifier"),
        ("pair_context", "1"),
        ("pair_context", "3"),
    ]


def test_seed_display_fields_from_assignments_no_op_for_no_relationships(
    db: Session,
) -> None:
    """Sessions without any relationships rows seed no pair_context
    display fields. (Pre-15D this scanned ``Assignment.context``;
    post-15D PR 6b the data lives on the relationships table.)"""

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
    # Locked Name + Email rows are still seeded, but no pair_context rows
    # are added when ``context`` is None.
    pairs = sorted((r.source_type, r.source_field) for r in rows)
    assert pairs == [
        ("reviewee", "email_or_identifier"),
        ("reviewee", "name"),
    ]
