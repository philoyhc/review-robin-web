"""Coverage for ``app.services.session_clone`` and the lobby clone
route — Segment 18A Part 1 session cloning."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    DataShape,
    Instrument,
    InstrumentResponseField,
    Relationship,
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


def test_clone_copies_data_shapes_retention_and_toggles(db: Session) -> None:
    """18P PR D1 — clone carries the feature toggles, retention config,
    and saved Data shapes (scope chips re-pointed at the clone), while
    the schedule resets by design."""
    source, op = _source_session(db, "clone-d1")
    source.relationships_enabled = True
    source.observers_enabled = True
    source.retention_exception = True
    source.retention_overrides = {"audit_log_days": 365}
    # A scheduling anchor that must NOT survive the clone.
    source.scheduled_activate_at = dt.datetime(
        2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc
    )
    db.flush()

    src_inst = db.execute(
        select(Instrument).where(Instrument.session_id == source.id)
    ).scalars().first()
    src_rf = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == src_inst.id
        )
    ).scalars().first()
    db.add(
        DataShape(
            session_id=source.id,
            name="My shape",
            axis="reviewer",
            instrument_id=src_inst.id,
            response_field_id=src_rf.id,
            column_chip_slots="[]",
            created_by_user_id=op.id,
        )
    )
    db.commit()

    clone = session_clone.clone_session(
        db, source=source, user=op, mode="config"
    )
    db.refresh(clone)

    assert clone.relationships_enabled is True
    assert clone.observers_enabled is True
    assert clone.retention_exception is True
    assert clone.retention_overrides == {"audit_log_days": 365}
    # Schedule resets by design.
    assert clone.scheduled_activate_at is None

    clone_shapes = db.execute(
        select(DataShape).where(DataShape.session_id == clone.id)
    ).scalars().all()
    assert len(clone_shapes) == 1
    shape = clone_shapes[0]
    assert shape.name == "My shape"

    clone_inst = db.execute(
        select(Instrument).where(Instrument.session_id == clone.id)
    ).scalars().first()
    clone_rf = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == clone_inst.id
        )
    ).scalars().first()
    # Scope chips re-pointed at the clone's rows, not the source's.
    assert shape.instrument_id == clone_inst.id
    assert shape.response_field_id == clone_rf.id
    assert shape.instrument_id != src_inst.id


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
    # 18R Item 4 Slice 5 — clone redirects to Session Home with the Session
    # details card open in edit mode so the operator can rename the clone
    # immediately (the Edit page is retired).
    assert location.startswith("/operator/sessions/")
    assert location.endswith("?editing=1#session-config")
    clone_id = int(
        location.split("/operator/sessions/")[1].split("?")[0]
    )
    assert clone_id != session_id
    clone = db.get(ReviewSession, clone_id)
    assert clone.name == "Copy of Routed"
