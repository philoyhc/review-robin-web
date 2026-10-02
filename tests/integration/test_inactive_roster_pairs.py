"""Inactive reviewers and reviewees keep their pairs, excluded (findings B2).

`spec/assignments.md` says only active rows are candidates. The author
ruled (2026-10-02) that Prepare still writes an inactive side's pairs,
with `include=False`, rather than leaving them out: Prepare deletes a
pair it no longer generates together with its responses, so leaving
them out would make deactivate → Prepare → reactivate destroy a
reviewer's saved answers.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments, validation
from app.services.instruments import ensure_default_instrument


def _seed(db: Session) -> tuple[User, ReviewSession]:
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="inactive-pairs", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(session_id=review_session.id, name="Ana", email="ana@example.edu"),
            Reviewer(session_id=review_session.id, name="Bo", email="bo@example.edu"),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Dan",
                email_or_identifier="dan@example.edu",
            ),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.commit()
    return user, review_session


def _prepare(db: Session, user: User, review_session: ReviewSession) -> None:
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="c"
    )
    db.commit()


def _rows(db: Session, session_id: int) -> dict[tuple[str, str], Assignment]:
    rows = db.execute(
        select(Assignment, Reviewer.name, Reviewee.name)
        .join(Reviewer, Reviewer.id == Assignment.reviewer_id)
        .join(Reviewee, Reviewee.id == Assignment.reviewee_id)
        .where(Assignment.session_id == session_id)
    ).all()
    return {(reviewer, reviewee): row for row, reviewer, reviewee in rows}


def _set_status(db: Session, model, name: str, status: str) -> None:
    db.execute(select(model).where(model.name == name)).scalar_one().status = status
    db.commit()


def test_an_inactive_side_keeps_its_pairs_excluded_and_its_responses(
    db: Session,
) -> None:
    user, review_session = _seed(db)
    _prepare(db, user, review_session)
    rows = _rows(db, review_session.id)
    assert len(rows) == 4 and all(r.include for r in rows.values())

    field = db.execute(select(InstrumentResponseField)).scalars().first()
    db.add(
        Response(
            assignment_id=rows[("Ana", "Dan")].id,
            response_field_id=field.id,
            value="5",
        )
    )
    db.commit()

    _set_status(db, Reviewee, "Dan", "inactive")
    _set_status(db, Reviewer, "Bo", "inactive")
    _prepare(db, user, review_session)
    rows = _rows(db, review_session.id)
    assert len(rows) == 4
    assert {k for k, r in rows.items() if r.include} == {("Ana", "Carol")}
    assert db.execute(select(Response)).scalars().one().value == "5"

    _set_status(db, Reviewee, "Dan", "active")
    _set_status(db, Reviewer, "Bo", "active")
    _prepare(db, user, review_session)
    rows = _rows(db, review_session.id)
    assert all(r.include for r in rows.values())
    response = db.execute(select(Response)).scalars().one()
    assert response.assignment_id == rows[("Ana", "Dan")].id


def _reviewer_missing(db: Session, review_session: ReviewSession) -> list[str]:
    return [
        i.message
        for i in validation.validate_session_setup(db, review_session)
        if i.source == "assignments" and "no active assignments" in i.message
    ]


def test_validate_warns_an_active_reviewer_left_with_no_active_work(
    db: Session,
) -> None:
    """Findings B4: the warning counts included rows on active reviewees
    for active reviewers. Bo, whose every reviewee is inactive, is
    warned about although his rows exist; an inactive reviewer is not,
    since no work is the point."""
    user, review_session = _seed(db)
    _prepare(db, user, review_session)
    assert _reviewer_missing(db, review_session) == []

    _set_status(db, Reviewee, "Carol", "inactive")
    _set_status(db, Reviewee, "Dan", "inactive")
    _set_status(db, Reviewer, "Ana", "inactive")
    db.refresh(review_session)
    messages = _reviewer_missing(db, review_session)
    assert messages == [
        "Reviewer 'Bo' (bo@example.edu) has no active assignments"
    ]


def test_the_self_review_column_ignores_a_row_excluded_by_status(
    db: Session,
) -> None:
    """An inactive person's self-review row is excluded by roster
    status, not by the Self review toggle: the column does not read it
    as mixed, and ticking the toggle leaves it excluded."""
    user, review_session = _seed(db)
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Ana as reviewee",
            email_or_identifier="ana@example.edu",
        )
    )
    db.commit()
    review_session.self_reviews_active = True
    db.commit()
    _prepare(db, user, review_session)
    instrument_id = db.execute(select(Assignment.instrument_id)).scalars().first()
    assert assignments.self_review_breakdown_per_instrument(
        db, review_session.id
    ) == {instrument_id: (1, 0)}

    _set_status(db, Reviewer, "Ana", "inactive")
    _prepare(db, user, review_session)
    assert assignments.self_review_breakdown_per_instrument(
        db, review_session.id
    ) == {}
    assignments.set_instrument_self_reviews_active(
        db,
        review_session=review_session,
        instrument_id=instrument_id,
        user=user,
        active=True,
        correlation_id="c",
    )
    self_row = db.execute(
        select(Assignment).where(Assignment.is_self_review.is_(True))
    ).scalar_one()
    assert self_row.include is False


def test_nothing_included_is_reported_once_not_per_reviewer(
    db: Session,
) -> None:
    """With every row excluded, ``assignments.no_included_pairs`` says
    so once; ``reviewer_missing`` does not repeat it per reviewer."""
    user, review_session = _seed(db)
    _prepare(db, user, review_session)
    for row in db.execute(select(Assignment)).scalars():
        row.include = False
    db.commit()
    keys = [
        i.rule_key for i in validation.validate_session_setup(db, review_session)
    ]
    assert "assignments.no_included_pairs" in keys
    assert "assignments.reviewer_missing" not in keys


def test_bulk_activate_does_not_include_a_pair_with_an_inactive_side(
    db: Session,
) -> None:
    """Codex on #2727: Activate on the Assignments page is allowed in
    ``validated`` and does not invalidate it, so including a pair with
    an inactive side would put that person back into a live review. It
    is skipped; a pair between two active people still flips."""
    user, review_session = _seed(db)
    _set_status(db, Reviewee, "Dan", "inactive")
    _prepare(db, user, review_session)
    rows = _rows(db, review_session.id)
    for row in rows.values():
        row.include = False
    db.commit()

    flipped = assignments.bulk_set_assignment_include(
        db,
        review_session=review_session,
        assignment_ids=[r.id for r in rows.values()],
        include=True,
        user=user,
        correlation_id="c",
    )
    assert flipped == 2
    rows = _rows(db, review_session.id)
    assert {k for k, r in rows.items() if r.include} == {
        ("Ana", "Carol"),
        ("Bo", "Carol"),
    }
