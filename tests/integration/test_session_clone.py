"""Coverage for ``app.services.session_clone`` and the lobby clone
route — Segment 18A Part 1 session cloning."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Relationship,
    ResponseTypeDefinition,
    ReviewSession,
    Reviewee,
    Reviewer,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services import session_clone, session_tags, sessions


def _source_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    """A session with the create-time seed config plus a one-pair
    roster and a tag — a realistic clone source."""
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name=code.title(), code=code)
    )
    reviewer = Reviewer(
        session_id=review_session.id, name="R One", email="r1@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="E One",
        email_or_identifier="e1@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            status="active",
        )
    )
    db.commit()
    session_tags.add_tag(
        db, review_session=review_session, user=op, tag="pilot"
    )
    return review_session, op


def test_clone_all_copies_full_graph(db: Session) -> None:
    source, op = _source_session(db, "clone-all")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    assert clone.id != source.id
    assert clone.name == "Copy of Clone-All"
    assert clone.code != source.code
    assert clone.status == "draft"
    assert clone.deadline is None
    assert clone.created_by_user_id == op.id

    # Roster copied, with relationship FKs re-pointed at the clones.
    clone_reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == clone.id)
    ).scalars().all()
    clone_reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == clone.id)
    ).scalars().all()
    clone_rels = db.execute(
        select(Relationship).where(Relationship.session_id == clone.id)
    ).scalars().all()
    assert len(clone_reviewers) == 1
    assert len(clone_reviewees) == 1
    assert len(clone_rels) == 1
    assert clone_rels[0].reviewer_id == clone_reviewers[0].id
    assert clone_rels[0].reviewee_id == clone_reviewees[0].id

    # Config copied; tags copied in every mode.
    assert db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().all()
    assert session_tags.tags_for_sessions(db, [clone.id])[clone.id] == [
        "pilot"
    ]


def test_clone_remaps_response_field_rtd(db: Session) -> None:
    """A cloned instrument's response fields point at the clone's own
    response type definitions, not the source's."""
    source, op = _source_session(db, "clone-rtd")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    clone_rtd_ids = {
        rtd.id
        for rtd in db.execute(
            select(ResponseTypeDefinition).where(
                ResponseTypeDefinition.session_id == clone.id
            )
        ).scalars()
    }
    clone_instrument_ids = [
        i.id
        for i in db.execute(
            select(Instrument).where(Instrument.session_id == clone.id)
        ).scalars()
    ]
    response_fields = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id.in_(clone_instrument_ids)
        )
    ).scalars().all()
    assert response_fields
    for field in response_fields:
        assert field.response_type_id in clone_rtd_ids


def test_clone_config_skips_roster(db: Session) -> None:
    source, op = _source_session(db, "clone-config")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="config"
    )

    assert (
        db.execute(
            select(Reviewer).where(Reviewer.session_id == clone.id)
        ).scalars().all()
        == []
    )
    assert (
        db.execute(
            select(Relationship).where(Relationship.session_id == clone.id)
        ).scalars().all()
        == []
    )
    # Config + tags still copied.
    assert db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().all()
    assert session_tags.tags_for_sessions(db, [clone.id])[clone.id] == [
        "pilot"
    ]


def test_clone_writes_audit_event(db: Session) -> None:
    source, op = _source_session(db, "clone-audit")

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.cloned",
            AuditEvent.session_id == clone.id,
        )
    ).scalar_one()
    assert event.detail["context"]["mode"] == "all"
    assert event.detail["refs"]["source_session_id"] == source.id


def test_clone_derives_a_unique_code(db: Session) -> None:
    source, op = _source_session(db, "clone-dup")

    first = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )
    second = session_clone.clone_session(
        db, source=source, user=op, mode="all"
    )

    assert first.code != second.code


def test_clone_route_redirects_to_the_clone(
    client: TestClient, db: Session
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Routed", "code": "clone-route"},
        follow_redirects=False,
    )
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "clone-route")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session_id}/clone",
        data={"mode": "all"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    # Clone redirects to the Edit page so the operator can rename
    # the clone immediately; ends in ``/edit``.
    assert location.startswith("/operator/sessions/")
    assert location.endswith("/edit")
    clone_id = int(location.rsplit("/", 2)[1])
    assert clone_id != session_id
    clone = db.get(ReviewSession, clone_id)
    assert clone.name == "Copy of Routed"
