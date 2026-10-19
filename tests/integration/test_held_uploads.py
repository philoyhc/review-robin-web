"""Segment 19W rung 2 — the held-uploads service (hold / take / discard
/ sweep).

Scoped to an operator and a session, one row per slot under a shared
token, expiring an hour after it was held.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import HeldUpload, ReviewSession, User
from app.services import held_uploads
from app.services.held_uploads import HeldFile


def _user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User, code: str) -> ReviewSession:
    review_session = ReviewSession(name=code, code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    return review_session


def _count(db: Session) -> int:
    return db.execute(select(func.count()).select_from(HeldUpload)).scalar_one()


def _age(db: Session, token: str, *, hours: float) -> None:
    for row in db.execute(
        select(HeldUpload).where(HeldUpload.token == token)
    ).scalars():
        row.created_at = datetime.now(timezone.utc) - timedelta(hours=hours)
    db.flush()


_ROSTER = HeldFile(filename="reviewers.csv", content=b"ReviewerName\nAda\n")
_SETTINGS = HeldFile(filename="settings.csv", content=b"field,value\n")


def test_hold_and_take_round_trip_by_slot(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-a")
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={"reviewers": _ROSTER, "settings": _SETTINGS},
    )
    assert token is not None
    assert held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ) == {"reviewers": _ROSTER, "settings": _SETTINGS}
    # Taking does not end the hold.
    assert _count(db) == 2


def test_another_operator_or_session_reads_nothing(db: Session) -> None:
    owner = _user(db, "owner@e.edu")
    other = _user(db, "other@e.edu")
    mine = _session(db, owner, "held-b")
    theirs = _session(db, owner, "held-c")
    token = held_uploads.hold(
        db, user=owner, session_id=mine.id, files={"reviewers": _ROSTER}
    )
    assert token is not None
    assert held_uploads.take(db, token=token, user=other, session_id=mine.id) == {}
    assert held_uploads.take(db, token=token, user=owner, session_id=theirs.id) == {}
    assert held_uploads.discard(db, token=token, user=other, session_id=mine.id) == 0
    assert _count(db) == 1


def test_an_expired_hold_reads_empty_and_is_deleted(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-d")
    token = held_uploads.hold(
        db, user=user, session_id=review_session.id, files={"reviewers": _ROSTER}
    )
    assert token is not None
    _age(db, token, hours=2)
    assert held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ) == {}
    assert _count(db) == 0


def test_a_new_hold_sweeps_expired_ones(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-e")
    old = held_uploads.hold(
        db, user=user, session_id=review_session.id, files={"reviewers": _ROSTER}
    )
    assert old is not None
    _age(db, old, hours=2)
    held_uploads.hold(
        db, user=user, session_id=review_session.id, files={"settings": _SETTINGS}
    )
    assert _count(db) == 1


def test_joining_a_hold_replaces_only_its_slot(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-f")
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={"reviewers": _ROSTER, "settings": _SETTINGS},
    )
    newer = HeldFile(filename="reviewers2.csv", content=b"ReviewerName\nBo\n")
    again = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={"reviewers": newer},
        token=token,
    )
    assert again == token
    assert held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ) == {"reviewers": newer, "settings": _SETTINGS}


def test_someone_elses_token_starts_a_new_hold(db: Session) -> None:
    owner = _user(db, "owner@e.edu")
    other = _user(db, "other@e.edu")
    review_session = _session(db, owner, "held-g")
    token = held_uploads.hold(
        db, user=owner, session_id=review_session.id, files={"reviewers": _ROSTER}
    )
    theirs = held_uploads.hold(
        db,
        user=other,
        session_id=review_session.id,
        files={"settings": _SETTINGS},
        token=token,
    )
    assert theirs is not None and theirs != token
    assert held_uploads.take(
        db, token=token, user=owner, session_id=review_session.id
    ) == {"reviewers": _ROSTER}


def test_empty_and_oversized_files_are_not_held(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-h")
    big = HeldFile(
        filename="big.csv", content=b"x" * (held_uploads.MAX_HELD_BYTES + 1)
    )
    empty = HeldFile(filename="empty.csv", content=b"")
    assert held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={"settings": big, "reviewers": empty},
    ) is None
    assert _count(db) == 0


def test_discard_ends_the_hold(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-i")
    token = held_uploads.hold(
        db,
        user=user,
        session_id=review_session.id,
        files={"reviewers": _ROSTER, "settings": _SETTINGS},
    )
    assert token is not None
    assert held_uploads.discard(
        db, token=token, user=user, session_id=review_session.id
    ) == 2
    assert held_uploads.take(
        db, token=token, user=user, session_id=review_session.id
    ) == {}


def test_deleting_the_session_drops_its_holds(db: Session) -> None:
    user = _user(db, "op@e.edu")
    review_session = _session(db, user, "held-j")
    held_uploads.hold(
        db, user=user, session_id=review_session.id, files={"reviewers": _ROSTER}
    )
    db.delete(review_session)
    db.flush()
    assert _count(db) == 0
