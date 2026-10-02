"""A copy's derived name fits its 255-character column.

Duplicate names a session ``"Copy of <name>"`` and Replicate names an
instrument ``"<name> (copy)"``. Neither trimmed, so a source name near
the limit produced a name Postgres refuses (``String(255)``) — a 500
there, though SQLite stores it. Duplicate cuts the tail now; Replicate
trims the source name so the " (copy)" suffix is kept."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, User
from app.schemas.sessions import SessionCreate
from app.services import instruments, session_clone, sessions

LONG_NAME = "n" * 255


def _operator(db: Session) -> User:
    op = User(email="op-names@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    return op


def test_duplicate_of_a_255_char_name_fits(db: Session) -> None:
    op = _operator(db)
    source = sessions.create_session(
        db, user=op, payload=SessionCreate(name=LONG_NAME, code="long-name")
    )

    clone = session_clone.clone_session(db, source=source, user=op, mode="config")

    assert clone.name == ("Copy of " + LONG_NAME)[:255]
    assert len(clone.name) == 255


def test_replicate_of_a_255_char_instrument_name_fits(db: Session) -> None:
    op = _operator(db)
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name="Inst", code="long-inst")
    )
    source = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    source.name = LONG_NAME
    db.commit()

    replica = instruments.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )

    assert replica.name == "n" * 248 + " (copy)"
    assert len(replica.name) == 255
