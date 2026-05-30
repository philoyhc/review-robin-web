"""Unit coverage for :func:`app.services.assignments.classify_self_review`
— the canonical self-review classification helper introduced in PR 1
of the ``guide/self_review_consolidate.md`` slice.

Exercises both arms of the rule:

* **Individual-scoped instrument** → per-row pair test.
* **Group-scoped instrument** → whole-group rule. When a group's
  reviewer is themselves a member, every assignment in the group
  flips to ``True``; when they're not, every assignment flips to
  ``False``.

Also confirms ``_self_review_assignment_ids`` stays a faithful
set-of-ids wrapper around the same machinery.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import assignments
from app.services.instruments import (
    ensure_default_instrument,
    encode_group_kind,
)


def _seed_session(db: Session, code: str) -> tuple[User, ReviewSession]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=code,
        created_by_user_id=user.id,
    )
    db.add(review_session)
    db.flush()
    return user, review_session


def _materialise_rows(
    db: Session, session_id: int
) -> list[tuple[Assignment, Reviewer, Reviewee]]:
    return [
        (a, r, e)
        for a, r, e in db.query(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .filter(Assignment.session_id == session_id)
        .all()
    ]


# --------------------------------------------------------------------------- #
# Individual-scoped instrument
# --------------------------------------------------------------------------- #


def test_individual_email_match_flips_true(db: Session) -> None:
    _, review_session = _seed_session(db, code="ind-match")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="Alice@Example.edu",  # casing should not matter
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    db.add_all([alice_r, alice_e])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_e.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert result == {assignment.id: True}


def test_individual_email_mismatch_flips_false(db: Session) -> None:
    _, review_session = _seed_session(db, code="ind-no-match")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([alice_r, bob_e])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=bob_e.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert result == {assignment.id: False}


def test_individual_non_email_identifier_never_self_review(
    db: Session,
) -> None:
    """Reviewees can carry a display identifier in
    ``email_or_identifier`` instead of an email. Without ``@``
    in the identifier, no match is possible — the rule returns
    ``False`` regardless of casing or substring overlap."""
    _, review_session = _seed_session(db, code="ind-non-email")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    alice_id = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="Alice",  # display identifier, no @
    )
    db.add_all([alice_r, alice_id])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_id.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert result == {assignment.id: False}


# --------------------------------------------------------------------------- #
# Group-scoped instrument — the whole-group rule
# --------------------------------------------------------------------------- #


def _make_group_instrument(
    db: Session, review_session: ReviewSession, boundary_code: str = "r1"
) -> Instrument:
    """A group-scoped instrument keyed off ``reviewee.tag_1`` by
    default."""
    instrument = ensure_default_instrument(db, review_session)
    if boundary_code == "both":
        instrument.group_kind = "both"
    else:
        instrument.group_kind = encode_group_kind(
            [("reviewee", "tag_1")]
            if boundary_code == "r1"
            else [("reviewee", "tag_2")]
        )
    db.flush()
    return instrument


def test_group_reviewer_is_member_flags_every_row_in_group(
    db: Session,
) -> None:
    """Alice (reviewer) reviewing a group she's a member of — the
    whole group counts as self-review, not just the ``(Alice,
    Alice)`` row."""
    _, review_session = _seed_session(db, code="grp-member")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    # Three reviewees all in tag_1="X" → one group.
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
        tag_1="X",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
        tag_1="X",
    )
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="X",
    )
    db.add_all([alice_e, bob_e, carol_e])
    db.flush()
    instrument = _make_group_instrument(db, review_session)

    assignment_ids: list[int] = []
    for reviewee in (alice_e, bob_e, carol_e):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        assignment_ids.append(assignment.id)

    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    # Every assignment in the group flagged — including Bob and Carol.
    assert all(result[aid] is True for aid in assignment_ids)


def test_group_reviewer_not_a_member_flags_no_row_in_group(
    db: Session,
) -> None:
    """Alice (reviewer) reviewing a group she is NOT a member of —
    no row counts as self-review, even though the group boundary
    matches Alice's own tag in other contexts."""
    _, review_session = _seed_session(db, code="grp-not-member")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    # Reviewees all in tag_1="Y" (a group Alice is not a member of).
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
        tag_1="Y",
    )
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="Y",
    )
    db.add_all([bob_e, carol_e])
    db.flush()
    instrument = _make_group_instrument(db, review_session)

    assignment_ids: list[int] = []
    for reviewee in (bob_e, carol_e):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        assignment_ids.append(assignment.id)

    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert all(result[aid] is False for aid in assignment_ids)


