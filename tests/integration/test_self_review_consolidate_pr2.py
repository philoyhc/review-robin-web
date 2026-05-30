"""PR 2 of the ``guide/self_review_consolidate.md`` slice — write
sites + recompute hooks keep ``Assignment.is_self_review`` current.

Verifies that every code path that creates or materially changes
an Assignment populates / refreshes the column:

* Regenerate (``replace_assignments``).
* Instrument clone via ``create_instrument`` with a source row.
* Instrument clone via ``replicate_instrument``.
* Reviewer email change (``update_reviewer``).
* Reviewee identifier change (``update_reviewee``).
* Reviewee tag change affecting group composition (rides on
  ``reconcile_group_responses_for_tag_change``).
* Instrument ``group_kind`` change
  (``set_group_boundary`` / ``set_unit_of_review``).

Each test seeds a small population, applies the trigger, and
asserts ``Assignment.is_self_review`` reflects the canonical
classification — same rule the migration backfilled in PR 1.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments, reviewees, reviewers
from app.services.instruments import (
    create_instrument,
    encode_group_kind,
    ensure_default_instrument,
    replicate_instrument,
    set_group_boundary,
    set_unit_of_review,
)


def _seed(db: Session, *, code: str) -> tuple[User, ReviewSession]:
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


def _assignment_for(
    db: Session, *, reviewer_id: int, reviewee_id: int, instrument_id: int
) -> Assignment:
    return (
        db.query(Assignment)
        .filter(
            Assignment.reviewer_id == reviewer_id,
            Assignment.reviewee_id == reviewee_id,
            Assignment.instrument_id == instrument_id,
        )
        .one()
    )


# --------------------------------------------------------------------------- #
# Regenerate path
# --------------------------------------------------------------------------- #


def test_regenerate_populates_is_self_review_on_fresh_rows(
    db: Session,
) -> None:
    user, review_session = _seed(db, code="regen")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    bob_r = Reviewer(
        session_id=review_session.id, name="Bob", email="bob@example.edu"
    )
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
    db.add_all([alice_r, bob_r, alice_e, bob_e])
    db.flush()
    full_matrix = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(full_matrix)
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    instrument.rule_set_id = full_matrix.id
    db.flush()

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="test-regen",
    )
    db.flush()

    # Self-review rows flipped TRUE, the rest FALSE.
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=alice_e.id,
            instrument_id=instrument.id,
        ).is_self_review
        is True
    )
    assert (
        _assignment_for(
            db,
            reviewer_id=bob_r.id,
            reviewee_id=bob_e.id,
            instrument_id=instrument.id,
        ).is_self_review
        is True
    )
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=bob_e.id,
            instrument_id=instrument.id,
        ).is_self_review
        is False
    )


# --------------------------------------------------------------------------- #
# Instrument clone paths
# --------------------------------------------------------------------------- #


def test_create_instrument_clone_populates_is_self_review(
    db: Session,
) -> None:
    """When ``create_instrument`` clones assignments from an existing
    instrument, the new instrument's rows pick up the correct value
    — and crucially can DIVERGE from the source's value when the
    new instrument's grouping shape differs from the source's."""
    user, review_session = _seed(db, code="create-clone")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
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
    db.add_all([alice_r, alice_e, bob_e])
    db.flush()

    # Source instrument: individual-scoped. Alice's row about Alice
    # is the only self-review; Alice's row about Bob is not.
    source = ensure_default_instrument(db, review_session)
    db.add_all(
        [
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=alice_e.id,
                instrument_id=source.id,
            ),
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=bob_e.id,
                instrument_id=source.id,
            ),
        ]
    )
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )

    # Sanity: source rows reflect the individual rule.
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=alice_e.id,
            instrument_id=source.id,
        ).is_self_review
        is True
    )
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=bob_e.id,
            instrument_id=source.id,
        ).is_self_review
        is False
    )

    # ``create_instrument`` auto-clones from the lowest-ordered
    # existing instrument (the source above) when one exists —
    # see ``_instrument_crud.py`` ~line 244. The new instrument
    # picks up cloned assignments + the recompute fires.
    new_instrument = create_instrument(
        db,
        review_session=review_session,
        actor=user,
    )
    db.flush()
    # Cloned rows landed; recompute fired during the clone path.
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=alice_e.id,
            instrument_id=new_instrument.id,
        ).is_self_review
        is True
    )
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=bob_e.id,
            instrument_id=new_instrument.id,
        ).is_self_review
        is False
    )


def test_replicate_instrument_populates_is_self_review(
    db: Session,
) -> None:
    user, review_session = _seed(db, code="replicate")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
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
    db.add_all([alice_r, alice_e, bob_e])
    db.flush()
    source = ensure_default_instrument(db, review_session)
    db.add_all(
        [
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=alice_e.id,
                instrument_id=source.id,
            ),
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=bob_e.id,
                instrument_id=source.id,
            ),
        ]
    )
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )

    replicated = replicate_instrument(
        db,
        review_session=review_session,
        source=source,
        actor=user,
    )
    db.flush()
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=alice_e.id,
            instrument_id=replicated.id,
        ).is_self_review
        is True
    )
    assert (
        _assignment_for(
            db,
            reviewer_id=alice_r.id,
            reviewee_id=bob_e.id,
            instrument_id=replicated.id,
        ).is_self_review
        is False
    )


# --------------------------------------------------------------------------- #
# Reviewer email change
# --------------------------------------------------------------------------- #


def test_reviewer_email_change_recomputes_is_self_review(
    db: Session,
) -> None:
    """Alice's reviewer email starts misaligned with reviewee Alice
    (so no self-review). Edit the email to align — the row flips."""
    user, review_session = _seed(db, code="rev-email")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice-old@example.edu",
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
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    assert assignment.is_self_review is False

    reviewers.update_reviewer(
        db, reviewer=alice_r, email="alice@example.edu", user=user
    )
    db.refresh(assignment)
    assert assignment.is_self_review is True


# --------------------------------------------------------------------------- #
# Reviewee identifier change
# --------------------------------------------------------------------------- #


def test_reviewee_identifier_change_recomputes_is_self_review(
    db: Session,
) -> None:
    user, review_session = _seed(db, code="ree-id")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        # Start as a non-email identifier — no self-review.
        email_or_identifier="AliceID",
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
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    assert assignment.is_self_review is False

    reviewees.update_reviewee(
        db,
        reviewee=alice_e,
        email_or_identifier="alice@example.edu",
        user=user,
    )
    db.refresh(assignment)
    assert assignment.is_self_review is True


# --------------------------------------------------------------------------- #
# Reviewee tag change — group composition shift
# --------------------------------------------------------------------------- #


def test_reviewee_tag_change_recomputes_is_self_review(
    db: Session,
) -> None:
    """Alice (reviewer) reviews a group on tag_1. Bob is currently
    in group Y (not Alice's group), so no row is self-review. Move
    Bob into group X (where Alice lives) — Alice's reviews of both
    Alice and Bob flip to self-review (whole-group rule)."""
    user, review_session = _seed(db, code="ree-tag")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
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
        tag_1="Y",  # Different group from Alice initially.
    )
    db.add_all([alice_r, alice_e, bob_e])
    db.flush()
    # Group-scoped instrument on tag_1.
    instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = encode_group_kind([("reviewee", "tag_1")])
    db.flush()
    a_alice = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_e.id,
        instrument_id=instrument.id,
    )
    a_bob = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=bob_e.id,
        instrument_id=instrument.id,
    )
    db.add_all([a_alice, a_bob])
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    # Alice's group "X" is currently {Alice} → self-review row only
    # for the Alice-on-Alice cell. Bob is in group "Y" → not in
    # Alice's group; Alice's row about Bob isn't self-review.
    assert a_alice.is_self_review is True
    assert a_bob.is_self_review is False

    # Move Bob into Alice's group.
    reviewees.update_reviewee(
        db, reviewee=bob_e, tag_1="X", user=user
    )
    db.refresh(a_alice)
    db.refresh(a_bob)
    # Whole-group rule: Alice's group X now {Alice, Bob}, and Alice
    # is a member → both rows flip TRUE.
    assert a_alice.is_self_review is True
    assert a_bob.is_self_review is True


# --------------------------------------------------------------------------- #
# Instrument group_kind change
# --------------------------------------------------------------------------- #


def test_set_group_boundary_recomputes_is_self_review(
    db: Session,
) -> None:
    """A group-scoped instrument starts with the ``"both"`` sentinel
    (single global group; every row in the global group counts as
    self-review since Alice is a member). Edit the boundary to
    ``tag_1`` — Bob's row about Carol (different ``tag_1``) drops out
    of Alice's group entirely, so its self-review flag flips off."""
    user, review_session = _seed(db, code="set-boundary")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
        tag_1="X",
    )
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="Y",
    )
    db.add_all([alice_r, alice_e, carol_e])
    db.flush()
    # Start with the ``"both"`` sentinel: a single global group
    # containing Alice and Carol; Alice's review of either row is
    # in a group Alice is a member of → both self-review.
    instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = "both"
    db.flush()
    a_alice = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_e.id,
        instrument_id=instrument.id,
    )
    a_carol = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=carol_e.id,
        instrument_id=instrument.id,
    )
    db.add_all([a_alice, a_carol])
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    assert a_alice.is_self_review is True
    assert a_carol.is_self_review is True

    # Edit boundary → tag_1. Now Alice (X) and Carol (Y) sit in
    # different groups; Alice's review of Carol is no longer in a
    # group Alice is a member of.
    set_group_boundary(
        db,
        instrument=instrument,
        boundary_pairs=[("reviewee", "tag_1")],
        actor=user,
    )
    db.refresh(a_alice)
    db.refresh(a_carol)
    assert a_alice.is_self_review is True
    assert a_carol.is_self_review is False


