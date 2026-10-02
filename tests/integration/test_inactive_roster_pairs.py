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
