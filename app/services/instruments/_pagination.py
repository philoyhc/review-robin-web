"""Instrument ordering + per-instrument page-break slice.

Carved out of ``_instrument_crud.py`` in Segment 18N PR 2 alongside
``_band2.py``. Owns the Segment 18M write surface — the operator-
driven drag-and-drop reorder + the per-card ``+`` / ``×``
page-break toggle.

Page-break = list-item model + three reorder invariants (locked
decision 4 in ``guide/archive/segment_18M_instrument_layout.md``).
The operator's mental model is a mixed list of instrument and
page-break items; persistence is the ``Instrument.starts_new_page``
boolean (true on instruments at position >= 2 means "this
instrument starts a new page"). ``reorder_instruments`` takes the
list directly; ``create_page_break_after`` + ``clear_page_break``
are surface convenience helpers for the operator-UI per-card +/-
buttons.

Cross-slice reads (all uni-directional):

- ``_state._instrument_label`` for audit-event summaries.

``_instrument_crud.py`` reads nothing from this module — the
dependency is one-way.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle
from app.services.instruments._state import _instrument_label


def _ordered_instruments(
    db: Session, review_session: ReviewSession
) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )


def reorder_instruments(
    db: Session,
    *,
    review_session: ReviewSession,
    items: list[int | None],
    actor: User | None = None,
) -> None:
    """Apply a reorder of a session's instruments + page breaks.

    ``items`` is the mixed visual list the operator-UI drag-and-drop
    produces: integers are instrument ids; ``None`` entries mark
    page-break positions. Example:
    ``[3, 1, None, 2, 4]`` = instruments 3, 1 on page 1; page break;
    instruments 2, 4 on page 2.

    The list must enumerate every instrument on the session exactly
    once (no duplicates, no unknown ids, no missing ids) and satisfy
    the three reorder invariants from locked decision 4 in
    ``guide/segment_18M_instrument_layout.md``:

    - **(a) No leading page break** — ``items[0]`` is not ``None``.
    - **(b) No trailing page break** — ``items[-1]`` is not ``None``.
    - **(c) No double-stacked breaks** — no two consecutive ``None``
      entries.

    Each invariant violation raises ``ValueError``. Unknown / missing
    / duplicate instrument ids also raise ``ValueError``.

    The algorithm runs in three steps (locked decision 4):
    1. Validate (a) + (b) + (c) + id membership.
    2. **Re-derive** ``starts_new_page`` flags from the list: every
       instrument that immediately follows a ``None`` entry has its
       flag set; every other instrument has it cleared. The flag on
       the position-1 instrument is always cleared (ignored at
       render time anyway; keeps the DB tidy).
    3. Persist the new ``order`` values (0..N-1) + re-derived flags
       in one flush, emit a single ``instruments.reordered`` audit
       event covering both the id reorder and the implicit flag
       flips, and commit.

    No-op reorders (the requested order + flags match the current
    state) short-circuit before the lifecycle invalidation + audit
    emit — mirrors ``reorder_display_fields``.
    """
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    if not items or items[0] is None:
        raise ValueError("page break is not allowed before the first instrument")
    if items[-1] is None:
        raise ValueError("page break is not allowed after the last instrument")
    for prev, nxt in zip(items, items[1:]):
        if prev is None and nxt is None:
            raise ValueError("page breaks may not be double-stacked")

    new_order_ids: list[int] = [v for v in items if v is not None]
    new_breaks_at: set[int] = set()
    for prev, nxt in zip(items, items[1:]):
        if prev is None and nxt is not None:
            new_breaks_at.add(nxt)

    if len(set(new_order_ids)) != len(new_order_ids):
        raise ValueError("items contains duplicate instrument ids")

    instruments = _ordered_instruments(db, review_session)
    by_id: dict[int, Instrument] = {inst.id: inst for inst in instruments}
    if set(new_order_ids) != set(by_id):
        raise ValueError(
            "items must enumerate every instrument on the session exactly once"
        )

    current_order_ids = [inst.id for inst in instruments]
    current_breaks_at = {inst.id for inst in instruments if inst.starts_new_page}

    if (
        current_order_ids == new_order_ids
        and current_breaks_at == new_breaks_at
    ):
        return

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=actor,
        reason="instruments_reordered",
    )

    for idx, instrument_id in enumerate(new_order_ids):
        inst = by_id[instrument_id]
        if inst.order != idx:
            inst.order = idx
        desired_flag = instrument_id in new_breaks_at
        if inst.starts_new_page != desired_flag:
            inst.starts_new_page = desired_flag
    db.flush()

    audit.write_event(
        db,
        event_type="instruments.reordered",
        summary=f"Reordered instruments on session {review_session.name}",
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.changes(
            {
                "instrument_order": [current_order_ids, new_order_ids],
                "page_breaks_at": [
                    sorted(current_breaks_at),
                    sorted(new_breaks_at),
                ],
            }
        ),
    )
    db.commit()


def create_page_break_after(
    db: Session,
    *,
    instrument: Instrument,
    actor: User | None = None,
) -> None:
    """Add a page break immediately after ``instrument`` by setting
    ``starts_new_page=true`` on its successor.

    Raises ``ValueError`` if:
    - ``instrument`` is the last instrument on the session (would
      create a trailing page break — invariant (b) from locked
      decision 4).
    - The successor already has ``starts_new_page=true`` (would
      create a double-stack — invariant (c)).

    Emits ``instrument.page_break_set`` referencing the successor
    (the instrument whose flag was flipped) plus an
    ``anchor_instrument_id`` ref so the audit trail records the
    operator's intent (which card's "+ Page break" button was
    clicked).
    """
    review_session = instrument.session
    siblings = _ordered_instruments(db, review_session)
    try:
        idx = next(i for i, s in enumerate(siblings) if s.id == instrument.id)
    except StopIteration as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"instrument {instrument.id} is not on session {review_session.id}"
        ) from exc
    if idx == len(siblings) - 1:
        raise ValueError(
            "cannot add a page break after the last instrument "
            "(trailing breaks are not allowed)"
        )
    successor = siblings[idx + 1]
    if successor.starts_new_page:
        raise ValueError(
            f"a page break already exists between instrument {instrument.id} "
            f"and instrument {successor.id}"
        )

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=actor,
        reason="page_break_set",
    )
    successor.starts_new_page = True
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.page_break_set",
        summary=(
            f"Added page break before instrument "
            f"{_instrument_label(successor)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.changes({"starts_new_page": [False, True]}),
        refs={
            "instrument_id": successor.id,
            "anchor_instrument_id": instrument.id,
        },
    )
    db.commit()


def clear_page_break(
    db: Session,
    *,
    instrument: Instrument,
    actor: User | None = None,
) -> None:
    """Remove the page break that ``instrument`` carries by clearing
    its ``starts_new_page`` flag.

    Raises ``ValueError`` if ``instrument`` doesn't currently carry a
    page break (``starts_new_page`` is already ``False``). Callers
    that want a no-op-safe variant should check the flag first.
    """
    if not instrument.starts_new_page:
        raise ValueError(
            f"instrument {instrument.id} does not carry a page break"
        )

    review_session = instrument.session
    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=actor,
        reason="page_break_cleared",
    )
    instrument.starts_new_page = False
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.page_break_cleared",
        summary=(
            f"Removed page break before instrument "
            f"{_instrument_label(instrument)}"
        ),
        actor_user_id=actor.id if actor else None,
        session=review_session,
        payload=audit.changes({"starts_new_page": [True, False]}),
        refs={"instrument_id": instrument.id},
    )
    db.commit()
