"""Setup rosters — Reviewers / Reviewees / Relationships pages,
their CSV imports, and their delete-all destructive actions.
Slice 6 of the major refactor; Relationships routes added in
Segment 15D PR 2.

Source ranges in pre-refactor ``routes_operator.py``: 528-667,
2122-2180, 2296-2348.
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

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import (
    assignments,
    csv_imports,
    field_labels as field_labels_service,
    relationships as relationships_service,
    reviewees as reviewees_service,
    reviewers as reviewers_service,
)
from app.services import session_lifecycle as lifecycle
from app.services.reviewees import RevieweeOperationError
from app.services.reviewers import ReviewerOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _require_editable,
    _require_response_loss_ack,
    _templates,
)


router = APIRouter()


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


async def _handle_import(
    *,
    request: Request,
    file: UploadFile,
    confirm_replace: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    content = await file.read()
    result = parse_fn(content)
    if not result.is_blocked:
        result.issues.extend(
            csv_imports.check_cross_table_identity(
                db,
                session_id=review_session.id,
                rows=result.rows,
                kind=kind,
            )
        )
    existing = existing_count_fn(db, review_session.id)
    assignment_count = csv_imports.existing_assignment_count(db, review_session.id)

    if kind == "reviewers":
        template = "operator/session_reviewers.html"
        crumb_label = "Reviewers"
        list_key = "reviewers"
        list_items = assignments.list_reviewers(db, review_session.id)
    else:
        template = "operator/session_reviewees.html"
        crumb_label = "Reviewees"
        list_key = "reviewees"
        list_items = assignments.list_reviewees(db, review_session.id)

    def render(status_code: int = status.HTTP_200_OK) -> HTMLResponse:
        context: dict[str, object] = {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            list_key: list_items,
            "existing_count": existing,
            "assignment_count": assignment_count,
            "issues": result.issues,
            "filename": file.filename,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, crumb_label
            ),
        }
        if kind in ("reviewers", "reviewees"):
            # Segment 15F — the Reviewers / Reviewees templates'
            # right-side operator-actions card needs the filter / cap
            # context even on the CSV-import error-render path so the
            # form keeps reading consistent. The error render is
            # never an edit state.
            if kind == "reviewers":
                status_options = views.REVIEWERS_STATUS_OPTIONS
                search_options = views.reviewers_search_options(list_items)
                fields_with_data = assignments.reviewer_fields_with_data(
                    db, review_session.id
                )
            else:
                status_options = views.REVIEWEES_STATUS_OPTIONS
                search_options = views.reviewees_search_options(list_items)
                fields_with_data = assignments.reviewee_fields_with_data(
                    db, review_session.id
                )
            context.update(
                {
                    "total_row_count": len(list_items),
                    "displayed_row_count": len(list_items),
                    "filter_status": "all",
                    "filter_search": "",
                    "filter_status_options": status_options,
                    "filter_search_options": search_options,
                    "is_ready": lifecycle.is_ready(review_session),
                    "fields_with_data": fields_with_data,
                    "edit_id": None,
                    "add_mode": False,
                    "edit_values": None,
                    "edit_error": None,
                }
            )
        return _templates.TemplateResponse(
            request, template, context, status_code=status_code
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/{kind}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


_REVIEWER_SORT_KEYS = {"name", "email", "tag_1", "tag_2", "tag_3", "status"}
_REVIEWEE_SORT_KEYS = {
    "name",
    "email_or_identifier",
    "tag_1",
    "tag_2",
    "tag_3",
    "status",
}


def _reviewer_sort_value(reviewer, key: str):
    """Sort-key resolver for the Reviewers Setup table (Segment 13B
    Part 2 PR 6)."""
    return getattr(reviewer, key, None)


def _reviewee_sort_value(reviewee, key: str):
    """Sort-key resolver for the Reviewees Setup table (Segment 13B
    Part 2 PR 6)."""
    return getattr(reviewee, key, None)


_REVIEWERS_DEFAULT_CAP: int = 200
_REVIEWERS_FILTERED_CAP: int = 500


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
    cap = _REVIEWERS_FILTERED_CAP if is_filtered else _REVIEWERS_DEFAULT_CAP
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
            "fields_with_data": assignments.reviewer_fields_with_data(
                db, review_session.id
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewers/bulk-inactivate")
def reviewers_bulk_inactivate(
    reviewer_ids: list[int] = Form(default=[]),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewers/bulk-reactivate")
def reviewers_bulk_reactivate(
    reviewer_ids: list[int] = Form(default=[]),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewers",
        status_code=status.HTTP_303_SEE_OTHER,
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
    cap = _REVIEWERS_FILTERED_CAP if is_filtered else _REVIEWERS_DEFAULT_CAP
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
            "fields_with_data": assignments.reviewee_fields_with_data(
                db, review_session.id
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewees/bulk-inactivate")
def reviewees_bulk_inactivate(
    reviewee_ids: list[int] = Form(default=[]),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/reviewees/bulk-reactivate")
def reviewees_bulk_reactivate(
    reviewee_ids: list[int] = Form(default=[]),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/reviewees",
        status_code=status.HTTP_303_SEE_OTHER,
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


# ---------------------------------------------------------------------------
# Relationships (Segment 15D PR 2)
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/relationships", response_class=HTMLResponse)
def relationships_list(
    request: Request,
    search_by: str = "reviewer",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_relationships_page(
        request=request,
        review_session=review_session,
        user=user,
        db=db,
        issues=[],
        filename=None,
        search_by=search_by,
        search=q,
    )


@router.post(
    "/sessions/{session_id}/relationships/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def relationships_import_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    content = await file.read()
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    result = relationships_service.parse_relationship_csv(
        content, reviewers=reviewers, reviewees=reviewees
    )

    existing = relationships_service.existing_count(db, review_session.id)
    if result.is_blocked:
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=result.issues,
            filename=file.filename,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if existing > 0 and confirm_replace != "true":
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=result.issues,
            filename=file.filename,
            missing_confirm=True,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    relationships_service.save_relationships(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/relationships",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/relationships/delete-all")
def relationships_delete_all(
    confirm: str | None = Form(default=None),
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
    relationships_service.delete_all_relationships(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/relationships",
        status_code=status.HTTP_303_SEE_OTHER,
    )


_RELATIONSHIP_SORT_KEYS = {
    "reviewer", "reviewee", "tag_1", "tag_2", "tag_3", "status",
}


def _render_relationships_page(
    *,
    request: Request,
    review_session: ReviewSession,
    user: User,
    db: Session,
    issues: list,
    filename: str | None,
    missing_confirm: bool = False,
    search_by: str = "reviewer",
    search: str = "",
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    rows = relationships_service.list_for_session(db, review_session.id)
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    reviewer_by_id = {r.id: r for r in reviewers}
    reviewee_by_id = {r.id: r for r in reviewees}
    # Segment 13B Part 2 PR 7 — cookie-backed personal sort.
    # ``reviewer`` / ``reviewee`` resolve via the lookup maps so
    # sort matches the rendered identity (email) rather than the
    # raw FK id; tags + status resolve directly on the row.
    def _relationship_sort_value(row, key: str):
        if key == "reviewer":
            reviewer = reviewer_by_id.get(row.reviewer_id)
            return reviewer.email if reviewer else None
        if key == "reviewee":
            reviewee = reviewee_by_id.get(row.reviewee_id)
            return reviewee.email_or_identifier if reviewee else None
        return getattr(row, key, None)

    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-relationships-{review_session.id}",
        valid_keys=_RELATIONSHIP_SORT_KEYS,
    )
    all_rows = views.apply_cookie_sort(
        rows,
        sort_spec,
        value_resolver=_relationship_sort_value,
    )

    # Segment 15F PR 5 — locate-a-pair search: the ``search_by``
    # dropdown picks which side of the pair the search box matches.
    # 200/500 cap mirrors Reviewers / Reviewees.
    search_dimension = search_by if search_by == "reviewee" else "reviewer"
    filtered = views.filter_relationships_rows(
        all_rows,
        reviewer_by_id=reviewer_by_id,
        reviewee_by_id=reviewee_by_id,
        search_by=search_dimension,
        search=search,
    )
    is_filtered = bool(search.strip())
    cap = _REVIEWERS_FILTERED_CAP if is_filtered else _REVIEWERS_DEFAULT_CAP
    capped = filtered[:cap]

    return _templates.TemplateResponse(
        request,
        "operator/session_relationships.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "relationships": capped,
            "reviewer_by_id": reviewer_by_id,
            "reviewee_by_id": reviewee_by_id,
            "existing_count": len(all_rows),
            "total_row_count": len(all_rows),
            "displayed_row_count": len(capped),
            "filter_search_by": search_dimension,
            "filter_search": search,
            "filter_search_by_options": views.RELATIONSHIPS_SEARCH_BY_OPTIONS,
            "filter_search_options": views.relationships_search_options(
                all_rows,
                reviewer_by_id=reviewer_by_id,
                reviewee_by_id=reviewee_by_id,
                search_by=search_dimension,
            ),
            "fields_with_data": relationships_service.fields_with_data(
                db, review_session.id
            ),
            "issues": issues,
            "missing_confirm": missing_confirm,
            "filename": filename,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Relationships"
            ),
        },
        status_code=status_code,
    )


# ── Segment 15A Slice 3 — per-page friendly-label editors ──────────────


# Allowlist of (source_field) values each editor accepts, mirroring
# ``app.services.field_labels._VALID_SOURCE_FIELDS``. Each tuple is
# (form_param_name, source_field) since form-param names must be
# valid Python identifiers (the ``pair_context`` source_fields are
# bare digits, so the form names get a ``slot_`` prefix).
_REVIEWER_SLOTS: tuple[tuple[str, str], ...] = (
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
)
_REVIEWEE_SLOTS: tuple[tuple[str, str], ...] = (
    ("name", "name"),
    ("email_or_identifier", "email_or_identifier"),
    ("profile_link", "profile_link"),
    ("tag_1", "tag_1"),
    ("tag_2", "tag_2"),
    ("tag_3", "tag_3"),
)
_PAIR_CONTEXT_SLOTS: tuple[tuple[str, str], ...] = (
    ("slot_1", "1"),
    ("slot_2", "2"),
    ("slot_3", "3"),
)


def _save_field_labels(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    source_type: str,
    slots: tuple[tuple[str, str], ...],
    submitted: dict[str, str],
    correlation_id: str | None,
) -> None:
    """Upsert / clear per submitted slot.

    Rejected with 409 when ``is_ready`` — labels are locked
    alongside the rest of the page's data on a live session;
    operators revert to draft to rename.
    """
    if lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to "
                "draft to rename labels."
            ),
        )
    for form_param, source_field in slots:
        value = (submitted.get(form_param) or "").strip()
        if value:
            field_labels_service.upsert(
                db,
                review_session,
                source_type=source_type,
                source_field=source_field,
                label=value,
                user=user,
                correlation_id=correlation_id,
            )
        else:
            field_labels_service.clear(
                db,
                review_session,
                source_type=source_type,
                source_field=source_field,
                user=user,
                correlation_id=correlation_id,
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
    """Save the six reviewee labels (identity + tags) for this session."""
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


@router.post(
    "/sessions/{session_id}/relationships/field-labels",
    response_class=RedirectResponse,
)
async def relationships_save_field_labels(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the three pair-context labels for this session."""
    form = await request.form()
    submitted = {
        param: str(form.get(param, "")) for param, _ in _PAIR_CONTEXT_SLOTS
    }
    _save_field_labels(
        db,
        review_session=review_session,
        user=user,
        source_type="pair_context",
        slots=_PAIR_CONTEXT_SLOTS,
        submitted=submitted,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/relationships",
        status_code=status.HTTP_303_SEE_OTHER,
    )
