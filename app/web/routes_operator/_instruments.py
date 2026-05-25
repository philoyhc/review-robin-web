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

from typing import Any

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
from app.web import views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _lifecycle_error_response,
    _require_instrument_editable,
    _templates,
)

router = APIRouter()


# --------------------------------------------------------------------------- #
# Slice-local helpers. The cross-slice edit-lock guards
# (``_require_editable`` / ``_require_response_loss_ack`` /
# ``_lifecycle_error_response`` / ``_require_instrument_editable``)
# live in ``_shared.py``.
# --------------------------------------------------------------------------- #


def _require_instrument_in_session(
    instrument_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    db: Session = Depends(get_db),
) -> tuple[Instrument, ReviewSession]:
    instrument = db.execute(
        select(Instrument).where(
            Instrument.id == instrument_id,
            Instrument.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if instrument is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return instrument, review_session


@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    editing: int | None = Query(default=None),
    saved: int | None = Query(default=None),
    rtd_error: str | None = Query(default=None),
    rtd_id: int | None = Query(default=None),
    rf_save_error: str | None = Query(default=None),
    editing_rtd_id: int | None = Query(default=None),
    rtd_delete_blocked_id: int | None = Query(default=None),
    rtd_delete_blocked_rfs: int | None = Query(default=None),
    rtd_delete_blocked_instruments: int | None = Query(default=None),
    rtd_delete_blocked_responses: int | None = Query(default=None),
    rtd_delete_blocked_assignments: int | None = Query(default=None),
    rtd_would_empty_id: int | None = Query(default=None),
    rtd_would_empty_instruments: str | None = Query(default=None),
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
        rtd_error=rtd_error,
        rtd_id=rtd_id,
        rf_save_error=rf_save_error,
        editing_rtd_id=editing_rtd_id,
        rtd_delete_blocked_id=rtd_delete_blocked_id,
        rtd_delete_blocked_rfs=rtd_delete_blocked_rfs,
        rtd_delete_blocked_instruments=rtd_delete_blocked_instruments,
        rtd_delete_blocked_responses=rtd_delete_blocked_responses,
        rtd_delete_blocked_assignments=rtd_delete_blocked_assignments,
        rtd_would_empty_id=rtd_would_empty_id,
        rtd_would_empty_instruments=rtd_would_empty_instruments,
        sort_save_error=sort_save_error,
        sort_save_error_instrument_id=sort_save_error_instrument_id,
    )
    return _templates.TemplateResponse(
        request, "operator/instruments_index.html", context
    )


def _instruments_redirect(
    session_id: int, fragment: str | None = None
) -> RedirectResponse:
    """Redirect to the Instruments index, optionally landing on an
    in-page anchor.

    Per-instrument actions (open / close / visibility / save) should
    pass ``fragment="instrument-{id}"`` so the operator lands on the
    instrument they were just acting on instead of being yanked to
    the top of the page. Bulk actions (accepting/visibility all-on/
    off) pass no fragment — they affect the whole list, so landing
    at the top is appropriate.
    """
    url = f"/operator/sessions/{session_id}/instruments"
    if fragment:
        url = f"{url}#{fragment}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


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
    if instrument.is_new_model:
        try:
            band1 = instruments_service.parse_band1_form(form)
        except instruments_service.Band1ParseError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        link3_mode, link3_pairs = instruments_service.parse_link3_form(form)
        instruments_service.set_band1_assignment_rules(
            db, instrument=instrument, actor=user, **band1
        )
        instruments_service.set_unit_of_review(
            db,
            instrument=instrument,
            mode=link3_mode,
            boundary_pairs=link3_pairs,
            actor=user,
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

    kinds = [str(v) for v in form.getlist("kind")]
    raw_ids = [str(v) for v in form.getlist("id")]
    orders = [str(v) for v in form.getlist("order")]
    labels = [str(v) for v in form.getlist("label")]
    # ``visible_ids`` and ``required_ids`` are submitted as raw row
    # ids so they can carry either real ints or ``new_N`` placeholders
    # for JS-added rows.
    visible_id_strs: set[str] = {
        str(v) for v in form.getlist("visible_ids")
    }
    # Segment 13C — the group-scoped Display Fields table submits
    # ``group_by_ids`` (the tag rows ticked *Group by*). On a
    # group-scoped instrument a tag row's Include is derived from
    # its Group-by tick, so these ids fold into ``visible_ids``
    # below and also drive the encoded ``group_kind`` boundary spec.
    group_by_id_strs: set[str] = {
        str(v) for v in form.getlist("group_by_ids")
    }
    required_id_strs: set[str] = {
        str(v) for v in form.getlist("required_ids")
    }
    # JS-deferred deletes: each ✗ click appends a hidden
    # ``response_delete_ids`` input on the bulk-save form so Cancel
    # discards the deletion.
    response_delete_ids: set[int] = set()
    for raw in form.getlist("response_delete_ids"):
        try:
            response_delete_ids.add(int(str(raw)))
        except ValueError:
            continue
    # Response Fields Help: per-row help_text + help_text_visible.
    # The Help card emits parallel ``help_text_id`` + ``help_text``
    # arrays plus a ``help_text_visible_ids`` set. Help ids may also
    # be ``new_N`` placeholders for JS-added rows.
    help_text_id_strs = [str(v) for v in form.getlist("help_text_id")]
    help_texts = [str(v) for v in form.getlist("help_text")]
    help_text_visible_id_strs: set[str] = {
        str(v) for v in form.getlist("help_text_visible_ids")
    }
    help_by_id_str: dict[str, str] = {}
    if len(help_text_id_strs) == len(help_texts):
        for raw_id, text in zip(help_text_id_strs, help_texts):
            help_by_id_str[raw_id] = text

    if not (len(kinds) == len(raw_ids) == len(orders) == len(labels)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bulk save row inputs are misaligned.",
        )

    # Slice 4d Gap 2: refuse to save an instrument with zero
    # Response Fields rows. Compute the post-save RF count up-front
    # (existing - deletes + new_* draft adds) and bounce back to the
    # editing context with an inline error banner if it would be
    # zero. Symmetric with the cascade-side guard on the Response
    # Type Definitions card.
    existing_rf_count = int(
        db.execute(
            select(func.count(instruments_service.InstrumentResponseField.id)).where(
                instruments_service.InstrumentResponseField.instrument_id
                == instrument.id
            )
        ).scalar_one()
    )
    new_response_count = sum(
        1
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    )
    # Deduplicate ``new_*`` ids — duplicates in the form payload
    # don't create extra rows.
    new_unique_ids = {
        raw_id
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    }
    new_response_count = len(new_unique_ids)
    post_save_rf_count = (
        existing_rf_count - len(response_delete_ids) + new_response_count
    )
    if post_save_rf_count <= 0:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&rf_save_error=An+instrument+must+have+at+least+one+response+field."
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )


    # 1. Apply JS-deferred deletes first so the bulk-save step below
    #    sees a clean existing-rows list. Use ``confirm=True`` since
    #    the page is only editable while the session is in setup; no
    #    responses can exist yet.
    for delete_id in response_delete_ids:
        field = db.get(instruments_service.InstrumentResponseField, delete_id)
        if field is None or field.instrument_id != instrument.id:
            continue
        try:
            instruments_service.delete_response_field(
                db, field=field, confirm=True, actor=user
            )
        except instruments_service.ResponsesPresentError:
            # Defensive: if a concurrent edit made the session ongoing
            # between the GET and POST, just skip this row.
            continue

    # 2. Allocate real ids for any ``new_*`` response rows. The route
    #    creates them via ``add_default_response_field``, passing the
    #    operator-chosen RTD (Slice 4c), the typed label, and the
    #    Required flag so the new row lands at the right shape on
    #    Save. ``add_default_response_field`` slugifies the label
    #    into a non-conflicting ``field_key`` (falling back to the
    #    auto ``rating{N}`` series when the label is blank).
    #    The bulk-save step below then folds in any subsequent edits.
    new_rtd_targets = [str(v) for v in form.getlist("new_rtd_target")]
    new_rtd_ids = [str(v) for v in form.getlist("new_rtd_id")]
    new_rtd_by_draft: dict[str, int] = {}
    if len(new_rtd_targets) == len(new_rtd_ids):
        for target, rtd_id_str in zip(new_rtd_targets, new_rtd_ids):
            try:
                new_rtd_by_draft[target] = int(rtd_id_str)
            except ValueError:
                continue
    new_label_by_draft: dict[str, str] = {}
    for kind, raw_id, label_value in zip(kinds, raw_ids, labels):
        if kind == "response" and raw_id.startswith("new_"):
            new_label_by_draft[raw_id] = label_value

    new_id_map: dict[str, int] = {}
    for kind, raw_id in zip(kinds, raw_ids):
        if kind != "response":
            continue
        if not raw_id.startswith("new_") or raw_id in new_id_map:
            continue
        if raw_id in {str(d) for d in response_delete_ids}:
            continue  # added then deleted before save — skip
        new_field = instruments_service.add_default_response_field(
            db,
            instrument=instrument,
            after_field_id=None,
            rtd_id=new_rtd_by_draft.get(raw_id),
            label=new_label_by_draft.get(raw_id),
            required=raw_id in required_id_strs,
            actor=user,
        )
        new_id_map[raw_id] = new_field.id

    def _resolve_id(raw: str) -> int | None:
        if raw.startswith("new_"):
            return new_id_map.get(raw)
        try:
            return int(raw)
        except ValueError:
            return None

    visible_ids: set[int] = set()
    for s in visible_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            visible_ids.add(rid)
    group_by_ids: set[int] = set()
    for s in group_by_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            group_by_ids.add(rid)
    # On a group-scoped instrument a tag row's Include == its
    # Group-by tick; fold so ``bulk_save_fields`` stores ``visible``
    # for the tag rows. The Name row's Include rides ``visible_ids``
    # directly.
    if instrument.group_kind is not None:
        visible_ids |= group_by_ids
    required_ids: set[int] = set()
    for s in required_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            required_ids.add(rid)
    help_text_visible_ids: set[int] = set()
    for s in help_text_visible_id_strs:
        rid = _resolve_id(s)
        if rid is not None:
            help_text_visible_ids.add(rid)
    help_by_id: dict[int, str] = {}
    for raw_id, text in help_by_id_str.items():
        rid = _resolve_id(raw_id)
        if rid is not None:
            help_by_id[rid] = text

    rows: list[dict[str, Any]] = []
    for kind, raw_id, raw_order, label in zip(kinds, raw_ids, orders, labels):
        row_id = _resolve_id(raw_id)
        if row_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk save id values must be integers or new_*.",
            )
        # Skip rows the operator marked deleted in this same submit.
        if kind == "response" and row_id in response_delete_ids:
            continue
        try:
            row_order = int(raw_order)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk save order values must be integers.",
            )
        row: dict[str, Any] = {"kind": kind, "id": row_id, "order": row_order}
        if kind == "display":
            row["label"] = label
            row["visible"] = row_id in visible_ids
        elif kind == "response":
            row["label"] = label
            row["required"] = row_id in required_ids
            if row_id in help_by_id:
                row["help_text"] = help_by_id[row_id]
                row["help_text_visible"] = row_id in help_text_visible_ids
        rows.append(row)

    instruments_service.bulk_save_fields(
        db, instrument=instrument, rows=rows, actor=user
    )
    # Segment 13C — persist the group-boundary spec encoded from the
    # tag rows the operator ticked *Group by*, ordered by the
    # display-field order. Only group-scoped instruments carry it.
    if instrument.group_kind is not None:
        df_by_id = {f.id: f for f in instrument.display_fields}
        boundary_fields = sorted(
            (df_by_id[i] for i in group_by_ids if i in df_by_id),
            key=lambda f: f.order,
        )
        instruments_service.set_group_boundary(
            db,
            instrument=instrument,
            boundary_pairs=[
                (f.source_type, f.source_field) for f in boundary_fields
            ],
            actor=user,
        )
    # Sort spec (Segment 13B PR 2) — parsed from the Display
    # Fields card's hidden ``sort_display_field_id`` + ``sort_dir``
    # parallel arrays. Empty / missing → clear the spec back to
    # the unsorted default. The service-layer validator owns
    # length / dup / cross-instrument / dir checks; rejections
    # bubble up as a per-instrument banner via the redirect.
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
    # Section A — instrument description shares the same Save / Cancel
    # state machine as the tables. Only push the update when the value
    # actually changed to avoid an audit-event for a no-op edit.
    if "description" in form:
        submitted_desc = form.get("description")
        cleaned = (
            submitted_desc.strip() if isinstance(submitted_desc, str) else None
        ) or None
        if cleaned != instrument.description:
            instruments_service.update_instrument_description(
                db, instrument=instrument, description=cleaned, actor=user
            )
    # Section A — short_label shares the same Save / Cancel state machine
    # as description. Per Segment 11L, the field is reviewer-facing and
    # capped at 32 chars (HTML5 ``maxlength`` is the user-visible
    # guardrail; the service helper raises ValueError as a defensive
    # fallback that yields HTTP 400).
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
    # Section E — Assignment Rule picker (Segment 15B Slice 2a).
    # Rides the same bulk-save form via the picker `<select>`'s
    # ``form="dfsave-{id}"`` attribute. PIN-only: the service helper
    # writes ``instruments.rule_set_id`` and emits
    # ``instrument.rule_pinned``; no Assignment rows are touched.
    # Materialisation belongs to Slice 3a / Slice 4 (page-level
    # Generate). Empty string posts as "— No rule —" and clears the
    # pin to NULL.
    if "rule_set_id" in form:
        raw_rule_set_id = form.get("rule_set_id")
        if not isinstance(raw_rule_set_id, str) or raw_rule_set_id == "":
            new_rule_set_id: int | None = None
        else:
            try:
                new_rule_set_id = int(raw_rule_set_id)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="rule_set_id must be an integer.",
                ) from exc
        try:
            instruments_service.pin_rule_set(
                db,
                instrument=instrument,
                rule_set_id=new_rule_set_id,
                actor=user,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    # Redirect with ``?saved={iid}`` so the page renders a flash
    # confirmation. Wave 4 PR 2 — the ``?editing`` param is now
    # PRESERVED on a successful Save so the operator stays in edit
    # mode and can keep working without clicking Unlock again.
    # Lock/Unlock owns the gating; Save owns persistence.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?editing={instrument.id}&saved={instrument.id}"
            f"#instrument-{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/add")
