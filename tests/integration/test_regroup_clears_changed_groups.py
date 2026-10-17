"""Redrawing an instrument's groups clears the groups it changed
(findings E2).

A group instrument's subject is the group, so a group whose members
changed is a different subject and its reviewer answers it again
(author's ruling 2026-10-17). Changing the boundary tags or the unit
of review used to rewrite ``group_kind`` and leave every copy in
place, so one group could hold several answers and the next Save
overwrote one member's with another's.
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
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import instruments as instruments_service

_SAVED = dt.datetime(2026, 10, 17, tzinfo=dt.timezone.utc)
_TEAM = ("reviewee", "tag_1")
_SITE = ("reviewee", "tag_2")


class _World:
    def __init__(self, user: User, instrument: Instrument, rows: dict[str, Assignment]):
        self.user = user
        self.instrument = instrument
        self.rows = rows


def _seed(
    db: Session,
    *,
    group_kind: str | None,
    tags: dict[str, tuple[str, str]],
    answers: dict[str, str],
) -> _World:
    """One reviewer, a reviewee per key of ``tags`` (its ``tag_1``,
    ``tag_2``), and each ``answers`` entry the copy that row holds."""
    user = User(email="op-e2@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="E2", code="e2", created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id, name="Grp", order=0, group_kind=group_kind
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
    reviewer = Reviewer(session_id=review_session.id, name="Rae", email="rae@example.edu")
    reviewees = {
        name: Reviewee(
            session_id=review_session.id,
            name=name,
            email_or_identifier=f"{name.lower()}@example.edu",
            tag_1=team,
            tag_2=site,
        )
        for name, (team, site) in tags.items()
    }
    db.add_all([field, reviewer, *reviewees.values()])
    db.flush()
    rows = {
        name: Assignment(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        for name, reviewee in reviewees.items()
    }
    db.add_all(rows.values())
    db.flush()
    db.add_all(
        Response(
            assignment_id=rows[name].id,
            response_field_id=field.id,
            value=value,
            saved_at=_SAVED,
            version=1,
        )
        for name, value in answers.items()
    )
    db.commit()
    return _World(user, instrument, rows)


def _answers(db: Session, world: _World) -> dict[str, str | None]:
    db.expire_all()
    out: dict[str, str | None] = {}
    for name, row in world.rows.items():
        values = db.execute(
            select(Response.value).where(Response.assignment_id == row.id)
        ).scalars().all()
        out[name] = values[0] if values else None
    return out


def _cleared(db: Session, world: _World) -> int | None:
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.group_boundary_updated")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    return ((event.detail or {}).get("context") or {}).get("defuncted_group_responses")


def _boundary(db: Session, world: _World, pairs: list[tuple[str, str]]) -> None:
    instruments_service.set_group_boundary(
        db, instrument=world.instrument, boundary_pairs=pairs, actor=world.user
    )


def _unit(db: Session, world: _World, mode: str, pairs: list[tuple[str, str]]) -> None:
    instruments_service.set_unit_of_review(
        db, instrument=world.instrument, mode=mode, boundary_pairs=pairs, actor=world.user
    )
    db.commit()


_TEAMS = {"Ann": ("red", "x"), "Bo": ("red", "x"), "Cy": ("blue", "x"), "Di": ("blue", "x")}


def test_a_split_clears_both_halves(db: Session) -> None:
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([]),
        tags=_TEAMS,
        answers={"Ann": "4", "Bo": "4", "Cy": "4", "Di": "4"},
    )
    _boundary(db, world, [_TEAM])
    assert _answers(db, world) == {"Ann": None, "Bo": None, "Cy": None, "Di": None}
    assert _cleared(db, world) == 4


def test_a_merge_clears_the_merged_group(db: Session) -> None:
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=_TEAMS,
        answers={"Ann": "2", "Bo": "2"},
    )
    _boundary(db, world, [])
    assert _answers(db, world) == {"Ann": None, "Bo": None, "Cy": None, "Di": None}
    assert _cleared(db, world) == 2


def test_a_boundary_that_redraws_no_group_clears_nothing(db: Session) -> None:
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=_TEAMS,
        answers={"Ann": "2", "Bo": "2", "Cy": "5", "Di": "5"},
    )
    _boundary(db, world, [_TEAM, _SITE])
    assert _answers(db, world) == {"Ann": "2", "Bo": "2", "Cy": "5", "Di": "5"}
    assert _cleared(db, world) is None


def test_only_the_changed_group_is_cleared(db: Session) -> None:
    tags = {**_TEAMS, "Cy": ("blue", "y"), "Di": ("blue", "z")}
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=tags,
        answers={"Ann": "2", "Bo": "2", "Cy": "5", "Di": "5"},
    )
    _boundary(db, world, [_TEAM, _SITE])
    assert _answers(db, world) == {"Ann": "2", "Bo": "2", "Cy": None, "Di": None}
    assert _cleared(db, world) == 2


def test_individual_to_grouped_keeps_only_a_one_member_group(db: Session) -> None:
    tags = {"Ann": ("red", "x"), "Bo": ("red", "x"), "Cy": ("blue", "x")}
    world = _seed(
        db, group_kind=None, tags=tags, answers={"Ann": "1", "Bo": "3", "Cy": "5"}
    )
    _unit(db, world, "grouped", [_TEAM])
    assert _answers(db, world) == {"Ann": None, "Bo": None, "Cy": "5"}
    assert _cleared(db, world) == 2


def test_grouped_to_individual_keeps_only_a_one_member_group(db: Session) -> None:
    tags = {"Ann": ("red", "x"), "Bo": ("red", "x"), "Cy": ("blue", "x")}
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=tags,
        answers={"Ann": "4", "Bo": "4", "Cy": "5"},
    )
    _unit(db, world, "individual", [])
    assert _answers(db, world) == {"Ann": None, "Bo": None, "Cy": "5"}
    assert _cleared(db, world) == 2


def test_an_unanswered_instrument_regroups_without_a_count(db: Session) -> None:
    world = _seed(
        db, group_kind=instruments_service.encode_group_kind([_TEAM]), tags=_TEAMS, answers={}
    )
    _boundary(db, world, [])
    assert _cleared(db, world) is None


def test_an_excluded_member_is_cleared_with_its_group(db: Session) -> None:
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([]),
        tags=_TEAMS,
        answers={"Ann": "4", "Bo": "4", "Cy": "4", "Di": "4"},
    )
    world.rows["Bo"].include = False
    db.commit()
    _boundary(db, world, [_TEAM])
    assert _answers(db, world)["Bo"] is None
    assert _cleared(db, world) == 4


def test_another_reviewers_unchanged_group_keeps_its_answer(db: Session) -> None:
    """Groups are per reviewer: a split in one reviewer's universe is
    not a change to another's group that keeps its rows."""
    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([]),
        tags={"Ann": ("red", "x"), "Bo": ("blue", "x")},
        answers={"Ann": "4", "Bo": "4"},
    )
    review_session = world.instrument.session
    other = Reviewer(session_id=review_session.id, name="Sam", email="sam@example.edu")
    db.add(other)
    db.flush()
    ann = world.rows["Ann"]
    sams = Assignment(
        session_id=review_session.id,
        reviewer_id=other.id,
        reviewee_id=ann.reviewee_id,
        instrument_id=world.instrument.id,
    )
    db.add(sams)
    db.flush()
    field_id = db.execute(
        select(InstrumentResponseField.id).where(
            InstrumentResponseField.instrument_id == world.instrument.id
        )
    ).scalar_one()
    db.add(
        Response(
            assignment_id=sams.id,
            response_field_id=field_id,
            value="1",
            saved_at=_SAVED,
            version=1,
        )
    )
    db.commit()
    world.rows["Sam/Ann"] = sams

    _boundary(db, world, [_TEAM])

    assert _answers(db, world) == {"Ann": None, "Bo": None, "Sam/Ann": "1"}
    assert _cleared(db, world) == 2


