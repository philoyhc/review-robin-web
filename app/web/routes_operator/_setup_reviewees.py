"""Reviewees Setup page — the list / edit / add view, its CSV
import, bulk status actions, delete-all, and friendly-label editor.

Split out of ``_setup_rosters.py`` in Segment 17A PR 3; the shared
import / redirect / field-label plumbing now lives in ``_shared.py``.
The reviewee surface mirrors ``_setup_reviewers.py`` with the
identity field ``email_or_identifier`` and an extra ``profile_link``.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, User
from app.db.session import get_db
from app.services import assignments, csv_imports
from app.services import reviewees as reviewees_service
from app.services import session_lifecycle as lifecycle
from app.services.reviewees import RevieweeOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _SETUP_DEFAULT_CAP,
    _SETUP_FILTERED_CAP,
    _handle_import,
    _redirect_keeping_selection,
    _require_editable,
    _require_response_loss_ack,
    _save_field_labels,
    _templates,
)

router = APIRouter()


_REVIEWEE_SORT_KEYS = {
    "name",
    "email_or_identifier",
    "tag_1",
    "tag_2",
    "tag_3",
    "status",
    "updated_at",
}


def _reviewee_sort_value(reviewee, key: str):
    """Sort-key resolver for the Reviewees Setup table (Segment 13B
    Part 2 PR 6)."""
    return getattr(reviewee, key, None)


@router.post(
    "/sessions/{session_id}/reviewees/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewees_import_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _handle_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        acknowledge_response_loss=acknowledge_response_loss,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewees",
        existing_count_fn=csv_imports.existing_reviewee_count,
        parse_fn=csv_imports.parse_reviewee_csv,
        save_fn=csv_imports.save_reviewees,
    )


def _render_reviewees_page(
    *,
    request: Request,
    db: Session,
    user: User,
    review_session: ReviewSession,
    status_filter: str = "all",
    search: str = "",
    edit_id: int | None = None,
    add_mode: bool = False,
    edit_values: dict[str, str] | None = None,
    edit_error: str | None = None,
    selected_ids: set[int] | None = None,
    http_status: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render the Reviewees Setup page — the reviewee-side mirror of
    ``_render_reviewers_page`` (Segment 15F PR 4)."""
    is_ready = lifecycle.is_ready(review_session)
    if is_ready:
        edit_id = None
        add_mode = False

    all_reviewees = assignments.list_reviewees(db, review_session.id)
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-reviewees-{review_session.id}",
        valid_keys=_REVIEWEE_SORT_KEYS,
    )
    all_reviewees = views.apply_cookie_sort(
        all_reviewees,
        sort_spec,
        value_resolver=_reviewee_sort_value,
    )

    filtered = views.filter_reviewees_rows(
        all_reviewees, status=status_filter, search=search
    )
    is_filtered = status_filter != "all" or bool(search.strip())
    cap = _SETUP_FILTERED_CAP if is_filtered else _SETUP_DEFAULT_CAP
    capped = filtered[:cap]
    displayed_row_count = len(capped)

    reviewees = capped
    if edit_id is not None and edit_id not in {r.id for r in reviewees}:
        edited = next(
            (r for r in all_reviewees if r.id == edit_id), None
        )
        if edited is None:
            edit_id = None
        else:
            reviewees = [edited, *reviewees]

    if edit_values is None and edit_id is not None:
        edited = next(
            (r for r in reviewees if r.id == edit_id), None
        )
        if edited is not None:
            edit_values = {
                "name": edited.name,
                "email_or_identifier": edited.email_or_identifier,
                "profile_link": edited.profile_link or "",
                "tag_1": edited.tag_1 or "",
                "tag_2": edited.tag_2 or "",
                "tag_3": edited.tag_3 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "name": "",
            "email_or_identifier": "",
            "profile_link": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        }

    return _templates.TemplateResponse(
        request,
        "operator/session_reviewees.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewees": reviewees,
            "selected_ids": selected_ids or set(),
            "total_row_count": len(all_reviewees),
            "displayed_row_count": displayed_row_count,
            "filter_status": status_filter,
            "filter_search": search,
            "filter_status_options": views.REVIEWEES_STATUS_OPTIONS,
            "filter_search_options": views.reviewees_search_options(
                all_reviewees
            ),
            "existing_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
            "is_ready": is_ready,
            "fields_with_data": views.friendly_fields_with_data(
                review_session,
                assignments.reviewee_fields_with_data(db, review_session.id),
            ),
            "edit_id": edit_id,
            "add_mode": add_mode,
            "edit_values": edit_values,
            "edit_error": edit_error,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Reviewees"
            ),
        },
        status_code=http_status,
    )


