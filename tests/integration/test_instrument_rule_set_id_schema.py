"""Schema-level coverage for Segment 13D PR 4 — ``instruments.rule_set_id``.

Pins the per-instrument RuleSet selection pointer for Segment 15B
Slice 2 to consume:

- Round-trip insert + read with both NULL (initial state) and
  non-NULL (selected state).
- ``ON DELETE SET NULL`` on the referenced ``session_rule_sets``
  row clears every instrument's pointer (the instrument survives;
  rule_set_id falls back to NULL).
- Deleting an instrument disposes of its pointer cleanly without
  touching the ``session_rule_sets`` copy.

The column sits inert until 15B Slice 2 starts persisting the
selection.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    ReviewSession,
    SessionRuleSet,
    User,
)


def _make_session(db: Session, code: str) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _make_instrument(db: Session, session: ReviewSession, name: str) -> Instrument:
    instrument = Instrument(session_id=session.id, name=name, order=0)
    db.add(instrument)
    db.flush()
    return instrument


def _make_session_rule_set(
    db: Session, session: ReviewSession, name: str
) -> SessionRuleSet:
    row = SessionRuleSet(
        session_id=session.id,
        name=name,
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
        library_origin_id=None,
    )
    db.add(row)
    db.flush()
    return row


def test_initial_state_is_null(db: Session) -> None:
    """Every existing instrument carries ``rule_set_id = NULL`` after
    the migration — no rule selected."""

    review_session = _make_session(db, "irs-init")
    instrument = _make_instrument(db, review_session, "Default")

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.rule_set_id is None


def test_round_trip_with_session_rule_set(db: Session) -> None:
    """Setting ``rule_set_id`` to a session_rule_sets row id round-trips
    cleanly — the persistent per-instrument selection 15B Slice 2 will
    write."""

    review_session = _make_session(db, "irs-rt")
    instrument = _make_instrument(db, review_session, "Default")
    srs = _make_session_rule_set(db, review_session, "My session RuleSet")

    instrument.rule_set_id = srs.id
    db.flush()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument.id)
    ).scalar_one()
    assert fetched.rule_set_id == srs.id


def test_set_null_on_session_rule_set_delete(db: Session) -> None:
    """When the referenced ``session_rule_sets`` row is deleted, every
    instrument's ``rule_set_id`` clears to NULL via SQL ``SET NULL``.
    The instrument survives; the operator's next assignment generation
    will require choosing a new rule."""

    review_session = _make_session(db, "irs-setnull")
    instrument = _make_instrument(db, review_session, "Default")
    srs = _make_session_rule_set(db, review_session, "Soon-to-be-deleted")
    instrument.rule_set_id = srs.id
    db.flush()
    instrument_id = instrument.id

    db.delete(srs)
    db.flush()
    db.expire_all()

    fetched = db.execute(
        select(Instrument).where(Instrument.id == instrument_id)
    ).scalar_one()
    assert fetched.rule_set_id is None
    # Instrument itself is intact.
    assert fetched.name == "Default"


def test_instrument_delete_does_not_touch_session_rule_set(
    db: Session,
) -> None:
    """Deleting the instrument disposes of the pointer column with
    the row; the ``session_rule_sets`` copy survives unchanged."""

    review_session = _make_session(db, "irs-instr-del")
    instrument = _make_instrument(db, review_session, "Default")
    srs = _make_session_rule_set(db, review_session, "Survivor")
    instrument.rule_set_id = srs.id
    db.flush()
    srs_id = srs.id

    db.delete(instrument)
    db.flush()

    fetched = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.id == srs_id)
    ).scalar_one()
    assert fetched.name == "Survivor"


def test_two_instruments_can_share_the_same_session_rule_set(
    db: Session,
) -> None:
    """Multiple instruments in a session can apply the same
    session_rule_sets row — the FK is many-to-one without any
    uniqueness constraint."""

    review_session = _make_session(db, "irs-shared")
    inst_a = _make_instrument(db, review_session, "A")
    inst_b = _make_instrument(db, review_session, "B")
    srs = _make_session_rule_set(db, review_session, "Shared")
    inst_a.rule_set_id = srs.id
    inst_b.rule_set_id = srs.id
    db.flush()

    rows = db.execute(
        select(Instrument)
        .where(Instrument.session_id == review_session.id)
        .order_by(Instrument.name)
    ).scalars().all()
    assert [r.rule_set_id for r in rows] == [srs.id, srs.id]
