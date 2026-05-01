from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Instrument, Invitation, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.schemas.sessions import SessionCreate
from app.services import (
    assignments,
    csv_imports,
    instruments as instruments_service,
    invitations,
    monitoring,
    responses,
    sessions,
    validation,
)
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)

router = APIRouter(prefix="/operator", tags=["operator"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_templates.env.globals["app_version"] = settings.app_version
_templates.env.globals["display_field_label"] = (
    instruments_service.display_field_label
)
_templates.env.globals["is_locked_display_source"] = (
    instruments_service.is_locked_display_source
)


@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    review_sessions = sessions.list_for_user(db, user)
    return _templates.TemplateResponse(
        request,
        "operator/sessions_list.html",
        {
            "user": user,
            "sessions": review_sessions,
            "breadcrumbs": breadcrumbs.operator_root(),
        },
    )


@router.get("/sessions/new", response_class=HTMLResponse)
def new_session_form(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_new.html",
        {
            "user": user,
            "breadcrumbs": breadcrumbs.operator_new_session(),
        },
    )


@router.post("/sessions")
def create_session(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
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
    )
    review_session = sessions.create_session(
        db,
        user=user,
        payload=payload,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(
    request: Request,
    validated: bool = Query(default=False),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    setup_rows = views.build_setup_rows(db, review_session)
    validation_summary: dict[str, object] | None = None
    if validated:
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
            "validation_summary": validation_summary,
            "is_draft": lifecycle.is_draft(review_session),
            "is_validated": lifecycle.is_validated(review_session),
            "is_ready": lifecycle.is_ready(review_session),
            "has_responses": lifecycle.session_has_responses(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session(review_session),
        },
    )


@router.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_session(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)
    return _templates.TemplateResponse(
        request,
        "operator/session_validate.html",
        {
            "user": user,
            "session": review_session,
            "issues": issues,
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate
            and lifecycle.is_validated(review_session),
            "needs_acknowledge": report.has_non_blocking_findings,
            "is_draft": lifecycle.is_draft(review_session),
            "is_validated": lifecycle.is_validated(review_session),
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Validate setup"
            ),
        },
    )


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
        return _templates.TemplateResponse(
            request,
            template,
            {
                "user": user,
                "session": review_session,
                list_key: list_items,
                "existing_count": existing,
                "assignment_count": assignment_count,
                "issues": result.issues,
                "filename": file.filename,
                "breadcrumbs": breadcrumbs.operator_session_child(
                    review_session, crumb_label
                ),
            },
            status_code=status_code,
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    _invalidate_if_validated(db, review_session, user, reason=f"{kind}_imported")
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



@router.get("/sessions/{session_id}/assignments", response_class=HTMLResponse)
def assignments_hub(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_assignments_hub(request, db, review_session, user)


def _render_assignments_hub(
    request: Request,
    db: Session,
    review_session: ReviewSession,
    user: User,
    *,
    issues: list | None = None,
    missing_confirm: bool = False,
    is_blocked: bool = False,
) -> HTMLResponse:
    assignment_count = assignments.existing_count(db, review_session.id)
    pair_sample = (
        assignments.list_pairs(db, review_session.id) if assignment_count else []
    )
    truncated_count = max(0, assignment_count - len(pair_sample))
    self_review_found = 0
    self_review_included = 0
    if assignment_count:
        reviewers = assignments.list_reviewers(db, review_session.id)
        reviewees = assignments.list_reviewees(db, review_session.id)
        self_review_found = assignments.count_self_review_candidates(
            reviewers, reviewees
        )
        self_review_included = assignments.count_self_reviews_in_assignments(
            db, review_session.id
        )
    status_code = (
        status.HTTP_400_BAD_REQUEST if (missing_confirm or is_blocked) else status.HTTP_200_OK
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_assignments.html",
        {
            "user": user,
            "session": review_session,
            "assignment_count": assignment_count,
            "reviewer_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "reviewee_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "pair_sample": pair_sample,
            "truncated_count": truncated_count,
            "self_review_found": self_review_found,
            "self_review_included": self_review_included,
            "self_review_excluded": self_review_found - self_review_included,
            "issues": issues,
            "missing_confirm": missing_confirm,
            "is_blocked": is_blocked,
            "is_ready": lifecycle.is_ready(review_session),
            "fields_with_data": assignments.assignment_fields_with_data(
                db, review_session.id
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Assignments"
            ),
        },
        status_code=status_code,
    )





@router.post(
    "/sessions/{session_id}/assignments/full-matrix",
    response_class=HTMLResponse,
    response_model=None,
)
def assignments_full_matrix(
    request: Request,
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    pairs, excluded_counts = assignments.generate_full_matrix(
        reviewers, reviewees, exclude_self_review=exclude_self
    )
    existing = assignments.existing_count(db, review_session.id)
    needs_confirm = existing > 0 and confirm_replace != "true"

    if needs_confirm:
        return _render_assignments_hub(
            request, db, review_session, user,
            missing_confirm=True,
        )

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    _invalidate_if_validated(
        db, review_session, user, reason="assignments_generated"
    )
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.full_matrix,
        correlation_id=request_correlation_id(),
        excluded_counts=excluded_counts,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/manual/import",
    response_class=HTMLResponse,
    response_model=None,
)
async def assignments_manual_import(
    request: Request,
    file: UploadFile = File(...),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_editable(review_session)
    content = await file.read()
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    result = assignments.parse_manual_csv(content, reviewers, reviewees)
    existing = assignments.existing_count(db, review_session.id)
    needs_confirm = existing > 0 and confirm_replace != "true"

    if result.is_blocked or needs_confirm:
        return _render_assignments_hub(
            request, db, review_session, user,
            issues=result.issues,
            missing_confirm=needs_confirm and not result.is_blocked,
            is_blocked=result.is_blocked,
        )

    rows = result.rows
    if exclude_self_review == "true":
        rows = [
            r for r in rows
            if r.reviewer_email.casefold() != r.reviewee_identifier.casefold()
        ]

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    pairs, contexts, includes = assignments.manual_rows_to_pairs(
        rows, reviewers, reviewees
    )
    _invalidate_if_validated(
        db, review_session, user, reason="assignments_imported"
    )
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.manual,
        correlation_id=request_correlation_id(),
        filename=file.filename,
        contexts=contexts,
        includes=includes,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/reviewers", response_class=HTMLResponse)
def reviewers_list(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    reviewers = assignments.list_reviewers(db, review_session.id)
    return _templates.TemplateResponse(
        request,
        "operator/session_reviewers.html",
        {
            "user": user,
            "session": review_session,
            "reviewers": reviewers,
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
    return _templates.TemplateResponse(
        request,
        "operator/session_reviewees.html",
        {
            "user": user,
            "session": review_session,
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


@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
def session_edit_form(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_edit.html",
        {
            "user": user,
            "session": review_session,
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
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
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
    )
    _invalidate_if_validated(db, review_session, user, reason="session_edited")
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
    _invalidate_if_validated(
        db, review_session, user, reason="reviewers_deleted_all"
    )
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
    _invalidate_if_validated(
        db, review_session, user, reason="reviewees_deleted_all"
    )
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


@router.post("/sessions/{session_id}/assignments/delete-all")
def assignments_delete_all(
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
    _invalidate_if_validated(
        db, review_session, user, reason="assignments_deleted_all"
    )
    assignments.delete_all_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Edit-lock helpers
# --------------------------------------------------------------------------- #


def _require_editable(review_session: ReviewSession) -> None:
    """Reject mutating operator actions while session is not draft/validated."""
    if not lifecycle.is_editable(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to draft to edit"
            ),
        )


def _invalidate_if_validated(
    db: Session,
    review_session: ReviewSession,
    user: User,
    *,
    reason: str,
) -> None:
    """Flip ``validated → draft`` so a setup-mutating action can land in ``draft``."""
    if lifecycle.is_validated(review_session):
        lifecycle.invalidate_session(
            db,
            review_session=review_session,
            user=user,
            reason=reason,
            correlation_id=request_correlation_id(),
        )


def _require_response_loss_ack(
    db: Session, review_session: ReviewSession, ack: str | None
) -> None:
    """When responses exist, require explicit acknowledge_response_loss=true."""
    if not lifecycle.session_has_responses(db, review_session):
        return
    if ack != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Existing reviewer responses will be discarded; tick "
                "'acknowledge response loss' to proceed"
            ),
        )


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


def _lifecycle_error_response(exc: lifecycle.LifecycleError) -> HTTPException:
    code_to_status = {
        "not_draft": status.HTTP_409_CONFLICT,
        "not_ready": status.HTTP_409_CONFLICT,
        "session_not_ready": status.HTTP_409_CONFLICT,
        "deadline_passed": status.HTTP_409_CONFLICT,
        "locked": status.HTTP_409_CONFLICT,
        "has_errors": status.HTTP_400_BAD_REQUEST,
        "needs_acknowledge": status.HTTP_400_BAD_REQUEST,
        "needs_confirm": status.HTTP_400_BAD_REQUEST,
    }
    return HTTPException(
        status_code=code_to_status.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=str(exc),
    )


# --------------------------------------------------------------------------- #
# Lifecycle routes (Segment 9.1)
# --------------------------------------------------------------------------- #


@router.post("/sessions/{session_id}/activate")
def session_activate(
    acknowledge_warnings: str | None = Form(default=None),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


_REVERT_RETURN_TO = {"reviewers", "reviewees", "assignments", "instruments"}


@router.post("/sessions/{session_id}/revert")
def session_revert_to_draft(
    confirm: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
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


def _can_edit_instrument(review_session: ReviewSession) -> bool:
    """Setup-side mutations are blocked while session is ready."""
    return not lifecycle.is_ready(review_session)


def _require_instrument_editable(review_session: ReviewSession) -> None:
    if not _can_edit_instrument(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Instrument structure is locked while the session is ready"
            ),
        )


def _bulk_accepting_state(instruments: list[Instrument]) -> str:
    """Three-state value for the bulk Accepting toggle: all-on, all-off, or mixed."""
    if not instruments:
        return "all-off"
    on = [i for i in instruments if i.accepting_responses]
    if len(on) == 0:
        return "all-off"
    if len(on) == len(instruments):
        return "all-on"
    return "mixed"


def _bulk_visibility_state(instruments: list[Instrument]) -> str:
    """Three-state value for the bulk Visibility toggle: all-on, all-off, or mixed."""
    if not instruments:
        return "all-off"
    on = [i for i in instruments if i.responses_visible_when_closed]
    if len(on) == 0:
        return "all-off"
    if len(on) == len(instruments):
        return "all-on"
    return "mixed"


@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    editing: int | None = Query(default=None),
    saved: int | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifecycle.observe_deadline(db, review_session)
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Make sure every instrument has its locked Name / Email Display
    # Fields rows. The Alembic migration backfills existing instruments;
    # this is the per-request safety net for any sessions that slip
    # through (e.g. created before the migration ran).
    for instrument in instruments:
        instruments_service.ensure_locked_display_fields(
            db, instrument=instrument
        )
    # Prune Display Fields rows whose underlying data source no longer
    # has any populated value (locked Name / Email rows are exempt and
    # always kept). Runs before the lazy seeds so the canonical seed
    # order — reviewee.* before pair_context.* — falls out naturally:
    # any stale rows are gone, then the seeds append fresh in the
    # canonical sequence the route hands them down in.
    instruments_service.prune_unpopulated_display_fields(
        db, review_session
    )
    # Per-request idempotent backfill of the lazy-seeded display
    # fields. The reviewee / assignment imports already trigger these
    # in the happy path; calling them on every GET catches sessions
    # whose roster or assignments were imported before the lazy-seed
    # logic landed (PR #203). Cheap — both helpers short-circuit when
    # there's nothing to seed.
    instruments_service.seed_display_fields_from_reviewees(
        db, review_session
    )
    instruments_service.seed_display_fields_from_assignments(
        db, review_session
    )
    db.commit()

    is_ready = lifecycle.is_ready(review_session)
    # State machine: ``?editing={instrument_id}`` opens that card for
    # editing. The yellow lock card on a ``ready`` session overrides
    # everything — every per-instrument card stays locked.
    editing_instrument_id = None if is_ready else editing

    # "Saved" / "not saved" pill on each per-instrument card's status
    # sub-card. An instrument is "saved" if it has at least one audit
    # event indicating an operator-driven persistence of its field
    # tables (display fields saved via bulk save, edit, add, delete, or
    # move). Pure draft instruments — only seeded rows, never touched —
    # render as "not saved".
    instrument_saved_state = instruments_service.saved_state_for_session(
        db, session_id=review_session.id
    )

    return _templates.TemplateResponse(
        request,
        "operator/instruments_index.html",
        {
            "user": user,
            "session": review_session,
            "instruments": instruments,
            "is_ready": is_ready,
            "can_edit": _can_edit_instrument(review_session),
            "bulk_accepting_state": _bulk_accepting_state(instruments),
            "bulk_visibility_state": _bulk_visibility_state(instruments),
            "editing_instrument_id": editing_instrument_id,
            "instrument_saved_state": instrument_saved_state,
            "saved_instrument_id": saved,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Instruments"
            ),
        },
    )


@router.get("/sessions/{session_id}/setupinvite", response_class=HTMLResponse)
def setupinvite_stub(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_setupinvite.html",
        {
            "user": user,
            "session": review_session,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Email Invites"
            ),
        },
    )


@router.get("/sessions/{session_id}/preview", response_class=HTMLResponse)
def session_preview(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Operator preview of the reviewer surface (Segment 10B-3).

    Operator-only via ``require_session_operator``. Bypasses session-status
    / deadline / acceptance gates per D9. Pads with up to three synthetic
    rows when fewer real assignments exist; all inputs render disabled and
    the reviewer write-path forms are suppressed via the ``preview_mode``
    template flag.
    """
    from app.web.routes_reviewer import build_preview_context

    context = build_preview_context(
        db=db, user=user, review_session=review_session
    )
    context["breadcrumbs"] = breadcrumbs.operator_session_child(
        review_session, "Preview"
    )
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )


def _instruments_redirect(session_id: int) -> RedirectResponse:
    return RedirectResponse(
        url=f"/operator/sessions/{session_id}/instruments",
        status_code=status.HTTP_303_SEE_OTHER,
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
    _invalidate_if_validated(
        db, review_session, user, reason="instrument_described"
    )
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

    validation_block: dict[str, int] | None = None
    if response_type == "integer":
        bounds: dict[str, int] = {}
        if validation_min:
            try:
                bounds["min"] = int(validation_min)
            except ValueError:
                pass
        if validation_max:
            try:
                bounds["max"] = int(validation_max)
            except ValueError:
                pass
        validation_block = bounds or None

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_field_added"
    )
    try:
        instruments_service.add_response_field(
            db,
            instrument=instrument,
            field_key=key,
            label=label,
            response_type=response_type,
            required=required == "true",
            validation=validation_block,
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
    _invalidate_if_validated(
        db, review_session, user, reason="instrument_field_added"
    )
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

    validation_block: dict[str, int] | None = None
    if field.response_type == "integer":
        bounds: dict[str, int] = {}
        if validation_min:
            try:
                bounds["min"] = int(validation_min)
            except ValueError:
                pass
        if validation_max:
            try:
                bounds["max"] = int(validation_max)
            except ValueError:
                pass
        validation_block = bounds or None
    else:
        validation_block = field.validation

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_field_updated"
    )
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_field_deleted"
    )
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_fields_reordered"
    )
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_display_field_added"
    )
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
    label: str | None = Form(default=None),
    visible: str | None = Form(default=None),
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    instrument, review_session = bundle
    _require_instrument_editable(review_session)
    field = _require_display_field_in_instrument(df_id, instrument, db)

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_display_field_updated"
    )
    try:
        instruments_service.update_display_field(
            db,
            field=field,
            label=label or "",
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_display_field_deleted"
    )
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_display_field_moved"
    )
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

    _invalidate_if_validated(
        db, review_session, user, reason="instrument_fields_saved"
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
    #    creates them via ``add_default_response_field`` (which picks a
    #    fresh field_key + label) and remembers the temp→real id map;
    #    the bulk-save step below then applies the operator-typed
    #    label / required / help to the new row.
    new_id_map: dict[str, int] = {}
    for kind, raw_id in zip(kinds, raw_ids):
        if kind != "response":
            continue
        if not raw_id.startswith("new_") or raw_id in new_id_map:
            continue
        if raw_id in {str(d) for d in response_delete_ids}:
            continue  # added then deleted before save — skip
        new_field = instruments_service.add_default_response_field(
            db, instrument=instrument, after_field_id=None, actor=user
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
    # Redirect with ``?saved={iid}`` so the page renders a flash
    # confirmation. The ``?editing`` param is intentionally cleared —
    # per spec, a successful Save locks the tables.
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments"
            f"?saved={instrument.id}#instrument-{instrument.id}"
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
    _invalidate_if_validated(
        db, review_session, user, reason="instrument_added"
    )
    instrument = instruments_service.create_instrument(
        db, review_session=review_session, after_instrument_id=after, actor=user
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/delete")
def instruments_delete(
    instrument_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
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
    _invalidate_if_validated(
        db, review_session, user, reason="instrument_deleted"
    )
    instruments_service.delete_instrument(
        db, instrument=instrument, actor=user
    )
    return _instruments_redirect(review_session.id)


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
    return _instruments_redirect(review_session.id)


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
    return _instruments_redirect(review_session.id)


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
    return _instruments_redirect(review_session.id)


# --------------------------------------------------------------------------- #
# Invitation + outbox routes (Segment 9.2)
# --------------------------------------------------------------------------- #


def _require_ready(review_session: ReviewSession) -> None:
    """Reject invitation actions while session is not ready.

    Inverse of the 9.1 ``_require_draft`` lock: invitations point at a live
    reviewer surface, so they must only be issued / sent on a ready session.
    """
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Invitations can only be issued while the session is ready"
            ),
        )


def _require_invitation_in_session(
    invitation_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    db: Session = Depends(get_db),
) -> tuple[Invitation, ReviewSession]:
    invitation = db.execute(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return invitation, review_session


@router.get(
    "/sessions/{session_id}/invitations", response_class=HTMLResponse
)
def invitations_index(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = invitations.list_invitations_for_session(db, review_session.id)
    eligible = invitations.reviewers_eligible_for_invitation(db, review_session.id)
    invited_ids = {r.invitation.reviewer_id for r in rows}
    pending_ids = [
        r.invitation.id for r in rows if r.invitation.status == "pending"
    ]
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations.html",
        {
            "user": user,
            "session": review_session,
            "rows": rows,
            "eligible_count": len(eligible),
            "uninvited_count": sum(1 for r in eligible if r.id not in invited_ids),
            "pending_count": len(pending_ids),
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Invitations"
            ),
        },
    )


@router.post("/sessions/{session_id}/invitations/generate")
def invitations_generate(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_ready(review_session)
    invitations.generate_invitations(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/invitations/send-all")
def invitations_send_all(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_ready(review_session)
    rows = invitations.list_invitations_for_session(db, review_session.id)
    for row in rows:
        if row.invitation.status != "pending":
            continue
        invitations.send_invitation(
            db,
            invitation=row.invitation,
            review_session=review_session,
            reviewer=row.reviewer,
            user=user,
            request=request,
            correlation_id=request_correlation_id(),
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/regenerate"
)
def invitations_regenerate(
    bundle: tuple[Invitation, ReviewSession] = Depends(_require_invitation_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    invitations.regenerate_token(
        db,
        invitation=invitation,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/send"
)
def invitations_send_one(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(_require_invitation_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    invitations.send_invitation(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        request=request,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/outbox", response_class=HTMLResponse)
def outbox_index(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = invitations.list_outbox_for_session(db, review_session.id)
    return _templates.TemplateResponse(
        request,
        "operator/session_outbox.html",
        {
            "user": user,
            "session": review_session,
            "rows": rows,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Outbox"
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Monitoring + reminders (Segment 9.3)
# --------------------------------------------------------------------------- #


@router.get(
    "/sessions/{session_id}/monitoring", response_class=HTMLResponse
)
def session_monitoring(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    rows = monitoring.per_reviewer_progress(db, review_session)
    summary = monitoring.summary_counts(db, review_session)
    return _templates.TemplateResponse(
        request,
        "operator/session_monitoring.html",
        {
            "user": user,
            "session": review_session,
            "summary": summary,
            "rows": rows,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Monitoring"
            ),
        },
    )


@router.post(
    "/sessions/{session_id}/invitations/{invitation_id}/remind"
)
def invitations_remind_one(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(
        _require_invitation_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    invitation, review_session = bundle
    _require_ready(review_session)
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    invitations.send_reminder(
        db,
        invitation=invitation,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        request=request,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/monitoring",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/monitoring/remind-incomplete"
)
def session_remind_incomplete(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_ready(review_session)
    invitations.send_reminders_to_incomplete(
        db,
        review_session=review_session,
        user=user,
        request=request,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/monitoring",
        status_code=status.HTTP_303_SEE_OTHER,
    )
