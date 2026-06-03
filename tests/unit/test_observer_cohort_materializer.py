"""Unit tests for
``app.services.observer_cohort.materialize_cohort_assignments``.

Pins the walker shape: empty-rule / no-match return ``EMPTY_COHORT``,
single-side rules pick out the matching assignments, distinct
side counts derive from the matching pool, and the walker scopes
strictly to the given session + instrument.

Per-rule predicate semantics (every operator, AND / OR
combinator, observer-attribute operands, single-side rules
ignoring the other side, pair_context / cross-roster deferral)
are pinned separately in ``test_assignment_matches_cohort.py``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.observer_cohort import (
    EMPTY_COHORT,
    materialize_cohort_assignments,
)


def _session(db: Session, *, code: str) -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    sess = ReviewSession(
        name="Sess",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(sess)
    db.flush()
    return sess


def _instrument(db: Session, sess: ReviewSession) -> Instrument:
    inst = Instrument(session_id=sess.id, name="Inst", order=0)
    db.add(inst)
    db.flush()
    return inst


def _reviewer(
    db: Session,
    session_id: int,
    *,
    name: str,
    email: str,
    tag_1: str | None = None,
) -> Reviewer:
    r = Reviewer(
        session_id=session_id, name=name, email=email, tag_1=tag_1
    )
    db.add(r)
    db.flush()
    return r


def _reviewee(
    db: Session,
    session_id: int,
    *,
    name: str,
    email_or_identifier: str,
    tag_1: str | None = None,
) -> Reviewee:
    r = Reviewee(
        session_id=session_id,
        name=name,
        email_or_identifier=email_or_identifier,
        tag_1=tag_1,
    )
    db.add(r)
    db.flush()
    return r


def _observer(
    db: Session,
    session_id: int,
    *,
    email: str,
    tag_1: str | None = None,
    cohort_rule: dict | None = None,
) -> Observer:
    o = Observer(
        session_id=session_id,
        email=email,
        tag_1=tag_1,
        cohort_rule=cohort_rule,
    )
    db.add(o)
    db.flush()
    return o


def _assignment(
    db: Session,
    sess: ReviewSession,
    inst: Instrument,
    reviewer: Reviewer,
    reviewee: Reviewee,
) -> Assignment:
    a = Assignment(
        session_id=sess.id,
        instrument_id=inst.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
    )
    db.add(a)
    db.flush()
    return a


def _rule_reviewer_tag1_is(value: str) -> dict:
    return {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": value,
            }
        ],
    }


def test_no_saved_rule_returns_empty_cohort(db: Session) -> None:
    sess = _session(db, code="mca-none")
    inst = _instrument(db, sess)
    obs = _observer(db, sess.id, email="o@x")
    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst.id
    )
    assert cohort == EMPTY_COHORT


def test_empty_rules_returns_empty_cohort(db: Session) -> None:
    sess = _session(db, code="mca-empty")
    inst = _instrument(db, sess)
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={"combinator": "AND", "rules": []},
    )
    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst.id
    )
    assert cohort == EMPTY_COHORT


def test_single_side_rule_picks_out_matching_assignments(
    db: Session,
) -> None:
    """``reviewer.tag1 IS "math"`` picks the assignments whose
    reviewer carries that tag; everything else is excluded."""
    sess = _session(db, code="mca-rev-tag")
    inst = _instrument(db, sess)
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    r2 = _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    e1 = _reviewee(db, sess.id, name="E", email_or_identifier="e@x")
    a_in = _assignment(db, sess, inst, r1, e1)
    a_out = _assignment(db, sess, inst, r2, e1)
    obs = _observer(
        db, sess.id, email="o@x", cohort_rule=_rule_reviewer_tag1_is("math")
    )
    db.commit()

    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst.id
    )
    assert cohort.assignment_ids == frozenset({a_in.id})
    assert a_out.id not in cohort.assignment_ids
    assert cohort.distinct_reviewer_count == 1
    assert cohort.distinct_reviewee_count == 1


def test_distinct_counts_can_differ(db: Session) -> None:
    """The pool can be wide-and-short (few reviewers, many
    reviewees) or vice versa — the distinct counts reflect that."""
    sess = _session(db, code="mca-asym")
    inst = _instrument(db, sess)
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    e1 = _reviewee(db, sess.id, name="E1", email_or_identifier="e1@x")
    e2 = _reviewee(db, sess.id, name="E2", email_or_identifier="e2@x")
    e3 = _reviewee(db, sess.id, name="E3", email_or_identifier="e3@x")
    _assignment(db, sess, inst, r1, e1)
    _assignment(db, sess, inst, r1, e2)
    _assignment(db, sess, inst, r1, e3)
    obs = _observer(
        db, sess.id, email="o@x", cohort_rule=_rule_reviewer_tag1_is("math")
    )
    db.commit()

    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst.id
    )
    assert len(cohort.assignment_ids) == 3
    assert cohort.distinct_reviewer_count == 1
    assert cohort.distinct_reviewee_count == 3


def test_no_matches_returns_empty_ids_but_keeps_zero_counts(
    db: Session,
) -> None:
    """Rule exists but matches no assignment → empty ids and
    zero counts (not ``EMPTY_COHORT`` per se, but equivalent)."""
    sess = _session(db, code="mca-no-match")
    inst = _instrument(db, sess)
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="bio")
    e1 = _reviewee(db, sess.id, name="E", email_or_identifier="e@x")
    _assignment(db, sess, inst, r1, e1)
    obs = _observer(
        db, sess.id, email="o@x", cohort_rule=_rule_reviewer_tag1_is("math")
    )
    db.commit()

    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst.id
    )
    assert cohort.assignment_ids == frozenset()
    assert cohort.distinct_reviewer_count == 0
    assert cohort.distinct_reviewee_count == 0


def test_other_instruments_assignments_are_excluded(
    db: Session,
) -> None:
    """Assignments on a different instrument in the same session
    must not contribute, even if their reviewer/reviewee would
    pass the rule."""
    sess = _session(db, code="mca-other-inst")
    inst_a = _instrument(db, sess)
    inst_b = Instrument(session_id=sess.id, name="Inst B", order=1)
    db.add(inst_b)
    db.flush()
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    e1 = _reviewee(db, sess.id, name="E", email_or_identifier="e@x")
    a_a = _assignment(db, sess, inst_a, r1, e1)
    _assignment(db, sess, inst_b, r1, e1)
    obs = _observer(
        db, sess.id, email="o@x", cohort_rule=_rule_reviewer_tag1_is("math")
    )
    db.commit()

    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst_a.id
    )
    assert cohort.assignment_ids == frozenset({a_a.id})


def test_only_in_session_assignments_match(db: Session) -> None:
    """Assignments in a different session never contribute, even
    when the rule + reviewer/reviewee tags align."""
    sess_a = _session(db, code="mca-cross-a")
    sess_b = _session(db, code="mca-cross-b")
    inst_a = _instrument(db, sess_a)
    inst_b = _instrument(db, sess_b)
    r_a = _reviewer(db, sess_a.id, name="A", email="ra@x", tag_1="math")
    r_b = _reviewer(db, sess_b.id, name="B", email="rb@x", tag_1="math")
    e_a = _reviewee(db, sess_a.id, name="E", email_or_identifier="ea@x")
    e_b = _reviewee(db, sess_b.id, name="E", email_or_identifier="eb@x")
    a_a = _assignment(db, sess_a, inst_a, r_a, e_a)
    _assignment(db, sess_b, inst_b, r_b, e_b)
    obs = _observer(
        db,
        sess_a.id,
        email="o@x",
        cohort_rule=_rule_reviewer_tag1_is("math"),
    )
    db.commit()

    cohort = materialize_cohort_assignments(
        db, observer=obs, instrument_id=inst_a.id
    )
    assert cohort.assignment_ids == frozenset({a_a.id})
