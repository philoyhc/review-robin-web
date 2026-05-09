"""Unit tests for ``app.services.extracts.assignments_extract`` —
Segment 12A-1 PR 3.

Covers the manual-mode gate, the per-row column shape (matching
``app.services.assignments.parse_manual_csv``), the
multi-instrument N×M fanout, and the deterministic ordering. The
HTTP 404-on-non-manual behaviour is in
``tests/integration/test_extracts_assignments_route.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.assignments_extract import (
    HEADER,
    ManualOnlyError,
    serialize_assignments,
)


def _user(db: Session) -> User:
    user = User(email="alice@example.edu", display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(
    db: Session,
    *,
    code: str,
    mode: str | None = "manual",
) -> ReviewSession:
    user = _user(db)
    review_session = ReviewSession(
        name="Assignments",
        code=code,
        created_by_user_id=user.id,
        assignment_mode=mode,
    )
    db.add(review_session)
    db.flush()
    return review_session


def _add_reviewer(
    db: Session, review_session: ReviewSession, *, email: str, name: str
) -> Reviewer:
    r = Reviewer(
        session_id=review_session.id,
        name=name,
        email=email,
    )
    db.add(r)
    db.flush()
    return r


def _add_reviewee(
    db: Session, review_session: ReviewSession, *, identifier: str, name: str
) -> Reviewee:
    e = Reviewee(
        session_id=review_session.id,
        name=name,
        email_or_identifier=identifier,
    )
    db.add(e)
    db.flush()
    return e


def _add_instrument(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    short_label: str | None = None,
    order: int = 0,
) -> Instrument:
    instr = Instrument(
        session_id=review_session.id,
        name=name,
        short_label=short_label,
        order=order,
    )
    db.add(instr)
    db.flush()
    return instr


def _add_assignment(
    db: Session,
    review_session: ReviewSession,
    *,
    reviewer: Reviewer,
    reviewee: Reviewee,
    instrument: Instrument,
    include: bool = True,
) -> Assignment:
    a = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=include,
        created_by_mode="manual",
    )
    db.add(a)
    db.flush()
    return a


def test_non_manual_session_raises_manual_only_error(db: Session) -> None:
    review_session = _session(db, code="rb", mode="rule_based")
    with pytest.raises(ManualOnlyError) as exc_info:
        list(serialize_assignments(db, review_session))
    assert exc_info.value.mode == "rule_based"


def test_full_matrix_session_also_raises(db: Session) -> None:
    review_session = _session(db, code="fm", mode="full_matrix")
    with pytest.raises(ManualOnlyError):
        list(serialize_assignments(db, review_session))


def test_unset_assignment_mode_raises(db: Session) -> None:
    """Sessions that have never been generated against (mode None
    or empty) also raise — the export contract is "operator
    typed manual rows". Empty-state UX surfaces via the card row
    note, not via an empty CSV."""

    review_session = _session(db, code="unset", mode=None)
    with pytest.raises(ManualOnlyError):
        list(serialize_assignments(db, review_session))


def test_manual_session_emits_header_only_when_no_rows(db: Session) -> None:
    review_session = _session(db, code="empty-manual", mode="manual")
    rows = list(serialize_assignments(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_matches_importer_columns(db: Session) -> None:
    review_session = _session(db, code="shape", mode="manual")
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="carol@example.edu", name="Carol"
    )
    instrument = _add_instrument(db, review_session, name="Peer evaluation")
    _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
    )

    rows = list(serialize_assignments(db, review_session))
    assert rows[0] == HEADER
    assert rows[1] == (
        "alex@example.edu",
        "carol@example.edu",
        "true",
        "Peer evaluation",
    )


def test_inactive_assignments_export_as_false(db: Session) -> None:
    review_session = _session(db, code="inactive", mode="manual")
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="carol@example.edu", name="Carol"
    )
    instrument = _add_instrument(db, review_session, name="Peer evaluation")
    _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
        include=False,
    )

    body = list(serialize_assignments(db, review_session))[1:]
    assert body[0][2] == "false"


def test_instrument_label_prefers_short_label_then_description(
    db: Session,
) -> None:
    review_session = _session(db, code="label", mode="manual")
    reviewer = _add_reviewer(
        db, review_session, email="alex@example.edu", name="Alex"
    )
    reviewee = _add_reviewee(
        db, review_session, identifier="carol@example.edu", name="Carol"
    )
    instrument = _add_instrument(
        db,
        review_session,
        name="instrument_42",
        short_label="Peer Eval",
    )
    _add_assignment(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        instrument=instrument,
    )

    rows = list(serialize_assignments(db, review_session))
    assert rows[1][3] == "Peer Eval"


def test_multi_instrument_session_emits_n_times_m_rows(db: Session) -> None:
    """Two reviewer→reviewee pairs × three instruments = 6 body
    rows. Pins the multi-instrument fanout the upload-side
    importer collapses on the way back in."""

    review_session = _session(db, code="multi", mode="manual")
    reviewers = [
        _add_reviewer(
            db, review_session, email=f"r{n}@example.edu", name=f"R{n}"
        )
        for n in range(2)
    ]
    reviewees = [
        _add_reviewee(
            db, review_session, identifier="e1@example.edu", name="E1"
        ),
    ]
    instruments = [
        _add_instrument(
            db, review_session, name=f"Instrument {n}", order=n
        )
        for n in range(3)
    ]
    for reviewer in reviewers:
        for reviewee in reviewees:
            for instrument in instruments:
                _add_assignment(
                    db,
                    review_session,
                    reviewer=reviewer,
                    reviewee=reviewee,
                    instrument=instrument,
                )

    body = list(serialize_assignments(db, review_session))[1:]
    assert len(body) == 2 * 1 * 3


def test_ordering_groups_rows_by_reviewer_then_reviewee_then_instrument(
    db: Session,
) -> None:
    review_session = _session(db, code="order", mode="manual")
    alice = _add_reviewer(
        db, review_session, email="alice@example.edu", name="Alice"
    )
    bob = _add_reviewer(
        db, review_session, email="bob@example.edu", name="Bob"
    )
    carol = _add_reviewee(
        db, review_session, identifier="carol@example.edu", name="Carol"
    )
    instr_first = _add_instrument(
        db, review_session, name="First", order=0
    )
    instr_second = _add_instrument(
        db, review_session, name="Second", order=1
    )
    # Insert in the OPPOSITE of the desired order to prove
    # ordering is by query, not by insertion.
    _add_assignment(
        db,
        review_session,
        reviewer=bob,
        reviewee=carol,
        instrument=instr_second,
    )
    _add_assignment(
        db,
        review_session,
        reviewer=alice,
        reviewee=carol,
        instrument=instr_second,
    )
    _add_assignment(
        db,
        review_session,
        reviewer=alice,
        reviewee=carol,
        instrument=instr_first,
    )
    _add_assignment(
        db,
        review_session,
        reviewer=bob,
        reviewee=carol,
        instrument=instr_first,
    )

    body = list(serialize_assignments(db, review_session))[1:]
    # alice→carol[First, Second], bob→carol[First, Second]
    assert [(r[0], r[3]) for r in body] == [
        ("alice@example.edu", "First"),
        ("alice@example.edu", "Second"),
        ("bob@example.edu", "First"),
        ("bob@example.edu", "Second"),
    ]
