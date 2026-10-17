"""Pair tags through Generate, on real ``Relationship`` rows (author,
2026-10-17; ``guide/archive/assignment_rule_clarify.md`` Item 2).

A relationship is a pair of individuals: on a Group instrument a Link 2
pair-tag IS NOT drops only the ruled-out member's row, not the group;
and a reviewer's pair tag (``reviewer.pair_tagN``) holds for every one
of their pairs, through ``relationships.pair_context_lookup``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments


def _seed(db: Session, code: str, *, group_kind: str | None, rules_json: list) -> tuple:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="Band1",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=rules_json,
    )
    db.add(rule_set)
    db.flush()
    db.add(
        Instrument(
            session_id=review_session.id,
            name="I",
            order=0,
            group_kind=group_kind,
            rule_set_id=rule_set.id,
        )
    )
    rae = Reviewer(session_id=review_session.id, name="Rae", email="rae@example.edu")
    sol = Reviewer(session_id=review_session.id, name="Sol", email="sol@example.edu")
    team = {
        name: Reviewee(
            session_id=review_session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
            tag_1="Blue",
        )
        for name in ("Ann", "Ben")
    }
    db.add_all([rae, sol, *team.values()])
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=rae.id,
            reviewee_id=team["Ann"].id,
            tag_1="COI",
        )
    )
    db.commit()
    return user, review_session


def _link(link: str, field: str, operator: str, operand: str) -> dict:
    return {
        "id": link,
        "enabled": True,
        "kind": "COMPOSITE",
        "op": "AND",
        "rules": [
            {
                "id": f"{link}-r0",
                "enabled": True,
                "kind": "MATCH",
                "predicate": {"field": field, "operator": operator, "operand": operand},
            }
        ],
    }


def _generated(db: Session, user: User, review_session: ReviewSession) -> set[tuple[str, str]]:
    assignments.replace_assignments(
        db, review_session=review_session, user=user, correlation_id="t"
    )
    db.commit()
    rows = db.execute(
        select(Reviewer.name, Reviewee.name)
        .join(Assignment, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == review_session.id)
    ).all()
    return {(reviewer, reviewee) for reviewer, reviewee in rows}


def test_group_pair_tag_is_not_drops_only_that_members_row(db: Session) -> None:
    """Ann and Ben are one Blue group; Rae–Ann is a COI pair. Rae keeps
    Ben, and Sol, with no relationship, keeps both."""
    user, review_session = _seed(
        db,
        "pt-group",
        group_kind="r1",
        rules_json=[_link("link2", "pair_context.tag1", "not_equals", "COI")],
    )
    assert _generated(db, user, review_session) == {
        ("Rae", "Ben"),
        ("Sol", "Ann"),
        ("Sol", "Ben"),
    }


def test_a_reviewers_pair_tag_holds_for_every_one_of_their_pairs(db: Session) -> None:
    user, review_session = _seed(
        db,
        "pt-person",
        group_kind=None,
        rules_json=[_link("link1", "reviewer.pair_tag1", "equals", "COI")],
    )
    assert _generated(db, user, review_session) == {("Rae", "Ann"), ("Rae", "Ben")}
