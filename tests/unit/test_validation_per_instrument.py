"""Slice 5 coverage for the per-instrument validation rules.

Three new ``ValidationRule`` entries land in this slice:

- ``assignments.reviewer_missing`` — single-instrument sessions
  only; flags reviewers with zero ``Assignment`` rows.
- ``assignments.reviewer_missing_for_instrument`` —
  multi-instrument sessions only; flags (reviewer, instrument)
  pairs where the reviewer is missing on that instrument but
  present on others.
- ``assignments.instrument_empty`` — multi-instrument sessions
  only; flags instruments with zero ``Assignment`` rows.

All three rules skip the check when ``assignment_mode is None``
(the ``assignments.no_mode`` rule already covers the
no-assignments-yet case). The per-reviewer-per-instrument rule
also skips any instrument whose total row count is zero — the
``assignments.instrument_empty`` sibling handles that case
without (reviewers × instruments) duplicate noise.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.validation import Severity
from app.services.instruments import ensure_default_instrument
from app.services.validation import validate_session_setup


def _seed(
    db: Session,
    *,
    code: str = "per-inst",
    reviewer_emails: tuple[str, ...] = ("alice@example.edu",),
    reviewee_idents: tuple[str, ...] = ("carol@example.edu",),
) -> tuple[ReviewSession, list[Reviewer], list[Reviewee]]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="PerInst", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    reviewers = [
        Reviewer(
            session_id=review_session.id,
            name=email.split("@", 1)[0].title(),
            email=email,
        )
        for email in reviewer_emails
    ]
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name=ident.split("@", 1)[0].title(),
            email_or_identifier=ident,
        )
        for ident in reviewee_idents
    ]
    db.add_all(reviewers)
    db.add_all(reviewees)
    db.flush()
    ensure_default_instrument(db, review_session)
    return review_session, reviewers, reviewees


def _add_instrument(
    db: Session, review_session: ReviewSession, *, name: str
) -> Instrument:
    instrument = Instrument(
        session_id=review_session.id, name=name, order=99
    )
    db.add(instrument)
    db.flush()
    return instrument


def _add_assignment(
    db: Session,
    *,
    review_session: ReviewSession,
    reviewer: Reviewer,
    reviewee: Reviewee,
    instrument: Instrument,
) -> Assignment:
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    return assignment


def _issues_with_key(
    issues: list, key: str
) -> list:
    return [i for i in issues if i.rule_key == key]


def test_reviewer_missing_skipped_when_no_assignment_mode(
    db: Session,
) -> None:
    """When ``assignment_mode is None`` the ``assignments.no_mode``
    rule already fires; the per-reviewer rule sits this one out so
    operators see one issue rather than (reviewers × 1) duplicate
    noise on a freshly-created session."""

    review_session, _reviewers, _reviewees = _seed(db, code="skip-nm")
    # assignment_mode stays None — the seed never generates.

    issues = validate_session_setup(db, review_session)

    assert _issues_with_key(issues, "assignments.reviewer_missing") == []
    assert (
        _issues_with_key(issues, "assignments.reviewer_missing_for_instrument")
        == []
    )
    assert _issues_with_key(issues, "assignments.instrument_empty") == []
    # ``assignments.no_mode`` still fires.
    assert _issues_with_key(issues, "assignments.no_mode")


def test_single_instrument_flags_reviewer_with_no_assignments(
    db: Session,
) -> None:
    """N==1 session: every reviewer with zero ``Assignment`` rows
    surfaces as ``assignments.reviewer_missing``. The per-instrument
    sibling rule does not fire (the breakdown isn't useful with
    only one instrument)."""

    review_session, reviewers, reviewees = _seed(
        db,
        code="single-missing",
        reviewer_emails=("alice@example.edu", "bob@example.edu"),
    )
    [instrument] = list(
        db.query(Instrument).filter(
            Instrument.session_id == review_session.id
        ).all()
    )
    # Alice gets an assignment; Bob doesn't.
    _add_assignment(
        db,
        review_session=review_session,
        reviewer=reviewers[0],
        reviewee=reviewees[0],
        instrument=instrument,
    )
    review_session.assignment_mode = "rule_based"
    db.flush()

    issues = validate_session_setup(db, review_session)

    single = _issues_with_key(issues, "assignments.reviewer_missing")
    assert len(single) == 1
    assert single[0].severity is Severity.warning
    assert "Bob" in single[0].message
    assert single[0].fix_anchor == f"#reviewer-row-{reviewers[1].id}"
    # Per-instrument sibling stays quiet on N==1 sessions.
    assert (
        _issues_with_key(
            issues, "assignments.reviewer_missing_for_instrument"
        )
        == []
    )


def test_multi_instrument_skips_single_rule(db: Session) -> None:
    """N>1 session: the single-instrument
    ``assignments.reviewer_missing`` rule sits out (the per-instrument
    sibling carries the breakdown)."""

    review_session, reviewers, reviewees = _seed(db, code="multi-skip")
    instruments = list(
        db.query(Instrument).filter(
            Instrument.session_id == review_session.id
        ).all()
    )
    second = _add_instrument(db, review_session, name="Peer survey")
    # Both instruments have at least one assignment so the
    # instrument_empty rule doesn't fire either.
    _add_assignment(
        db,
        review_session=review_session,
        reviewer=reviewers[0],
        reviewee=reviewees[0],
        instrument=instruments[0],
    )
    _add_assignment(
        db,
        review_session=review_session,
        reviewer=reviewers[0],
        reviewee=reviewees[0],
        instrument=second,
    )
    review_session.assignment_mode = "rule_based"
    db.flush()

    issues = validate_session_setup(db, review_session)

    assert _issues_with_key(issues, "assignments.reviewer_missing") == []


def test_multi_instrument_reviewer_missing_on_some_instruments(
    db: Session,
) -> None:
    """Alice is present on both instruments; Bob only on instrument
    A. The rule fires once for (Bob, instrument B). Message names
    the instrument; ``fix_anchor`` deep-links to that instrument's
    card on the Instruments page."""

    review_session, reviewers, reviewees = _seed(
        db,
        code="multi-some-missing",
        reviewer_emails=("alice@example.edu", "bob@example.edu"),
    )
    [first] = list(
        db.query(Instrument).filter(
            Instrument.session_id == review_session.id
        ).all()
    )
    second = _add_instrument(db, review_session, name="Peer survey")
    for instrument in (first, second):
        _add_assignment(
            db,
            review_session=review_session,
            reviewer=reviewers[0],  # Alice everywhere.
            reviewee=reviewees[0],
            instrument=instrument,
        )
    _add_assignment(
        db,
        review_session=review_session,
        reviewer=reviewers[1],  # Bob on instrument A only.
        reviewee=reviewees[0],
        instrument=first,
    )
    review_session.assignment_mode = "rule_based"
    db.flush()

    issues = validate_session_setup(db, review_session)

    per_instr = _issues_with_key(
        issues, "assignments.reviewer_missing_for_instrument"
    )
    assert len(per_instr) == 1
    issue = per_instr[0]
    assert "Bob" in issue.message
    assert "Peer survey" in issue.message
    assert issue.fix_anchor == f"#instrument-{second.id}"


def test_multi_instrument_empty_instrument_suppresses_per_reviewer(
    db: Session,
) -> None:
    """Instrument B has zero ``Assignment`` rows. The
    ``assignments.instrument_empty`` rule fires once for instrument
    B; the per-(reviewer, instrument) rule stays quiet for B so the
    operator sees one issue per empty instrument rather than
    duplicate noise scaled by roster size."""

    review_session, reviewers, reviewees = _seed(
        db,
        code="multi-empty",
        reviewer_emails=("alice@example.edu", "bob@example.edu"),
    )
    [first] = list(
        db.query(Instrument).filter(
            Instrument.session_id == review_session.id
        ).all()
    )
    second = _add_instrument(db, review_session, name="Peer survey")
    for reviewer in reviewers:
        _add_assignment(
            db,
            review_session=review_session,
            reviewer=reviewer,
            reviewee=reviewees[0],
            instrument=first,
        )
    review_session.assignment_mode = "rule_based"
    db.flush()

    issues = validate_session_setup(db, review_session)

    empties = _issues_with_key(issues, "assignments.instrument_empty")
    assert len(empties) == 1
    assert "Peer survey" in empties[0].message
    assert empties[0].fix_anchor == f"#instrument-{second.id}"
    # Per-(reviewer, instrument) noise suppressed for instrument B.
    per_instr = _issues_with_key(
        issues, "assignments.reviewer_missing_for_instrument"
    )
    assert per_instr == []