def test_a_member_removed_clears_the_group_it_leaves(db: Session) -> None:
    """Generate dropping a row the rules no longer produce goes through
    the same rule: the group it left is a different subject."""
    from app.services import responses as responses_service

    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=_TEAMS,
        answers={"Ann": "2", "Bo": "2", "Cy": "5", "Di": "5"},
    )
    session_id = world.instrument.session_id
    before = responses_service.snapshot_group_partitions(
        db, session_id=session_id, instrument_ids={world.instrument.id}
    )
    bo = world.rows.pop("Bo")
    db.query(Response).filter(Response.assignment_id == bo.id).delete()
    db.delete(bo)
    db.flush()

    cleared = responses_service.clear_changed_groups(
        db, session_id=session_id, before=before
    )

    assert cleared == 1
    assert _answers(db, world) == {"Ann": None, "Cy": "5", "Di": "5"}


def test_deleting_a_reviewee_clears_the_group_it_leaves(db: Session) -> None:
    from app.services import reviewees as reviewees_service

    world = _seed(
        db,
        group_kind=instruments_service.encode_group_kind([_TEAM]),
        tags=_TEAMS,
        answers={"Ann": "2", "Bo": "2", "Cy": "5", "Di": "5"},
    )
    bo = world.rows.pop("Bo")

    reviewees_service.delete_selected(
        db,
        review_session=world.instrument.session,
        reviewee_ids=[bo.reviewee_id],
        user=world.user,
    )

    assert _answers(db, world) == {"Ann": None, "Cy": "5", "Di": "5"}
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "reviewee.bulk_deleted")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["context"] == {"defuncted_group_responses": 1}
