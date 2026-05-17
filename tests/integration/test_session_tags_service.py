"""Service-level coverage for ``app.services.session_tags`` — the
Segment 18A Part 2 tagging read / write layer."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services import session_tags


def _make_session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session, op


def test_normalize_tag_lowercases_and_trims() -> None:
    assert session_tags.normalize_tag("  Cohort-A  ") == "cohort-a"


def test_normalize_tag_rejects_empty() -> None:
    with pytest.raises(ValueError):
        session_tags.normalize_tag("   ")


def test_normalize_tag_rejects_overlong() -> None:
    with pytest.raises(ValueError):
        session_tags.normalize_tag("x" * 65)


def test_add_tag_persists_normalized_and_audits(db: Session) -> None:
    review_session, op = _make_session(db, "tag-add")

    added = session_tags.add_tag(
        db, review_session=review_session, user=op, tag="  Pilot "
    )

    assert added is True
    assert session_tags.tags_for_sessions(db, [review_session.id]) == {
        review_session.id: ["pilot"]
    }
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.tag_added",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["context"]["tag"] == "pilot"


def test_add_tag_is_idempotent(db: Session) -> None:
    review_session, op = _make_session(db, "tag-idem")
    session_tags.add_tag(db, review_session=review_session, user=op, tag="peer")

    # A second add of the same (normalized) tag is a no-op.
    added_again = session_tags.add_tag(
        db, review_session=review_session, user=op, tag="PEER"
    )

    assert added_again is False
    assert session_tags.tags_for_sessions(db, [review_session.id]) == {
        review_session.id: ["peer"]
    }


def test_remove_tag_deletes_and_audits(db: Session) -> None:
    review_session, op = _make_session(db, "tag-rm")
    session_tags.add_tag(db, review_session=review_session, user=op, tag="drop")

    removed = session_tags.remove_tag(
        db, review_session=review_session, user=op, tag="DROP"
    )

    assert removed is True
    assert session_tags.tags_for_sessions(db, [review_session.id]) == {
        review_session.id: []
    }
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.tag_removed",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    assert event.detail["context"]["tag"] == "drop"


def test_remove_tag_absent_is_noop(db: Session) -> None:
    review_session, op = _make_session(db, "tag-rm-absent")
    removed = session_tags.remove_tag(
        db, review_session=review_session, user=op, tag="never-there"
    )
    assert removed is False


def test_tags_for_sessions_groups_and_sorts(db: Session) -> None:
    session_a, op_a = _make_session(db, "tag-grp-a")
    session_b, op_b = _make_session(db, "tag-grp-b")
    session_tags.add_tag(db, review_session=session_a, user=op_a, tag="zeta")
    session_tags.add_tag(db, review_session=session_a, user=op_a, tag="alpha")
    session_tags.add_tag(db, review_session=session_b, user=op_b, tag="beta")

    grouped = session_tags.tags_for_sessions(
        db, [session_a.id, session_b.id]
    )

    assert grouped[session_a.id] == ["alpha", "zeta"]
    assert grouped[session_b.id] == ["beta"]


def test_vocabulary_is_distinct_and_sorted(db: Session) -> None:
    session_a, op_a = _make_session(db, "tag-vocab-a")
    session_b, op_b = _make_session(db, "tag-vocab-b")
    session_tags.add_tag(db, review_session=session_a, user=op_a, tag="shared")
    session_tags.add_tag(db, review_session=session_b, user=op_b, tag="shared")
    session_tags.add_tag(db, review_session=session_b, user=op_b, tag="extra")

    vocab = session_tags.vocabulary(db, [session_a.id, session_b.id])

    assert vocab == ["extra", "shared"]
