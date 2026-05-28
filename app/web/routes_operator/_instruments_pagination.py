"""Instruments-page pagination route slice — Segment 18M's
operator-driven reorder + per-instrument page-break toggle.

Carved out of ``_instruments.py`` in Segment 18N PR 3 alongside
``_instruments_band2.py``. Mirrors the service-side carve under
PR 2 that moved the equivalent CRUD into
``app/services/instruments/_pagination.py``.

Routes owned by this slice:

- ``POST /sessions/{sid}/instruments/{iid}/page-break/create`` —
  per-card ``+`` button: set ``starts_new_page=True`` on the
  instrument immediately after this one.
- ``POST /sessions/{sid}/instruments/{iid}/page-break/delete`` —
  per-card ``×`` button: clear ``starts_new_page`` on this
  instrument.
- ``POST /sessions/{sid}/instruments/order`` — drag-and-drop
  reorder endpoint. Accepts JSON ``{"items": [int | null, ...]}``
  per Segment 18M locked decision 4.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.db.session import get_db
from app.services import instruments as instruments_service
from app.web.deps import get_or_create_user, require_session_operator
from app.web.routes_operator._shared import (
    _instruments_redirect,
    _require_instrument_editable,
    _require_instrument_in_session,
)

router = APIRouter()


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/page-break/create"
)
def instrument_page_break_create(
    bundle: tuple[Instrument, ReviewSession] = Depends(
        _require_instrument_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Add a page break immediately after ``instrument_id`` (sets
    ``starts_new_page=true`` on its successor). 409 on the two
    locked-decision-4 invariant rejections (last instrument /
    successor already flagged) and on the lifecycle gate.
    """
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    try:
        instruments_service.create_page_break_after(
            db, instrument=instrument, actor=user
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/page-break/delete"
)
def instrument_page_break_delete(
    bundle: tuple[Instrument, ReviewSession] = Depends(
        _require_instrument_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Remove the page break that ``instrument_id`` carries (clears
    ``starts_new_page`` on this instrument). 409 if the instrument
    doesn't currently carry a break, or if the lifecycle gate
    rejects.
    """
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    try:
        instruments_service.clear_page_break(
            db, instrument=instrument, actor=user
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post(
    "/sessions/{session_id}/instruments/order",
    response_class=JSONResponse,
)
async def instruments_order(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Apply a reorder of instruments + page breaks driven by the
    operator-UI drag-and-drop. Accepts JSON
    ``{"items": [int | null, ...]}`` where each integer is an
    instrument id and each ``null`` marks a page-break position
    (Segment 18M locked decision 4).

    Returns ``{"ok": true, "order": [...], "breaks_at": [...]}`` on
    success so the client can patch the DOM in place. 400 on bad
    body shape, 409 on any invariant rejection (leading / trailing
    / double-stack / unknown id / duplicate / missing).
    """
    _require_instrument_editable(review_session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="instruments/order body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="instruments/order body must be a JSON object",
        )
    raw_items = body.get("items")
    if not isinstance(raw_items, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="instruments/order.items must be a list",
        )
    items: list[int | None] = []
    for v in raw_items:
        if v is None:
            items.append(None)
        elif isinstance(v, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instruments/order.items must be integers or null",
            )
        elif isinstance(v, int):
            items.append(v)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instruments/order.items must be integers or null",
            )
    try:
        instruments_service.reorder_instruments(
            db, review_session=review_session, items=items, actor=user
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    # Echo the persisted state so the client can patch the DOM (page-
    # break cards + +Page break button disabled states) without a
    # full reload.
    rows = (
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )
    order = [inst.id for inst in rows]
    breaks_at = [inst.id for inst in rows if inst.starts_new_page]
    return JSONResponse(
        {"ok": True, "order": order, "breaks_at": breaks_at},
        status_code=status.HTTP_200_OK,
    )
