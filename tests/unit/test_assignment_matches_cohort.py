"""Unit tests for
``app.services.observer_cohort.assignment_matches_cohort`` — the
per-row predicate the CSV download filter uses.

Per-row evaluation differs from the set-based ``materialize_cohort``
in the cases that matter for the CSV download:

- A rule on ``reviewer.*`` only constrains the reviewer side
  of the row; the reviewee can be anything.
- ``OR`` across cross-side rules (e.g. ``reviewer.tag1 = math``
  OR ``reviewee.tag1 = junior``) means "this row passes if
  EITHER per-row predicate holds" — not "every row passes" as
  the set-union with unconstrained-fallback would give.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services.observer_cohort import assignment_matches_cohort


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


def _observer(db, sess, *, email="o@x", tag_1=None):
    o = Observer(
        session_id=sess.id,
        email=email,
        display_name="Alice",
        tag_1=tag_1,
    )
    db.add(o)
    db.flush()
    return o


def _reviewer(db, sess, *, tag_1=None, tag_2=None):
    r = Reviewer(
        session_id=sess.id,
        name="R",
        email=f"r{tag_1 or ''}@x",
        tag_1=tag_1,
        tag_2=tag_2,
    )
    db.add(r)
    db.flush()
    return r


def _reviewee(db, sess, *, tag_1=None, tag_2=None):
    e = Reviewee(
        session_id=sess.id,
        name="E",
        email_or_identifier=f"e{tag_1 or ''}@x",
        tag_1=tag_1,
        tag_2=tag_2,
    )
    db.add(e)
    db.flush()
    return e


def test_none_rule_set_returns_false(db: Session) -> None:
    sess = _session(db, code="amr-none")
    obs = _observer(db, sess)
    r = _reviewer(db, sess, tag_1="math")
    e = _reviewee(db, sess, tag_1="junior")
    assert assignment_matches_cohort(
        None, observer=obs, reviewer=r, reviewee=e
    ) is False


def test_empty_rules_returns_false(db: Session) -> None:
    sess = _session(db, code="amr-empty")
    obs = _observer(db, sess)
    r = _reviewer(db, sess, tag_1="math")
    e = _reviewee(db, sess, tag_1="junior")
    assert assignment_matches_cohort(
        {"combinator": "AND", "rules": []},
        observer=obs,
        reviewer=r,
        reviewee=e,
    ) is False


def test_reviewer_only_rule_ignores_reviewee_side(db: Session) -> None:
    """A rule on ``reviewer.tag1`` tests only the reviewer's
    tag1; the reviewee's attributes don't enter the predicate
    at all."""
    sess = _session(db, code="amr-rev-only")
    obs = _observer(db, sess)
    r_pass = _reviewer(db, sess, tag_1="math")
    r_fail = _reviewer(db, sess, tag_1="bio")
    e_a = _reviewee(db, sess, tag_1="anything")
    e_b = _reviewee(db, sess, tag_1="other")
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }
    # Reviewer matches → passes regardless of reviewee.
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_pass, reviewee=e_a
    )
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_pass, reviewee=e_b
    )
    # Reviewer fails → fails regardless of reviewee.
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_fail, reviewee=e_a
    )


def test_reviewee_only_rule_ignores_reviewer_side(db: Session) -> None:
    """Mirror of the reviewer-only case for ``reviewee.tag1``."""
    sess = _session(db, code="amr-ree-only")
    obs = _observer(db, sess, tag_1="cohort-A")
    r_a = _reviewer(db, sess, tag_1="anything")
    e_pass = _reviewee(db, sess, tag_1="cohort-A")
    e_fail = _reviewee(db, sess, tag_1="cohort-B")
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewee.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.tag1",
                "operand_value": "",
            }
        ],
    }
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_a, reviewee=e_pass
    )
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_a, reviewee=e_fail
    )


def test_and_requires_every_rule_to_pass(db: Session) -> None:
    sess = _session(db, code="amr-and")
    obs = _observer(db, sess)
    r = _reviewer(db, sess, tag_1="math")
    e_pass = _reviewee(db, sess, tag_1="senior")
    e_fail = _reviewee(db, sess, tag_1="junior")
    rule_set = {
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
    }
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r, reviewee=e_pass
    )
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r, reviewee=e_fail
    )


def test_or_passes_if_any_rule_passes(db: Session) -> None:
    """The case the set-based filter got wrong: ``OR`` of
    cross-side rules must mean "row passes if either rule
    holds", not "every row passes via the unconstrained-side
    fallback"."""
    sess = _session(db, code="amr-or")
    obs = _observer(db, sess)
    r_math = _reviewer(db, sess, tag_1="math")
    r_bio = _reviewer(db, sess, tag_1="bio")
    e_junior = _reviewee(db, sess, tag_1="junior")
    e_senior = _reviewee(db, sess, tag_1="senior")
    rule_set = {
        "combinator": "OR",
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
                "operand_value": "junior",
            },
        ],
    }
    # Matches via reviewer side only.
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_math, reviewee=e_senior
    )
    # Matches via reviewee side only.
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_bio, reviewee=e_junior
    )
    # Matches both.
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_math, reviewee=e_junior
    )
    # Matches neither — DOES NOT pass.
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_bio, reviewee=e_senior
    )


