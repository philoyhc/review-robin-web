"""Response Type Definitions slice — operator add / edit / delete
on the Response Type Definitions card, plus the save-to-library /
add-from-library operator-library routes.

Carved out of ``_instruments.py`` in Segment 17A PR 5 (it was the
block marked "Slice 4b" there). ``response_type`` (name) +
``data_type`` are spec-locked once a row is saved, so the edit
route only accepts Min / Max / Step / List. Cascade-on-delete
confirmation is handled via a redirect-with-query when the
dependent count is nonzero and ``confirm`` is not set.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import instruments as instruments_service
from app.web.deps import get_or_create_user, require_session_operator
from app.web.routes_operator._shared import _require_instrument_editable

router = APIRouter()


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse {raw!r} as a number.",
        )


def _rtd_redirect_with_error(
    session_id: int,
    *,
    error: str,
    rtd_id: int | None = None,
    keep_editing: bool = False,
) -> RedirectResponse:
    fragment = "rtd-card" if rtd_id is None else f"rtd-row-{rtd_id}"
    encoded = error.replace("&", "%26").replace(" ", "+")
    rtd_param = f"&rtd_id={rtd_id}" if rtd_id is not None else ""
    editing_param = (
        f"&editing_rtd_id={rtd_id}"
        if (keep_editing and rtd_id is not None)
        else ""
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{session_id}/instruments"
            f"?rtd_error={encoded}{rtd_param}{editing_param}#{fragment}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types")
def response_type_add(
    response_type: str = Form(...),
    data_type: str = Form(...),
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.add_response_type_definition(
            db,
            review_session=review_session,
            response_type=response_type,
            data_type=data_type,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(review_session.id, error=str(exc))
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _require_rtd_in_session(
    rtd_id: int,
    review_session: ReviewSession,
    db: Session,
):
    rtd = db.execute(
        select(instruments_service.ResponseTypeDefinition).where(
            instruments_service.ResponseTypeDefinition.id == rtd_id,
            instruments_service.ResponseTypeDefinition.session_id
            == review_session.id,
        )
    ).scalar_one_or_none()
    if rtd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response Type Definition not found",
        )
    return rtd


@router.post("/sessions/{session_id}/response-types/{rtd_id}/edit")
def response_type_edit(
    rtd_id: int,
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be edited.",
        )

    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.update_response_type_definition(
            db,
            rtd=rtd,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(
            review_session.id,
            error=str(exc),
            rtd_id=rtd.id,
            keep_editing=True,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types/{rtd_id}/delete")
def response_type_delete(
    rtd_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be deleted.",
        )

    try:
        instruments_service.delete_response_type_definition(
            db, rtd=rtd, confirm=(confirm == "true"), actor=user
        )
    except instruments_service.RTDDeleteWouldEmptyInstrumentError as exc:
        # Slice 4d Gap 3: hard-block. The cascade would leave at
        # least one instrument with zero RF rows; operator must add
        # a non-ODT row to that instrument first.
        names = ",".join(
            str(e["instrument_number"]) for e in exc.would_empty
        )
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_would_empty_id={rtd.id}"
                f"&rtd_would_empty_instruments={names}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except instruments_service.RTDInUseError as exc:
        d = exc.dependents
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_delete_blocked_id={rtd.id}"
                f"&rtd_delete_blocked_rfs={d['response_field_count']}"
                f"&rtd_delete_blocked_instruments={d['instrument_count']}"
                f"&rtd_delete_blocked_responses={d['response_count']}"
                f"&rtd_delete_blocked_assignments={d['assignment_count']}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/response-types/{rtd_id}/save-to-library"
)
def response_type_save_to_library(
    rtd_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 15C Slice 3 — promote a session RTD to the operator's
    library. Refuses on seeded rows and on name collisions in the
    operator's library."""
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    try:
        instruments_service.save_session_rtd_to_library(
            db, session_rtd=rtd, actor=user
        )
    except instruments_service.RTDLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except instruments_service.RTDLibraryConflictError as exc:
        return _rtd_redirect_with_error(
            review_session.id, error=str(exc), rtd_id=rtd.id
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"#rtd-row-{rtd.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types/add-from-library")
def response_type_add_from_library(
    operator_rtd_id: int = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Segment 15C Slice 3 — copy an operator-library RTD into the
    session. The picker on the Instruments page surfaces only
    library entries whose name isn't already on this session."""
    _require_instrument_editable(review_session)
    library_rtd = db.execute(
        select(instruments_service.OperatorResponseTypeDefinition).where(
            instruments_service.OperatorResponseTypeDefinition.id
            == operator_rtd_id,
            instruments_service.OperatorResponseTypeDefinition.owner_user_id
            == user.id,
        )
    ).scalar_one_or_none()
    if library_rtd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library Response Type not found",
        )
    try:
        instruments_service.add_rtd_from_library(
            db,
            review_session=review_session,
            library_rtd=library_rtd,
            actor=user,
        )
    except instruments_service.RTDValidationError as exc:
        return _rtd_redirect_with_error(review_session.id, error=str(exc))
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
