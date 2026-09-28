"""19T Item 13 rung 2 — ``branch_mode`` is stored and copied: clone and
Replicate instrument carry a parent's mode. (The write paths, the card's
save and the settings CSV, are rung 3b's:
``test_conditional_required_writes.py``.)"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField, User
from app.services import instruments as instruments_service
from app.services import session_clone

from .test_response_field_branching_roundtrip import (
    _branched_instrument,
    _fields,
    _session,
)
from .test_response_field_branching_save import _branched


def test_replicate_instrument_copies_the_mode(db: Session) -> None:
    review_session, op = _session(db, "13-replicate")
    source = _branched_instrument(db, review_session)
    _fields(db, source.id)["colour"].branch_mode = "require"
    db.flush()
    copy = instruments_service.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    fields = _fields(db, copy.id)
    assert fields["colour"].branch_mode == "require"
    assert fields["why"].branch_mode is None and fields["notes"].branch_mode is None


def test_clone_copies_the_mode(client: TestClient, db: Session) -> None:
    review_session, _, rating, _ = _branched(client, db, "13-clone")
    rating.branch_mode = "require"
    db.commit()
    user = db.execute(select(User)).scalars().first()
    clone = session_clone.clone_session(db, source=review_session, user=user, mode="all")
    db.flush()
    cloned = db.execute(
        select(InstrumentResponseField)
        .join(Instrument)
        .where(Instrument.session_id == clone.id, InstrumentResponseField.label == "Rating")
    ).scalars().all()
    assert [f.branch_mode for f in cloned if f.branch_op] == ["require"]
