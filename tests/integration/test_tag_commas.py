"""Findings Gc1 (ruled 2026-10-07): no roster tag value may contain a
comma, in any roster, on import or edit.

A group instrument names a group by its tag values joined with ", ", so
a comma inside one would let two groups render the same name. Each CSV
importer reports a blocking issue on the cell; each single-row service
raises its ``comma_in_tag`` operation error, which the routes render
like any other refusal."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services import observers, relationships, reviewees, reviewers
from app.services.csv_imports import (
    parse_observer_csv,
    parse_reviewee_csv,
    parse_reviewer_csv,
)


def _issue_fields(result) -> set[str]:
    return {issue.field for issue in result.issues if "comma" in issue.message}


def test_the_roster_imports_refuse_a_comma_in_a_tag() -> None:
    reviewer = parse_reviewer_csv(
        b'ReviewerName,ReviewerEmail,ReviewerTag2\nAl,a@x.edu,"A, B"\n'
    )
    assert reviewer.is_blocked and reviewer.rows == []
    assert _issue_fields(reviewer) == {"ReviewerTag2"}

    reviewee = parse_reviewee_csv(
        b'RevieweeName,RevieweeEmail,RevieweeTag1\nBo,b@x.edu,"A,B"\n'
    )
    assert reviewee.is_blocked
    assert _issue_fields(reviewee) == {"RevieweeTag1"}

    observer = parse_observer_csv(b'ObserverEmail,ObserverTag1\no@x.edu,"x,y"\n')
    assert observer.is_blocked
    assert _issue_fields(observer) == {"ObserverTag1"}


def test_a_tag_without_a_comma_still_imports() -> None:
    result = parse_reviewee_csv(
        b"RevieweeName,RevieweeEmail,RevieweeTag1\nBo,b@x.edu,Team A; B\n"
    )
    assert result.issues == []
    assert result.rows[0].tag_1 == "Team A; B"


def _seed(db: Session) -> tuple[User, ReviewSession, Reviewer, Reviewee]:
    user = User(email="op-gc1@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    rs = ReviewSession(name="Gc1", code="gc1", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    rvr = Reviewer(session_id=rs.id, name="R", email="r@x.edu")
    rve = Reviewee(session_id=rs.id, name="E", email_or_identifier="e@x.edu")
    db.add_all([rvr, rve])
    db.flush()
    return user, rs, rvr, rve


def test_the_relationship_import_refuses_a_comma_in_a_tag(db: Session) -> None:
    _, _, rvr, rve = _seed(db)
    result = relationships.parse_relationship_csv(
        b'ReviewerEmail,RevieweeEmail,PairContextTag3\nr@x.edu,e@x.edu,"p,q"\n',
        reviewers=[rvr],
        reviewees=[rve],
    )
    assert result.is_blocked
    assert _issue_fields(result) == {"PairContextTag3"}


def test_the_single_row_editors_refuse_a_comma_in_a_tag(db: Session) -> None:
    user, rs, rvr, rve = _seed(db)

    with pytest.raises(reviewers.ReviewerOperationError) as exc:
        reviewers.create_reviewer(
            db, review_session=rs, name="Al", email="a@x.edu", tag_1="A,B",
            user=user,
        )
    assert exc.value.code == "comma_in_tag"
    assert exc.value.message == "Tag 1 may not contain a comma."
    with pytest.raises(reviewers.ReviewerOperationError) as exc:
        reviewers.update_reviewer(db, reviewer=rvr, tag_3="A,B", user=user)
    assert exc.value.code == "comma_in_tag"

    with pytest.raises(reviewees.RevieweeOperationError) as exc:
        reviewees.create_reviewee(
            db, review_session=rs, name="Bo", email_or_identifier="b@x.edu",
            tag_2="A,B", user=user,
        )
    assert exc.value.code == "comma_in_tag"
    with pytest.raises(reviewees.RevieweeOperationError) as exc:
        reviewees.update_reviewee(db, reviewee=rve, tag_1="A,B", user=user)
    assert exc.value.code == "comma_in_tag"

    with pytest.raises(observers.ObserverOperationError) as exc:
        observers.create_observer(
            db, review_session=rs, email="o@x.edu", tag_1="A,B", user=user
        )
    assert exc.value.code == "comma_in_tag"
    observer = observers.create_observer(
        db, review_session=rs, email="o@x.edu", user=user
    )
    with pytest.raises(observers.ObserverOperationError) as exc:
        observers.update_observer(db, observer=observer, tag_1="A,B", user=user)
    assert exc.value.code == "comma_in_tag"

    with pytest.raises(relationships.RelationshipOperationError) as exc:
        relationships.create_relationship(
            db, review_session=rs, reviewer_id=rvr.id, reviewee_id=rve.id,
            tag_2="A,B", user=user,
        )
    assert exc.value.code == "comma_in_tag"
    rel = relationships.create_relationship(
        db, review_session=rs, reviewer_id=rvr.id, reviewee_id=rve.id,
        user=user,
    )
    with pytest.raises(relationships.RelationshipOperationError) as exc:
        relationships.update_relationship(
            db, relationship=rel, tag_1="A,B", user=user
        )
    assert exc.value.code == "comma_in_tag"
