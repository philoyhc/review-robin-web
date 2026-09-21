"""Quick Setup's lock gate asks a yes/no question (19R Item 1 rung 2).

The card locks on ``draft`` sessions that already carry responses. It
used to establish that through ``responses.session_response_count``,
which loads every ``Assignment`` in the session as an ORM object to
decide whether any instrument is group-scoped — a count computed so a
caller could compare it to zero. It now calls
``session_lifecycle.session_has_responses``, the helper whose docstring
says it "answers the yes/no a gate needs" and which seven other call
sites already use.

The two agree by construction, and the group-scoped case is where that
is worth proving rather than asserting: the deduped count collapses a
group's fan-out to one cell per group, so it can be *smaller* than the
row count — but never zero while a row exists.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.web.views import build_quick_setup_context

NOW = dt.datetime(2026, 9, 21, tzinfo=dt.timezone.utc)


def _session(db: Session, code: str, *, group: bool) -> ReviewSession:
    """One reviewer, two reviewees, one instrument, two assignments.

    ``group=True`` makes the instrument group-scoped by pair-context
    tag 1 and puts both pairs in the same group, so a response on each
    is two rows that the deduped count folds into one cell.
    """
    user = db.query(User).filter_by(email=f"{code}@example.edu").one_or_none()
    if user is None:
        user = User(email=f"{code}@example.edu", display_name=code)
        db.add(user)
        db.flush()
    review_session = ReviewSession(
        name=code, code=code, status="draft", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()

    instrument = Instrument(
        session_id=review_session.id,
        name="I",
        order=0,
        session_seq=1,
        group_kind="p1" if group else None,
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id, field_key="q1", label="Q1", order=0
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="R", email=f"r-{code}@example.edu"
    )
    db.add_all([field, reviewer])
    db.flush()

    for n in range(2):
        reviewee = Reviewee(
            session_id=review_session.id,
            name=f"E{n}",
            email_or_identifier=f"e{n}-{code}@example.edu",
        )
        db.add(reviewee)
        db.flush()
        db.add(
            Relationship(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                tag_1="Cohort A",
                status="active",
            )
        )
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewer.id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
                include=True,
                created_by_mode="rule_based",
            )
        )
    db.flush()
    return review_session


def _answer_every_assignment(db: Session, review_session: ReviewSession) -> None:
    field = (
        db.query(InstrumentResponseField)
        .join(Instrument)
        .filter(Instrument.session_id == review_session.id)
        .first()
    )
    for assignment in (
        db.query(Assignment)
        .filter(Assignment.session_id == review_session.id)
        .all()
    ):
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=field.id,
                value="4",
                saved_at=NOW,
                submitted_at=NOW,
                version=1,
            )
        )
    db.flush()


@pytest.mark.parametrize("group", [False, True])
def test_the_boolean_agrees_with_the_count_it_replaced(
    db: Session, group: bool
) -> None:
    review_session = _session(db, f"QH{int(group)}", group=group)

    assert lifecycle.session_has_responses(db, review_session) is False
    assert responses_service.session_response_count(db, review_session.id) == 0

    _answer_every_assignment(db, review_session)

    counted = responses_service.session_response_count(db, review_session.id)
    assert lifecycle.session_has_responses(db, review_session) is True
    assert counted > 0
    # The group case is the one worth seeding: two rows, one cell. If
    # dedup ever reached zero the gate would silently unlock a session
    # that holds answers.
    assert counted == (1 if group else 2)


def test_the_card_locks_once_a_response_exists(db: Session) -> None:
    review_session = _session(db, "QHC", group=False)

    before = build_quick_setup_context(db, review_session)
    assert before.is_disabled is False

    _answer_every_assignment(db, review_session)

    after = build_quick_setup_context(db, review_session)
    assert after.is_disabled is True


def test_a_neighbours_responses_do_not_lock_this_card(db: Session) -> None:
    """The gate is session-scoped. Without a populated neighbour in the
    table, that is a claim no assertion here would test."""
    noisy = _session(db, "QHN", group=False)
    _answer_every_assignment(db, noisy)
    quiet = _session(db, "QHQ", group=False)

    assert lifecycle.session_has_responses(db, noisy) is True
    assert lifecycle.session_has_responses(db, quiet) is False

    assert build_quick_setup_context(db, quiet).is_disabled is False
    assert build_quick_setup_context(db, noisy).is_disabled is True