@router.get("/sessions/{session_id}/reviewees", response_class=HTMLResponse)
def reviewees_list(
    request: Request,
    status_filter: str = Query(default="all", alias="status"),
    q: str = "",
    edit_id: int | None = None,
    add: int = 0,
    selected: list[int] = Query(default=[]),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_reviewees_page(
        request=request,
        db=db,
        user=user,
        review_session=review_session,
        status_filter=status_filter,
        search=q,
        edit_id=edit_id,
        add_mode=bool(add),
        selected_ids=set(selected),
    )


def _require_reviewee_in_session(
    db: Session, review_session: ReviewSession, reviewee_id: int
) -> Reviewee:
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.id == reviewee_id,
            Reviewee.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return reviewee


@router.post(
    "/sessions/{session_id}/reviewees/create",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewees_create(
    request: Request,
    name: str = Form(default=""),
    email_or_identifier: str = Form(default=""),
    profile_link: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    try:
        reviewees_service.create_reviewee(
            db,
            review_session=review_session,
            name=name,
            email_or_identifier=email_or_identifier,
            profile_link=profile_link,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        return _render_reviewees_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            add_mode=True,
            edit_values={
                "name": name,
                "email_or_identifier": email_or_identifier,
                "profile_link": profile_link,
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/reviewees/{reviewee_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewees_update(
    request: Request,
    reviewee_id: int,
    name: str = Form(default=""),
    email_or_identifier: str = Form(default=""),
    profile_link: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    reviewee = _require_reviewee_in_session(db, review_session, reviewee_id)
    try:
        reviewees_service.update_reviewee(
            db,
            reviewee=reviewee,
            name=name,
            email_or_identifier=email_or_identifier,
            profile_link=profile_link,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        return _render_reviewees_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=reviewee_id,
            edit_values={
                "name": name,
                "email_or_identifier": email_or_identifier,
                "profile_link": profile_link,
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewees",
        [reviewee_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewees/bulk-inactivate")
def reviewees_bulk_inactivate(
    reviewee_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewees_service.bulk_inactivate(
            db,
            review_session=review_session,
            reviewee_ids=reviewee_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewees",
        reviewee_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewees/bulk-reactivate")
def reviewees_bulk_reactivate(
    reviewee_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewees_service.bulk_reactivate(
            db,
            review_session=review_session,
            reviewee_ids=reviewee_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RevieweeOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewees",
        reviewee_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewees/delete-all")
def reviewees_delete_all(
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    csv_imports.delete_all_reviewees(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Allowlist of (form_param, source_field) the reviewee label editor
# accepts, mirroring ``app.services.field_labels._VALID_SOURCE_FIELDS``
# (Segment 15A Slice 3). Identity columns retired 2026-05-31 per
# ``guide/archive/participant_model_upgrade.md`` §3.7 — only the three tag
# slots remain.
_REVIEWEE_SLOTS: tuple[tuple[str, str], ...] = (
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
)


@router.post(
    "/sessions/{session_id}/reviewees/field-labels",
    response_class=RedirectResponse,
)
async def reviewees_save_field_labels(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the three reviewee tag labels for this session.

    Identity columns (Name / Email_Identifier / Profile) retired
    2026-05-31 per upgrade-doc §3.7; form fields for those names
    are silently ignored if submitted.
    """
    form = await request.form()
    submitted = {
        param: str(form.get(param, "")) for param, _ in _REVIEWEE_SLOTS
    }
    _save_field_labels(
        db,
        review_session=review_session,
        user=user,
        source_type="reviewee",
        slots=_REVIEWEE_SLOTS,
        submitted=submitted,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
    )
