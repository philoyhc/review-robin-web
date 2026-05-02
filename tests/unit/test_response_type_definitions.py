from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    ResponseTypeDefinition,
    ReviewSession,
    User,
)
from app.services.instruments import (
    SEEDED_RESPONSE_TYPE_DEFINITIONS,
    ensure_default_instrument,
    ensure_default_response_type_definitions,
    get_session_rtds,
    validation_block_for_rtd,
)


def _user(db: Session) -> User:
    user = User(email="rtd-author@example.edu", display_name="RTD")
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session, user: User, *, code: str = "rtd-session"
) -> ReviewSession:
    s = ReviewSession(name="RTD", code=code, created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def test_seeded_constants_match_spec_count_and_order() -> None:
    """The 10 seeded RTDs match the locked spec in
    ``guide/instruments.md`` (count + order + parameters)."""
    names = [r["response_type"] for r in SEEDED_RESPONSE_TYPE_DEFINITIONS]
    assert names == [
        "Long_text",
        "Short_text",
        "Yes_no",
        "Grade",
        "Likert5",
        "100int",
        "0-to-2int",
        "1-to-5int",
        "1-to-5half",
        "1-to-5dec",
    ]
    by_name = {r["response_type"]: r for r in SEEDED_RESPONSE_TYPE_DEFINITIONS}
    assert by_name["Long_text"]["max"] == 200
    assert by_name["Short_text"]["max"] == 50
    assert by_name["100int"] == {
        "response_type": "100int", "data_type": "Integer",
        "min": 0, "max": 100, "step": 1, "list_csv": None,
    }
    assert by_name["Likert5"]["list_csv"].startswith("Strongly Disagree")


def test_ensure_seed_is_idempotent(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-idem")

    first = ensure_default_response_type_definitions(db, review)
    second = ensure_default_response_type_definitions(db, review)

    assert set(first.keys()) == set(second.keys())
    assert first["1-to-5int"].id == second["1-to-5int"].id

    rows = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review.id
        )
    ).scalars().all()
    assert len(rows) == 10
    assert all(r.is_seeded for r in rows)


def test_validation_block_for_rtd_covers_all_data_types(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-vb")
    rtds = ensure_default_response_type_definitions(db, review)

    assert validation_block_for_rtd(rtds["Long_text"]) == {
        "min_length": 0, "max_length": 200,
    }
    assert validation_block_for_rtd(rtds["Short_text"]) == {
        "min_length": 0, "max_length": 50,
    }
    assert validation_block_for_rtd(rtds["Yes_no"]) == {
        "choices": ["Yes", "No"],
    }
    assert validation_block_for_rtd(rtds["Grade"]) == {
        "choices": [
            "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D+", "D", "F",
        ],
    }
    assert validation_block_for_rtd(rtds["Likert5"]) == {
        "choices": [
            "Strongly Disagree", "Disagree", "Neutral", "Agree",
            "Strongly Agree",
        ],
    }
    assert validation_block_for_rtd(rtds["100int"]) == {
        "min": 0, "max": 100, "step": 1,
    }
    assert validation_block_for_rtd(rtds["1-to-5half"]) == {
        "min": 1.0, "max": 5.0, "step": 0.5,
    }


def test_get_session_rtds_orders_seeded_first_in_seed_order(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-order")
    ensure_default_response_type_definitions(db, review)

    # Pretend an operator already added a row (Slice 4b territory).
    operator_added = ResponseTypeDefinition(
        session_id=review.id,
        response_type="MyType",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
        is_seeded=False,
        seed_order=0,
    )
    db.add(operator_added)
    db.flush()

    sorted_rtds = get_session_rtds(db, session_id=review.id)
    seeded_names = [r.response_type for r in sorted_rtds if r.is_seeded]
    assert seeded_names == [
        "Long_text", "Short_text", "Yes_no", "Grade", "Likert5",
        "100int", "0-to-2int", "1-to-5int", "1-to-5half", "1-to-5dec",
    ]
    # Operator-added rows sit after seeded.
    assert sorted_rtds[-1].response_type == "MyType"


def test_ensure_default_instrument_seeds_rating_to_5int_and_comments_to_long_text(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-default-inst")

    instrument = ensure_default_instrument(db, review)
    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    rating, comments = fields
    assert rating.response_type == "1-to-5int"
    assert rating.data_type == "Integer"
    assert rating.validation == {"min": 1, "max": 5, "step": 1}
    assert comments.response_type == "Long_text"
    assert comments.data_type == "String"
    assert comments.validation == {"min_length": 0, "max_length": 200}


def test_seeded_rows_have_unique_names_per_session(db: Session) -> None:
    """The (session_id, response_type) UniqueConstraint blocks dupes."""
    user = _user(db)
    review = _session(db, user, code="rtd-uniq")
    ensure_default_response_type_definitions(db, review)

    dup = ResponseTypeDefinition(
        session_id=review.id,
        response_type="Long_text",
        data_type="String",
        min=0,
        max=42,
        is_seeded=False,
        seed_order=0,
    )
    db.add(dup)
    with pytest.raises(Exception):
        db.flush()
    db.rollback()


def test_session_cascade_drops_rtds(db: Session) -> None:
    """When a session is deleted, its RTDs cascade away via the
    ``ondelete=CASCADE`` FK on ``response_type_definitions.session_id``."""
    user = _user(db)
    review = _session(db, user, code="rtd-cascade")
    ensure_default_response_type_definitions(db, review)
    review_id = review.id
    db.commit()

    db.delete(review)
    db.commit()

    remaining = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.session_id == review_id
        )
    ).scalars().all()
    assert remaining == []


def test_response_field_carries_response_type_id_fk_with_cascade() -> None:
    """The schema declares the ``response_type_id`` FK with
    ``ON DELETE CASCADE`` so 4b's operator-defined-RTD delete drops
    dependent Response Fields (and their Responses, transitively).
    Verified via schema introspection — the actual cascade is exercised
    by the ``ci-postgres-migration`` smoke job, since SQLite ignores
    FK constraints by default without a per-connection PRAGMA."""
    fks = list(InstrumentResponseField.__table__.foreign_keys)
    rtd_fk = next(
        (
            fk for fk in fks
            if fk.column.table.name == "response_type_definitions"
        ),
        None,
    )
    assert rtd_fk is not None, "response_type_id FK should exist"
    assert rtd_fk.ondelete == "CASCADE"
