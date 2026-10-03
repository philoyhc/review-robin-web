"""Relationship changes re-derive group answer copies (findings B34).

A group instrument boundaried on pair context (``group_kind="p1"``)
keeps one answer per group, copied onto every member's assignment. A
pair's group key is its active relationship's ``tag_1``; an inactive
or missing relationship reads as empty. When a change moves a pair to
another group, the copy it carries belongs to the old group: it is
deleted, and the pair takes its new group's answer if that group has
one. A tag edit or a re-point through ``update_relationship`` already
did this; every other relationship change left the old copy in place.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.imports import RelationshipImportRow
from app.services import relationships as relationships_service

_SAVED = dt.datetime(2026, 10, 3, tzinfo=dt.timezone.utc)


class _World:
    def __init__(
        self,
        user: User,
        review_session: ReviewSession,
        reviewer: Reviewer,
        reviewees: dict[str, Reviewee],
        rows: dict[str, Assignment],
    ) -> None:
        self.user = user
        self.review_session = review_session
        self.reviewer = reviewer
        self.reviewees = reviewees
        self.rows = rows


def _seed(
    db: Session, *, tags: dict[str, str | None], answers: dict[str, str]
) -> _World:
    """One reviewer on a ``p1`` group instrument, a reviewee per key of
    ``tags``. A ``None`` tag means no relationship for that pair; each
    ``answers`` entry is the copy that pair's assignment carries."""
    user = User(email="op-b34@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="B34", code="b34", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id, name="Grp", order=0, group_kind="p1"
    )
    db.add(instrument)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="rating",
        label="Rating",
        _inline_data_type="Integer",
        _inline_response_type="Likert5",
        order=0,
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="Rae", email="rae@example.edu"
    )
    reviewees = {
        name: Reviewee(
            session_id=review_session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
        )
        for name in tags
    }
    db.add_all([field, reviewer, *reviewees.values()])
    db.flush()
    rows: dict[str, Assignment] = {}
    for name, tag in tags.items():
        if tag is not None:
            db.add(
                Relationship(
                    session_id=review_session.id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewees[name].id,
                    tag_1=tag,
                )
            )
        rows[name] = Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewees[name].id,
            instrument_id=instrument.id,
        )
    db.add_all(rows.values())
    db.flush()
    for name, value in answers.items():
        db.add(
            Response(
                assignment_id=rows[name].id,
                response_field_id=field.id,
                value=value,
                saved_at=_SAVED,
                version=1,
            )
        )
    db.commit()
    return _World(user, review_session, reviewer, reviewees, rows)


def _answers(db: Session, world: _World) -> dict[str, str | None]:
    db.expire_all()
    out: dict[str, str | None] = {}
    for name, row in world.rows.items():
        values = db.execute(
            select(Response.value).where(Response.assignment_id == row.id)
        ).scalars().all()
        out[name] = values[0] if values else None
    return out


def _relationship(db: Session, world: _World, name: str) -> Relationship:
    return db.execute(
        select(Relationship).where(
            Relationship.reviewer_id == world.reviewer.id,
            Relationship.reviewee_id == world.reviewees[name].id,
        )
    ).scalar_one()


def _last_context(db: Session, event_type: str) -> dict | None:
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == event_type)
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    return (event.detail or {}).get("context")


def test_creating_a_relationship_moves_the_pair_into_its_group(
    db: Session,
) -> None:
    world = _seed(
        db, tags={"Ann": "A", "Cal": None}, answers={"Ann": "4", "Cal": "2"}
    )

    relationships_service.create_relationship(
        db,
        review_session=world.review_session,
        reviewer_id=world.reviewer.id,
        reviewee_id=world.reviewees["Cal"].id,
        tag_1="A",
        user=world.user,
    )

    assert _answers(db, world) == {"Ann": "4", "Cal": "4"}
    assert _last_context(db, "relationship.created") == {
        "defuncted_group_responses": 1
    }


def test_inactivating_drops_the_copy_and_reactivating_restores_it(
    db: Session,
) -> None:
    world = _seed(
        db, tags={"Ann": "A", "Bob": "A"}, answers={"Ann": "4", "Bob": "4"}
    )
    bob = _relationship(db, world, "Bob").id

    relationships_service.bulk_inactivate(
        db,
        review_session=world.review_session,
        relationship_ids=[bob],
        user=world.user,
    )
    assert _answers(db, world) == {"Ann": "4", "Bob": None}
    assert _last_context(db, "relationship.bulk_inactivated") == {
        "defuncted_group_responses": 1
    }

    relationships_service.bulk_reactivate(
        db,
        review_session=world.review_session,
        relationship_ids=[bob],
        user=world.user,
    )
    assert _answers(db, world) == {"Ann": "4", "Bob": "4"}


def test_a_status_edit_moves_the_pair_out(db: Session) -> None:
    world = _seed(
        db,
        tags={"Ann": "A", "Bob": "A", "Dan": None},
        answers={"Ann": "4", "Bob": "4", "Dan": "7"},
    )

    relationships_service.update_relationship(
        db,
        relationship=_relationship(db, world, "Bob"),
        status="inactive",
        user=world.user,
    )

    # Bob now reads as an empty tag, Dan's group: he takes its answer.
    assert _answers(db, world) == {"Ann": "4", "Bob": "7", "Dan": "7"}
    assert _last_context(db, "relationship.updated") == {
        "defuncted_group_responses": 1
    }


