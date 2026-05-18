from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ResponseTypeDefinition,
    ReviewSession,
    User,
)
from app.services.instruments import (
    SEEDED_RESPONSE_TYPE_DEFINITIONS,
    RTDDeleteWouldEmptyInstrumentError,
    RTDInUseError,
    RTDLockedError,
    RTDPrecisionError,
    RTDValidationError,
    add_default_response_field,
    add_response_type_definition,
    assert_rtd_precision,
    count_rtd_dependents,
    delete_response_type_definition,
    ensure_default_instrument,
    ensure_default_response_type_definitions,
    get_session_rtds,
    update_response_type_definition,
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
    ``spec/instruments.md`` (count + order + parameters)."""
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
    assert by_name["Long_text"]["max"] == 2000
    assert by_name["Short_text"]["max"] == 100
    assert by_name["100int"] == {
        "response_type": "100int", "data_type": "Integer",
        "min": 0, "max": 100, "step": 1, "list_csv": None,
    }
    assert by_name["Likert5"]["list_csv"] == (
        "Strongly Agree, Agree, Neutral, Disagree, Strongly Disagree"
    )


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
        "min_length": 0, "max_length": 2000,
    }
    assert validation_block_for_rtd(rtds["Short_text"]) == {
        "min_length": 0, "max_length": 100,
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
            "Strongly Agree", "Agree", "Neutral", "Disagree",
            "Strongly Disagree",
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
    assert comments.validation == {"min_length": 0, "max_length": 2000}


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


def test_assert_rtd_precision_accepts_seeded_rows() -> None:
    """The ten seeded rows comply with the precision rule (Integer:
    no fractional part; Decimal: ≤ 1 decimal place)."""
    for spec in SEEDED_RESPONSE_TYPE_DEFINITIONS:
        # Should not raise.
        assert_rtd_precision(
            data_type=spec["data_type"],
            min=spec["min"],
            max=spec["max"],
            step=spec["step"],
        )


def test_assert_rtd_precision_rejects_integer_with_fraction() -> None:
    with pytest.raises(RTDPrecisionError, match="integer"):
        assert_rtd_precision(
            data_type="Integer", min=0, max=10, step=0.5
        )


def test_assert_rtd_precision_rejects_decimal_over_one_dp() -> None:
    with pytest.raises(RTDPrecisionError, match="decimal place"):
        assert_rtd_precision(
            data_type="Decimal", min=1.0, max=5.0, step=0.05
        )


def test_assert_rtd_precision_accepts_decimal_one_dp() -> None:
    # 0.5 and 0.1 are exactly one decimal place; 1.0 and 5.0 also
    # satisfy "at most one decimal place".
    assert_rtd_precision(
        data_type="Decimal", min=1.0, max=5.0, step=0.5
    )
    assert_rtd_precision(
        data_type="Decimal", min=1.0, max=5.0, step=0.1
    )


def test_assert_rtd_precision_skips_string_and_list() -> None:
    # String / List rows go through different validation paths; the
    # precision rule does not apply to them. Should not raise.
    assert_rtd_precision(
        data_type="String", min=0, max=200, step=None
    )
    assert_rtd_precision(
        data_type="List", min=None, max=None, step=None
    )


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


# --- Slice 4b: operator add / edit / delete on RTD card --------------


def test_add_rtd_integer_persists_and_is_not_seeded(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-add-int")

    rtd = add_response_type_definition(
        db,
        review_session=review,
        response_type="MyIntScale",
        data_type="Integer",
        min=0,
        max=10,
        step=2,
        list_csv=None,
        actor=user,
    )
    assert rtd.id is not None
    assert rtd.is_seeded is False
    assert rtd.response_type == "MyIntScale"
    assert rtd.list_csv is None


def test_add_rtd_list_persists_with_choices(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-add-list")

    rtd = add_response_type_definition(
        db,
        review_session=review,
        response_type="Stoplight",
        data_type="List",
        min=None,
        max=None,
        step=None,
        list_csv="Red, Yellow, Green",
        actor=user,
    )
    assert validation_block_for_rtd(rtd) == {
        "choices": ["Red", "Yellow", "Green"],
    }


def test_add_rtd_rejects_step_not_dividing_span(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-step-rej")
    with pytest.raises(RTDValidationError, match="evenly divide"):
        add_response_type_definition(
            db,
            review_session=review,
            response_type="BadStep",
            data_type="Integer",
            min=1,
            max=5,
            step=3,
            list_csv=None,
            actor=user,
        )


def test_add_rtd_rejects_min_greater_than_max(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-mm-rej")
    with pytest.raises(RTDValidationError, match="cannot exceed"):
        add_response_type_definition(
            db,
            review_session=review,
            response_type="Reversed",
            data_type="Integer",
            min=10,
            max=1,
            step=1,
            list_csv=None,
            actor=user,
        )


def test_add_rtd_rejects_decimal_with_too_many_dp(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-dp-rej")
    with pytest.raises(RTDPrecisionError):
        add_response_type_definition(
            db,
            review_session=review,
            response_type="Hi-precision",
            data_type="Decimal",
            min=0.0,
            max=1.0,
            step=0.05,
            list_csv=None,
            actor=user,
        )


def test_add_rtd_rejects_empty_list(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-empty-list")
    with pytest.raises(RTDValidationError, match="at least one"):
        add_response_type_definition(
            db,
            review_session=review,
            response_type="Empty",
            data_type="List",
            min=None,
            max=None,
            step=None,
            list_csv="",
            actor=user,
        )


def test_add_rtd_rejects_duplicate_name_on_session(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-dup")
    ensure_default_response_type_definitions(db, review)
    with pytest.raises(RTDValidationError, match="already exists"):
        add_response_type_definition(
            db,
            review_session=review,
            response_type="Long_text",
            data_type="String",
            min=0,
            max=100,
            step=None,
            list_csv=None,
            actor=user,
        )


def test_update_rtd_propagates_validation_to_dependent_rf(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-prop")
    instrument = ensure_default_instrument(db, review)

    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="Custom-1-to-3",
        data_type="Integer",
        min=1,
        max=3,
        step=1,
        list_csv=None,
        actor=user,
    )
    # Point the seeded ``rating`` field at our new RTD so we can
    # verify propagation.
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    rating.validation = {"min": 1, "max": 3, "step": 1}
    db.commit()

    update_response_type_definition(
        db,
        rtd=custom,
        min=0,
        max=10,
        step=2,
        list_csv=None,
        actor=user,
    )
    db.refresh(rating)
    assert rating.validation == {"min": 0, "max": 10, "step": 2}


def test_update_rtd_seeded_row_is_locked(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-locked-edit")
    rtds = ensure_default_response_type_definitions(db, review)
    seeded = rtds["1-to-5int"]
    with pytest.raises(RTDLockedError):
        update_response_type_definition(
            db,
            rtd=seeded,
            min=0,
            max=20,
            step=1,
            list_csv=None,
            actor=user,
        )


def test_delete_rtd_seeded_row_is_locked(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-locked-del")
    rtds = ensure_default_response_type_definitions(db, review)
    with pytest.raises(RTDLockedError):
        delete_response_type_definition(
            db, rtd=rtds["Long_text"], confirm=False, actor=user
        )


def test_delete_rtd_not_in_use_drops_immediately(db: Session) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-del-free")

    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="Throwaway",
        data_type="Integer",
        min=0,
        max=10,
        step=1,
        list_csv=None,
        actor=user,
    )
    custom_id = custom.id

    delete_response_type_definition(
        db, rtd=custom, confirm=False, actor=user
    )
    remaining = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == custom_id
        )
    ).scalar_one_or_none()
    assert remaining is None


def test_delete_rtd_in_use_with_saved_responses_cascades(
    db: Session,
) -> None:
    """Deleting a confirmed in-use RTD whose fields carry saved
    `Response` rows succeeds — the dependent responses are cleared
    before the delete. Regression: `responses.response_field_id`
    has no `ON DELETE CASCADE`, so the DB cascade alone would abort
    on a foreign-key violation."""
    user = _user(db)
    review = _session(db, user, code="rtd-del-responses")
    instrument = ensure_default_instrument(db, review)

    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="Scored",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    rating_id = rating.id

    reviewer = Reviewer(
        session_id=review.id, name="R", email="r@example.edu"
    )
    reviewee = Reviewee(
        session_id=review.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    assignment = Assignment(
        session_id=review.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()
    response = Response(
        assignment_id=assignment.id,
        response_field_id=rating_id,
        value="3",
    )
    db.add(response)
    db.commit()

    custom_id = custom.id
    dependents = delete_response_type_definition(
        db, rtd=custom, confirm=True, actor=user
    )
    assert dependents["response_count"] == 1

    # Re-query the DB rather than trusting the identity map — the
    # response-field row is removed by the DB cascade, not the ORM.
    db.expire_all()
    assert (
        db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.id == custom_id
            )
        ).scalar_one_or_none()
        is None
    )
    assert (
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.id == rating_id
            )
        ).scalar_one_or_none()
        is None
    )
    assert (
        db.execute(
            select(Response).where(Response.response_field_id == rating_id)
        ).scalar_one_or_none()
        is None
    )


def test_delete_rtd_in_use_without_confirm_raises_with_dependent_counts(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-del-in-use")
    instrument = ensure_default_instrument(db, review)

    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="In-Use",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    db.commit()

    with pytest.raises(RTDInUseError) as excinfo:
        delete_response_type_definition(
            db, rtd=custom, confirm=False, actor=user
        )
    assert excinfo.value.dependents["response_field_count"] == 1
    assert excinfo.value.dependents["instrument_count"] == 1


def test_count_rtd_dependents_returns_zero_for_unused_rtd(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rtd-count")
    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="Quiet",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    counts = count_rtd_dependents(db, rtd=custom)
    assert counts == {
        "response_field_count": 0,
        "instrument_count": 0,
        "response_count": 0,
        "assignment_count": 0,
        "would_empty_instruments": [],
    }


# --- Slice 4c: operator-pickable Type on new RF rows ----------------


def test_add_default_response_field_default_args_preserves_slice2_contract(
    db: Session,
) -> None:
    """No-override call still gives the seeded ``1-to-5int`` RTD,
    auto ``RatingN`` label, ``ratingN`` key, ``required=True``."""
    user = _user(db)
    review = _session(db, user, code="rf-default-add")
    instrument = ensure_default_instrument(db, review)

    new = add_default_response_field(
        db, instrument=instrument, after_field_id=None, actor=user
    )
    assert new.response_type == "1-to-5int"
    assert new.label.startswith("Rating")
    assert new.field_key.startswith("rating")
    assert new.required is True
    assert new.validation == {"min": 1, "max": 5, "step": 1}


def test_add_default_response_field_with_rtd_id_picks_chosen_rtd(
    db: Session,
) -> None:
    user = _user(db)
    review = _session(db, user, code="rf-rtd-pick")
    instrument = ensure_default_instrument(db, review)
    rtds = ensure_default_response_type_definitions(db, review)

    new = add_default_response_field(
        db,
        instrument=instrument,
        after_field_id=None,
        rtd_id=rtds["Yes_no"].id,
        label="Decision",
        required=False,
        actor=user,
    )
    assert new.response_type == "Yes_no"
    assert new.label == "Decision"
    # field_key derived from label via slugify_field_key.
    assert new.field_key == "decision"
    assert new.required is False
    assert new.validation == {"choices": ["Yes", "No"]}


def test_add_default_response_field_falls_back_to_default_rtd_when_unknown(
    db: Session,
) -> None:
    """A bogus rtd_id (e.g. forged form post) silently falls back to
    the seeded ``1-to-5int`` rather than raising."""
    user = _user(db)
    review = _session(db, user, code="rf-rtd-bogus")
    instrument = ensure_default_instrument(db, review)

    new = add_default_response_field(
        db,
        instrument=instrument,
        after_field_id=None,
        rtd_id=999_999,
        label="Salvage",
        actor=user,
    )
    assert new.response_type == "1-to-5int"
    assert new.label == "Salvage"


def test_add_default_response_field_blank_label_uses_auto_rating_key(
    db: Session,
) -> None:
    """If the operator left the label blank, fall back to the
    classic ``RatingN`` / ``ratingN`` auto numbering."""
    user = _user(db)
    review = _session(db, user, code="rf-blank-label")
    instrument = ensure_default_instrument(db, review)

    new = add_default_response_field(
        db,
        instrument=instrument,
        after_field_id=None,
        rtd_id=None,
        label="   ",  # whitespace only
        actor=user,
    )
    assert new.label.startswith("Rating")
    assert new.field_key.startswith("rating")


def test_add_default_response_field_field_key_collision_gets_numeric_suffix(
    db: Session,
) -> None:
    """Two operator-typed labels that slugify to the same key get
    distinct ``field_key`` values via numeric suffixing."""
    user = _user(db)
    review = _session(db, user, code="rf-key-collide")
    instrument = ensure_default_instrument(db, review)

    add_default_response_field(
        db,
        instrument=instrument,
        after_field_id=None,
        label="Quality",
        actor=user,
    )
    second = add_default_response_field(
        db,
        instrument=instrument,
        after_field_id=None,
        label="Quality",
        actor=user,
    )
    assert second.field_key == "quality2"


# --- Slice 4d: would-empty-instrument cascade-delete block ---------


def test_count_rtd_dependents_lists_would_be_emptied_instruments(
    db: Session,
) -> None:
    """When the cascade would leave an instrument with zero RF rows,
    ``count_rtd_dependents`` returns the would-empty list with the
    instrument's display number (1-indexed by ``Instrument.order``)."""
    user = _user(db)
    review = _session(db, user, code="rtd-empty-count")
    instrument = ensure_default_instrument(db, review)

    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="OnlyType",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )

    # Replace BOTH default RF rows so the only remaining ones reference
    # ``custom`` — cascade-delete would empty the instrument.
    rfs = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    for rf in rfs:
        rf.response_type_id = custom.id
    db.commit()

    counts = count_rtd_dependents(db, rtd=custom)
    assert counts["would_empty_instruments"] == [
        {"instrument_id": instrument.id, "instrument_number": 1},
    ]


