"""Unit tests for ``app.services.observer_cohort.materialize_cohort``.

Pins per-rule semantics + AND/OR combination + unsupported
edge cases (pair_context, cross-roster operand) before the
collation surface starts reading the result.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services.observer_cohort import (
    CohortIds,
    materialize_cohort,
)


def _session(db: Session, *, code: str) -> tuple[ReviewSession, User]:
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
    return sess, user


def _reviewer(
    db: Session,
    session_id: int,
    *,
    name: str,
    email: str,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> Reviewer:
    r = Reviewer(
        session_id=session_id,
        name=name,
        email=email,
        tag_1=tag_1,
        tag_2=tag_2,
        tag_3=tag_3,
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
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> Reviewee:
    r = Reviewee(
        session_id=session_id,
        name=name,
        email_or_identifier=email_or_identifier,
        tag_1=tag_1,
        tag_2=tag_2,
        tag_3=tag_3,
    )
    db.add(r)
    db.flush()
    return r


def _observer(
    db: Session,
    session_id: int,
    *,
    email: str,
    display_name: str | None = None,
    tag_1: str | None = None,
    cohort_rule: dict | None = None,
) -> Observer:
    o = Observer(
        session_id=session_id,
        email=email,
        display_name=display_name,
        tag_1=tag_1,
        cohort_rule=cohort_rule,
    )
    db.add(o)
    db.flush()
    return o


def test_no_saved_rule_returns_empty_cohort(db: Session) -> None:
    sess, _ = _session(db, code="m-none")
    obs = _observer(db, sess.id, email="o@x")
    cohort = materialize_cohort(db, observer=obs)
    assert cohort == CohortIds(frozenset(), frozenset())


def test_empty_rules_returns_empty_cohort(db: Session) -> None:
    sess, _ = _session(db, code="m-empty")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={"combinator": "AND", "rules": []},
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort == CohortIds(frozenset(), frozenset())


def test_reviewer_is_filters_reviewers_leaves_reviewees_open(
    db: Session,
) -> None:
    sess, _ = _session(db, code="m-rev-is")
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    e1 = _reviewee(db, sess.id, name="EA", email_or_identifier="ea@x", tag_1="math")
    e2 = _reviewee(db, sess.id, name="EB", email_or_identifier="eb@x", tag_1="bio")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    # reviewer.tag1 IS "math" → only r1; reviewee side
    # unconstrained → all reviewees.
    assert cohort.reviewer_ids == frozenset({r1.id})
    assert cohort.reviewee_ids == frozenset({e1.id, e2.id})


def test_reviewee_contains_is_case_insensitive_substring(
    db: Session,
) -> None:
    sess, _ = _session(db, code="m-ree-contains")
    _reviewee(db, sess.id, name="E1", email_or_identifier="e1@x", tag_1="MathStream")
    e2 = _reviewee(db, sess.id, name="E2", email_or_identifier="e2@x", tag_1="mathfoo")
    _reviewee(db, sess.id, name="E3", email_or_identifier="e3@x", tag_1="biology")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewee.tag1",
                    "op": "CONTAINS",
                    "operand_tag": "",
                    "operand_value": "math",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    # Case-insensitive substring → MathStream + mathfoo, not biology.
    # MathStream is found via case-insensitive comparison.
    assert e2.id in cohort.reviewee_ids
    assert len(cohort.reviewee_ids) == 2


def test_is_not_negates(db: Session) -> None:
    sess, _ = _session(db, code="m-is-not")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    r2 = _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS NOT",
                    "operand_tag": "",
                    "operand_value": "math",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r2.id})


def test_does_not_contain_negates_substring(db: Session) -> None:
    sess, _ = _session(db, code="m-not-contains")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="math_a")
    r2 = _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "DOES NOT CONTAIN",
                    "operand_tag": "",
                    "operand_value": "math",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r2.id})


def test_is_the_same_as_observer_attribute(db: Session) -> None:
    sess, _ = _session(db, code="m-same-as")
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="cohort-A")
    _reviewer(db, sess.id, name="B", email="b@x", tag_1="cohort-B")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        tag_1="cohort-A",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS THE SAME AS",
                    "operand_tag": "observer.tag1",
                    "operand_value": "",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r1.id})


def test_is_different_from_observer_attribute(db: Session) -> None:
    sess, _ = _session(db, code="m-diff-from")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="cohort-A")
    r2 = _reviewer(db, sess.id, name="B", email="b@x", tag_1="cohort-B")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        tag_1="cohort-A",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS DIFFERENT FROM",
                    "operand_tag": "observer.tag1",
                    "operand_value": "",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r2.id})


def test_observer_attribute_missing_yields_empty(db: Session) -> None:
    sess, _ = _session(db, code="m-missing-attr")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="x")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        # tag_1 is None — IS THE SAME AS observer.tag1 has no
        # meaningful operand → empty cohort.
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS THE SAME AS",
                    "operand_tag": "observer.tag1",
                    "operand_value": "",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset()


def test_and_combinator_intersects_constrained_sides(db: Session) -> None:
    sess, _ = _session(db, code="m-and")
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math", tag_2="senior")
    _reviewer(db, sess.id, name="B", email="b@x", tag_1="math", tag_2="junior")
    _reviewer(db, sess.id, name="C", email="c@x", tag_1="bio", tag_2="senior")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                },
                {
                    "field": "reviewer.tag2",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "senior",
                },
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r1.id})


def test_or_combinator_unions_constrained_sides(db: Session) -> None:
    sess, _ = _session(db, code="m-or")
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    r2 = _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    _reviewer(db, sess.id, name="C", email="c@x", tag_1="chem")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "OR",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                },
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "bio",
                },
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({r1.id, r2.id})


def test_and_with_mixed_sides(db: Session) -> None:
    sess, _ = _session(db, code="m-and-cross")
    r1 = _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    _reviewer(db, sess.id, name="B", email="b@x", tag_1="bio")
    e1 = _reviewee(db, sess.id, name="E1", email_or_identifier="e1@x", tag_1="senior")
    _reviewee(db, sess.id, name="E2", email_or_identifier="e2@x", tag_1="junior")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                },
                {
                    "field": "reviewee.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "senior",
                },
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    # Reviewer side constrained to {r1}; reviewee side
    # constrained to {e1}.
    assert cohort.reviewer_ids == frozenset({r1.id})
    assert cohort.reviewee_ids == frozenset({e1.id})


def test_pair_context_rule_returns_empty_for_now(db: Session) -> None:
    """``pair_context.*`` is recognised by the schema but the
    materialiser doesn't yet do the pair-level join. The rule
    is treated as unmatched until a future PR adds the join."""
    sess, _ = _session(db, code="m-pair-ctx")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="math")
    _reviewee(db, sess.id, name="E", email_or_identifier="e@x", tag_1="math")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "pair_context.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "tutorial-A",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset()
    assert cohort.reviewee_ids == frozenset()


def test_cross_roster_operand_tag_returns_empty_for_now(db: Session) -> None:
    """``reviewer.tag1 IS THE SAME AS reviewee.tag2`` is
    recognised by the schema but the materialiser doesn't yet
    do the pair-level join."""
    sess, _ = _session(db, code="m-cross-operand")
    _reviewer(db, sess.id, name="A", email="a@x", tag_1="x")
    _reviewee(db, sess.id, name="E", email_or_identifier="e@x", tag_1="x")
    obs = _observer(
        db,
        sess.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS THE SAME AS",
                    "operand_tag": "reviewee.tag1",
                    "operand_value": "",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset()
    assert cohort.reviewee_ids == frozenset()


def test_only_in_session_observers_are_matched(db: Session) -> None:
    """The materialiser must not cross session boundaries."""
    sess_a, _ = _session(db, code="m-cross-sess-a")
    sess_b, _ = _session(db, code="m-cross-sess-b")
    # Same tag value across sessions.
    in_a = _reviewer(db, sess_a.id, name="A", email="a@x", tag_1="math")
    _reviewer(db, sess_b.id, name="B", email="b@x", tag_1="math")
    obs = _observer(
        db,
        sess_a.id,
        email="o@x",
        cohort_rule={
            "combinator": "AND",
            "rules": [
                {
                    "field": "reviewer.tag1",
                    "op": "IS",
                    "operand_tag": "",
                    "operand_value": "math",
                }
            ],
        },
    )
    cohort = materialize_cohort(db, observer=obs)
    assert cohort.reviewer_ids == frozenset({in_a.id})
