from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Instrument, Invitation, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.schemas.sessions import SessionCreate
from app.services import (
    assignments,
    csv_imports,
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
        validation_summary = {
            "error_count": len(report.errors),
            "warning_count": len(report.warnings),
            "info_count": len(report.info),
            "can_activate": report.can_activate
            and lifecycle.is_draft(review_session),
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
            "can_activate": report.can_activate and lifecycle.is_draft(review_session),
            "needs_acknowledge": report.has_non_blocking_findings,
            "is_draft": lifecycle.is_draft(review_session),
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
    _require_draft(review_session)
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

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )



@router.get("/sessions/{session_id}/assignments", response_class=HTMLResponse)
def assignments_hub(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    assignment_count = assignments.existing_count(db, review_session.id)
    pair_sample = (
        assignments.list_pairs(db, review_session.id) if assignment_count else []
    )
    truncated_count = max(0, assignment_count - len(pair_sample))
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
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Assignments"
            ),
        },
    )


@router.post(
    "/sessions/{session_id}/assignments/full-matrix",
    response_class=HTMLResponse,
    response_model=None,
)
def assignments_full_matrix(
    request: Request,
    exclude_self_review: str | None = Form(default=None),
    dry_run: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_draft(review_session)
    exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    pairs, excluded_counts = assignments.generate_full_matrix(
        reviewers, reviewees, exclude_self_review=exclude_self
    )
    stats = assignments.coverage_stats(reviewers, reviewees, pairs)
    existing = assignments.existing_count(db, review_session.id)

    is_dry_run = dry_run == "true"
    needs_confirm = existing > 0 and confirm_replace != "true"

    if is_dry_run or needs_confirm:
        status_code = (
            status.HTTP_400_BAD_REQUEST
            if needs_confirm and not is_dry_run
            else status.HTTP_200_OK
        )
        pair_sample = pairs[: assignments.PAIR_PREVIEW_LIMIT]
        truncated_count = max(0, len(pairs) - assignments.PAIR_PREVIEW_LIMIT)
        return _templates.TemplateResponse(
            request,
            "operator/assignments_preview_full_matrix.html",
            {
                "user": user,
                "session": review_session,
                "exclude_self_review": exclude_self,
                "excluded_self_count": excluded_counts.get("self_review", 0),
                "excluded_counts": excluded_counts,
                "stats": stats,
                "existing_count": existing,
                "needs_confirm_replace": existing > 0,
                "missing_confirm": needs_confirm and not is_dry_run,
                "pair_sample": pair_sample,
                "truncated_count": truncated_count,
                "breadcrumbs": breadcrumbs.operator_session_child(
                    review_session, "Preview FullMatrix"
                ),
            },
            status_code=status_code,
        )

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)
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
    dry_run: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    _require_draft(review_session)
    content = await file.read()
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    result = assignments.parse_manual_csv(content, reviewers, reviewees)
    existing = assignments.existing_count(db, review_session.id)

    is_dry_run = dry_run == "true"
    needs_confirm = existing > 0 and confirm_replace != "true"

    def render(status_code: int) -> HTMLResponse:
        pair_sample = result.rows[: assignments.PAIR_PREVIEW_LIMIT]
        truncated_count = max(0, len(result.rows) - assignments.PAIR_PREVIEW_LIMIT)
        return _templates.TemplateResponse(
            request,
            "operator/assignments_preview_manual.html",
            {
                "user": user,
                "session": review_session,
                "issues": result.issues,
                "rows": result.rows,
                "pair_sample": pair_sample,
                "truncated_count": truncated_count,
                "filename": file.filename,
                "existing_count": existing,
                "needs_confirm_replace": existing > 0,
                "missing_confirm": needs_confirm and not is_dry_run and not result.is_blocked,
                "is_blocked": result.is_blocked,
                "breadcrumbs": breadcrumbs.operator_session_child(
                    review_session, "Preview manual import"
                ),
            },
            status_code=status_code,
        )

    if result.is_blocked:
        return render(status.HTTP_400_BAD_REQUEST)

    if is_dry_run:
        return render(status.HTTP_200_OK)

    if needs_confirm:
        return render(status.HTTP_400_BAD_REQUEST)

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)
    pairs, contexts, includes = assignments.manual_rows_to_pairs(
        result.rows, reviewers, reviewees
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
    _require_draft(review_session)
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
    _require_draft(review_session)
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
    _require_draft(review_session)
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
    _require_draft(review_session)
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


@router.post("/sessions/{session_id}/assignments/delete-all")
def assignments_delete_all(
    confirm: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_draft(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    _require_response_loss_ack(db, review_session, acknowledge_response_loss)
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


def _require_draft(review_session: ReviewSession) -> None:
    """Reject mutating operator actions while session is not draft."""
    if not lifecycle.is_draft(review_session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Session is {review_session.status}; revert to draft to edit"
            ),
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


@router.post("/sessions/{session_id}/revert")
def session_revert_to_draft(
    confirm: str | None = Form(default=None),
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
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifecycle.observe_deadline(db, review_session)
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        ).scalars()
    )
    return _templates.TemplateResponse(
        request,
        "operator/instruments_index.html",
        {
            "user": user,
            "session": review_session,
            "instruments": instruments,
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
                review_session, "Set up invites"
            ),
        },
    )


@router.get(
    "/sessions/{session_id}/instruments/{instrument_id}",
    response_class=HTMLResponse,
)
def instrument_detail(
    request: Request,
    bundle: tuple[Instrument, ReviewSession] = Depends(_require_instrument_in_session),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    instrument, review_session = bundle
    lifecycle.observe_deadline(db, review_session)
    db.refresh(instrument)
    return _templates.TemplateResponse(
        request,
        "operator/instrument_detail.html",
        {
            "user": user,
            "session": review_session,
            "instrument": instrument,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, instrument.name
            ),
        },
    )


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
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
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
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
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
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments/{instrument.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


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