def test_group_two_groups_only_self_group_flips(
    db: Session,
) -> None:
    """Two groups under one reviewer: the one R is a member of
    flips; the one R isn't doesn't. Confirms the rule is keyed on
    ``(instrument, reviewer, group_key)`` not just any membership."""
    _, review_session = _seed_session(db, code="grp-two-groups")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    # Group X: contains Alice (self-review group).
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
        tag_1="X",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
        tag_1="X",
    )
    # Group Y: doesn't contain Alice.
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="Y",
    )
    dan_e = Reviewee(
        session_id=review_session.id,
        name="Dan",
        email_or_identifier="dan@example.edu",
        tag_1="Y",
    )
    db.add_all([alice_e, bob_e, carol_e, dan_e])
    db.flush()
    instrument = _make_group_instrument(db, review_session)

    self_group_ids: list[int] = []
    other_group_ids: list[int] = []
    for reviewee, target in (
        (alice_e, self_group_ids),
        (bob_e, self_group_ids),
        (carol_e, other_group_ids),
        (dan_e, other_group_ids),
    ):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        target.append(assignment.id)

    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert all(result[aid] is True for aid in self_group_ids)
    assert all(result[aid] is False for aid in other_group_ids)


def test_group_both_sentinel_single_global_group_flags_member(
    db: Session,
) -> None:
    """The ``"both"`` sentinel encodes a single global group — every
    reviewee belongs to the same group. When the reviewer is a
    member, every assignment under that reviewer flips."""
    _, review_session = _seed_session(db, code="grp-both")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([alice_e, bob_e])
    db.flush()
    instrument = _make_group_instrument(
        db, review_session, boundary_code="both"
    )

    ids: list[int] = []
    for reviewee in (alice_e, bob_e):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        ids.append(assignment.id)

    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert all(result[aid] is True for aid in ids)


def test_group_pair_context_boundary_with_active_relationship(
    db: Session,
) -> None:
    """Pair-context boundary tags come from the active relationship
    between (reviewer, reviewee). The migration replicates the
    classification helper's lookup; verify the runtime helper also
    handles it cleanly here."""
    _, review_session = _seed_session(db, code="grp-pair-context")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([alice_e, bob_e])
    db.flush()
    # Pair-context-keyed group instrument.
    instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = encode_group_kind([("pair_context", "1")])
    db.flush()
    # Active relationships keying both reviewees into the same group.
    for reviewee in (alice_e, bob_e):
        db.add(
            Relationship(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=reviewee.id,
                tag_1="cohort-A",
                status="active",
            )
        )
    db.flush()

    ids: list[int] = []
    for reviewee in (alice_e, bob_e):
        assignment = Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        db.add(assignment)
        db.flush()
        ids.append(assignment.id)

    rows = _materialise_rows(db, review_session.id)
    result = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    assert all(result[aid] is True for aid in ids)


# --------------------------------------------------------------------------- #
# ``_self_review_assignment_ids`` thin-wrapper contract
# --------------------------------------------------------------------------- #


def test_assignment_ids_wrapper_returns_subset_of_classify(
    db: Session,
) -> None:
    """``_self_review_assignment_ids`` must keep returning the
    set of ids where ``classify_self_review`` flagged ``True``."""
    _, review_session = _seed_session(db, code="wrapper")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    db.add(alice_r)
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
    )
    db.add_all([alice_e, bob_e])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    a_self = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_e.id,
        instrument_id=instrument.id,
    )
    a_other = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=bob_e.id,
        instrument_id=instrument.id,
    )
    db.add_all([a_self, a_other])
    db.flush()

    rows = _materialise_rows(db, review_session.id)
    classified = assignments.classify_self_review(
        db, session_id=review_session.id, rows=rows
    )
    ids = assignments._self_review_assignment_ids(
        db, session_id=review_session.id, rows=rows
    )
    assert ids == {aid for aid, v in classified.items() if v}
    assert ids == {a_self.id}
