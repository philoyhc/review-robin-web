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
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import (
    assignments,
    csv_imports,
    field_labels as field_labels_service,
    relationships as relationships_service,
)
from app.services import session_lifecycle as lifecycle
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
        if kind == "reviewers":
            # Segment 15F PR 2 — the reviewers template's right-side
            # operator-actions card needs the filter / cap context
            # even on the error-render path so the form keeps reading
            # consistent.
            context.update(
                {
                    "total_row_count": len(list_items),
                    "displayed_row_count": len(list_items),
                    "filter_status": "all",
                    "filter_search": "",
                    "filter_status_options": views.REVIEWERS_STATUS_OPTIONS,
                    "filter_search_options": (
                        views.reviewers_search_options(list_items)
                    ),
                    "is_ready": lifecycle.is_ready(review_session),
                    "fields_with_data": assignments.reviewer_fields_with_data(
                        db, review_session.id
                    ),
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


@router.get("/sessions/{session_id}/reviewers", response_class=HTMLResponse)
def reviewers_list(
    request: Request,
    status: str = "all",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
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
        all_reviewers, status=status, search=q
    )
    is_filtered = status != "all" or bool(q.strip())
    cap = _REVIEWERS_FILTERED_CAP if is_filtered else _REVIEWERS_DEFAULT_CAP
    reviewers = filtered[:cap]

    return _templates.TemplateResponse(
        request,
        "operator/session_reviewers.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewers": reviewers,
            "total_row_count": len(all_reviewers),
            "displayed_row_count": len(reviewers),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.REVIEWERS_STATUS_OPTIONS,
            "filter_search_options": views.reviewers_search_options(
                all_reviewers
            ),
            "existing_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
            "is_ready": lifecycle.is_ready(review_session),
            "fields_with_data": assignments.reviewer_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Reviewers"
            ),
        },
    )


@router.get("/sessions/{session_id}/reviewees", response_class=HTMLResponse)
def reviewees_list(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reviewees = assignments.list_reviewees(db, review_session.id)
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name=f"rrw-sort-reviewees-{review_session.id}",
        valid_keys=_REVIEWEE_SORT_KEYS,
    )
    reviewees = views.apply_cookie_sort(
        reviewees,
        sort_spec,
        value_resolver=_reviewee_sort_value,
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_reviewees.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewees": reviewees,
            "existing_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
            "is_ready": lifecycle.is_ready(review_session),
            "fields_with_data": assignments.reviewee_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Reviewees"
            ),
        },
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
    rows = views.apply_cookie_sort(
        rows,
        sort_spec,
        value_resolver=_relationship_sort_value,
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_relationships.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "relationships": rows,
            "reviewer_by_id": reviewer_by_id,
            "reviewee_by_id": reviewee_by_id,
            "existing_count": len(rows),
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
