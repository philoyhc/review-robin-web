"""Observers Setup page — the list / edit / add view, its CSV
import, bulk status actions, and delete-all.

Lights up the third participant audience (the observer roster).
Mirrors the Reviewers / Reviewees Setup-page shape but trimmed
for the simpler observer model: a single ``tag_1`` column,
``email`` as the required identity, and an optional human-
facing ``display_name``.

Route-gated on ``session.observers_enabled``
(``require_observers_enabled_session``) — the page 404s until
the operator opts in via the User interface settings card on
Session Edit Details.
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

from app.db.models import Observer, ReviewSession, User
from app.db.session import get_db
from app.services import csv_imports
from app.services import observers as observers_service
from app.services import session_lifecycle as lifecycle
from app.services.observers import ObserverOperationError
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
)
from app.web.routes_operator._shared import (
    _SETUP_DEFAULT_CAP,
    _SETUP_FILTERED_CAP,
    _redirect_keeping_selection,
    _require_editable,
    _require_response_loss_ack,
    _templates,
    require_observers_enabled_session,
)

router = APIRouter()


def _list_observers(db: Session, session_id: int) -> list[Observer]:
    return list(
        db.execute(
            select(Observer)
            .where(Observer.session_id == session_id)
            .order_by(Observer.id)
        ).scalars()
    )


def _require_observer_in_session(
    db: Session, review_session: ReviewSession, observer_id: int
) -> Observer:
    observer = db.execute(
        select(Observer).where(
            Observer.id == observer_id,
            Observer.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if observer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return observer


def _render_observers_page(
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
    issues: list | None = None,
    filename: str | None = None,
    http_status: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Render the Observers Setup page.

    Shared by the GET route and the create / update error-render
    paths. ``edit_id`` / ``add_mode`` drive the server-rendered
    edit state; ``edit_values`` / ``edit_error`` carry an
    operator's rejected submission back into the edit row."""
    is_ready = lifecycle.is_ready(review_session)
    if is_ready:
        edit_id = None
        add_mode = False

    all_observers = _list_observers(db, review_session.id)
    filtered = views.filter_observers_rows(
        all_observers, status=status_filter, search=search
    )
    is_filtered = status_filter != "all" or bool(search.strip())
    cap = _SETUP_FILTERED_CAP if is_filtered else _SETUP_DEFAULT_CAP
    capped = filtered[:cap]
    displayed_row_count = len(capped)

    observers = capped
    if edit_id is not None and edit_id not in {o.id for o in observers}:
        edited = next(
            (o for o in all_observers if o.id == edit_id), None
        )
        if edited is None:
            edit_id = None
        else:
            observers = [edited, *observers]

    if edit_values is None and edit_id is not None:
        edited = next(
            (o for o in observers if o.id == edit_id), None
        )
        if edited is not None:
            edit_values = {
                "email": edited.email,
                "display_name": edited.display_name or "",
                "tag_1": edited.tag_1 or "",
                "status": edited.status,
            }
    if edit_values is None and add_mode:
        edit_values = {
            "email": "",
            "display_name": "",
            "tag_1": "",
            "status": "active",
        }

    existing_count = csv_imports.existing_observer_count(
        db, review_session.id
    )

    return _templates.TemplateResponse(
        request,
        "operator/session_observers.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "observers": observers,
            "selected_ids": selected_ids or set(),
            "total_row_count": len(all_observers),
            "displayed_row_count": displayed_row_count,
            "filter_status": status_filter,
            "filter_search": search,
            "filter_status_options": views.OBSERVERS_STATUS_OPTIONS,
            "filter_search_options": views.observers_search_options(
                all_observers
            ),
            "existing_count": existing_count,
            "issues": issues or [],
            "filename": filename,
            "is_ready": is_ready,
            "edit_id": edit_id,
            "add_mode": add_mode,
            "edit_values": edit_values,
            "edit_error": edit_error,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Observers"
            ),
        },
        status_code=http_status,
    )


@router.get(
    "/sessions/{session_id}/observers", response_class=HTMLResponse
)
def observers_page(
    request: Request,
    status_filter: str = Query(default="all", alias="status"),
    q: str = "",
    edit_id: int | None = None,
    add: int = 0,
    selected: list[int] = Query(default=[]),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_observers_page(
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


@router.post(
    "/sessions/{session_id}/observers/create",
    response_class=HTMLResponse,
    response_model=None,
)
def observers_create(
    request: Request,
    email: str = Form(default=""),
    display_name: str = Form(default=""),
    tag_1: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    try:
        observers_service.create_observer(
            db,
            review_session=review_session,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            add_mode=True,
            edit_values={
                "email": email,
                "display_name": display_name,
                "tag_1": tag_1,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/observers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/observers/{observer_id}/update",
    response_class=HTMLResponse,
    response_model=None,
)
def observers_update(
    request: Request,
    observer_id: int,
    email: str = Form(default=""),
    display_name: str = Form(default=""),
    tag_1: str = Form(default=""),
    status_value: str = Form(default="active", alias="status"),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    observer = _require_observer_in_session(db, review_session, observer_id)
    try:
        observers_service.update_observer(
            db,
            observer=observer,
            email=email,
            display_name=display_name,
            tag_1=tag_1,
            status=status_value,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            edit_id=observer_id,
            edit_values={
                "email": email,
                "display_name": display_name,
                "tag_1": tag_1,
                "status": status_value,
            },
            edit_error=exc.message,
            http_status=status.HTTP_400_BAD_REQUEST,
        )
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        [observer_id],
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/observers/bulk-inactivate")
def observers_bulk_inactivate(
    observer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        observers_service.bulk_inactivate(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/observers/bulk-reactivate")
def observers_bulk_reactivate(
    observer_ids: list[int] = Form(default=[]),
    filter_status: str = Form(default="all"),
    filter_q: str = Form(default=""),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    try:
        observers_service.bulk_reactivate(
            db,
            review_session=review_session,
            observer_ids=observer_ids,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except ObserverOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc
    return _redirect_keeping_selection(
        f"/operator/sessions/{review_session.id}/observers",
        observer_ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
    )


@router.post("/sessions/{session_id}/observers/delete-all")
def observers_delete_all(
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
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
    csv_imports.delete_all_observers(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/observers",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/observers/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def observers_import_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_observers_enabled_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Observers CSV import. Mirrors ``_handle_import`` for the
    reviewer / reviewee path but skips the cross-table identity
    check (observers don't conflict with reviewers / reviewees —
    a person can be both an observer and a reviewer / reviewee
    by design)."""
    _require_editable(review_session)
    content = await file.read()
    result = csv_imports.parse_observer_csv(content)
    existing = csv_imports.existing_observer_count(db, review_session.id)

    def render(status_code: int = status.HTTP_200_OK) -> HTMLResponse:
        return _render_observers_page(
            request=request,
            db=db,
            user=user,
            review_session=review_session,
            issues=result.issues,
            filename=file.filename,
            http_status=status_code,
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    csv_imports.save_observers(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/observers",
        status_code=status.HTTP_303_SEE_OTHER,
    )
