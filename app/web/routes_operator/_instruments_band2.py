"""Instruments-page Band 2 route slice — the routes that back the
operator-card's Band 2 (preview row) UX.

Carved out of ``_instruments.py`` in Segment 18N PR 3 — that file
had grown to 1,497 LOC and was the codebase's biggest production
file. The Band 2 routes form a natural sub-concern: they POST
JSON, return JSON (no HTML redirect), and back the Band 2-area
interactions (column drag-resize, the chip-toggle / Band 3 row
save round-trip, and the live "Refresh" reviewer-sample pick).

Routes owned by this slice:

- ``POST /sessions/{sid}/instruments/{iid}/column-widths`` —
  persist drag-resized per-column widths from the Band 2 preview.
- ``POST /sessions/{sid}/instruments/{iid}/band2-state`` — Band 2
  selections + Band 3 row save (the big one); includes the
  Segment 18K PR 4 ``acknowledged_drop`` confirm-guard 409 and
  the Wave 3 PR ii shape-change 409.
- ``POST /sessions/{sid}/instruments/{iid}/preview-sample`` —
  the live "Refresh" button on Band 2's preview row; runs the
  rule engine against the current Band 1 form state.

Mirror of the service-side carve under Segment 18N PR 2 that
moved ``set_band2_state`` into ``app/services/instruments/_band2.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession, User
from app.db.session import get_db
from app.services import instruments as instruments_service
from app.web.deps import get_or_create_user
from app.web.routes_operator._shared import (
    _require_instrument_editable,
    _require_instrument_in_session,
)

router = APIRouter()


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/column-widths"
)
async def instrument_column_widths(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist drag-resized column widths from the new-model card's
    Band 2 preview table. Accepts a JSON body
    ``{"widths": {"identity": 200, "df_<id>": 150, ...}}`` and writes
    the sanitised payload onto ``instruments.column_widths`` via the
    :func:`instruments_service.set_column_widths` service. Returns
    204 No Content on success.
    """
    instrument, _ = bundle
    _require_instrument_editable(instrument.session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column-widths body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column-widths body must be a JSON object",
        )
    widths = body.get("widths") or {}
    if not isinstance(widths, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column-widths.widths must be an object",
        )
    instruments_service.set_column_widths(
        db, instrument=instrument, widths=widths, actor=user
    )
    db.commit()
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/band2-state"
)
async def instrument_band2_state(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist the new-model card's Band 2 selections + Band 3
    response-field rows. Accepts JSON
    ``{"selected_display_keys": [...], "response_fields": [...]}``
    and writes through
    :func:`instruments_service.set_band2_state`. Returns 200 on
    success.
    """
    instrument, _ = bundle
    _require_instrument_editable(instrument.session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="band2-state body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="band2-state body must be a JSON object",
        )
    # Segment 18K PR 4 — Band 2 chip un-pin confirm guard. The
    # operator-side JS shows a ``confirm()`` naming the field +
    # response count before flipping a chip whose backing row has
    # saved responses; on OK it re-POSTs with
    # ``acknowledged_drop=true``. Top-level boolean (rather than
    # per-field) matches the one-chip-click-at-a-time UX. Forged /
    # buggy clients that omit it land on the 409 path below.
    acknowledged_drop = bool(body.get("acknowledged_drop", False))
    try:
        instruments_service.set_band2_state(
            db,
            instrument=instrument,
            state=body,
            actor=user,
            acknowledged_drop=acknowledged_drop,
        )
    except instruments_service.ResponsesPresentError as exc:
        # Wave 3 PR i — cascade-blocked delete. The Band 3 row's X
        # is rendered ``disabled`` when ``has_responses`` is true,
        # so this code path is defence-in-depth for a buggy /
        # forged client that posts a JSON payload omitting an id
        # whose row has saved responses. Surface 409.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "cascade_blocked",
                "responses": exc.cascaded_response_count,
            },
        ) from exc
    except instruments_service.ResponseFieldDropAcknowledgementRequired as exc:
        # Segment 18K PR 4 — un-pin against a field with saved
        # responses, without the ``acknowledged_drop`` flag. JSON
        # body so the client confirm dialog can name the field +
        # response count. The normal operator-flow JS confirms +
        # re-POSTs with the flag set; this 409 is defence-in-depth
        # for direct / forged API hits.
        return JSONResponse(
            {
                "error": "drop_acknowledgement_required",
                "field_label": exc.field_label,
                "responses": exc.cascaded_response_count,
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    except instruments_service.ResponseFieldShapeChangeError as exc:
        # Wave 3 PR ii — operator tried to change data_type / bounds
        # on a row with saved responses. The Band 3 data_type select
        # + bound inputs are rendered ``disabled`` when has_responses
        # is true; this server guard catches direct API hits. 409.
        # Return JSONResponse directly so the structured detail
        # reaches the client (the app's global HTTPException handler
        # renders HTML and drops dict ``detail``).
        return JSONResponse(
            {
                "error": "shape_change_blocked",
                "field_label": exc.field_label,
                "responses": exc.cascaded_response_count,
                "changed": exc.changed_attrs,
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    except instruments_service.InvalidResponseFieldShapeError as exc:
        # Wave 3 PR ii — operator-authored bounds don't make sense
        # (max < min, step ≤ 0, empty List, etc). The Band 3 ✓ button
        # is client-side-gated against the same checks; surface 422
        # for the defence-in-depth case.
        return JSONResponse(
            {
                "error": "invalid_field_shape",
                "errors": [
                    {"field_label": label, "message": msg}
                    for label, msg in exc.errors
                ],
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    db.commit()
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/preview-sample"
)
async def instrument_preview_sample(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Run the rule engine against the current Band 1 form state and
    return the first reviewee that lands in any in-scope
    ``(reviewer, reviewee)`` pair. The Band 2 preview's "Refresh"
    button consumes this to re-pick the sample reviewee so the
    operator can see Link 1 + Link 2 filtering applied to the
    preview row without saving first.
    """
    instrument, _ = bundle
    _require_instrument_editable(instrument.session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="preview-sample body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="preview-sample body must be a JSON object",
        )
    def _str_list(v: Any) -> list[str]:
        return [str(x) for x in v] if isinstance(v, list) else []
    def _rule_list(v: Any) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        if not isinstance(v, list):
            return out
        for entry in v:
            if not isinstance(entry, dict):
                continue
            out.append(
                {
                    "field": str(entry.get("field") or ""),
                    "op": str(entry.get("op") or ""),
                    "operand_value": str(entry.get("operand_value") or ""),
                    "operand_tag": str(entry.get("operand_tag") or ""),
                }
            )
        return out
    # Live Link 3 boundary list (canonical keys like
    # ``"reviewee.tag3"``) — the operator's in-progress boundary
    # selection. Pre-Gap-10 the route silently used the persisted
    # ``instrument.group_kind`` so a Refresh under a changed
    # boundary computed against the OLD boundary. ``None`` (key
    # absent) preserves that fallback for older callers.
    raw_boundary = body.get("link3_boundary")
    link3_boundary = (
        _str_list(raw_boundary) if raw_boundary is not None else None
    )
    sample_pick = instruments_service.find_sample_in_scope_reviewee(
        db,
        instrument=instrument,
        link1_mode=str(body.get("link1_mode") or "all"),
        link1_combinator=str(body.get("link1_combinator") or "AND"),
        link1_rules=_rule_list(body.get("link1_rules")),
        link2_mode=str(body.get("link2_mode") or "all"),
        link2_combinator=str(body.get("link2_combinator") or "AND"),
        link2_rules=_rule_list(body.get("link2_rules")),
        link3_boundary=link3_boundary,
    )
    if sample_pick is None:
        return JSONResponse(
            {"sample_reviewee": None}, status_code=status.HTTP_200_OK
        )
    reviewee, sample_group_member_ids = sample_pick
    # Persist the picked sample on band2_state so the choice
    # survives across page reloads (especially the transition from
    # edit → view mode after Save, which is where the operator
    # first noticed the sample resetting to "first by name"). Also
    # persist the rule-surviving group-member ID set (Gap 10) so
    # the next render's Grouped-mode preview filters its member
    # list against the engine's actual survivors rather than the
    # full active-reviewee roster. None when there's no
    # reviewee-side boundary — render falls back to its existing
    # unconstrained partition.
    # set_band2_state preserves the existing selected_display_keys
    # + response_fields when not in the payload.
    state_update: dict[str, Any] = {
        "sample_reviewee_name": reviewee.name or "",
        "sample_group_member_ids": sample_group_member_ids,
    }
    instruments_service.set_band2_state(
        db,
        instrument=instrument,
        state=state_update,
        actor=user,
    )
    db.commit()
    return JSONResponse(
        {
            "sample_reviewee": {
                "name": reviewee.name or "",
                "email_or_identifier": reviewee.email_or_identifier or "",
                "profile_link": reviewee.profile_link or "",
                "tag_1": reviewee.tag_1 or "",
                "tag_2": reviewee.tag_2 or "",
                "tag_3": reviewee.tag_3 or "",
            },
            # Gap 10 — the rule-surviving group-member IDs so the
            # client-side preview rebuild can intersect its
            # boundary partition against the engine's actual
            # survivors. Empty list when there's no reviewee-side
            # boundary (per-reviewee mode, or grouped-by-pair-
            # context-only); render falls back to the
            # unconstrained partition for those cases.
            "sample_group_member_ids": (
                sample_group_member_ids
                if sample_group_member_ids is not None
                else []
            ),
        },
        status_code=status.HTTP_200_OK,
    )
