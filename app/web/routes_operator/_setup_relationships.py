"""Relationships Setup page — the list / edit / add view, its CSV
import, bulk status actions, delete-all, and friendly-label editor.

Split out of ``_setup_rosters.py`` in Segment 17A PR 3 (the
Relationships routes were added in Segment 15D PR 2). The shared
redirect / field-label plumbing lives in ``_shared.py``; the CSV
import is relationship-specific and stays here.
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

from app.db.models import Relationship, ReviewSession, User
from app.db.session import get_db
from app.services import assignments
from app.services import relationships as relationships_service
from app.services import session_lifecycle as lifecycle
from app.services.relationships import RelationshipOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import (
    _SETUP_DEFAULT_CAP,
    _SETUP_FILTERED_CAP,
    _redirect_keeping_selection,
    _require_editable,
    _save_field_labels,
    _templates,
)

router = APIRouter()


_RELATIONSHIP_SORT_KEYS = {
    "reviewer", "reviewee", "tag_1", "tag_2", "tag_3", "status",
    "updated_at",
}


@router.get("/sessions/{session_id}/relationships", response_class=HTMLResponse)
def relationships_list(
    request: Request,
    search_by: str = "reviewer",
    q: str = "",
    edit_id: int | None = None,
    add: int = 0,
    selected: list[int] = Query(default=[]),
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
        edit_id=edit_id,
        add_mode=bool(add),
        selected_ids=set(selected),
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


def _require_relationship_in_session(
    db: Session, review_session: ReviewSession, relationship_id: int
) -> Relationship:
    relationship = db.execute(
        select(Relationship).where(
            Relationship.id == relationship_id,
            Relationship.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return relationship


@router.post(
    "/sessions/{session_id}/relationships/create",
    response_class=HTMLResponse,
    response_model=None,
)
def relationships_create(
    request: Request,
    reviewer_pick: str = Form(default=""),
    reviewee_pick: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    reviewer_id = _resolve_picker_label(
        reviewer_pick,
        _relationship_picker_options(
            assignments.list_reviewers(db, review_session.id),
            handle_attr="email",
        ),
    )
    reviewee_id = _resolve_picker_label(
        reviewee_pick,
        _relationship_picker_options(
            assignments.list_reviewees(db, review_session.id),
            handle_attr="email_or_identifier",
        ),
    )
    edit_values: dict[str, object] = {
        "reviewer_label": reviewer_pick,
        "reviewee_label": reviewee_pick,
        "tag_1": tag_1,
        "tag_2": tag_2,
        "tag_3": tag_3,
        "status": status_value,
    }
    if reviewer_id is None or reviewee_id is None:
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=[],
            filename=None,
            add_mode=True,
            edit_values=edit_values,
            edit_error="Pick a reviewer and a reviewee from the list.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        relationships_service.create_relationship(
            db,
            review_session=review_session,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RelationshipOperationError as exc:
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=[],
            filename=None,
            add_mode=True,
            edit_values=edit_values,
            edit_error=exc.message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/relationships",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/relationships/{relationship_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def relationships_update(
    request: Request,
    relationship_id: int,
    reviewer_pick: str = Form(default=""),
    reviewee_pick: str = Form(default=""),
    tag_1: str = Form(default=""),
    tag_2: str = Form(default=""),
    tag_3: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    filter_search_by: str = Form(default="reviewer"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    relationship = _require_relationship_in_session(
        db, review_session, relationship_id
    )
    # The edit row's reviewer / reviewee cells are name-or-email
    # search boxes — resolve the submitted label back to a roster id
    # (Segment 15F).
    reviewer_id = _resolve_picker_label(
        reviewer_pick,
        _relationship_picker_options(
            assignments.list_reviewers(db, review_session.id),
            handle_attr="email",
        ),
    )
    reviewee_id = _resolve_picker_label(
        reviewee_pick,
        _relationship_picker_options(
            assignments.list_reviewees(db, review_session.id),
            handle_attr="email_or_identifier",
        ),
    )
    edit_values: dict[str, object] = {
        "reviewer_label": reviewer_pick,
        "reviewee_label": reviewee_pick,
        "tag_1": tag_1,
        "tag_2": tag_2,
        "tag_3": tag_3,
        "status": status_value,
    }
    if reviewer_id is None or reviewee_id is None:
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=[],
            filename=None,
            edit_id=relationship_id,
            edit_values=edit_values,
            edit_error="Pick a reviewer and a reviewee from the list.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    try:
        relationships_service.update_relationship(
            db,
            relationship=relationship,
            reviewer_id=reviewer_id,
            reviewee_id=reviewee_id,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RelationshipOperationError as exc:
        return _render_relationships_page(
            request=request,
            review_session=review_session,
            user=user,
            db=db,
            issues=[],
            filename=None,
            edit_id=relationship_id,
            edit_values=edit_values,
            edit_error=exc.message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/relationships",
        [relationship_id],
        filter_params=[("search_by", filter_search_by), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/relationships/bulk-inactivate")
def relationships_bulk_inactivate(
    relationship_ids: list[int] = Form(default=[]),
    filter_search_by: str = Form(default="reviewer"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        relationships_service.bulk_inactivate(
            db,
            review_session=review_session,
            relationship_ids=relationship_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RelationshipOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/relationships",
        relationship_ids,
        filter_params=[("search_by", filter_search_by), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/relationships/bulk-reactivate")
def relationships_bulk_reactivate(
    relationship_ids: list[int] = Form(default=[]),
    filter_search_by: str = Form(default="reviewer"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        relationships_service.bulk_reactivate(
            db,
            review_session=review_session,
            relationship_ids=relationship_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except RelationshipOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/relationships",
        relationship_ids,
        filter_params=[("search_by", filter_search_by), ("q", filter_q)],
    )


def _picker_label(member: object, handle_attr: str) -> str:
    """Canonical relationship-picker label — ``"Name (handle)"`` with
    a ``— inactive`` suffix on non-active members. Carries both the
    name and the handle so a `<datalist>` autocomplete matches a
    substring of either (Segment 15F)."""
    label = f"{member.name} ({getattr(member, handle_attr)})"  # type: ignore[attr-defined]
    if member.status != "active":  # type: ignore[attr-defined]
        label += " — inactive"
    return label


def _relationship_picker_options(
    members: list, *, handle_attr: str
) -> list[tuple[int, str]]:
    """``(id, label)`` tuples for a reviewer / reviewee picker,
    sorted by name (Segment 15F PR 5). The label feeds a
    `<datalist>` the operator searches by name or email — it scales
    past a native `<select>` for 1,000+ rosters. No cap: every
    member must be reachable for a re-point to be possible."""
    return [
        (m.id, _picker_label(m, handle_attr))
        for m in sorted(members, key=lambda x: x.name.casefold())
    ]


def _resolve_picker_label(
    value: str, options: list[tuple[int, str]]
) -> int | None:
    """Map a submitted picker string back to its member id by exact
    label match. ``None`` when the operator typed something that
    isn't a roster member — the route then re-renders with an error
    rather than guessing (Segment 15F)."""
    cleaned = value.strip()
    for opt_id, label in options:
        if label == cleaned:
            return opt_id
    return None


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
    edit_id: int | None = None,
    add_mode: bool = False,
    edit_values: dict[str, object] | None = None,
    edit_error: str | None = None,
    selected_ids: set[int] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    is_ready = lifecycle.is_ready(review_session)
    if is_ready:
        edit_id = None
        add_mode = False

    rows = relationships_service.list_for_session(db, review_session.id)
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    reviewer_by_id = {r.id: r for r in reviewers}
    reviewee_by_id = {r.id: r for r in reviewees}
    # Segment 13B Part 2 PR 7 — cookie-backed personal sort.
    # ``reviewer`` / ``reviewee`` resolve via the lookup maps; the
    # sort keys on the rendered name (Segment 15F PR 5 stage 2 —
    # name is now the prominent identity text).
    def _relationship_sort_value(row, key: str):
        if key == "reviewer":
            reviewer = reviewer_by_id.get(row.reviewer_id)
            return reviewer.name if reviewer else None
        if key == "reviewee":
            reviewee = reviewee_by_id.get(row.reviewee_id)
            return reviewee.name if reviewee else None
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
    cap = _SETUP_FILTERED_CAP if is_filtered else _SETUP_DEFAULT_CAP
    capped = filtered[:cap]
    displayed_row_count = len(capped)

    relationships = capped
    # Force-include the edited row when it falls outside the cap.
    if edit_id is not None and edit_id not in {r.id for r in relationships}:
        edited = next((r for r in all_rows if r.id == edit_id), None)
        if edited is None:
            edit_id = None
        else:
            relationships = [edited, *relationships]

    # Resolve the edit-row prefill values from the row on a plain
    # edit GET; an error re-render supplies its own dict. The
    # reviewer / reviewee cells prefill with the picker label so the
    # search box shows the current member.
    if edit_values is None and edit_id is not None:
        edited = next(
            (r for r in relationships if r.id == edit_id), None
        )
        if edited is not None:
            edit_reviewer = reviewer_by_id.get(edited.reviewer_id)
            edit_reviewee = reviewee_by_id.get(edited.reviewee_id)
            edit_values = {
                "reviewer_label": (
                    _picker_label(edit_reviewer, "email")
                    if edit_reviewer is not None
                    else ""
                ),
                "reviewee_label": (
                    _picker_label(edit_reviewee, "email_or_identifier")
                    if edit_reviewee is not None
                    else ""
                ),
                "tag_1": edited.tag_1 or "",
                "tag_2": edited.tag_2 or "",
                "tag_3": edited.tag_3 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "reviewer_label": "",
            "reviewee_label": "",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        }
    return _templates.TemplateResponse(
        request,
        "operator/session_relationships.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "relationships": relationships,
            "selected_ids": selected_ids or set(),
            "reviewer_by_id": reviewer_by_id,
            "reviewee_by_id": reviewee_by_id,
            "existing_count": len(all_rows),
            "total_row_count": len(all_rows),
            "displayed_row_count": displayed_row_count,
            "is_ready": is_ready,
            "edit_id": edit_id,
            "add_mode": add_mode,
            "can_add_relationship": bool(reviewers) and bool(reviewees),
            "edit_values": edit_values,
            "edit_error": edit_error,
            "reviewer_picker_options": _relationship_picker_options(
                reviewers, handle_attr="email"
            ),
            "reviewee_picker_options": _relationship_picker_options(
                reviewees, handle_attr="email_or_identifier"
            ),
            "filter_search_by": search_dimension,
            "filter_search": search,
            "filter_search_by_options": views.RELATIONSHIPS_SEARCH_BY_OPTIONS,
            # Both dimensions' datalists ship every render — the
            # template's `<select>` swaps the input's `list=` so the
            # autocomplete is "Search by"-aware without a reload.
            "filter_search_options_reviewer": (
                views.relationships_search_options(
                    all_rows,
                    reviewer_by_id=reviewer_by_id,
                    reviewee_by_id=reviewee_by_id,
                    search_by="reviewer",
                )
            ),
            "filter_search_options_reviewee": (
                views.relationships_search_options(
                    all_rows,
                    reviewer_by_id=reviewer_by_id,
                    reviewee_by_id=reviewee_by_id,
                    search_by="reviewee",
                )
            ),
            "fields_with_data": relationships_service.fields_with_data(
                db, review_session.id
            ),
            "issues": issues,
            "missing_confirm": missing_confirm,
            "filename": filename,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Relationships"
            ),
        },
        status_code=status_code,
    )


# Allowlist of (form_param, source_field) the pair-context label
# editor accepts (Segment 15A Slice 3). The ``pair_context``
# source_fields are bare digits, so the form-param names carry a
# ``slot_`` prefix to stay valid Python identifiers.
_PAIR_CONTEXT_SLOTS: tuple[tuple[str, str], ...] = (
    ("slot_1", "1"),
    ("slot_2", "2"),
    ("slot_3", "3"),
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
