"""Extract data — Operations-strip tab for fine-grained shaping
of response data for offline analysis (per ``guide/extract_data.md``).

Ships as a skeleton in this PR: the page renders with the
Operations chrome and three placeholder lens sections
(By instrument / By reviewer / By reviewee). Wiring per-lens
downloads is the follow-up.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentResponseField,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import audit, data_shapes, field_labels
from app.services.extracts import stream_csv
from app.services.extracts.data_shape_extract import (
    build_shape_rows,
    compose_shape_header,
)
from app.web import breadcrumbs, views
from app.web.deps import get_or_create_user, require_session_operator
from app.web.routes_operator._shared import _templates

router = APIRouter()


def _slug_shape_name(name: str) -> str:
    """Alphanumeric-plus-underscore slug for the shape's
    filename. Mirrors ``by_instrument_filename_slug`` so the
    output naming reads consistently. Empty slug after
    sanitisation falls back to ``shape``."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug or "shape"


# --------------------------------------------------------------------------- #
# Data shaper saved-shape CRUD — POST / PATCH / DELETE. Per the
# wiring decisions in ``spec/extract_data.md``.
# --------------------------------------------------------------------------- #


class DataShapePayload(BaseModel):
    """Request body for ``POST`` / ``PATCH`` on a saved
    Data shape. Mirrors the persisted columns 1:1."""

    model_config = ConfigDict(extra="forbid")

    name: str
    axis: str
    instrument_id: int | None = None
    response_field_id: int | None = None
    column_chip_slots: list[str] = Field(default_factory=list)


def _validation_error_response(
    exc: data_shapes.DataShapeValidationError,
) -> JSONResponse:
    """422 with a structured body the inline error display
    on the page consumes. ``conflict=True`` lets the JS
    target the name input specifically rather than rendering
    a generic error."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": str(exc),
            "conflict": isinstance(
                exc, data_shapes.DataShapeNameConflictError
            ),
        },
    )


# Numeric response fields with a finite, small number of valid
# values get a Data shaper "Discrete steps" chip. Threshold: 12
# (one chip per value would scale poorly past that).
_DISCRETE_STEPS_THRESHOLD = 12


def _discrete_steps_values(field: InstrumentResponseField) -> list[str]:
    """Return the discrete step values for a numeric response
    field as a list of pre-formatted strings, or an empty list
    when the field is non-numeric, lacks the min/max/step
    triple, or has more than ``_DISCRETE_STEPS_THRESHOLD``
    steps. Used by the Data shaper to decide whether to ship
    the per-field "Discrete steps" chip in the field pool."""
    data_type = field._inline_data_type
    if data_type not in ("Integer", "Decimal"):
        return []
    mn = field._inline_min
    mx = field._inline_max
    step = field._inline_step
    if step is None and data_type == "Integer":
        step = 1.0
    if mn is None or mx is None or step is None or step <= 0:
        return []
    span = mx - mn
    if span < 0:
        return []
    count = int(round(span / step)) + 1
    if count <= 0 or count > _DISCRETE_STEPS_THRESHOLD:
        return []
    is_int = data_type == "Integer"
    values: list[str] = []
    for i in range(count):
        v = mn + i * step
        if is_int or v == int(v):
            values.append(str(int(round(v))))
        else:
            values.append(f"{v:g}")
    return values


@router.get(
    "/sessions/{session_id}/extract-data", response_class=HTMLResponse
)
def session_extract_data(
    request: Request,
    super_status: str | None = None,
    super_button: str | None = None,
    super_step: str | None = None,
    super_error: str | None = None,
    prepare_confirm: str | None = None,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="extract-data",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
    )
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Per-field discrete-steps values, keyed by field id.
    # Empty list when the field doesn't qualify for the
    # Data shaper's "Discrete steps" chip.
    field_discrete_steps: dict[int, list[str]] = {}
    for instrument in instruments:
        for f in instrument.response_fields:
            field_discrete_steps[f.id] = _discrete_steps_values(f)
    # Friendly labels for the Data shaper's Reviewer / Reviewee
    # tag chips — picks up operator renames done on the Setup
    # pages and falls back to ``Tag 1`` / ``Tag 2`` / ``Tag 3``
    # when no override is set (per ``field_labels.resolve``'s
    # built-in default chain).
    reviewer_tag_labels = [
        field_labels.resolve(review_session, "reviewer", slot)
        for slot in ("tag_1", "tag_2", "tag_3")
    ]
    reviewee_tag_labels = [
        field_labels.resolve(review_session, "reviewee", slot)
        for slot in ("tag_1", "tag_2", "tag_3")
    ]
    saved_shapes = data_shapes.list_shapes(db, review_session)
    # The template walks each saved shape's column-chip slot
    # list to re-toggle the matching chips when the operator
    # clicks ``Edit``. Decoding the JSON server-side keeps
    # the template clean.
    # The template walks each saved shape's column-chip slot
    # list to re-toggle the matching chips when the operator
    # clicks ``Edit``. ``column_headers`` carries the
    # canonical CSV header for each shape so the preview
    # ``<th>`` cells render the same labels the eventual
    # download would (``ReviewerName``, actual step values,
    # etc.) — without it the cells fell back to the raw
    # chip slot strings like ``reviewer:name``.
    saved_shape_rows = [
        {
            "id": shape.id,
            "name": shape.name,
            "axis": shape.axis,
            "instrument_id": shape.instrument_id,
            "response_field_id": shape.response_field_id,
            "column_chip_slots": json.loads(shape.column_chip_slots),
            "column_headers": list(
                compose_shape_header(db, review_session, shape)
            ),
        }
        for shape in saved_shapes
    ]
    return _templates.TemplateResponse(
        request,
        "operator/session_extract_data.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Extract data"
            ),
            "instruments": instruments,
            "reviewer_tag_labels": reviewer_tag_labels,
            "reviewee_tag_labels": reviewee_tag_labels,
            "field_discrete_steps": field_discrete_steps,
            "saved_shapes": saved_shape_rows,
            **workflow_ctx,
        },
    )


@router.post("/sessions/{session_id}/extract-data/shapes")
def create_data_shape(
    payload: DataShapePayload,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist a brand-new Data shape on ``review_session``.

    Returns 201 with the new row's columns on success or
    422 with an inline error on validation failure (see
    ``_validation_error_response``).
    """
    try:
        shape = data_shapes.create_shape(
            db,
            review_session=review_session,
            actor=user,
            name=payload.name,
            axis=payload.axis,
            instrument_id=payload.instrument_id,
            response_field_id=payload.response_field_id,
            column_chip_slots=payload.column_chip_slots,
        )
    except data_shapes.DataShapeValidationError as exc:
        return _validation_error_response(exc)
    db.commit()
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "id": shape.id,
            "name": shape.name,
            "axis": shape.axis,
            "instrument_id": shape.instrument_id,
            "response_field_id": shape.response_field_id,
            "column_chip_slots": json.loads(shape.column_chip_slots),
            "column_headers": list(
                compose_shape_header(db, review_session, shape)
            ),
        },
    )