def test_contains_is_case_insensitive_substring(db: Session) -> None:
    sess = _session(db, code="amr-contains")
    obs = _observer(db, sess)
    r_pass = _reviewer(db, sess, tag_1="MathStream")
    r_fail = _reviewer(db, sess, tag_1="Biology")
    e = _reviewee(db, sess)
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "CONTAINS",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_pass, reviewee=e
    )
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_fail, reviewee=e
    )


def test_does_not_contain_negates_substring(db: Session) -> None:
    sess = _session(db, code="amr-not-contains")
    obs = _observer(db, sess)
    r_pass = _reviewer(db, sess, tag_1="biology")
    r_fail = _reviewer(db, sess, tag_1="math")
    e = _reviewee(db, sess)
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "DOES NOT CONTAIN",
                "operand_tag": "",
                "operand_value": "math",
            }
        ],
    }
    assert assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_pass, reviewee=e
    )
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r_fail, reviewee=e
    )


def test_observer_attribute_missing_yields_false(db: Session) -> None:
    """``IS THE SAME AS observer.tag1`` against an observer
    whose tag1 is null has no meaningful operand → False."""
    sess = _session(db, code="amr-missing-obs")
    obs = _observer(db, sess, tag_1=None)
    r = _reviewer(db, sess, tag_1="x")
    e = _reviewee(db, sess)
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "observer.tag1",
                "operand_value": "",
            }
        ],
    }
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r, reviewee=e
    )


def test_pair_context_rule_returns_false_for_now(db: Session) -> None:
    sess = _session(db, code="amr-pair-ctx")
    obs = _observer(db, sess)
    r = _reviewer(db, sess)
    e = _reviewee(db, sess)
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "pair_context.tag1",
                "op": "IS",
                "operand_tag": "",
                "operand_value": "x",
            }
        ],
    }
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r, reviewee=e
    )


def test_cross_roster_operand_tag_returns_false_for_now(
    db: Session,
) -> None:
    sess = _session(db, code="amr-cross-operand")
    obs = _observer(db, sess)
    r = _reviewer(db, sess, tag_1="x")
    e = _reviewee(db, sess, tag_1="x")
    rule_set = {
        "combinator": "AND",
        "rules": [
            {
                "field": "reviewer.tag1",
                "op": "IS THE SAME AS",
                "operand_tag": "reviewee.tag1",
                "operand_value": "",
            }
        ],
    }
    assert not assignment_matches_cohort(
        rule_set, observer=obs, reviewer=r, reviewee=e
    )
