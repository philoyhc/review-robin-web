from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.schemas.sessions import SessionCreate
from app.services import assignments, csv_imports, sessions, validation
from app.web.deps import get_or_create_user, request_correlation_id, require_session_operator

router = APIRouter(prefix="/operator", tags=["operator"])

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
        {"user": user, "sessions": review_sessions},
    )


@router.get("/sessions/new", response_class=HTMLResponse)
def new_session_form(
    request: Request,
    user: User = Depends(get_or_create_user),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_new.html",
        {"user": user},
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_detail.html",
        {
            "user": user,
            "session": review_session,
            "reviewer_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "reviewee_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "assignment_count": assignments.existing_count(db, review_session.id),
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
    return _templates.TemplateResponse(
        request,
        "operator/session_validate.html",
        {
            "user": user,
            "session": review_session,
            "issues": issues,
            "error_count": sum(1 for i in issues if i.is_blocking),
            "warning_count": sum(1 for i in issues if i.severity.value == "warning"),
            "info_count": sum(1 for i in issues if i.severity.value == "info"),
        },
    )


@router.get("/sessions/{session_id}/reviewers/import", response_class=HTMLResponse)
def reviewers_import_form(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_import_reviewers.html",
        {
            "user": user,
            "session": review_session,
            "existing_count": csv_imports.existing_reviewer_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _handle_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewers",
        template="operator/session_import_reviewers.html",
        existing_count_fn=csv_imports.existing_reviewer_count,
        parse_fn=csv_imports.parse_reviewer_csv,
        save_fn=csv_imports.save_reviewers,
    )


@router.get("/sessions/{session_id}/reviewees/import", response_class=HTMLResponse)
def reviewees_import_form(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _templates.TemplateResponse(
        request,
        "operator/session_import_reviewees.html",
        {
            "user": user,
            "session": review_session,
            "existing_count": csv_imports.existing_reviewee_count(db, review_session.id),
            "assignment_count": csv_imports.existing_assignment_count(db, review_session.id),
            "issues": [],
        },
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    return await _handle_import(
        request=request,
        file=file,
        confirm_replace=confirm_replace,
        review_session=review_session,
        user=user,
        db=db,
        kind="reviewees",
        template="operator/session_import_reviewees.html",
        existing_count_fn=csv_imports.existing_reviewee_count,
        parse_fn=csv_imports.parse_reviewee_csv,
        save_fn=csv_imports.save_reviewees,
    )


async def _handle_import(
    *,
    request: Request,
    file: UploadFile,
    confirm_replace: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
    kind: str,
    template: str,
    existing_count_fn,
    parse_fn,
    save_fn,
) -> HTMLResponse | RedirectResponse:
    content = await file.read()
    result = parse_fn(content)
    existing = existing_count_fn(db, review_session.id)
    assignment_count = csv_imports.existing_assignment_count(db, review_session.id)

    def render(status_code: int = status.HTTP_200_OK) -> HTMLResponse:
        return _templates.TemplateResponse(
            request,
            template,
            {
                "user": user,
                "session": review_session,
                "existing_count": existing,
                "assignment_count": assignment_count,
                "issues": result.issues,
                "filename": file.filename,
            },
            status_code=status_code,
        )

    if result.is_blocked:
        return render(status_code=status.HTTP_400_BAD_REQUEST)

    if existing > 0 and confirm_replace != "true":
        return render(status_code=status.HTTP_400_BAD_REQUEST)

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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    pairs, excluded = assignments.generate_full_matrix(
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
                "excluded_self_count": excluded,
                "stats": stats,
                "existing_count": existing,
                "needs_confirm_replace": existing > 0,
                "missing_confirm": needs_confirm and not is_dry_run,
                "pair_sample": pair_sample,
                "truncated_count": truncated_count,
            },
            status_code=status_code,
        )

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.full_matrix,
        correlation_id=request_correlation_id(),
        excluded_self_count=excluded,
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
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
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
            },
            status_code=status_code,
        )

    if result.is_blocked:
        return render(status.HTTP_400_BAD_REQUEST)

    if is_dry_run:
        return render(status.HTTP_200_OK)

    if needs_confirm:
        return render(status.HTTP_400_BAD_REQUEST)

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
        excluded_self_count=0,
        filename=file.filename,
        contexts=contexts,
        includes=includes,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
    )
