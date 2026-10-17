"""Findings E3 — the per-instrument Self review toggle is stored on the
instrument (``Instrument.self_reviews_active``), so Prepare keeps it.

Before the column the toggle lived only in its rows' ``include`` and
``replace_assignments`` reset every self-review row from the session's
``self_reviews_active``. These pin the ruling: the toggle writes the
column, Prepare writes each self-review row with both sides active from
it (kept or inserted), a new instrument seeds it from the session, and
Replicate / Duplicate / the Settings CSV carry it.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments, session_clone
from app.services.instruments import (
    create_instrument,
    ensure_default_instrument,
    replicate_instrument,
)
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _person(db: Session, review_session: ReviewSession, name: str):
    email = f"{name.lower()}@example.edu"
    reviewer = Reviewer(session_id=review_session.id, name=name, email=email)
    reviewee = Reviewee(
        session_id=review_session.id, name=name, email_or_identifier=email
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    return reviewer, reviewee


def _pin_full_matrix(db: Session, instrument: Instrument) -> None:
    rule_set = SessionRuleSet(
        session_id=instrument.session_id,
        name=f"Full Matrix {instrument.id}",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.flush()


def _seed(
    db: Session, *, code: str, session_active: bool = True, people=("Alice",)
) -> tuple[User, ReviewSession, Instrument]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="E3",
        code=code,
        created_by_user_id=user.id,
        self_reviews_active=session_active,
    )
    db.add(review_session)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    _pin_full_matrix(db, instrument)
    for name in people:
        _person(db, review_session, name)
    db.commit()
    return user, review_session, instrument


def _prepare(db: Session, user: User, review_session: ReviewSession) -> None:
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="e3"
    )
    db.commit()


def _toggle(
    db: Session,
    user: User,
    review_session: ReviewSession,
    instrument: Instrument,
    active: bool,
) -> None:
    assignments.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=instrument.id,
        user=user,
        active=active,
        correlation_id="e3",
    )


def _self_includes(
    db: Session, instrument: Instrument
) -> dict[str, bool]:
    """Reviewer email -> ``include`` of their self-review row here."""
    rows = db.execute(
        select(Reviewer.email, Assignment.include)
        .join(Reviewer, Reviewer.id == Assignment.reviewer_id)
        .where(
            Assignment.instrument_id == instrument.id,
            Assignment.is_self_review.is_(True),
        )
    ).all()
    return {email: bool(include) for email, include in rows}


def test_toggle_off_survives_the_next_prepare(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="e3-off")
    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {"alice@example.edu": True}

    _toggle(db, user, review_session, instrument, False)
    db.refresh(instrument)
    assert instrument.self_reviews_active is False
    assert _self_includes(db, instrument) == {"alice@example.edu": False}

    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {"alice@example.edu": False}
    # The session's flag is untouched: the toggle is per instrument.
    db.refresh(review_session)
    assert review_session.self_reviews_active is True


def test_toggle_on_survives_prepare_with_the_session_default_off(
    db: Session,
) -> None:
    user, review_session, instrument = _seed(
        db, code="e3-on", session_active=False
    )
    # Seeded from the session at creation.
    assert instrument.self_reviews_active is False
    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {"alice@example.edu": False}

    _toggle(db, user, review_session, instrument, True)
    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {"alice@example.edu": True}


def test_a_new_self_review_pair_takes_the_instruments_flag(
    db: Session,
) -> None:
    user, review_session, instrument = _seed(db, code="e3-new")
    _prepare(db, user, review_session)
    _toggle(db, user, review_session, instrument, False)

    _person(db, review_session, "Dave")
    db.commit()
    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {
        "alice@example.edu": False,
        "dave@example.edu": False,
    }


def test_a_reactivated_reviewer_rejoins_the_instruments_state(
    db: Session,
) -> None:
    user, review_session, instrument = _seed(
        db, code="e3-react", session_active=False, people=("Alice", "Dave")
    )
    _prepare(db, user, review_session)
    alice = db.execute(
        select(Reviewer).where(Reviewer.email == "alice@example.edu")
    ).scalar_one()
    alice.status = "inactive"
    db.commit()
    _prepare(db, user, review_session)

    # Turned on while Alice is inactive: only Dave's row is flipped now.
    _toggle(db, user, review_session, instrument, True)
    assert _self_includes(db, instrument) == {
        "alice@example.edu": False,
        "dave@example.edu": True,
    }

    alice.status = "active"
    db.commit()
    _prepare(db, user, review_session)
    assert _self_includes(db, instrument) == {
        "alice@example.edu": True,
        "dave@example.edu": True,
    }


def test_two_instruments_toggled_differently_stay_independent(
    db: Session,
) -> None:
    user, review_session, first = _seed(db, code="e3-two")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    _pin_full_matrix(db, second)
    db.commit()
    _prepare(db, user, review_session)

    _toggle(db, user, review_session, first, False)
    _prepare(db, user, review_session)
    assert _self_includes(db, first) == {"alice@example.edu": False}
    assert _self_includes(db, second) == {"alice@example.edu": True}
    db.refresh(first)
    db.refresh(second)
    assert (first.self_reviews_active, second.self_reviews_active) == (
        False,
        True,
    )


def test_a_new_instrument_seeds_from_the_session(db: Session) -> None:
    user, review_session, _ = _seed(
        db, code="e3-seed", session_active=False
    )
    created = create_instrument(db, review_session=review_session, actor=user)
    assert created.self_reviews_active is False
    review_session.self_reviews_active = True
    db.flush()
    another = create_instrument(db, review_session=review_session, actor=user)
    assert another.self_reviews_active is True
    # Changing the session moves no existing instrument.
    db.refresh(created)
    assert created.self_reviews_active is False


def test_replicate_carries_the_flag(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="e3-repl")
    instrument.self_reviews_active = False
    db.commit()
    replica = replicate_instrument(
        db, review_session=review_session, source=instrument, actor=user
    )
    assert replica.self_reviews_active is False


def test_duplicate_carries_each_instruments_flag(db: Session) -> None:
    user, review_session, first = _seed(db, code="e3-dup")
    second = Instrument(session_id=review_session.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.self_reviews_active = False
    db.commit()

    clone = session_clone.clone_session(
        db, source=review_session, user=user, mode="config"
    )
    flags = dict(
        db.execute(
            select(Instrument.name, Instrument.self_reviews_active).where(
                Instrument.session_id == clone.id
            )
        ).all()
    )
    assert flags == {first.name: False, "Second": True}


def _bare(db: Session, code: str, *, session_active: bool = True) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code,
        code=code,
        created_by_user_id=user.id,
        self_reviews_active=session_active,
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_settings_csv_round_trip_carries_each_instruments_flag(
    db: Session,
) -> None:
    _, source, first = _seed(db, code="e3-csv-src")
    second = Instrument(session_id=source.id, name="Second", order=1)
    db.add(second)
    db.flush()
    first.self_reviews_active = False
    db.commit()

    rows = serialize_session_config(db, source)
    by_field = {r.field: r for r in rows}
    assert by_field["instruments[1].self_reviews_active"] == Row(
        "instruments[1].self_reviews_active", "false", "boolean"
    )
    assert by_field["instruments[2].self_reviews_active"].value == "true"

    destination = _bare(db, "e3-csv-dst")
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    flags = [
        flag
        for (flag,) in db.execute(
            select(Instrument.self_reviews_active)
            .where(Instrument.session_id == destination.id)
            .order_by(Instrument.order)
        ).all()
    ]
    assert flags == [False, True]


def test_an_older_settings_csv_seeds_the_flag_from_the_session(
    db: Session,
) -> None:
    """A file from before the row existed imports as it did then: each
    instrument takes the file's ``session.self_reviews_active``."""
    destination = _bare(db, "e3-csv-old")
    rows = [
        Row("session.self_reviews_active", "false", "boolean"),
        Row("instruments[1].name", "Eval", "string"),
    ]
    result = apply_session_config(db, destination, rows)
    assert result.ok, result.errors
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == destination.id)
    ).scalar_one()
    assert instrument.self_reviews_active is False
