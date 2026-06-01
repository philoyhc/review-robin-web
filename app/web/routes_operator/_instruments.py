"""Instruments slice — instrument CRUD (page, add, delete, edit
description, bulk save fields), per-instrument response/display
field CRUD (add / edit / delete / move + bulk save), lifecycle
(open / close / visibility), and the session-level bulk
visibility / accepting toggles.

Slice 10 of the major refactor. Response Type Definition CRUD
was carved into the sibling ``_response_types.py`` slice in
Segment 17A PR 5.

Source ranges in pre-refactor ``routes_operator.py``: 2512-2575,
2871-3962.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import (
    instruments as instruments_service,
)
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies
from app.web import views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _instruments_redirect,
    _lifecycle_error_response,
    _require_instrument_editable,
    _require_instrument_in_session,
    _templates,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
# Slice-local helpers. The cross-slice edit-lock guards
# (``_require_editable`` / ``_require_response_loss_ack`` /
# ``_lifecycle_error_response`` / ``_require_instrument_editable``)
# live in ``_shared.py``.
# --------------------------------------------------------------------------- #



@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    editing: int | None = Query(default=None),
    saved: int | None = Query(default=None),
    rf_save_error: str | None = Query(default=None),
    sort_save_error: str | None = Query(default=None),
    sort_save_error_instrument_id: int | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    context = views.build_instruments_context(
        db,
        review_session=review_session,
        user=user,
        editing=editing,
        saved=saved,
        rf_save_error=rf_save_error,
        sort_save_error=sort_save_error,
        sort_save_error_instrument_id=sort_save_error_instrument_id,
    )
    return _templates.TemplateResponse(
        request, "operator/instruments_index.html", context
    )


def _require_response_field_in_instrument(
    field_id: int, instrument: Instrument, db: Session
):
    from app.db.models import InstrumentResponseField

    field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.id == field_id,
            InstrumentResponseField.instrument_id == instrument.id,
        )
    ).scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return field


def _require_display_field_in_instrument(
    df_id: int, instrument: Instrument, db: Session
):
    from app.db.models import InstrumentDisplayField

    field = db.execute(
        select(InstrumentDisplayField).where(
            InstrumentDisplayField.id == df_id,
            InstrumentDisplayField.instrument_id == instrument.id,
        )
    ).scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return field


@router.get(
    "/sessions/{session_id}/instruments/{instrument_id}",
)
def instrument_detail_redirect(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
) -> RedirectResponse:
    """Back-compat: legacy per-instrument page redirects to consolidated view."""
    _, review_session = bundle
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/edit")
def instrument_edit_description(
    description: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    instruments_service.update_instrument_description(
        db,
        instrument=instrument,
        description=description,
        actor=user,
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/fields")
def instrument_add_field(
    field_key: str | None = Form(default=None),
    label: str = Form(...),
    response_type: str = Form(...),
    required: str | None = Form(default=None),
    validation_min: str | None = Form(default=None),
    validation_max: str | None = Form(default=None),
    help_text: str | None = Form(default=None),
    help_text_visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    key = (field_key or "").strip()
    if not key:
        key = instruments_service.slugify_field_key(label)

    # Validation is now derived from the chosen Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored.
    _ = validation_min, validation_max  # silence unused-arg

    try:
        instruments_service.add_response_field(
            db,
            instrument=instrument,
            field_key=key,
            label=label,
            response_type=response_type,
            required=required == "true",
            help_text=help_text,
            help_text_visible=(help_text_visible == "true"),
            actor=user,
        )
    except instruments_service.FieldKeyError as exc:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?field_key_error={int(False)}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"X-FieldKey-Error": str(exc)},
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/add-row"
)
def instrument_add_default_field(
    after: int | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    instruments_service.add_default_response_field(
        db, instrument=instrument, after_field_id=after, actor=user
    )
    # Preserve editing state: the ➕ button is only rendered while
    # editing, so the operator stays in editing mode after the add.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/edit"
)
def instrument_edit_field(
    field_id: int,
    label: str = Form(...),
    required: str | None = Form(default=None),
    validation_min: str | None = Form(default=None),
    validation_max: str | None = Form(default=None),
    help_text: str | None = Form(default=None),
    help_text_visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)

    # Validation now derives from the field's Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored, and
    # the existing derived block on the row is preserved as-is.
    _ = validation_min, validation_max  # silence unused-arg
    validation_block = field.validation

    _, warning_count = instruments_service.update_response_field(
        db,
        field=field,
        label=label,
        required=required == "true",
        validation=validation_block,
        help_text=help_text,
        help_text_visible=(help_text_visible == "true"),
        actor=user,
    )

    if warning_count > 0:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?required_warning={warning_count}&field_id={field.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/delete"
)
def instrument_delete_field(
    field_id: int,
    confirm: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)

    try:
        instruments_service.delete_response_field(
            db,
            field=field,
            confirm=(confirm == "true"),
            actor=user,
        )
    except instruments_service.ResponsesPresentError as exc:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&delete_blocked_field_id={field.id}"
                f"&delete_blocked_count={exc.cascaded_response_count}"
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    # Preserve editing state on the redirect.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/fields/{field_id}/move"
)
def instrument_move_field(
    field_id: int,
    direction: str = Form(...),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_response_field_in_instrument(field_id, instrument, db)
    if direction not in ("up", "down"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    instruments_service.move_response_field(
        db, field=field, direction=direction, actor=user  # type: ignore[arg-type]
    )
    # Preserve editing state: the ▲ / ▼ buttons are only rendered
    # while editing.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/display-fields")
def instrument_add_display_field(
    source_pair: str = Form(...),
    label: str | None = Form(default=None),
    visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    if ":" not in source_pair:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?display_source_error=invalid_pair"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    source_type, source_field = source_pair.split(":", 1)

    try:
        instruments_service.add_display_field(
            db,
            instrument=instrument,
            source_type=source_type,
            source_field=source_field,
            label=label or "",
            visible=(visible == "true"),
            actor=user,
        )
    except instruments_service.DisplaySourceError:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?display_source_error={source_type}:{source_field}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/edit"
)
def instrument_edit_display_field(
    df_id: int,
    visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)

    # ``label`` form parameter retired in Segment 15A Slice 2 —
    # the per-instrument label override is no longer editable.
    # Friendly labels resolve via ``field_labels.resolve(...)``
    # against the session-wide ``session_field_labels`` table.
    # This endpoint now only toggles visibility (the
    # column-checkbox UI on the Display Fields table).
    try:
        instruments_service.update_display_field(
            db,
            field=field,
            label=field.label,  # preserve current value (dead data)
            visible=(visible == "true"),
            actor=user,
        )
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be hidden.",
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/delete"
)
def instrument_delete_display_field(
    df_id: int,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)

    try:
        instruments_service.delete_display_field(db, field=field, actor=user)
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be deleted.",
        )
    return _instruments_redirect(review_session.id)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}"
    "/display-fields/{df_id}/move"
)
def instrument_move_display_field(
    df_id: int,
    direction: str = Form(...),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)
    if direction not in ("up", "down"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    try:
        instruments_service.move_display_field(
            db, field=field, direction=direction, actor=user
        )
    except instruments_service.LockedDisplayFieldError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Locked display fields cannot be reordered.",
        )
    # Preserve editing state on the redirect so the operator stays in
    # the editable view after moving a row.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/fields/save")
async def instrument_bulk_save_fields(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)

    form = await request.form()

    # New-model instruments don't render the Display Fields / Response
    # Fields tables — the form only carries identity (short_label /
    # description) + Band 1's Link 1 / Link 2 / Link 3 controls. Branch
    # off the table-driven bulk-save logic for them and call the Band 1
    # service helpers instead.
    try:
        band1 = instruments_service.parse_band1_form(form)
    except instruments_service.Band1ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    link3_mode, link3_pairs, link3_touched = (
        instruments_service.parse_link3_form(form)
    )
    instruments_service.set_band1_assignment_rules(
        db, instrument=instrument, actor=user, **band1
    )
    instruments_service.set_unit_of_review(
        db,
        instrument=instrument,
        mode=link3_mode,
        boundary_pairs=link3_pairs,
        actor=user,
        touched=link3_touched,
    )
    # Column-widths race fix: the drag-resize handler POSTs to
    # /column-widths asynchronously. A fast Save click can win
    # the race and navigate the page before the async fetch
    # reaches the server. The JS mirrors the current widths
    # into ``column_widths_snapshot`` on every drag, so the
    # form payload always carries the latest set and the form
    # Save can persist them in the same transaction.
    snapshot = form.get("column_widths_snapshot")
    if isinstance(snapshot, str) and snapshot.strip():
        import json as _json

        try:
            widths_payload = _json.loads(snapshot)
        except (TypeError, ValueError):
            widths_payload = None
        if isinstance(widths_payload, dict):
            instruments_service.set_column_widths(
                db,
                instrument=instrument,
                widths=widths_payload,
                actor=user,
            )
    # Sort spec (Gap 3, 18J Wave 1) — the new-model card's
    # Band 2 preview header carries clickable sort badges that
    # populate the same ``sort_display_field_id`` /
    # ``sort_dir`` parallel arrays the legacy editor table
    # uses. Reuse the same service-layer call + error path as
    # the standard branch below; any rejection (length / dup /
    # cross-instrument / dir) redirects back to the index with
    # an inline banner.
    sort_ids_raw = [str(v) for v in form.getlist("sort_display_field_id")]
    sort_dirs_raw = [str(v) for v in form.getlist("sort_dir")]
    if len(sort_ids_raw) != len(sort_dirs_raw):
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&sort_save_error_instrument_id={instrument.id}"
                f"&sort_save_error=Sort+spec+arrays+misaligned."
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    sort_pairs: list[tuple[int, str]] = []
    for raw_id, raw_dir in zip(sort_ids_raw, sort_dirs_raw):
        try:
            sort_pairs.append((int(raw_id), raw_dir))
        except ValueError:
            return RedirectResponse(
                url=(
                    f"/operator/sessions/{review_session.id}/instruments"
                    f"?editing={instrument.id}"
                    f"&sort_save_error_instrument_id={instrument.id}"
                    f"&sort_save_error=Sort+spec+ids+must+be+integers."
                    f"#instrument-{instrument.id}"
                ),
                status_code=status.HTTP_303_SEE_OTHER,
            )
    try:
        instruments_service.set_sort_display_fields(
            db,
            instrument=instrument,
            fields=sort_pairs,
            actor=user,
            correlation_id=request_correlation_id(),
        )
    except instruments_service.SortSpecError as exc:
        from urllib.parse import quote

        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&sort_save_error_instrument_id={instrument.id}"
                f"&sort_save_error={quote(exc.message, safe=' ')}"
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    # Identity edits (description / short_label) come through the
    # same bulk-save form on the new-model card; reuse the same
    # block at the bottom of the standard handler.
    if "description" in form:
        submitted_desc = form.get("description")
        cleaned = (
            submitted_desc.strip()
            if isinstance(submitted_desc, str)
            else None
        ) or None
        if cleaned != instrument.description:
            instruments_service.update_instrument_description(
                db, instrument=instrument, description=cleaned, actor=user
            )
    if "short_label" in form:
        submitted_label = form.get("short_label")
        try:
            instruments_service.update_short_label(
                db,
                instrument=instrument,
                short_label=(
                    submitted_label
                    if isinstance(submitted_label, str)
                    else None
                ),
                actor=user,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    # Visibility-policy editor hitches a ride on this form (the
    # standalone "Save visibility" button retired — the Band 3
    # chips' hidden inputs carry ``form="dfsave-<id>"`` so they
    # land here alongside the rest of the card's state).
    vp_rows: list[dict[str, object]] = []
    for audience in visibility_policies.AUDIENCES:
        wo_raw = form.get(f"{audience}_while_ongoing_mode")
        ar_raw = form.get(f"{audience}_after_release_mode")
        if wo_raw is None and ar_raw is None:
            continue
        vp_rows.append(
            {
                "audience": audience,
                "while_ongoing_mode": (
                    (str(wo_raw).strip() or None)
                    if wo_raw is not None
                    else None
                ),
                "after_release_mode": (
                    (str(ar_raw).strip() or None)
                    if ar_raw is not None
                    else None
                ),
            }
        )
    if vp_rows:
        try:
            visibility_policies.upsert_many(
                db,
                review_session=review_session,
                instrument=instrument,
                rows=vp_rows,
                user=user,
                correlation_id=request_correlation_id(),
            )
        except visibility_policies.VisibilityPolicyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.message,
            ) from exc
    db.commit()
    # Wave 4 PR 2 — preserve ``?editing=<id>`` so Save doesn't
    # re-lock the new-model card. Lock/Unlock owns the gating;
    # Save owns persistence. ``?saved=<id>`` triggers the flash
    # confirmation banner on the next render.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}&saved={instrument.id}"
            f"#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
        )



# Wave 5 PR 5.3 — the legacy ``/instruments/add`` POST route
# retired (its ``+Add instrument`` button retired in Wave 4 PR
# 4c). ``+Instrument`` (the ``/add-new-model`` route below)
# is the sole UI affordance. ``/add-group`` survives as a back-
# door for fixtures + programmatic creation; the matching
# ``+Group instrument`` button retired in Wave 4 PR 4c, so
# operators reach group-scoped mode by toggling Band 1 Link 3 to
# "Grouped" on a fresh +Instrument card.


@router.post("/sessions/{session_id}/instruments/add-group")
def instruments_add_group(
    after: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Create a group-scoped instrument. Back-door for fixtures +
    programmatic callers; the corresponding ``+Group instrument``
    button retired in Wave 4 PR 4c."""
    _require_instrument_editable(review_session)
    instrument = instruments_service.create_instrument(
        db,
        review_session=review_session,
        after_instrument_id=after,
        actor=user,
        group_kind=instruments_service.GROUP_KIND_SENTINEL,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/add-new-model")
def instruments_add_new_model(
    after: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Create a new instrument. Wave 5 PR 5.3 collapsed the
    legacy / new-model distinction — every instrument now renders
    with the vertical-bands layout. The route name persists for
    back-compat with the template's existing form action.
    """
    _require_instrument_editable(review_session)
    instrument = instruments_service.create_instrument(
        db,
        review_session=review_session,
        after_instrument_id=after,
        actor=user,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/replicate")
def instruments_replicate(
    bundle: tuple[Instrument, ReviewSession] = Depends(
        _require_instrument_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Clone an instrument's content into a new instrument slotted
    immediately after the source (Segment 13C PR 3)."""
    source, review_session = bundle
    _require_instrument_editable(review_session)
    instrument = instruments_service.replicate_instrument(
        db,
        review_session=review_session,
        source=source,
        actor=user,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/delete")
def instruments_delete(
    instrument_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    instrument = db.execute(
        select(Instrument)
        .where(Instrument.id == instrument_id)
        .where(Instrument.session_id == review_session.id)
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instrument not found",
        )
    total = db.execute(
        select(func.count())
        .select_from(Instrument)
        .where(Instrument.session_id == review_session.id)
    ).scalar_one()
    if total <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last instrument",
        )
    # Pick the next-or-previous sibling so the operator lands near
    # the instrument they just deleted instead of being yanked to
    # the top of the page. Captured BEFORE the delete since the row
    # is gone after.
    sibling_ids = (
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        )
        .scalars()
        .all()
    )
    idx = sibling_ids.index(instrument_id)
    if idx + 1 < len(sibling_ids):
        landing_id = sibling_ids[idx + 1]
    else:
        landing_id = sibling_ids[idx - 1]
    instruments_service.delete_instrument(
        db, instrument=instrument, actor=user
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{landing_id}"
    )


@router.post("/sessions/{session_id}/instruments/accepting/all-on")
def instruments_bulk_accept_on(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bulk accepting toggle requires session to be ready",
        )
    instruments_service.bulk_set_accepting(
        db, review_session=review_session, target=True, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/accepting/all-off")
def instruments_bulk_accept_off(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bulk accepting toggle requires session to be ready",
        )
    instruments_service.bulk_set_accepting(
        db, review_session=review_session, target=False, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/visibility/all-on")
def instruments_bulk_visibility_on(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instruments_service.bulk_set_visibility(
        db, review_session=review_session, target=True, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/visibility/all-off")
def instruments_bulk_visibility_off(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instruments_service.bulk_set_visibility(
        db, review_session=review_session, target=False, actor=user
    )
    return _instruments_redirect(review_session.id)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/open")
def instrument_open(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    try:
        lifecycle.open_instrument(
            db,
            instrument=instrument,
            review_session=review_session,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except lifecycle.LifecycleError as exc:
        raise _lifecycle_error_response(exc) from exc
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/close")
def instrument_close(
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    lifecycle.close_instrument(
        db,
        instrument=instrument,
        review_session=review_session,
        user=user,
        reason="manual",
        correlation_id=request_correlation_id(),
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/display-fields/order"
)
async def instrument_display_fields_order(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Persist a bulk reorder of the non-locked display fields, driven
    by drag-and-drop on the new-model card's Band 2 pill row. Accepts
    JSON ``{"ordered_ids": [int, ...]}`` listing every non-locked
    display field id on the instrument in the new order; locked
    fields (RevieweeName, RevieweeEmail) keep their pinned positions.
    """
    instrument, _ = bundle
    _require_instrument_editable(instrument.session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display-fields/order body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display-fields/order body must be a JSON object",
        )
    raw_ids = body.get("ordered_ids")
    if not isinstance(raw_ids, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display-fields/order.ordered_ids must be a list of integers",
        )
    try:
        ordered_ids = [int(v) for v in raw_ids]
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="display-fields/order.ordered_ids must be a list of integers",
        ) from exc
    try:
        instruments_service.reorder_display_fields(
            db, instrument=instrument, ordered_ids=ordered_ids, actor=user
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    db.commit()
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)


@router.post(
    "/sessions/{session_id}/instruments/{instrument_id}/identity"
)
async def instrument_set_identity(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Patch a single identity field (short_label or description)
    on an instrument. Backs the new-model card's intro-card inline
    edit toggles — the operator clicks ✎, types, clicks ✓, and the
    JS fetches this endpoint with just the field that changed.
    Mirrors the band2-state and help-text card pattern of small
    JSON POSTs that persist independently of the bottom Save button.
    """
    instrument, _ = bundle
    _require_instrument_editable(instrument.session)
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identity body must be JSON",
        ) from exc
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="identity body must be a JSON object",
        )
    if "short_label" in body:
        raw = body.get("short_label")
        try:
            instruments_service.update_short_label(
                db,
                instrument=instrument,
                short_label=(raw if isinstance(raw, str) else None),
                actor=user,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    if "description" in body:
        raw = body.get("description")
        instruments_service.update_instrument_description(
            db,
            instrument=instrument,
            description=(raw if isinstance(raw, str) else None),
            actor=user,
        )
    db.commit()
    return JSONResponse({"ok": True}, status_code=status.HTTP_200_OK)


@router.post("/sessions/{session_id}/instruments/{instrument_id}/visibility")
def instrument_visibility(
    visible_when_closed: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    lifecycle.set_responses_visible_when_closed(
        db,
        instrument=instrument,
        review_session=review_session,
        user=user,
        visible=visible_when_closed == "true",
        correlation_id=request_correlation_id(),
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
    )