@router.patch(
    "/sessions/{session_id}/extract-data/shapes/{shape_id}"
)
def update_data_shape(
    shape_id: int,
    payload: DataShapePayload,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Update an existing Data shape on ``review_session``.

    404s on cross-session ids (so a malicious / typo'd
    shape_id can't leak data from another session). 422 on
    validation failure.
    """
    shape = data_shapes.get_shape(db, review_session, shape_id)
    if shape is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        data_shapes.update_shape(
            db,
            review_session=review_session,
            actor=user,
            shape=shape,
            name=payload.name,
            axis=payload.axis,
            instrument_id=payload.instrument_id,
            response_field_id=payload.response_field_id,
            column_chip_slots=payload.column_chip_slots,
        )
    except data_shapes.DataShapeValidationError as exc:
        return _validation_error_response(exc)
    db.commit()
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "id": shape.id,
            "name": shape.name,
            "axis": shape.axis,
            "instrument_id": shape.instrument_id,
            "response_field_id": shape.response_field_id,
            "column_chip_slots": json.loads(shape.column_chip_slots),
            "column_headers": list(
                compose_shape_header(db, review_session, shape)
            ),
        },
    )


@router.delete(
    "/sessions/{session_id}/extract-data/shapes/{shape_id}"
)
def delete_data_shape(
    shape_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a Data shape. Idempotent — re-deleting a
    missing shape still returns 204."""
    shape = data_shapes.get_shape(db, review_session, shape_id)
    if shape is not None:
        data_shapes.delete_shape(
            db,
            review_session=review_session,
            actor=user,
            shape=shape,
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/sessions/{session_id}/extract-data/shapes/{shape_id}/download.csv"
)
def download_data_shape(
    shape_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream the saved Data shape's CSV. Filename:
    ``{code}_{slug(shape.name)}.csv`` per the wiring
    decisions. Emits ``session.data_shape_extracted`` with
    ``counts.rows`` (body row count, header excluded) +
    ``refs.shape_id``."""
    shape = data_shapes.get_shape(db, review_session, shape_id)
    if shape is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rows = build_shape_rows(db, review_session, shape)
    body_count = max(0, len(rows) - 1)

    audit.write_event(
        db,
        event_type="session.data_shape_extracted",
        summary=(
            f"Extracted Data shape {shape.name!r} for session "
            f"{review_session.code} ({body_count} rows)"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(rows=body_count),
        refs={"shape_id": shape.id},
    )
    db.commit()

    code = (review_session.code or "session").strip() or "session"
    download_name = f"{code}_{_slug_shape_name(shape.name)}.csv"
    return StreamingResponse(
        stream_csv(rows),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download_name}"'
            ),
        },
    )
