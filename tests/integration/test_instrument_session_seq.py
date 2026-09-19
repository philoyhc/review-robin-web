"""``Instrument.session_seq`` — the per-session instrument number.

19Q Item 6 rung 1. The operator-facing number was ``Instrument.id``, a
workspace-wide autoincrement, so a session holding two instruments
could label them ``Instrument_1`` and ``Instrument_7`` (author's
screenshot, 2026-09-19). This column is per-session, assigned once at
creation, and never updated.

Nothing here reads a label or a tint yet — those are rungs 2 and 3.
What this pins is the number's three properties: per-session, creation
order, and immovable.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.schemas.sessions import SessionCreate
from app.services import session_clone, sessions
from app.services.instruments import _instrument_crud as crud


def _session(db: Session, code: str) -> tuple[ReviewSession, User]:
    op = db.execute(select(User).where(User.email == "seq-op@example.edu")).scalar()
    if op is None:
        op = User(email="seq-op@example.edu", display_name="Op")
        db.add(op)
        db.flush()
    review_session = sessions.create_session(
        db, user=op, payload=SessionCreate(name=code.title(), code=code)
    )
    return review_session, op


def _seqs(db: Session, session_id: int) -> list[int]:
    return list(
        db.execute(
            select(Instrument.session_seq)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.id)
        ).scalars()
    )


def test_each_session_numbers_from_one(db: Session) -> None:
    """The defect, directly. Two sessions' instruments interleave in
    ``id`` because the PK is workspace-wide; their ``session_seq`` does
    not, because it is not."""
    first, op = _session(db, "seq-a")
    second, _ = _session(db, "seq-b")

    crud.create_instrument(db, review_session=first, actor=op)
    crud.create_instrument(db, review_session=second, actor=op)
    crud.create_instrument(db, review_session=first, actor=op)
    db.flush()

    assert _seqs(db, first.id) == [1, 2, 3]
    assert _seqs(db, second.id) == [1, 2]

    # The premise: without it the assertions above would pass on a
    # column that had simply copied a contiguous id run.
    ids = list(
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == first.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    assert ids != [1, 2, 3], "ids happened to be contiguous — test is vacuous"


def test_delete_neither_renumbers_nor_frees_the_number(db: Session) -> None:
    """Gaps are the contract (author, 2026-09-19): a handle that closes
    up after a delete is a handle that moved."""
    review_session, op = _session(db, "seq-del")
    for _ in range(3):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2, 3, 4]  # 1 is the seeded default

    second = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .where(Instrument.session_seq == 2)
    ).scalar_one()
    crud.delete_instrument(db, instrument=second, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 3, 4]

    crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    assert _seqs(db, review_session.id) == [1, 3, 4, 5], "2 was reused"


def test_reorder_does_not_touch_the_number(db: Session) -> None:
    """The whole reason it is not ``Instrument.order``: drag-and-drop
    ships, and the number must not move under it."""
    review_session, op = _session(db, "seq-reorder")
    for _ in range(2):
        crud.create_instrument(db, review_session=review_session, actor=op)
    db.flush()
    rows = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    before = [r.session_seq for r in rows]

    from app.services import instruments as instruments_service

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[r.id for r in reversed(rows)],
        actor=op,
    )
    db.flush()

    for row in rows:
        db.refresh(row)
    assert [r.session_seq for r in rows] == before
    # The control: the reorder really did happen.
    assert [r.order for r in rows] != sorted(r.order for r in rows)


def test_replicate_takes_a_fresh_number(db: Session) -> None:
    review_session, op = _session(db, "seq-rep")
    source = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()

    crud.replicate_instrument(
        db, review_session=review_session, source=source, actor=op
    )
    db.flush()
    assert _seqs(db, review_session.id) == [1, 2]


def test_clone_preserves_the_source_sequence(db: Session) -> None:
    """Author's ruling, 2026-09-19: a source reading 1, 3, 2 down the
    page clones to 1, 3, 2, not 1, 2, 3.

    ``session_clone`` copies every mapped column, so this needs no code
    — which is exactly why it needs a test.
    """
    source, op = _session(db, "seq-clone")
    for _ in range(2):
        crud.create_instrument(db, review_session=source, actor=op)
    db.flush()
    middle = db.execute(
        select(Instrument)
        .where(Instrument.session_id == source.id)
        .where(Instrument.session_seq == 2)
    ).scalar_one()
    crud.delete_instrument(db, instrument=middle, actor=op)
    db.commit()
    assert _seqs(db, source.id) == [1, 3]

    clone = session_clone.clone_session(db, source=source, user=op, mode="all")
    db.flush()
    assert _seqs(db, clone.id) == [1, 3], "clone renumbered"


def test_the_migration_backfill_ranks_by_creation_order_per_session() -> None:
    """The backfill statement itself, run against real rows.

    The suite builds its schema from ORM metadata, so the migration
    never executes here — this is the only place its SQL is exercised.
    """
    import importlib.util
    import pathlib

    spec = importlib.util.spec_from_file_location(
        "_seq_migration",
        pathlib.Path(__file__).resolve().parents[2]
        / "alembic/versions/b7d4f2a9c153_instruments_session_seq.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _BACKFILL = module._BACKFILL

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE instruments ("
                "  id INTEGER PRIMARY KEY,"
                "  session_id INTEGER NOT NULL,"
                "  session_seq INTEGER"
                ")"
            )
        )
        # Interleaved ids across two sessions, with gaps — what a
        # workspace-wide autoincrement actually produces.
        conn.execute(
            sa.text(
                "INSERT INTO instruments (id, session_id) VALUES "
                "(3, 1), (7, 1), (8, 2), (12, 1), (40, 2)"
            )
        )
        conn.execute(_BACKFILL)
        rows = conn.execute(
            sa.text(
                "SELECT id, session_id, session_seq FROM instruments ORDER BY id"
            )
        ).all()

    assert rows == [(3, 1, 1), (7, 1, 2), (8, 2, 1), (12, 1, 3), (40, 2, 2)]
