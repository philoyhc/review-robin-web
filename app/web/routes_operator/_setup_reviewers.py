"""Reviewers Setup page — the list / edit / add view, its CSV
import, bulk status actions, delete-all, and friendly-label editor.

Split out of ``_setup_rosters.py`` in Segment 17A PR 3; the shared
import / redirect / field-label plumbing now lives in ``_shared.py``.
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

from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import assignments, csv_imports
from app.services import reviewers as reviewers_service
from app.services import session_lifecycle as lifecycle
from app.services.reviewers import ReviewerOperationError
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


_REVIEWER_SORT_KEYS = {
    "name", "email", "tag_1", "tag_2", "tag_3", "status", "updated_at",
}


def _reviewer_sort_value(reviewer, key: str):
    """Sort-key resolver for the Reviewers Setup table (Segment 13B
    Part 2 PR 6)."""
    return getattr(reviewer, key, None)


@router.post(
    "/sessions/{session_id}/reviewers/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewers_import_submit(
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
        kind="reviewers",
        existing_count_fn=csv_imports.existing_reviewer_count,
        parse_fn=csv_imports.parse_reviewer_csv,
        save_fn=csv_imports.save_reviewers,
    )


def _render_reviewers_page(
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
    """Render the Reviewers Setup page.

    Shared by the GET route and the create / update error-render
    paths (Segment 15F PR 3). ``edit_id`` / ``add_mode`` drive the
    server-rendered edit state; ``edit_values`` / ``edit_error``
    carry an operator's rejected submission back into the edit row.
    """
    is_ready = lifecycle.is_ready(review_session)
    if is_ready:
        # Edit / Add are setup mutations — not reachable on an
        # ongoing session. Fall back to the plain list.
        edit_id = None
        add_mode = False

    all_reviewers = assignments.list_reviewers(db, review_session.id)
    # Segment 13B Part 2 PR 6 — cookie-backed personal sort.
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-reviewers-{review_session.id}",
        valid_keys=_REVIEWER_SORT_KEYS,
    )
    all_reviewers = views.apply_cookie_sort(
        all_reviewers,
        sort_spec,
        value_resolver=_reviewer_sort_value,
    )

    # Segment 15F PR 2 — server-side search + status filter, 200/500
    # cap (200 unfiltered, 500 when either filter is applied). Cap is
    # applied after sort so the visible window is the same as the
    # operator's chosen sort order.
    filtered = views.filter_reviewers_rows(
        all_reviewers, status=status_filter, search=search
    )
    is_filtered = status_filter != "all" or bool(search.strip())
    cap = _SETUP_FILTERED_CAP if is_filtered else _SETUP_DEFAULT_CAP
    capped = filtered[:cap]
    displayed_row_count = len(capped)

    reviewers = capped
    # Force-include the edited row when it falls outside the cap so
    # the operator's edit target is always rendered.
    if edit_id is not None and edit_id not in {r.id for r in reviewers}:
        edited = next(
            (r for r in all_reviewers if r.id == edit_id), None
        )
        if edited is None:
            edit_id = None  # stale id — drop edit mode
        else:
            reviewers = [edited, *reviewers]

    # Resolve the edit-row prefill values: from the DB row for a
    # plain edit GET, or left as the caller-supplied dict on an
    # error re-render.
    if edit_values is None and edit_id is not None:
        edited = next(
            (r for r in reviewers if r.id == edit_id), None
        )
        if edited is not None:
            edit_values = {
                "name": edited.name,
                "email": edited.email,
                "tag_1": edited.tag_1 or "",
                "tag_2": edited.tag_2 or "",
                "tag_3": edited.tag_3 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "name": "",
            "email": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        }

    return _templates.TemplateResponse(
        request,
        "operator/session_reviewers.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewers": reviewers,
            "selected_ids": selected_ids or set(),
            "total_row_count": len(all_reviewers),
            "displayed_row_count": displayed_row_count,
            "filter_status": status_filter,
            "filter_search": search,
            "filter_status_options": views.REVIEWERS_STATUS_OPTIONS,
            "filter_search_options": views.reviewers_search_options(
                all_reviewers
            ),
            "existing_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
            "is_ready": is_ready,
            "fields_with_data": views.friendly_fields_with_data(
                review_session,
                assignments.reviewer_fields_with_data(db, review_session.id),
            ),
            "edit_id": edit_id,
            "add_mode": add_mode,
            "edit_values": edit_values,
            "edit_error": edit_error,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Reviewers"
            ),
        },
        status_code=http_status,
    )


@router.get("/sessions/{session_id}/reviewers", response_class=HTMLResponse)
def reviewers_list(
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
    return _render_reviewers_page(
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


def _require_reviewer_in_session(
    db: Session, review_session: ReviewSession, reviewer_id: int
) -> Reviewer:
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.id == reviewer_id,
            Reviewer.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return reviewer


@router.post(
    "/sessions/{session_id}/reviewers/create",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewers_create(
    request: Request,
    name: str = Form(default=""),
    email: str = Form(default=""),
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
        reviewers_service.create_reviewer(
            db,
            review_session=review_session,
            name=name,
            email=email,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ReviewerOperationError as exc:
        return _render_reviewers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            add_mode=True,
            edit_values={
                "name": name,
                "email": email,
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/reviewers/{reviewer_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewers_update(
    request: Request,
    reviewer_id: int,
    name: str = Form(default=""),
    email: str = Form(default=""),
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
    reviewer = _require_reviewer_in_session(db, review_session, reviewer_id)
    try:
        reviewers_service.update_reviewer(
            db,
            reviewer=reviewer,
            name=name,
            email=email,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ReviewerOperationError as exc:
        return _render_reviewers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=reviewer_id,
            edit_values={
                "name": name,
                "email": email,
                "tag_1": tag_1,
                "tag_2": tag_2,
                "tag_3": tag_3,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewers",
        [reviewer_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewers/bulk-inactivate")
def reviewers_bulk_inactivate(
    reviewer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewers_service.bulk_inactivate(
            db,
            review_session=review_session,
            reviewer_ids=reviewer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ReviewerOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewers",
        reviewer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewers/bulk-reactivate")
def reviewers_bulk_reactivate(
    reviewer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        reviewers_service.bulk_reactivate(
            db,
            review_session=review_session,
            reviewer_ids=reviewer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ReviewerOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/reviewers",
        reviewer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/reviewers/delete-all")
def reviewers_delete_all(
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
    csv_imports.delete_all_reviewers(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Allowlist of (form_param, source_field) the reviewer label editor
# accepts, mirroring ``app.services.field_labels._VALID_SOURCE_FIELDS``
# (Segment 15A Slice 3).
_REVIEWER_SLOTS: tuple[tuple[str, str], ...] = (
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
)


@router.post(
    "/sessions/{session_id}/reviewers/field-labels",
    response_class=RedirectResponse,
)
async def reviewers_save_field_labels(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the three reviewer tag labels for this session."""
    form = await request.form()
    submitted = {
        param: str(form.get(param, "")) for param, _ in _REVIEWER_SLOTS
    }
    _save_field_labels(
        db,
        review_session=review_session,
        user=user,
        source_type="reviewer",
        slots=_REVIEWER_SLOTS,
        submitted=submitted,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
    )
