"""Session Home — the per-session detail page + lifecycle / edit /
delete / data-deletion routes that hang off it. Slice 5 of the
major refactor.

Note on ``POST /sessions`` (``create_session``): the create route
is heavily coupled to ``_run_quick_setup_import`` and
``_run_quick_setup_assignments`` (both currently in ``_legacy.py``,
moving to ``_quick_setup.py`` in PR 7). Per the §3.0 "no slice-to-
slice imports" invariant, ``create_session`` stays in ``_legacy.py``
for now and lands in ``_quick_setup.py`` in PR 7 alongside its
helpers. The matching ``GET /sessions/new`` form is a thin
template render with no Quick Setup coupling, so it moves here.

Source ranges in pre-refactor ``routes_operator.py``:
241-525 (excluding 460-525 Validate, which goes to Operations
per §4.1), 2182-2294, 2447-2510.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import (
    csv_imports,
    instruments as instruments_service,
    responses,
    session_owners,
    sessions,
    validation,
)
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
    require_sys_admin_or_session_operator,
)
from app.web.routes_operator._shared import (
    _lifecycle_error_response,
    _quick_setup_unlocked,
    _require_editable,
    _require_response_loss_ack,
    _templates,
)


router = APIRouter()


_REVERT_RETURN_TO = {"reviewers", "reviewees", "assignments", "instruments"}


@router.get("/sessions/new", response_class=HTMLResponse)
def new_session_form(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_new.html",
        {
            "user": user,
            "quick_setup": views.build_new_session_quick_setup_context(
                db, user
            ),
            "breadcrumbs": breadcrumbs.operator_new_session(),
        },
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(
    request: Request,
    validated: bool = Query(default=False),
    quick_setup_error: str | None = Query(default=None),
    quick_setup_reason: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    setup_rows = views.build_setup_rows(db, review_session)
    validation_summary: dict[str, object] | None = None
    # Run validation on the ?validated=1 entry path AND whenever the
    # session is already in validated — the Activate Session control on
    # the contextual action card needs ``can_activate`` /
    # ``needs_acknowledge`` to render the right form shape.
    if validated or lifecycle.is_validated(review_session):
        issues = validation.validate_session_setup(db, review_session)
        report = lifecycle.build_readiness_report(issues)
        if report.can_activate and lifecycle.is_draft(review_session):
            lifecycle.mark_validated(
                db,
                review_session=review_session,
                user=user,
                report=report,
                correlation_id=request_correlation_id(),
            )
        validation_summary = {
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate
            and lifecycle.is_validated(review_session),
            "needs_acknowledge": report.has_non_blocking_findings,
        }
    return _templates.TemplateResponse(
        request,
        "operator/session_detail.html",
        {
            "user": user,
            "session": review_session,
            "setup_rows": setup_rows,
            "status_pills": views.session_status_pills(db, review_session),
            "validation_summary": validation_summary,
            "is_draft": lifecycle.is_draft(review_session),
            "is_validated": lifecycle.is_validated(review_session),
            "is_ready": lifecycle.is_ready(review_session),
            # Segment 15B Slice 4 — pre-Validate Generate signal for
            # the Next Action card. Internal wiring lands now; the
            # matching template branches (primary "Generate
            # assignments" button + supporting "Pin rules" link)
            # ship in Segment 15E. The dataclass surface is final;
            # 15E reads from this context key with no further
            # service-layer changes.
            "next_action_generate": views.compute_next_action_generate_state(
                db, review_session
            ),
            # Freshly-created draft with reviewers, reviewees, or
            # instrument rule pins still missing. Computed after the
            # validation flow so a session that just transitioned
            # ``draft → validated`` no longer falls through this gate.
            "is_setup_empty": (
                lifecycle.is_draft(review_session)
                and (
                    csv_imports.existing_reviewer_count(db, review_session.id) == 0
                    or csv_imports.existing_reviewee_count(db, review_session.id) == 0
                    or instruments_service.has_unpinned(db, review_session.id)
                )
            ),
            "has_responses": lifecycle.session_has_responses(db, review_session),
            "quick_setup": views.build_quick_setup_context(
                db,
                review_session,
                user=user,
                is_unlocked=_quick_setup_unlocked(request, review_session),
                error_kind=quick_setup_error,
                error_reason=quick_setup_reason,
            ),
            "extract_data": views.build_extract_data_context(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session(review_session),
        },
    )


@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
def session_edit_form(
    request: Request,
    owners_error: str | None = Query(default=None),
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_edit.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "owners": session_owners.list_owners(db, review_session),
            "owner_candidates": session_owners.workspace_operator_candidates(
                db, review_session
            ),
            "owners_error": owners_error,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Edit details"
            ),
        },
    )


@router.post("/sessions/{session_id}/edit")
def session_edit_submit(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    help_contact: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_editable(review_session)
    _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    parsed_deadline: datetime | None = None
    if deadline:
        try:
            parsed_deadline = datetime.fromisoformat(deadline)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="deadline must be ISO-8601",
            ) from exc

    payload = SessionCreate(
        name=name,
        code=code,
        description=description or None,
        deadline=parsed_deadline,
        help_contact=help_contact or None,
    )
    sessions.update_session(
        db,
        review_session=review_session,
        user=user,
        payload=payload,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/delete-data")
def session_delete_data(
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    responses.delete_all_for_session(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/delete")
def session_delete(
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
    sessions.delete_session(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/activate")
def session_activate(
    acknowledge_warnings: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)
    try:
        lifecycle.activate_session(
            db,
            review_session=review_session,
            user=user,
            report=report,
            acknowledge_warnings=acknowledge_warnings == "true",
            correlation_id=request_correlation_id(),
        )
    except lifecycle.LifecycleError as exc:
        raise _lifecycle_error_response(exc) from exc
    target = f"/operator/sessions/{review_session.id}"
    if return_to in _REVERT_RETURN_TO:
        target = f"{target}/{return_to}"
    return RedirectResponse(
        url=target,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/revert")
def session_revert_to_draft(
    confirm: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        if lifecycle.is_validated(review_session):
            lifecycle.invalidate_session(
                db,
                review_session=review_session,
                user=user,
                reason="operator_revert",
                correlation_id=request_correlation_id(),
            )
        else:
            lifecycle.revert_session_to_draft(
                db,
                review_session=review_session,
                user=user,
                confirm=confirm == "true",
                correlation_id=request_correlation_id(),
            )
    except lifecycle.LifecycleError as exc:
        raise _lifecycle_error_response(exc) from exc
    target = f"/operator/sessions/{review_session.id}"
    if return_to in _REVERT_RETURN_TO:
        target = f"{target}/{return_to}"
    return RedirectResponse(
        url=target,
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- Per-session owner management (Segment 16B PR 2) ----------------------


def _owners_redirect_url(session_id: int, error_code: str | None = None) -> str:
    base = f"/operator/sessions/{session_id}/edit#owners"
    if error_code:
        # Anchor stays at the end; the query param sits before the #.
        from urllib.parse import quote

        return (
            f"/operator/sessions/{session_id}/edit"
            f"?owners_error={quote(error_code, safe='')}#owners"
        )
    return base


@router.post("/sessions/{session_id}/owners/add")
def session_owners_add(
    target_email: str = Form(...),
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    actor: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from sqlalchemy import func as sa_func

    target = db.execute(
        select(User).where(
            sa_func.lower(User.email) == target_email.strip().lower()
        )
    ).scalar_one_or_none()
    if target is None:
        return RedirectResponse(
            url=_owners_redirect_url(review_session.id, "not_in_workspace"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        session_owners.add_owner(
            db,
            review_session=review_session,
            actor=actor,
            target=target,
            correlation_id=request_correlation_id(),
        )
    except session_owners.OwnerOperationError as exc:
        return RedirectResponse(
            url=_owners_redirect_url(review_session.id, exc.code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=_owners_redirect_url(review_session.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/owners/{user_id}/remove")
def session_owners_remove(
    user_id: int,
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    actor: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    target = db.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        session_owners.remove_owner(
            db,
            review_session=review_session,
            actor=actor,
            target=target,
            correlation_id=request_correlation_id(),
        )
    except session_owners.OwnerOperationError as exc:
        # last_owner / not_owner both fall through here.
        status_code = (
            status.HTTP_409_CONFLICT
            if exc.code == "last_owner"
            else status.HTTP_303_SEE_OTHER
        )
        if status_code == status.HTTP_409_CONFLICT:
            raise HTTPException(status_code=status_code, detail=exc.message) from exc
        return RedirectResponse(
            url=_owners_redirect_url(review_session.id, exc.code),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=_owners_redirect_url(review_session.id),
        status_code=status.HTTP_303_SEE_OTHER,
    )