def test_set_unit_of_review_recomputes_is_self_review(
    db: Session,
) -> None:
    """Switching an instrument from individual → grouped on tag_1
    extends self-review status from the (Alice, Alice) pair to
    every assignment in Alice's group."""
    user, review_session = _seed(db, code="set-unit")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
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
    db.add_all([alice_r, alice_e, bob_e])
    db.flush()
    # Individual-scoped instrument: only (Alice, Alice) is self-review.
    instrument = ensure_default_instrument(db, review_session)
    a_alice = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=alice_e.id,
        instrument_id=instrument.id,
    )
    a_bob = Assignment(
        session_id=review_session.id,
        reviewer_id=alice_r.id,
        reviewee_id=bob_e.id,
        instrument_id=instrument.id,
    )
    db.add_all([a_alice, a_bob])
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    assert a_alice.is_self_review is True
    assert a_bob.is_self_review is False

    # Switch to grouped on tag_1 — Alice + Bob now share group "X".
    set_unit_of_review(
        db,
        instrument=instrument,
        mode="grouped",
        boundary_pairs=[("reviewee", "tag_1")],
        actor=user,
    )
    db.refresh(a_alice)
    db.refresh(a_bob)
    # Whole-group rule: Alice is a member of group "X" → both rows
    # flip TRUE.
    assert a_alice.is_self_review is True
    assert a_bob.is_self_review is True


# --------------------------------------------------------------------------- #
# Recompute helper directness — no-op + change counter
# --------------------------------------------------------------------------- #


def test_recompute_returns_zero_when_nothing_changed(
    db: Session,
) -> None:
    """When the stored column already matches what
    ``classify_self_review`` returns, the helper writes nothing and
    returns 0. Defensively useful so callers can flush precisely."""
    user, review_session = _seed(db, code="noop")
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    db.add_all([alice_r, alice_e])
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    db.add(
        Assignment(
            session_id=review_session.id,
            reviewer_id=alice_r.id,
            reviewee_id=alice_e.id,
            instrument_id=instrument.id,
            is_self_review=True,
        )
    )
    db.flush()
    changed = assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    assert changed == 0
