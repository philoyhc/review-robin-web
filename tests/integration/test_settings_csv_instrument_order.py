"""Settings CSV ``instruments[n].order`` round-trips byte-stable
(findings D2, 2026-10-05).

The export wrote the stored ``Instrument.order`` (0-based for anything
the app created) while the import set ``order = n`` from the block's
``[n]`` number, so an export → import → export moved every order cell
up by one. Both sides now use the 0-based position: the cell reads the
block's position and the import stores each block's rank among the
file's numbers, and ``[n]`` stays the authority for ordering
(`spec/csv_contracts.md`).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.services.session_config_io import (
    apply_session_config,
    serialize_session_config,
)


def _session_with_instruments(
    db: Session, code: str, orders: list[int]
) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    for i, order in enumerate(orders):
        db.add(
            Instrument(
                session_id=review_session.id, name=f"I{i}", order=order
            )
        )
    db.flush()
    return review_session


def _order_cells(db: Session, review_session: ReviewSession) -> dict[str, str]:
    return {
        row.field: row.value
        for row in serialize_session_config(db, review_session)
        if row.field.endswith("].order") and row.field.count("[") == 1
    }


def test_order_cells_are_the_zero_based_position(db: Session) -> None:
    """Stored orders that are not 0..n-1 (a session imported before
    this fix holds them 1-based) export as the position, so the cell
    says what the import will do with it."""
    review_session = _session_with_instruments(db, "ord-gap", [1, 3])
    assert _order_cells(db, review_session) == {
        "instruments[1].order": "0",
        "instruments[2].order": "1",
    }


def test_export_import_export_is_byte_stable(db: Session) -> None:
    review_session = _session_with_instruments(db, "ord-rt", [0, 1])
    first = serialize_session_config(db, review_session)

    result = apply_session_config(db, review_session, first)
    assert result.errors == []

    second = serialize_session_config(db, review_session)
    assert [(r.field, r.value) for r in second] == [
        (r.field, r.value) for r in first
    ]
    stored = db.execute(
        select(Instrument.order)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order)
    ).scalars().all()
    assert stored == [0, 1]


def test_hand_numbered_blocks_store_their_rank(db: Session) -> None:
    """A file numbered from ``[0]``, or with a skipped number, stores
    0..n-1 by rank rather than ``n - 1`` (which gave -1, or a gap)."""
    review_session = _session_with_instruments(db, "ord-hand", [0, 1])
    rows = serialize_session_config(db, review_session)
    renumbered = [
        type(r)(
            r.field.replace("instruments[2]", "instruments[5]").replace(
                "instruments[1]", "instruments[0]"
            ),
            r.value,
            r.data_type,
        )
        for r in rows
    ]
    result = apply_session_config(db, review_session, renumbered)
    assert result.errors == []
    stored = db.execute(
        select(Instrument.name, Instrument.order)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.order)
    ).all()
    assert [tuple(r) for r in stored] == [("I0", 0), ("I1", 1)]

