from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.instruments import (
    FieldKeyError,
    ResponsesPresentError,
    add_response_field,
    bulk_set_accepting,
    delete_response_field,
    ensure_default_instrument,
    move_response_field,
    slugify_field_key,
    update_instrument_description,
    update_response_field,
)
from app.services.validation import validate_session_setup
from app.schemas.validation import Severity


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, *, code: str = "code") -> ReviewSession:
    s = ReviewSession(name="Test", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _bare_instrument(db: Session, session: ReviewSession) -> Instrument:
    """Create an instrument with NO seeded fields. Seeds the RTD
    catalog on the session so service calls that look up an RTD by
    name (e.g. ``add_response_field(response_type=...)``) can find
    it; the catalog is logically per-session, not per-instrument."""
    from app.services.instruments import (
        ensure_default_response_type_definitions,
    )
    ensure_default_response_type_definitions(db, session)
    instrument = Instrument(
        session_id=session.id,
        name="instrument_1",
        order=0,
        accepting_responses=False,
        responses_visible_when_closed=False,
    )
    db.add(instrument)
    db.flush()
    return instrument


def test_slugify_field_key_basic_cases() -> None:
    assert slugify_field_key("Overall Rating") == "overall_rating"
    assert slugify_field_key("1st choice") == "st_choice"
    assert slugify_field_key("a__b") == "a_b"
    assert slugify_field_key("") == ""
    assert len(slugify_field_key("x" * 100)) == 64


def test_add_response_field_rejects_invalid_key(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="invalid-key")
    instrument = _bare_instrument(db, session)

    with pytest.raises(FieldKeyError):
        add_response_field(
            db,
            instrument=instrument,
            field_key="Bad-Key!",
            label="Bad",
            response_type="Short_text",
            required=False,
            help_text=None,
            help_text_visible=True,
            actor=user,
        )

    fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert fields == []


def test_add_response_field_rejects_duplicate_key(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="dup-key")
    instrument = _bare_instrument(db, session)

    add_response_field(
        db,
        instrument=instrument,
        field_key="rating",
        label="Rating",
        response_type="1-to-5int",
        required=True,
        help_text=None,
        help_text_visible=True,
        actor=user,
    )

    with pytest.raises(FieldKeyError):
        add_response_field(
            db,
            instrument=instrument,
            field_key="rating",
            label="Rating Again",
            response_type="1-to-5int",
            required=False,
            help_text=None,
            help_text_visible=True,
            actor=user,
        )

    fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalars().all()
    assert len(fields) == 1


def test_add_response_field_appends_with_packed_order_and_audits(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="packed-order")
    instrument = ensure_default_instrument(db, session)

    new = add_response_field(
        db,
        instrument=instrument,
        field_key="decision",
        label="Decision",
        response_type="Yes_no",
        required=False,
        help_text="Pick yes or no.",
        help_text_visible=True,
        actor=user,
    )

    fields = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .order_by(InstrumentResponseField.order)
    ).scalars().all()
    assert [f.order for f in fields] == list(range(len(fields)))
    assert fields[-1].field_key == new.field_key

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.field_added")
    ).scalar_one()
    assert audit.detail["field_key"] == "decision"
    assert audit.detail["help_text"] == "Pick yes or no."


def test_update_response_field_records_only_changed_keys(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="upd-1")
    instrument = ensure_default_instrument(db, session)
    rating = next(f for f in instrument.response_fields if f.field_key == "rating")

    field, warning = update_response_field(
        db,
        field=rating,
        label="New Rating Label",
        required=rating.required,
        validation=rating.validation,
        help_text=rating.help_text,
        help_text_visible=rating.help_text_visible,
        actor=user,
    )

    assert warning == 0
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.field_updated")
    ).scalar_one()
    changes = audit.detail["changes"]
    assert "label" in changes
    assert "required" not in changes


def test_update_response_field_required_warning_counts_missing_rows(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="req-warn")
    instrument = ensure_default_instrument(db, session)
    comments = next(f for f in instrument.response_fields if f.field_key == "comments")
    rating = next(f for f in instrument.response_fields if f.field_key == "rating")

    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()

    assignment = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
    )
    db.add(assignment)
    db.flush()

    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="3",
        )
    )
    db.flush()

    _, warning = update_response_field(
        db,
        field=comments,
        label=comments.label,
        required=True,
        validation=None,
        help_text=None,
        help_text_visible=True,
        actor=user,
    )
    assert warning == 1

    _, warning_back = update_response_field(
        db,
        field=comments,
        label=comments.label,
        required=False,
        validation=None,
        help_text=None,
        help_text_visible=True,
        actor=user,
    )
    assert warning_back == 0


def test_delete_response_field_with_responses_blocks_without_confirm(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user, code="del-1")
    instrument = ensure_default_instrument(db, session)
    rating = next(f for f in instrument.response_fields if f.field_key == "rating")

    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    assignment = Assignment(
        session_id=session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=rating.id,
            value="3",
        )
    )
    db.flush()

    with pytest.raises(ResponsesPresentError) as exc_info:
        delete_response_field(db, field=rating, confirm=False, actor=user)
    assert exc_info.value.cascaded_response_count == 1

    delete_response_field(db, field=rating, confirm=True, actor=user)
    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.field_deleted")
    ).scalar_one()
    assert audit.detail["cascaded_response_count"] == 1


def test_move_response_field_swaps_and_audits_full_order(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="move-1")
    instrument = ensure_default_instrument(db, session)
    rating = next(f for f in instrument.response_fields if f.field_key == "rating")

    move_response_field(db, field=rating, direction="down", actor=user)

    fields = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .order_by(InstrumentResponseField.order)
    ).scalars().all()
    assert [f.field_key for f in fields] == ["comments", "rating"]
    assert [f.order for f in fields] == [0, 1]

    audit = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.fields_reordered"
        )
    ).scalar_one()
    assert audit.detail["old_order"] == ["rating", "comments"]
    assert audit.detail["new_order"] == ["comments", "rating"]


def test_update_instrument_description_normalises_blank_to_none(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="desc-1")
    instrument = ensure_default_instrument(db, session)
    instrument.description = "Old"
    db.flush()

    update_instrument_description(
        db, instrument=instrument, description="   ", actor=user
    )
    db.refresh(instrument)
    assert instrument.description is None

    audit = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.described")
    ).scalar_one()
    assert audit.detail["description"] == ["Old", None]


def test_bulk_set_accepting_writes_one_event_for_changed_only(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="bulk-1")
    instrument = ensure_default_instrument(db, session)
    instrument.accepting_responses = True
    db.flush()

    changed = bulk_set_accepting(
        db, review_session=session, target=False, actor=user
    )
    assert changed == [instrument.id]

    bulk_events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instruments.bulk_accepting_responses"
        )
    ).scalars().all()
    assert len(bulk_events) == 1
    per_instrument = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type.in_(["instrument.opened", "instrument.closed"])
        )
    ).scalars().all()
    assert per_instrument == []


def test_validate_setup_blocks_when_instrument_has_no_fields(db: Session) -> None:
    user = _user(db)
    session = _session(db, user, code="empty-instr")
    db.add(Reviewer(session_id=session.id, name="R", email="r@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id, name="E", email_or_identifier="e@example.edu"
        )
    )
    _bare_instrument(db, session)
    db.flush()

    issues = validate_session_setup(db, session)
    blocking = [
        i for i in issues if i.severity is Severity.error and i.source == "instruments"
    ]
    assert len(blocking) == 1
    assert "no response fields" in blocking[0].message