def test_deleting_the_selected_relationship_moves_the_pair_out(
    db: Session,
) -> None:
    world = _seed(
        db, tags={"Ann": "A", "Bob": "A"}, answers={"Ann": "4", "Bob": "4"}
    )

    relationships_service.delete_selected(
        db,
        review_session=world.review_session,
        relationship_ids=[_relationship(db, world, "Bob").id],
        user=world.user,
    )

    assert _answers(db, world) == {"Ann": "4", "Bob": None}
    assert _last_context(db, "relationship.bulk_deleted") == {
        "defuncted_group_responses": 1
    }


def test_deleting_every_relationship_moves_each_pair_to_the_empty_group(
    db: Session,
) -> None:
    world = _seed(
        db,
        tags={"Ann": "A", "Cal": "B", "Dan": None},
        answers={"Ann": "4", "Cal": "2", "Dan": "7"},
    )

    relationships_service.delete_all_relationships(
        db,
        review_session=world.review_session,
        user=world.user,
        correlation_id="b34",
    )

    # Dan never moved; the others join his group and take its answer.
    assert _answers(db, world) == {"Ann": "7", "Cal": "7", "Dan": "7"}
    assert _last_context(db, "relationships.deleted_all") == {
        "defuncted_group_responses": 2
    }


def test_importing_moves_only_the_pairs_whose_group_changed(
    db: Session,
) -> None:
    world = _seed(
        db,
        tags={"Ann": "A", "Bob": "A", "Cal": "B"},
        answers={"Ann": "4", "Bob": "4", "Cal": "2"},
    )

    def _import(tags: dict[str, str]) -> None:
        relationships_service.save_relationships(
            db,
            session=world.review_session,
            user=world.user,
            rows=[
                RelationshipImportRow(
                    reviewer_id=world.reviewer.id,
                    reviewee_id=world.reviewees[name].id,
                    tag_1=tag,
                )
                for name, tag in tags.items()
            ],
            filename="relationships.csv",
            correlation_id="b34",
        )

    # The same file again replaces every row but moves no pair, so no
    # answer is touched.
    _import({"Ann": "A", "Bob": "A", "Cal": "B"})
    assert _answers(db, world) == {"Ann": "4", "Bob": "4", "Cal": "2"}
    assert _last_context(db, "relationships.imported") == {
        "filename": "relationships.csv"
    }

    _import({"Ann": "A", "Bob": "A", "Cal": "A"})
    assert _answers(db, world) == {"Ann": "4", "Bob": "4", "Cal": "4"}
    assert _last_context(db, "relationships.imported") == {
        "filename": "relationships.csv",
        "defuncted_group_responses": 1,
    }


def test_a_status_edit_with_a_re_point_moves_the_old_pair(db: Session) -> None:
    """One save that inactivates Bob's relationship and re-points it at
    Cal moves Bob out (his tags leave) and leaves Cal where an inactive
    row puts him, with Dan, so both take the empty-tag group's answer."""
    world = _seed(
        db,
        tags={"Ann": "A", "Bob": "A", "Cal": None, "Dan": None},
        answers={"Ann": "4", "Bob": "4", "Cal": "7", "Dan": "7"},
    )

    relationships_service.update_relationship(
        db,
        relationship=_relationship(db, world, "Bob"),
        reviewee_id=world.reviewees["Cal"].id,
        status="inactive",
        user=world.user,
    )

    assert _answers(db, world) == {
        "Ann": "4",
        "Bob": "7",
        "Cal": "7",
        "Dan": "7",
    }
    assert _last_context(db, "relationship.updated") == {
        "defuncted_group_responses": 1
    }


def test_re_pointing_an_untagged_relationship_moves_nothing(
    db: Session,
) -> None:
    """Both pairs read as empty tags before and after, so no group key
    moves and no answer is touched."""
    world = _seed(
        db,
        tags={"Ann": "", "Bob": None},
        answers={"Ann": "7", "Bob": "7"},
    )

    relationships_service.update_relationship(
        db,
        relationship=_relationship(db, world, "Ann"),
        reviewee_id=world.reviewees["Bob"].id,
        user=world.user,
    )

    assert _answers(db, world) == {"Ann": "7", "Bob": "7"}
    assert _last_context(db, "relationship.updated") is None


def test_another_reviewers_answers_are_untouched(db: Session) -> None:
    world = _seed(
        db, tags={"Ann": "A", "Bob": "A"}, answers={"Ann": "4", "Bob": "4"}
    )
    other = Reviewer(
        session_id=world.review_session.id,
        name="Ola",
        email="ola@example.edu",
    )
    db.add(other)
    db.flush()
    instrument_id = world.rows["Ann"].instrument_id
    field_id = db.execute(
        select(Response.response_field_id).limit(1)
    ).scalar_one()
    other_rows = {}
    for name in ("Ann", "Bob"):
        db.add(
            Relationship(
                session_id=world.review_session.id,
                reviewer_id=other.id,
                reviewee_id=world.reviewees[name].id,
                tag_1="A",
            )
        )
        row = Assignment(
            session_id=world.review_session.id,
            reviewer_id=other.id,
            reviewee_id=world.reviewees[name].id,
            instrument_id=instrument_id,
        )
        db.add(row)
        db.flush()
        db.add(
            Response(
                assignment_id=row.id,
                response_field_id=field_id,
                value="5",
                saved_at=_SAVED,
                version=1,
            )
        )
        other_rows[name] = row.id
    db.commit()

    relationships_service.bulk_inactivate(
        db,
        review_session=world.review_session,
        relationship_ids=[_relationship(db, world, "Bob").id],
        user=world.user,
    )

    assert _answers(db, world) == {"Ann": "4", "Bob": None}
    assert {
        name: db.execute(
            select(Response.value).where(Response.assignment_id == row_id)
        ).scalar_one()
        for name, row_id in other_rows.items()
    } == {"Ann": "5", "Bob": "5"}
