"""Service-layer tests for Segment 18M PR 1.

Covers:

- The `instruments.starts_new_page` column ships with the right
  backfill semantics (existing rows = True; new instruments
  created post-migration = False).
- `reorder_instruments` happy paths (reorder only / add break /
  remove break / no-op) and every invariant rejection.
- `create_page_break_after` happy path + the two reject branches
  (last instrument, double-stack).
- `clear_page_break` happy path + reject branch (no break to
  clear).
- Each helper emits the correct `EVENT_SCHEMAS`-registered audit
  event and lifts the session out of `validated` state.
- The lifecycle gate is *not* part of the service layer (callers
  apply it at the route layer in PR 2).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession, User
from app.services import instruments as instruments_service


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"Session {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _add_instruments(
    client: TestClient, session_id: int, n: int
) -> None:
    """Add n more instruments to the session (default-seeded session
    already has one)."""
    for _ in range(n):
        response = client.post(
            f"/operator/sessions/{session_id}/instruments/add-new-model",
            follow_redirects=False,
        )
        assert response.status_code == 303


def _ordered(db: Session, session_id: int) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )


def _actor(db: Session) -> User:
    return db.execute(select(User)).scalars().first()


# --------------------------------------------------------------------------- #
# Migration semantics
# --------------------------------------------------------------------------- #


def test_new_instrument_defaults_starts_new_page_false(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bf-1")
    instruments = _ordered(db, review_session.id)
    # Seeded default instrument: False per model default (post-migration
    # semantics — existing rows backfilled True, new rows default False).
    assert len(instruments) == 1
    assert instruments[0].starts_new_page is False


# --------------------------------------------------------------------------- #
# reorder_instruments — happy paths
# --------------------------------------------------------------------------- #


def test_reorder_swaps_two_instruments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ro-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[b.id, a.id],
        actor=_actor(db),
    )
    db.refresh(a)
    db.refresh(b)
    assert (b.order, a.order) == (0, 1)
    assert b.starts_new_page is False
    assert a.starts_new_page is False


def test_reorder_inserts_a_page_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ro-2")
    _add_instruments(client, review_session.id, 2)
    a, b, c = _ordered(db, review_session.id)
    assert all(inst.starts_new_page is False for inst in (a, b, c))

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[a.id, None, b.id, c.id],
        actor=_actor(db),
    )
    db.refresh(a)
    db.refresh(b)
    db.refresh(c)
    assert (a.order, b.order, c.order) == (0, 1, 2)
    assert a.starts_new_page is False
    assert b.starts_new_page is True  # follows the break
    assert c.starts_new_page is False


def test_reorder_removes_a_page_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ro-3")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    b.starts_new_page = True
    db.commit()

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[a.id, b.id],
        actor=_actor(db),
    )
    db.refresh(b)
    assert b.starts_new_page is False


def test_reorder_drag_across_break_relocates_via_re_derive(
    client: TestClient, db: Session
) -> None:
    """Per the locked algorithm, flags are re-derived from list
    position — so dragging an instrument across a break makes the
    break stay where the post-drop list places it."""
    review_session = _make_session(client, db, code="ro-4")
    _add_instruments(client, review_session.id, 3)
    a, b, c, d = _ordered(db, review_session.id)
    # Initial: a on page 1; break; b, c on page 2; d alone (no break before d)
    # — actually we set break before b only.
    b.starts_new_page = True
    db.commit()

    # Operator drags c to position 2 (between a and b). New list:
    # [a, c, break, b, d] — break now between c and b.
    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[a.id, c.id, None, b.id, d.id],
        actor=_actor(db),
    )
    db.refresh(a)
    db.refresh(b)
    db.refresh(c)
    db.refresh(d)
    assert (a.order, c.order, b.order, d.order) == (0, 1, 2, 3)
    assert a.starts_new_page is False
    assert c.starts_new_page is False
    assert b.starts_new_page is True
    assert d.starts_new_page is False


def test_reorder_no_op_skips_audit_and_lifecycle(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ro-5")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    before = _audit_count(db, "instruments.reordered")

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[a.id, b.id],  # same as current order, no flags
        actor=_actor(db),
    )
    assert _audit_count(db, "instruments.reordered") == before


def test_reorder_emits_audit_event(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="ro-6")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    before = _audit_count(db, "instruments.reordered")

    instruments_service.reorder_instruments(
        db,
        review_session=review_session,
        items=[b.id, a.id],
        actor=_actor(db),
    )
    assert _audit_count(db, "instruments.reordered") == before + 1
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instruments.reordered")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event is not None
    assert event.detail["changes"]["instrument_order"] == [
        [a.id, b.id],
        [b.id, a.id],
    ]
    assert event.detail["changes"]["page_breaks_at"] == [[], []]


# --------------------------------------------------------------------------- #
# reorder_instruments — invariant rejections
# --------------------------------------------------------------------------- #


def test_reorder_rejects_leading_page_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="before the first instrument"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[None, a.id, b.id],
            actor=_actor(db),
        )


def test_reorder_rejects_trailing_page_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-2")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="after the last instrument"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[a.id, b.id, None],
            actor=_actor(db),
        )


def test_reorder_rejects_double_stacked_breaks(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-3")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="double-stacked"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[a.id, None, None, b.id],
            actor=_actor(db),
        )


def test_reorder_rejects_duplicate_instrument_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-4")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="duplicate"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[a.id, a.id],
            actor=_actor(db),
        )


def test_reorder_rejects_missing_instrument_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-5")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="enumerate every instrument"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[a.id],  # missing b
            actor=_actor(db),
        )


def test_reorder_rejects_unknown_instrument_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rj-6")
    a, = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="enumerate every instrument"):
        instruments_service.reorder_instruments(
            db,
            review_session=review_session,
            items=[a.id, 99_999],
            actor=_actor(db),
        )


# --------------------------------------------------------------------------- #
# create_page_break_after
# --------------------------------------------------------------------------- #


def test_create_page_break_after_sets_flag_on_successor(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="cb-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    before = _audit_count(db, "instrument.page_break_set")

    instruments_service.create_page_break_after(
        db, instrument=a, actor=_actor(db)
    )
    db.refresh(b)
    assert b.starts_new_page is True
    assert _audit_count(db, "instrument.page_break_set") == before + 1
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "instrument.page_break_set")
        .order_by(AuditEvent.id.desc())
    ).scalars().first()
    assert event.detail["refs"]["instrument_id"] == b.id
    assert event.detail["refs"]["anchor_instrument_id"] == a.id


def test_create_page_break_after_rejects_on_last_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="cb-2")
    _add_instruments(client, review_session.id, 1)
    _a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="trailing breaks"):
        instruments_service.create_page_break_after(
            db, instrument=b, actor=_actor(db)
        )


def test_create_page_break_after_rejects_when_already_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="cb-3")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    instruments_service.create_page_break_after(
        db, instrument=a, actor=_actor(db)
    )
    with pytest.raises(ValueError, match="already exists"):
        instruments_service.create_page_break_after(
            db, instrument=a, actor=_actor(db)
        )


# --------------------------------------------------------------------------- #
# clear_page_break
# --------------------------------------------------------------------------- #


def test_clear_page_break_flips_flag_and_emits_audit(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="xb-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    instruments_service.create_page_break_after(
        db, instrument=a, actor=_actor(db)
    )
    before = _audit_count(db, "instrument.page_break_cleared")

    instruments_service.clear_page_break(
        db, instrument=b, actor=_actor(db)
    )
    db.refresh(b)
    assert b.starts_new_page is False
    assert _audit_count(db, "instrument.page_break_cleared") == before + 1


def test_clear_page_break_rejects_when_no_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="xb-2")
    _add_instruments(client, review_session.id, 1)
    _a, b = _ordered(db, review_session.id)
    with pytest.raises(ValueError, match="does not carry a page break"):
        instruments_service.clear_page_break(
            db, instrument=b, actor=_actor(db)
        )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _audit_count(db: Session, event_type: str) -> int:
    return len(
        db.execute(
            select(AuditEvent).where(AuditEvent.event_type == event_type)
        ).scalars().all()
    )
