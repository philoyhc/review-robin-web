"""Relationship changes re-derive ``Assignment.is_self_review`` (findings B33).

A group instrument boundaried on pair context (``group_kind="p1"``)
reads each pair's group key off its active ``Relationship`` row; an
inactive or missing one resolves to an empty value. Sam reviews his
own reviewee row and Zoe's, so Zoe's row is a self-review exactly when
its key matches the key of Sam's own row. Each mutator below moves
Zoe's key and must flip the stored flag without waiting for Generate.
Only a tag edit or a re-point through ``update_relationship`` did so
before.
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
    User,
)
from app.schemas.imports import RelationshipImportRow
from app.services import assignments
from app.services import relationships as relationships_service
from app.services.instruments import ensure_default_instrument


class _World:
    def __init__(
        self,
        user: User,
        review_session: ReviewSession,
        reviewer: Reviewer,
        own: Reviewee,
        zoe: Reviewee,
        zoe_row: Assignment,
    ) -> None:
        self.user = user
        self.review_session = review_session
        self.reviewer = reviewer
        self.own = own
        self.zoe = zoe
        self.zoe_row = zoe_row


def _seed(
    db: Session, *, own_tag: str | None, zoe_tag: str | None
) -> _World:
    """Sam reviews his own row and Zoe's on a ``p1`` group instrument.
    A ``None`` tag means no relationship row for that pair."""
    user = User(email="op-b33@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="B33", code="b33", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    reviewer = Reviewer(
        session_id=review_session.id, name="Sam", email="sam@example.edu"
    )
    own = Reviewee(
        session_id=review_session.id,
        name="Sam",
        email_or_identifier="sam@example.edu",
    )
    zoe = Reviewee(
        session_id=review_session.id,
        name="Zoe",
        email_or_identifier="zoe@example.edu",
    )
    db.add_all([reviewer, own, zoe])
    db.flush()
    instrument: Instrument = ensure_default_instrument(db, review_session)
    instrument.group_kind = "p1"
    for reviewee, tag in ((own, own_tag), (zoe, zoe_tag)):
        if tag is not None:
            db.add(
                Relationship(
                    session_id=review_session.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    tag_1=tag,
                )
            )
    rows = [
        Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        for reviewee in (own, zoe)
    ]
    db.add_all(rows)
    db.flush()
    assignments.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    db.commit()
    return _World(user, review_session, reviewer, own, zoe, rows[1])


def _relationship(db: Session, world: _World, reviewee: Reviewee) -> Relationship:
    return db.execute(
        select(Relationship).where(
            Relationship.reviewer_id == world.reviewer.id,
            Relationship.reviewee_id == reviewee.id,
        )
    ).scalar_one()


def _zoe_is_self_review(db: Session, world: _World) -> bool:
    db.refresh(world.zoe_row)
    return world.zoe_row.is_self_review


def test_creating_a_relationship_moves_zoe_into_the_group(db: Session) -> None:
    world = _seed(db, own_tag="A", zoe_tag=None)
    assert not _zoe_is_self_review(db, world)

    relationships_service.create_relationship(
        db,
        review_session=world.review_session,
        reviewer_id=world.reviewer.id,
        reviewee_id=world.zoe.id,
        tag_1="A",
        user=world.user,
    )

    assert _zoe_is_self_review(db, world)


def test_importing_relationships_moves_zoe_into_the_group(db: Session) -> None:
    world = _seed(db, own_tag="A", zoe_tag="B")
    assert not _zoe_is_self_review(db, world)

    relationships_service.save_relationships(
        db,
        session=world.review_session,
        user=world.user,
        rows=[
            RelationshipImportRow(
                reviewer_id=world.reviewer.id,
                reviewee_id=reviewee.id,
                tag_1="A",
            )
            for reviewee in (world.own, world.zoe)
        ],
        filename="relationships.csv",
        correlation_id="b33",
    )

    assert _zoe_is_self_review(db, world)


def test_deleting_every_relationship_empties_both_keys(db: Session) -> None:
    world = _seed(db, own_tag="A", zoe_tag="B")
    assert not _zoe_is_self_review(db, world)

    relationships_service.delete_all_relationships(
        db,
        review_session=world.review_session,
        user=world.user,
        correlation_id="b33",
    )

    assert _zoe_is_self_review(db, world)


def test_deleting_the_selected_relationship_moves_zoe_out(db: Session) -> None:
    world = _seed(db, own_tag="A", zoe_tag="A")
    assert _zoe_is_self_review(db, world)

    relationships_service.delete_selected(
        db,
        review_session=world.review_session,
        relationship_ids=[_relationship(db, world, world.zoe).id],
        user=world.user,
    )

    assert not _zoe_is_self_review(db, world)


def test_bulk_inactivate_and_reactivate_move_zoe_out_and_back(
    db: Session,
) -> None:
    world = _seed(db, own_tag="A", zoe_tag="A")
    relationship_id = _relationship(db, world, world.zoe).id

    relationships_service.bulk_inactivate(
        db,
        review_session=world.review_session,
        relationship_ids=[relationship_id],
        user=world.user,
    )
    assert not _zoe_is_self_review(db, world)

    relationships_service.bulk_reactivate(
        db,
        review_session=world.review_session,
        relationship_ids=[relationship_id],
        user=world.user,
    )
    assert _zoe_is_self_review(db, world)


def test_a_status_edit_moves_zoe_out(db: Session) -> None:
    """A tag edit reached the recompute through the group-response
    reconcile; a status edit changes no tag and did not."""
    world = _seed(db, own_tag="A", zoe_tag="A")
    assert _zoe_is_self_review(db, world)

    relationships_service.update_relationship(
        db,
        relationship=_relationship(db, world, world.zoe),
        status="inactive",
        user=world.user,
    )

    assert not _zoe_is_self_review(db, world)