def test_delete_rtd_blocks_when_cascade_would_empty_instrument(
    db: Session,
) -> None:
    """``delete_response_type_definition`` raises
    ``RTDDeleteWouldEmptyInstrumentError`` even with ``confirm=True``
    — the operator can't override the would-empty-instrument guard."""
    user = _user(db)
    review = _session(db, user, code="rtd-empty-delete")
    instrument = ensure_default_instrument(db, review)
    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="OnlyType",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    rfs = list(
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    for rf in rfs:
        rf.response_type_id = custom.id
    db.commit()

    with pytest.raises(RTDDeleteWouldEmptyInstrumentError) as excinfo:
        delete_response_type_definition(
            db, rtd=custom, confirm=True, actor=user
        )
    assert excinfo.value.would_empty == [
        {"instrument_id": instrument.id, "instrument_number": 1},
    ]
    # The RTD row + its dependents are still there.
    assert db.get(ResponseTypeDefinition, custom.id) is not None


def test_delete_rtd_in_use_but_other_rows_remain_still_raises_in_use_error(
    db: Session,
) -> None:
    """When the cascade would leave the instrument with at least one
    remaining (non-cascaded) RF row, the would-empty guard does NOT
    fire — the existing ``RTDInUseError`` cascade-confirm flow runs."""
    user = _user(db)
    review = _session(db, user, code="rtd-in-use-still")
    instrument = ensure_default_instrument(db, review)
    custom = add_response_type_definition(
        db,
        review_session=review,
        response_type="OneOfMany",
        data_type="Integer",
        min=0,
        max=5,
        step=1,
        list_csv=None,
        actor=user,
    )
    # Replace only the ``rating`` row's RTD; ``comments`` keeps its
    # ``Long_text`` reference and survives the cascade.
    rating = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    rating.response_type_id = custom.id
    db.commit()

    with pytest.raises(RTDInUseError):
        delete_response_type_definition(
            db, rtd=custom, confirm=False, actor=user
        )