def instruments_add(
    after: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    instrument = instruments_service.create_instrument(
        db, review_session=review_session, after_instrument_id=after, actor=user
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/add-group")
def instruments_add_group(
    after: int | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Create a group-scoped instrument (Segment 13C).

    The new instrument starts with the no-boundary sentinel
    (``GROUP_KIND_SENTINEL``); the operator picks boundary tags via
    the Display Fields table's *Group by* column.
    """
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
    """Create a new-model instrument — concept-test card for the
    Instrument Builder (``guide/instrument_builder.md``). Behaves
    exactly like ``instruments_add`` at the service layer; the
    template renders the new row with the bands placeholder layout
    via the ``is_new_model`` flag.
    """
    _require_instrument_editable(review_session)
    instrument = instruments_service.create_instrument(
        db,
        review_session=review_session,
        after_instrument_id=after,
        actor=user,
        is_new_model=True,
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
    try:
        instruments_service.set_band2_state(
            db, instrument=instrument, state=body, actor=user
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
    sample_pick = instruments_service.find_sample_in_scope_reviewee(
        db,
        instrument=instrument,
        link1_mode=str(body.get("link1_mode") or "all"),
        link1_combinator=str(body.get("link1_combinator") or "AND"),
        link1_rules=_rule_list(body.get("link1_rules")),
        link2_mode=str(body.get("link2_mode") or "all"),
        link2_combinator=str(body.get("link2_combinator") or "AND"),
        link2_rules=_rule_list(body.get("link2_rules")),
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
            }
        },
        status_code=status.HTTP_200_OK,
    )


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


