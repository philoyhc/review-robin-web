from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    Instrument,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.schemas.assignments import AssignmentMode
from app.schemas.sessions import SessionCreate
from app.services import (
    assignments,
    csv_imports,
    email_templates,
    instruments as instruments_service,
    invitations,
    monitoring,
    operator_settings,
    responses,
    sessions,
    validation,
)
from app.services import lifecycle_display, session_lifecycle as lifecycle
from app.services._secrets import MissingEncryptionKey
from app.web.return_to import resolve_return_to
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
_templates.env.filters["lifecycle_label"] = (
    lifecycle_display.lifecycle_display_label
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


def _settings_redirect_url(return_to_raw: str | None) -> str:
    """Save / Clear keep the operator on the Settings page (so they
    can verify their changes); the ``return_to`` query param rides
    along on the redirect so the back-link stays wired through the
    Save → reload cycle."""
    if return_to_raw:
        from urllib.parse import quote

        return f"/operator/settings?return_to={quote(return_to_raw, safe='/')}"
    return "/operator/settings"


@router.get("/settings", response_class=HTMLResponse)
def operator_settings_form(
    request: Request,
    return_to: str | None = Query(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Operator-level Settings page — today: SMTP credentials only.

    Per-operator (send-as-me identity model). The page renders even
    when ``SMTP_ENCRYPTION_KEY`` isn't configured — the encryption
    helper only fires on Save / Clear, so a deployment can defer
    setting the env var until operators actually start configuring.

    Honours ``?return_to=<path>`` per ``app.web.return_to`` (same
    allowlist as the About page) so the page surfaces a "← Back to
    {context}" link and Cancel routes to the originating surface.
    """
    db.refresh(user)
    has_password = user.smtp_password_encrypted is not None
    target = resolve_return_to(return_to, db)
    return _templates.TemplateResponse(
        request,
        "operator/operator_settings.html",
        {
            "user": user,
            "has_password": has_password,
            "encryption_modes": operator_settings.SMTP_ENCRYPTION_MODES,
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
            "breadcrumbs": breadcrumbs.operator_root(),
        },
    )


@router.post("/settings")
def operator_settings_save(
    smtp_host: str | None = Form(default=None),
    smtp_port: str | None = Form(default=None),
    smtp_username: str | None = Form(default=None),
    smtp_password: str | None = Form(default=None),
    smtp_from_display_name: str | None = Form(default=None),
    smtp_encryption: str | None = Form(default=None),
    return_to: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    parsed_port: int | None = None
    if smtp_port and smtp_port.strip():
        try:
            parsed_port = int(smtp_port)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="smtp_port must be an integer",
            ) from exc
    if smtp_encryption and smtp_encryption not in operator_settings.SMTP_ENCRYPTION_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "smtp_encryption must be one of "
                f"{operator_settings.SMTP_ENCRYPTION_MODES}"
            ),
        )
    try:
        operator_settings.save_email_settings(
            db,
            user=user,
            host=smtp_host,
            port=parsed_port,
            username=smtp_username,
            plaintext_password=smtp_password,
            from_display_name=smtp_from_display_name,
            encryption=smtp_encryption,
            correlation_id=request_correlation_id(),
        )
    except MissingEncryptionKey as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return RedirectResponse(
        url=_settings_redirect_url(return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/settings/clear")
def operator_settings_clear(
    return_to: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    operator_settings.clear_email_settings(
        db, user=user, correlation_id=request_correlation_id()
    )
    return RedirectResponse(
        url=_settings_redirect_url(return_to),
        status_code=status.HTTP_303_SEE_OTHER,
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
            "quick_setup": views.build_new_session_quick_setup_context(),
            "breadcrumbs": breadcrumbs.operator_new_session(),
        },
    )


@router.post("/sessions")
def create_session(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    help_contact: str | None = Form(default=None),
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
        help_contact=help_contact or None,
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
            # Freshly-created draft with at least one of reviewers /
            # reviewees / assignments still empty. Computed after the
            # validation flow so a session that just transitioned
            # ``draft → validated`` no longer falls through this gate.
            "is_setup_empty": (
                lifecycle.is_draft(review_session)
                and (
                    csv_imports.existing_reviewer_count(db, review_session.id) == 0
                    or csv_imports.existing_reviewee_count(db, review_session.id) == 0
                    or assignments.existing_count(db, review_session.id) == 0
                )
            ),
            "has_responses": lifecycle.session_has_responses(db, review_session),
            "quick_setup": views.build_quick_setup_context(
                db,
                review_session,
                is_unlocked=_quick_setup_unlocked(request, review_session),
                error_kind=quick_setup_error,
                error_reason=quick_setup_reason,
            ),
            "extract_data": views.build_extract_data_context(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session(review_session),
        },
    )


@router.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_session(
    request: Request,
    severity: str = "all",
    activate: int = 0,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> Response:
    issues = validation.validate_session_setup(db, review_session)
    report = lifecycle.build_readiness_report(issues)
    # Activate-warns detour: ?activate=1 requests the inline
    # confirmation banner (Segment 11G PR D). It only renders on
    # ``validated`` sessions that have warnings or new errors. On
    # ineligible states (draft / ready / closed) or when there's
    # nothing to acknowledge, drop the param and 303 to the clean
    # URL — operator can activate (or not) from Home.
    activate_banner: dict[str, object] | None = None
    if activate:
        if not lifecycle.is_validated(review_session):
            return RedirectResponse(
                url=f"/operator/sessions/{review_session.id}/validate",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        if report.errors:
            activate_banner = {
                "kind": "error",
                "errors": report.errors,
            }
        elif report.warnings:
            activate_banner = {
                "kind": "warning",
                "warnings": report.warnings,
            }
        else:
            return RedirectResponse(
                url=f"/operator/sessions/{review_session.id}/validate",
                status_code=status.HTTP_303_SEE_OTHER,
            )
    validate_ctx = views.build_validate_context(
        db, review_session, issues, severity_filter=severity
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_validate.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "issues": issues,
            "validate": validate_ctx,
            "activate_banner": activate_banner,
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
        return _templates.TemplateResponse(
            request,
            template,
            {
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
        url=f"/operator/sessions/{review_session.id}/{kind}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 11J PR A — Quick Setup card live wiring
# --------------------------------------------------------------------------- #
#
# Three live POST endpoints back the Quick Setup card on Session Home:
#
#   - ``POST /sessions/{id}/quick-setup/lock`` flips the per-session
#     ``HttpOnly`` cookie that drives the card's ``is_locked`` state.
#   - ``POST /sessions/{id}/quick-setup/reviewers`` /
#     ``POST /sessions/{id}/quick-setup/reviewees`` delegate to a thin
#     ``_handle_quick_setup_import`` wrapper that reuses the existing
#     per-entity import pipeline. On success the wrapper 303s back to
#     Session Home with no flag (the slot's count indicator is the
#     success signal). On parse / validation / lifecycle rejection it
#     303s with ``?quick_setup_error={kind}&quick_setup_reason=...``
#     so the GET render places a ``.banner.banner-error`` inside the
#     offending slot.
#
# Slot 3 (Assignments) and slot 4 (Settings) ship in PR B / Segment
# 12A respectively and are not yet wired here.


_QUICK_SETUP_COOKIE_PREFIX = "qsu"


def _quick_setup_cookie_name(session_id: int) -> str:
    return f"{_QUICK_SETUP_COOKIE_PREFIX}_{session_id}"


def _quick_setup_unlocked(request: Request, review_session: ReviewSession) -> bool:
    """``True`` when the operator's last lock-toggle action was Unlock.

    Read from the per-session cookie set by
    ``POST /sessions/{id}/quick-setup/lock``. Absent ⇒ default locked.
    """

    return request.cookies.get(_quick_setup_cookie_name(review_session.id)) == "1"


@router.post(
    "/sessions/{session_id}/quick-setup/lock",
    response_class=HTMLResponse,
    response_model=None,
)
def quick_setup_lock_toggle(
    action: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Flip the Quick Setup card's per-session lock cookie.

    ``action="unlock"`` sets ``qsu_{id}=1`` (and the next render
    drops ``.locked`` from the body wrapper); ``action="lock"`` clears
    the cookie. The toggle is visual only — the service layer
    (``_require_editable``) stays the source of truth for whether a
    slot's submit can mutate.
    """

    redirect = RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}#quick-setup"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    cookie_name = _quick_setup_cookie_name(review_session.id)
    cookie_path = f"/operator/sessions/{review_session.id}"
    if action == "unlock":
        redirect.set_cookie(
            key=cookie_name,
            value="1",
            path=cookie_path,
            httponly=True,
            samesite="lax",
        )
    else:
        redirect.delete_cookie(
            key=cookie_name,
            path=cookie_path,
        )
    # Touch unused params to silence type checkers; ``user`` / ``db``
    # are pulled in for the operator-permission dependency chain.
    del user, db
    return redirect


@router.post(
    "/sessions/{session_id}/quick-setup/reviewers",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewers_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
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
    "/sessions/{session_id}/quick-setup/reviewees",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_reviewees_submit(
    request: Request,
    file: UploadFile = File(...),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    return await _handle_quick_setup_import(
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


async def _handle_quick_setup_import(
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
) -> RedirectResponse:
    """Quick Setup card slot handler — thin wrapper over the same
    parse / save pipeline the per-entity Setup pages use.

    On success: 303 → Session Home with no flag; the slot's count
    indicator on the next render is the success signal (per the
    "no flash banner" direction in segment_11J).

    On parse / validation failure, missing-confirm, or lifecycle
    rejection: 303 → Session Home with ``?quick_setup_error={kind}``
    and a ``quick_setup_reason`` token that drives the slot's
    inline ``banner-error`` copy.
    """

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = f"#quick-setup-{kind}"

    def error_redirect(reason: str) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error={kind}"
                f"&quick_setup_reason={reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not lifecycle.is_editable(review_session):
        return error_redirect("lifecycle")

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

    if result.is_blocked or any(
        issue.severity == "error" for issue in result.issues
    ):
        return error_redirect("parse")

    existing = existing_count_fn(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return error_redirect("needs_confirm")

    if existing > 0:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return error_redirect("needs_confirm")

    save_fn(
        db,
        session=review_session,
        user=user,
        rows=result.rows,
        filename=file.filename or "",
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/quick-setup/assignments",
    response_class=HTMLResponse,
    response_model=None,
)
async def quick_setup_assignments_submit(
    file: UploadFile | None = File(default=None),
    rule: str = Form(default="full_matrix"),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Quick Setup card slot 3 (Assignments) handler.

    Auto-detects mode from the form payload: when ``file`` is
    attached and non-empty, the route runs the manual-CSV pipeline;
    otherwise it generates assignments from the selected rule
    (FullMatrix only today; richer rule menu lands in Segment 13A).

    Lifecycle / parse / confirm-required failures 303 → Home with
    ``?quick_setup_error=assignments&quick_setup_reason=...``; the
    GET render places the corresponding ``.banner.banner-error``
    inside the slot. Success 303s back to Home with no flag — the
    slot's count + active-rule indicator updates in place.
    """

    home_url = f"/operator/sessions/{review_session.id}"
    fragment = "#quick-setup-assignments"

    def error_redirect(reason: str) -> RedirectResponse:
        return RedirectResponse(
            url=(
                f"{home_url}?quick_setup_error=assignments"
                f"&quick_setup_reason={reason}{fragment}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not lifecycle.is_editable(review_session):
        return error_redirect("lifecycle")

    file_content = b""
    if file is not None and file.filename:
        file_content = await file.read()

    use_csv_mode = bool(file_content)
    existing = assignments.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return error_redirect("needs_confirm")
    if existing > 0:
        try:
            _require_response_loss_ack(
                db, review_session, acknowledge_response_loss
            )
        except HTTPException:
            return error_redirect("needs_confirm")

    exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)

    if use_csv_mode:
        assert file is not None  # narrowed by ``use_csv_mode`` guard
        result = assignments.parse_manual_csv(
            file_content, reviewers, reviewees
        )
        if result.is_blocked or any(
            issue.severity == "error" for issue in result.issues
        ):
            return error_redirect("parse")
        rows = result.rows
        if exclude_self:
            rows = [
                r
                for r in rows
                if r.reviewer_email.casefold()
                != r.reviewee_identifier.casefold()
            ]
        pairs, contexts, includes = assignments.manual_rows_to_pairs(
            rows, reviewers, reviewees
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
    else:
        # Rule mode. ``rule`` is FullMatrix-only today; richer menu
        # lands in Segment 13A. Reject unknown values defensively.
        if rule != "full_matrix":
            return error_redirect("parse")
        pairs, excluded_counts = assignments.generate_full_matrix(
            reviewers, reviewees, exclude_self_review=exclude_self
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
        url=f"{home_url}{fragment}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/assignments", response_class=HTMLResponse)
def assignments_hub(
    request: Request,
    rule_based_error: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return _render_assignments_hub(
        request,
        db,
        review_session,
        user,
        rule_based_error=rule_based_error,
    )


def _render_assignments_hub(
    request: Request,
    db: Session,
    review_session: ReviewSession,
    user: User,
    *,
    issues: list | None = None,
    missing_confirm: bool = False,
    is_blocked: bool = False,
    rule_based_error: str | None = None,
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
            "status_pills": views.session_status_pills(db, review_session),
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
            "rule_based_card": views.build_rule_based_card_context(
                db,
                review_session,
                user=user,
                assignment_count=assignment_count,
                error_kind=rule_based_error,
            ),
        },
        status_code=status_code,
    )


@router.get(
    "/sessions/{session_id}/assignments/rule-based/edit/{rule_set_id}",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_editor(
    request: Request,
    rule_set_id: int,
    error: str | None = Query(default=None),
    saved: str | None = Query(default=None),
    renamed: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    from app.services.rules import library

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set, revision = loaded

    # Personal RuleSets are operator-private — only the owner can
    # open the editor on them. Seeds are visible to every operator.
    if not rule_set.is_seed and rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    error_messages = {
        "empty_name": "Pick a name for the new RuleSet before clicking Save.",
        "malformed_json": "The edited rule list could not be parsed.",
        "validation": (
            "One or more rules failed validation. Check operator-"
            "operand pairings, regexes, and quota bounds."
        ),
        "bad_combinator": "Pick a combinator (All / Any / In sequence).",
        "bad_seed": "RuleSet seed must be an integer.",
        "needs_delete_confirm": (
            "Delete not confirmed. Tick the confirm checkbox before "
            "clicking Delete."
        ),
    }
    editor = views.build_rule_based_editor_context(
        review_session,
        rule_set=rule_set,
        revision=revision,
        user=user,
        error_kind=error,
        error_message=error_messages.get(error or "") if error else None,
        saved_flash=(saved == "1"),
        renamed_flash=(renamed == "1"),
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_rule_based_editor.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "editor": editor,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, f"Rule Based · {rule_set.name}"
            ),
        },
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/copy",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_copy(
    request: Request,
    rule_set_id: int = Form(...),
    new_name: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from app.services.rules import library

    cleaned_name = new_name.strip()
    if not cleaned_name:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}"
                f"/assignments/rule-based/edit/{rule_set_id}"
                "?error=empty_name"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    source_rule_set, source_revision = loaded

    # Visibility rule: operators can copy any seed (visible to all)
    # plus any of their own Personal RuleSets, but not someone else's
    # Personal RuleSets.
    if (
        not source_rule_set.is_seed
        and source_rule_set.owner_user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    new_rule_set = library.copy_rule_set(
        db,
        source=source_rule_set,
        source_revision=source_revision,
        owner=user,
        new_name=cleaned_name,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based/edit/{new_rule_set.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/save-as",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_save_as(
    request: Request,
    source_rule_set_id: int = Form(...),
    new_name: str = Form(...),
    combinator: str = Form(...),
    exclude_self_reviews: str | None = Form(default=None),
    seed: str | None = Form(default=None),
    rules_json: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save the in-editor edited tree as a new Personal RuleSet
    (Segment 13A PR 5b). Always creates a new row; PR 6's Save will
    add the in-place revision write."""

    import json

    from pydantic import ValidationError

    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
    )
    from app.services.rules import library

    cleaned_name = new_name.strip()
    redirect_back = (
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{source_rule_set_id}"
    )

    if not cleaned_name:
        return RedirectResponse(
            url=f"{redirect_back}?error=empty_name",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Source RuleSet must exist + be visible to caller. Even though
    # Save As writes a brand-new row, we tie the audit's
    # ``refs.source_rule_set_id`` back to it for provenance, and the
    # 403 guard is the same as the Copy path.
    loaded = library.load_rule_set(db, source_rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    source_rule_set, source_revision = loaded
    if (
        not source_rule_set.is_seed
        and source_rule_set.owner_user_id != user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    try:
        parsed_rules = json.loads(rules_json)
    except json.JSONDecodeError:
        return RedirectResponse(
            url=f"{redirect_back}?error=malformed_json",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if not isinstance(parsed_rules, list):
        return RedirectResponse(
            url=f"{redirect_back}?error=malformed_json",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if combinator not in {c.value for c in Combinator}:
        return RedirectResponse(
            url=f"{redirect_back}?error=bad_combinator",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    seed_value: int | None = None
    if seed is not None and seed.strip():
        try:
            seed_value = int(seed.strip())
        except ValueError:
            return RedirectResponse(
                url=f"{redirect_back}?error=bad_seed",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    try:
        rule_set_schema = RuleSetSchema(
            id=None,
            name=cleaned_name,
            description=source_rule_set.description or "",
            scope="personal",  # type: ignore[arg-type]
            combinator=Combinator(combinator),
            rules=parsed_rules,  # type: ignore[arg-type]
            options=RuleSetOptions(
                excludeSelfReviews=(exclude_self_reviews == "true"),
                seed=seed_value,
            ),
        )
    except ValidationError:
        return RedirectResponse(
            url=f"{redirect_back}?error=validation",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    new_rule_set = library.save_as_rule_set_from_schema(
        db,
        rule_set_schema=rule_set_schema,
        owner=user,
        new_name=cleaned_name,
        source_rule_set_id=source_rule_set.id,
        source_revision_id=source_revision.id,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}"
            f"/assignments/rule-based/edit/{new_rule_set.id}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/save",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_save(
    request: Request,
    rule_set_id: int = Form(...),
    combinator: str = Form(...),
    exclude_self_reviews: str | None = Form(default=None),
    seed: str | None = Form(default=None),
    rules_json: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """In-place Save for a Personal RuleSet — appends a new revision
    (Segment 13A PR 6). Past audit refs to old revisions stay
    resolvable because revisions are retained, not deleted."""

    import json

    from pydantic import ValidationError

    from app.schemas.rules import (
        Combinator,
        RuleSetOptions,
        RuleSetSchema,
    )
    from app.services.rules import library

    redirect_back = (
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{rule_set_id}"
    )

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set, _ = loaded
    if rule_set.is_seed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seeded RuleSets are read-only.",
        )
    if rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    if combinator not in {c.value for c in Combinator}:
        return RedirectResponse(
            url=f"{redirect_back}?error=bad_combinator",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    seed_value: int | None = None
    if seed is not None and seed.strip():
        try:
            seed_value = int(seed.strip())
        except ValueError:
            return RedirectResponse(
                url=f"{redirect_back}?error=bad_seed",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    try:
        parsed_rules = json.loads(rules_json)
    except json.JSONDecodeError:
        return RedirectResponse(
            url=f"{redirect_back}?error=malformed_json",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if not isinstance(parsed_rules, list):
        return RedirectResponse(
            url=f"{redirect_back}?error=malformed_json",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        rule_set_schema = RuleSetSchema(
            id=rule_set.id,
            name=rule_set.name,
            description=rule_set.description or "",
            scope="personal",  # type: ignore[arg-type]
            combinator=Combinator(combinator),
            rules=parsed_rules,  # type: ignore[arg-type]
            options=RuleSetOptions(
                excludeSelfReviews=(exclude_self_reviews == "true"),
                seed=seed_value,
            ),
        )
    except ValidationError:
        return RedirectResponse(
            url=f"{redirect_back}?error=validation",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    library.save_in_place(
        db,
        rule_set=rule_set,
        rule_set_schema=rule_set_schema,
        actor=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"{redirect_back}?saved=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/rename",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_rename(
    request: Request,
    rule_set_id: int = Form(...),
    new_name: str = Form(...),
    new_description: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from app.services.rules import library

    redirect_back = (
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{rule_set_id}"
    )

    cleaned_name = new_name.strip()
    if not cleaned_name:
        return RedirectResponse(
            url=f"{redirect_back}?error=empty_name",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set, _ = loaded
    if rule_set.is_seed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seeded RuleSets are read-only.",
        )
    if rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    library.rename_rule_set(
        db,
        rule_set=rule_set,
        new_name=cleaned_name,
        new_description=(new_description or "").strip(),
        actor=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"{redirect_back}?renamed=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/delete",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_delete(
    request: Request,
    rule_set_id: int = Form(...),
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from app.services.rules import library

    redirect_back = (
        f"/operator/sessions/{review_session.id}"
        f"/assignments/rule-based/edit/{rule_set_id}"
    )

    if confirm != "true":
        return RedirectResponse(
            url=f"{redirect_back}?error=needs_delete_confirm",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set, _ = loaded
    if rule_set.is_seed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Seeded RuleSets are read-only.",
        )
    if rule_set.owner_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That RuleSet is private to its owner.",
        )

    library.soft_delete_rule_set(
        db,
        rule_set=rule_set,
        actor=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/assignments"
            "?rule_based_error=rule_set_deleted"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/assignments/rule-based/generate",
    response_class=HTMLResponse,
    response_model=None,
)
def rule_based_generate(
    request: Request,
    rule_set_id: int = Form(...),
    exclude_self_review: str | None = Form(default=None),
    confirm_replace: str | None = Form(default=None),
    acknowledge_response_loss: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    from pydantic import TypeAdapter

    from app.schemas.rules import Combinator, Rule, RuleSetOptions, RuleSetSchema
    from app.services.rules import engine, library

    _require_editable(review_session)

    loaded = library.load_rule_set(db, rule_set_id)
    if loaded is None:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=missing_rule_set"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    rule_set_row, revision = loaded

    existing = assignments.existing_count(db, review_session.id)
    if existing > 0 and confirm_replace != "true":
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/assignments"
                "?rule_based_error=needs_confirm"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if existing > 0:
        _require_response_loss_ack(db, review_session, acknowledge_response_loss)

    # Rehydrate the persisted RuleSet through the typed schema so the
    # engine sees the same shape as the editor would. Validators run
    # at ``model_validate`` time; the seed installer + editor save
    # paths already gate on that, so a malformed row here is a
    # data-integrity bug rather than user error.
    rule_adapter = TypeAdapter(Rule)
    rule_set_schema = RuleSetSchema(
        id=rule_set_row.id,
        name=rule_set_row.name,
        description=rule_set_row.description or "",
        scope=rule_set_row.scope,  # type: ignore[arg-type]
        combinator=Combinator(revision.combinator),
        rules=[
            rule_adapter.validate_python(payload)
            for payload in revision.rules_json
        ],
        options=RuleSetOptions(
            excludeSelfReviews=revision.exclude_self_reviews,
            seed=revision.seed,
        ),
    )

    override_exclude_self = exclude_self_review == "true"
    reviewers = assignments.list_reviewers(db, review_session.id)
    reviewees = assignments.list_reviewees(db, review_session.id)
    result = engine.evaluate(
        rule_set_schema,
        reviewers=reviewers,
        reviewees=reviewees,
        override_exclude_self_reviews=override_exclude_self,
        revision_seed=revision.id,
    )

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=result.pairs,
        mode=AssignmentMode.rule_based,
        correlation_id=request_correlation_id(),
        excluded_counts=result.excluded_counts,
        rule_set_revision=revision,
        exclude_self_reviews=override_exclude_self,
    )

    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/assignments",
        status_code=status.HTTP_303_SEE_OTHER,
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
            "status_pills": views.session_status_pills(db, review_session),
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


@router.get("/sessions/{session_id}/edit", response_class=HTMLResponse)
def session_edit_form(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
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


@router.get(
    "/sessions/{session_id}/instruments",
    response_class=HTMLResponse,
)
def instruments_index(
    request: Request,
    editing: int | None = Query(default=None),
    saved: int | None = Query(default=None),
    rtd_error: str | None = Query(default=None),
    rtd_id: int | None = Query(default=None),
    rf_save_error: str | None = Query(default=None),
    editing_rtd_id: int | None = Query(default=None),
    rtd_delete_blocked_id: int | None = Query(default=None),
    rtd_delete_blocked_rfs: int | None = Query(default=None),
    rtd_delete_blocked_instruments: int | None = Query(default=None),
    rtd_delete_blocked_responses: int | None = Query(default=None),
    rtd_delete_blocked_assignments: int | None = Query(default=None),
    rtd_would_empty_id: int | None = Query(default=None),
    rtd_would_empty_instruments: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    context = views.build_instruments_context(
        db,
        review_session=review_session,
        user=user,
        editing=editing,
        saved=saved,
        rtd_error=rtd_error,
        rtd_id=rtd_id,
        rf_save_error=rf_save_error,
        editing_rtd_id=editing_rtd_id,
        rtd_delete_blocked_id=rtd_delete_blocked_id,
        rtd_delete_blocked_rfs=rtd_delete_blocked_rfs,
        rtd_delete_blocked_instruments=rtd_delete_blocked_instruments,
        rtd_delete_blocked_responses=rtd_delete_blocked_responses,
        rtd_delete_blocked_assignments=rtd_delete_blocked_assignments,
        rtd_would_empty_id=rtd_would_empty_id,
        rtd_would_empty_instruments=rtd_would_empty_instruments,
    )
    return _templates.TemplateResponse(
        request, "operator/instruments_index.html", context
    )


_VALID_TEMPLATES = ("invitation", "reminder", "responses_received")


def _build_field_rows(
    review_session: ReviewSession, template: str
) -> list[dict[str, Any]]:
    """For each (field, key, default) tuple on the active template,
    return the dict the editor template iterates over to render
    each editable field plus its per-field "Reset to default" link.
    """
    rows: list[dict[str, Any]] = []
    for spec in email_templates.TEMPLATE_FIELDS[template]:
        override = email_templates.get_override(review_session, spec["key"])
        rows.append(
            {
                "field": spec["field"],
                "key": spec["key"],
                "value": override if override is not None else spec["default"],
                "default": spec["default"],
                "has_override": override is not None,
            }
        )
    return rows


@router.get("/sessions/{session_id}/setupinvite", response_class=HTMLResponse)
def setupinvite_form(
    request: Request,
    template: str = Query(default="invitation"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if template not in _VALID_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown template",
        )
    return _templates.TemplateResponse(
        request,
        "operator/session_setupinvite.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "active_template": template,
            "valid_templates": _VALID_TEMPLATES,
            "rows": _build_field_rows(review_session, template),
            "merge_tags": views.merge_tags_for_template(template),
            "responses_received_enabled": (
                email_templates.responses_received_enabled(review_session)
            ),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Email Template"
            ),
        },
    )


@router.post("/sessions/{session_id}/setupinvite")
async def setupinvite_save(
    request: Request,
    template: str = Form(default="invitation"),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if template not in _VALID_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown template",
        )
    form = await request.form()
    updates: dict[str, str | None] = {}
    for spec in email_templates.TEMPLATE_FIELDS[template]:
        raw = form.get(spec["field"])
        if not isinstance(raw, str):
            continue
        # Empty submission for any field falls through to the default
        # by removing the override key. Whitespace-only is treated as
        # empty for the same reason.
        updates[spec["key"]] = raw if raw.strip() else None
    changes = email_templates.set_overrides(review_session, updates)
    # Responses-received tab carries one extra control: a checkbox
    # backing ``responses_received_enabled``. Browsers omit unchecked
    # checkboxes from the form payload entirely, so absence == off
    # for this template; absence on any other template is ignored.
    if template == "responses_received":
        enabled_change = email_templates.set_responses_received_enabled(
            review_session,
            enabled=("enabled" in form),
        )
        if enabled_change is not None:
            changes[email_templates.RESPONSES_RECEIVED_ENABLED_KEY] = enabled_change
    email_templates.record_template_change(
        db,
        review_session=review_session,
        user=user,
        template=template,
        changes=changes,
        correlation_id=request_correlation_id(),
    )
    db.commit()
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/setupinvite?template={template}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/setupinvite/reset")
def setupinvite_reset(
    template: str = Form(...),
    field: str = Form(...),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if template not in _VALID_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown template",
        )
    spec = next(
        (s for s in email_templates.TEMPLATE_FIELDS[template] if s["field"] == field),
        None,
    )
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown field",
        )
    changes = email_templates.set_overrides(review_session, {spec["key"]: None})
    email_templates.record_template_reset(
        db,
        review_session=review_session,
        user=user,
        template=template,
        field=field,
        changes=changes,
        correlation_id=request_correlation_id(),
    )
    db.commit()
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/setupinvite"
            f"?template={template}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/previews", response_class=HTMLResponse)
def previews_index(
    request: Request,
    reviewer_email: str = "",
    email: str = "invitation",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Operations-row Previews tab — pre-flight reviewer experience hub.

    Distinct from ``/preview`` (singular), which is the operator's
    preview of the reviewer surface and is retired in PR C of segment
    11F. URL state:

    - ``?reviewer_email=…`` selects the picker's current reviewer; an
      unmatched value renders an inline "No reviewer matched" note
      rather than 404 or fall back to first.
    - ``?email=invitation|reminder|responses_received`` selects the
      active email-preview tab. PR B ships only the invitation render;
      unknown / unshipped values fall through to invitation so the
      page never blanks out.
    """
    picker = views.build_preview_picker_context(
        db, review_session, reviewer_email
    )
    active_email_tab = views.resolve_email_preview_tab(email)
    email_body: views.EmailBody | None = None
    surface_card: views.SurfacePreviewContext | None = None
    surface_html: str | None = None
    if picker.current is not None:
        reviewer_obj = db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id,
                Reviewer.id == picker.current.reviewer_id,
            )
        ).scalar_one()
        from_display = views.email_preview_from_display(user)
        email_body = views.build_email_preview_body(
            tab=active_email_tab,
            review_session=review_session,
            reviewer=reviewer_obj,
            from_display=from_display,
        )
        surface_card = views.build_surface_preview_context(
            db=db,
            user=user,
            review_session=review_session,
            reviewer=reviewer_obj,
        )
        if surface_card.preview is not None:
            # The iframe document is its own page, so breadcrumbs +
            # request go through the rendering context — the
            # breadcrumb partial in the operator chrome reads them
            # via Jinja's default. We point breadcrumbs at the
            # previews hub itself rather than back to a "Preview"
            # leaf so the operator-chrome trail inside the iframe
            # mirrors where they actually are.
            surface_html = _templates.get_template(
                "reviewer/review_surface.html"
            ).render(
                {
                    **surface_card.preview,
                    "request": request,
                    "breadcrumbs": breadcrumbs.operator_session_child(
                        review_session, "Previews"
                    ),
                }
            )
    return _templates.TemplateResponse(
        request,
        "operator/session_previews.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Previews"
            ),
            "picker": picker,
            "email_tabs": views.EMAIL_PREVIEW_TABS,
            "active_email_tab": active_email_tab,
            "email_body": email_body,
            "surface_card": surface_card,
            "surface_html": surface_html,
        },
    )


@router.post("/sessions/{session_id}/previews/random")
def previews_random(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Pick a random reviewer and 303 to the previews page.

    Random selection happens server-side via ``secrets.choice`` so no
    list of reviewer emails has to leak into client-side JS. Empty
    sessions 303 back without a ``?reviewer_email=`` param so the
    picker stays in its disabled empty state.
    """
    reviewers = list(
        db.execute(
            select(Reviewer)
            .where(Reviewer.session_id == review_session.id)
            .order_by(Reviewer.email)
        ).scalars()
    )
    base_url = f"/operator/sessions/{review_session.id}/previews"
    if not reviewers:
        return RedirectResponse(
            url=base_url, status_code=status.HTTP_303_SEE_OTHER
        )
    selected = secrets.choice(reviewers)
    return RedirectResponse(
        url=f"{base_url}?reviewer_email={quote(selected.email)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/preview")
def session_preview(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Permanent redirect from the standalone reviewer-surface preview
    (Segment 10B-3) to the consolidated previews hub's surface card
    (Segment 11F PR C).

    Status 308 keeps the GET method and preserves the bookmark / link
    semantics for stragglers. The fragment lands the operator on the
    surface card directly. The hub renders the surface card only after
    the operator picks a reviewer in the picker, so this redirect lands
    on the empty-state body until they do.
    """
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/previews"
            f"#reviewer-surface"
        ),
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


def _instruments_redirect(
    session_id: int, fragment: str | None = None
) -> RedirectResponse:
    """Redirect to the Instruments index, optionally landing on an
    in-page anchor.

    Per-instrument actions (open / close / visibility / save) should
    pass ``fragment="instrument-{id}"`` so the operator lands on the
    instrument they were just acting on instead of being yanked to
    the top of the page. Bulk actions (accepting/visibility all-on/
    off) pass no fragment — they affect the whole list, so landing
    at the top is appropriate.
    """
    url = f"/operator/sessions/{session_id}/instruments"
    if fragment:
        url = f"{url}#{fragment}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


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

    # Validation is now derived from the chosen Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored.
    _ = validation_min, validation_max  # silence unused-arg

    try:
        instruments_service.add_response_field(
            db,
            instrument=instrument,
            field_key=key,
            label=label,
            response_type=response_type,
            required=required == "true",
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

    # Validation now derives from the field's Response Type
    # Definition (Slice 4a); the legacy ``validation_min`` /
    # ``validation_max`` form fields are accepted but ignored, and
    # the existing derived block on the row is preserved as-is.
    _ = validation_min, validation_max  # silence unused-arg
    validation_block = field.validation

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

    # Slice 4d Gap 2: refuse to save an instrument with zero
    # Response Fields rows. Compute the post-save RF count up-front
    # (existing - deletes + new_* draft adds) and bounce back to the
    # editing context with an inline error banner if it would be
    # zero. Symmetric with the cascade-side guard on the Response
    # Type Definitions card.
    existing_rf_count = int(
        db.execute(
            select(func.count(instruments_service.InstrumentResponseField.id)).where(
                instruments_service.InstrumentResponseField.instrument_id
                == instrument.id
            )
        ).scalar_one()
    )
    new_response_count = sum(
        1
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    )
    # Deduplicate ``new_*`` ids — duplicates in the form payload
    # don't create extra rows.
    new_unique_ids = {
        raw_id
        for kind, raw_id in zip(kinds, raw_ids)
        if kind == "response"
        and raw_id.startswith("new_")
        and raw_id not in {str(d) for d in response_delete_ids}
    }
    new_response_count = len(new_unique_ids)
    post_save_rf_count = (
        existing_rf_count - len(response_delete_ids) + new_response_count
    )
    if post_save_rf_count <= 0:
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?editing={instrument.id}"
                f"&rf_save_error=An+instrument+must+have+at+least+one+response+field."
                f"#instrument-{instrument.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
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
    #    creates them via ``add_default_response_field``, passing the
    #    operator-chosen RTD (Slice 4c), the typed label, and the
    #    Required flag so the new row lands at the right shape on
    #    Save. ``add_default_response_field`` slugifies the label
    #    into a non-conflicting ``field_key`` (falling back to the
    #    auto ``rating{N}`` series when the label is blank).
    #    The bulk-save step below then folds in any subsequent edits.
    new_rtd_targets = [str(v) for v in form.getlist("new_rtd_target")]
    new_rtd_ids = [str(v) for v in form.getlist("new_rtd_id")]
    new_rtd_by_draft: dict[str, int] = {}
    if len(new_rtd_targets) == len(new_rtd_ids):
        for target, rtd_id_str in zip(new_rtd_targets, new_rtd_ids):
            try:
                new_rtd_by_draft[target] = int(rtd_id_str)
            except ValueError:
                continue
    new_label_by_draft: dict[str, str] = {}
    for kind, raw_id, label_value in zip(kinds, raw_ids, labels):
        if kind == "response" and raw_id.startswith("new_"):
            new_label_by_draft[raw_id] = label_value

    new_id_map: dict[str, int] = {}
    for kind, raw_id in zip(kinds, raw_ids):
        if kind != "response":
            continue
        if not raw_id.startswith("new_") or raw_id in new_id_map:
            continue
        if raw_id in {str(d) for d in response_delete_ids}:
            continue  # added then deleted before save — skip
        new_field = instruments_service.add_default_response_field(
            db,
            instrument=instrument,
            after_field_id=None,
            rtd_id=new_rtd_by_draft.get(raw_id),
            label=new_label_by_draft.get(raw_id),
            required=raw_id in required_id_strs,
            actor=user,
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
    # Section A — short_label shares the same Save / Cancel state machine
    # as description. Per Segment 11L, the field is reviewer-facing and
    # capped at 32 chars (HTML5 ``maxlength`` is the user-visible
    # guardrail; the service helper raises ValueError as a defensive
    # fallback that yields HTTP 400).
    if "short_label" in form:
        submitted_label = form.get("short_label")
        try:
            instruments_service.update_short_label(
                db,
                instrument=instrument,
                short_label=(
                    submitted_label
                    if isinstance(submitted_label, str)
                    else None
                ),
                actor=user,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
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
    instrument = instruments_service.create_instrument(
        db, review_session=review_session, after_instrument_id=after, actor=user
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/instruments#instrument-{instrument.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- Slice 4b: operator add / edit / delete on Response Type
# Definitions card. ``response_type`` (name) + ``data_type`` are
# spec-locked once a row is saved, so the edit route only accepts
# Min / Max / Step / List. Cascade-on-delete confirmation is
# handled via a redirect-with-query when the dependent count is
# nonzero and ``confirm`` is not set.

def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse {raw!r} as a number.",
        )


def _rtd_redirect_with_error(
    session_id: int,
    *,
    error: str,
    rtd_id: int | None = None,
    keep_editing: bool = False,
) -> RedirectResponse:
    fragment = "rtd-card" if rtd_id is None else f"rtd-row-{rtd_id}"
    encoded = error.replace("&", "%26").replace(" ", "+")
    rtd_param = f"&rtd_id={rtd_id}" if rtd_id is not None else ""
    editing_param = (
        f"&editing_rtd_id={rtd_id}"
        if (keep_editing and rtd_id is not None)
        else ""
    )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{session_id}/instruments"
            f"?rtd_error={encoded}{rtd_param}{editing_param}#{fragment}"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types")
def response_type_add(
    response_type: str = Form(...),
    data_type: str = Form(...),
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.add_response_type_definition(
            db,
            review_session=review_session,
            response_type=response_type,
            data_type=data_type,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(review_session.id, error=str(exc))
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _require_rtd_in_session(
    rtd_id: int,
    review_session: ReviewSession,
    db: Session,
):
    rtd = db.execute(
        select(instruments_service.ResponseTypeDefinition).where(
            instruments_service.ResponseTypeDefinition.id == rtd_id,
            instruments_service.ResponseTypeDefinition.session_id
            == review_session.id,
        )
    ).scalar_one_or_none()
    if rtd is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response Type Definition not found",
        )
    return rtd


@router.post("/sessions/{session_id}/response-types/{rtd_id}/edit")
def response_type_edit(
    rtd_id: int,
    min: str | None = Form(default=None),
    max: str | None = Form(default=None),
    step: str | None = Form(default=None),
    list_csv: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be edited.",
        )

    min_value = _parse_optional_float(min)
    max_value = _parse_optional_float(max)
    step_value = _parse_optional_float(step)

    try:
        instruments_service.update_response_type_definition(
            db,
            rtd=rtd,
            min=min_value,
            max=max_value,
            step=step_value,
            list_csv=list_csv,
            actor=user,
        )
    except (
        instruments_service.RTDValidationError,
        instruments_service.RTDPrecisionError,
    ) as exc:
        return _rtd_redirect_with_error(
            review_session.id,
            error=str(exc),
            rtd_id=rtd.id,
            keep_editing=True,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/response-types/{rtd_id}/delete")
def response_type_delete(
    rtd_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    rtd = _require_rtd_in_session(rtd_id, review_session, db)
    if rtd.is_seeded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seeded Response Types are spec-locked and cannot be deleted.",
        )

    try:
        instruments_service.delete_response_type_definition(
            db, rtd=rtd, confirm=(confirm == "true"), actor=user
        )
    except instruments_service.RTDDeleteWouldEmptyInstrumentError as exc:
        # Slice 4d Gap 3: hard-block. The cascade would leave at
        # least one instrument with zero RF rows; operator must add
        # a non-ODT row to that instrument first.
        names = ",".join(
            str(e["instrument_number"]) for e in exc.would_empty
        )
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_would_empty_id={rtd.id}"
                f"&rtd_would_empty_instruments={names}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except instruments_service.RTDInUseError as exc:
        d = exc.dependents
        return RedirectResponse(
            url=(
                f"/operator/sessions/{review_session.id}/instruments"
                f"?rtd_delete_blocked_id={rtd.id}"
                f"&rtd_delete_blocked_rfs={d['response_field_count']}"
                f"&rtd_delete_blocked_instruments={d['instrument_count']}"
                f"&rtd_delete_blocked_responses={d['response_count']}"
                f"&rtd_delete_blocked_assignments={d['assignment_count']}"
                f"#rtd-row-{rtd.id}"
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        url=(
            f"/operator/sessions/{review_session.id}/instruments#rtd-card"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/instruments/{instrument_id}/delete")
def instruments_delete(
    instrument_id: int,
    confirm: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    _require_instrument_editable(review_session)
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
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
    # Pick the next-or-previous sibling so the operator lands near
    # the instrument they just deleted instead of being yanked to
    # the top of the page. Captured BEFORE the delete since the row
    # is gone after.
    sibling_ids = (
        db.execute(
            select(Instrument.id)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.id)
        )
        .scalars()
        .all()
    )
    idx = sibling_ids.index(instrument_id)
    if idx + 1 < len(sibling_ids):
        landing_id = sibling_ids[idx + 1]
    else:
        landing_id = sibling_ids[idx - 1]
    instruments_service.delete_instrument(
        db, instrument=instrument, actor=user
    )
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{landing_id}"
    )


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
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
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
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
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
    return _instruments_redirect(
        review_session.id, fragment=f"instrument-{instrument.id}"
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
    status: str = "all",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    all_rows = views.build_invitations_rows(db, review_session)
    rows = views.filter_invitations_rows(all_rows, status=status, search=q)
    search_options = views.invitations_search_options(all_rows)
    invitation_rows = invitations.list_invitations_for_session(
        db, review_session.id
    )
    eligible = invitations.reviewers_eligible_for_invitation(db, review_session.id)
    invited_ids = {r.invitation.reviewer_id for r in invitation_rows}
    pending_count = sum(
        1
        for r in invitation_rows
        if r.invitation.status == "pending"
    )
    incomplete_count = sum(1 for r in all_rows if r.is_incomplete)
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "total_row_count": len(all_rows),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.INVITATIONS_STATUS_OPTIONS,
            "filter_search_options": search_options,
            "eligible_count": len(eligible),
            "uninvited_count": sum(1 for r in eligible if r.id not in invited_ids),
            "pending_count": pending_count,
            "incomplete_count": incomplete_count,
            "total_invitation_count": len(invitation_rows),
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Invitations"
            ),
        },
    )


@router.get(
    "/sessions/{session_id}/invitations/{invitation_id}/detail",
    response_class=HTMLResponse,
)
def invitation_reviewer_detail(
    request: Request,
    bundle: tuple[Invitation, ReviewSession] = Depends(
        _require_invitation_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Drill-in from a row on the Manage Invitations table.

    Segment 11C Part 1 scaffolds this as a thin per-reviewer summary —
    the same Email Status / Review Progress / Required Fields fields the
    consolidated table renders, plus the latest invitation outbox row's
    raw token URL when available. Future segments grow this surface
    (per-assignment progress, per-response detail).
    """
    invitation, review_session = bundle
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == invitation.reviewer_id)
    ).scalar_one()
    rows = views.build_invitations_rows(db, review_session)
    row = next((r for r in rows if r.reviewer.id == reviewer.id), None)
    invite_url = invitations.most_recent_invitation_url(
        db, invitation_id=invitation.id
    )
    return _templates.TemplateResponse(
        request,
        "operator/session_invitations_reviewer_detail.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewer": reviewer,
            "invitation": invitation,
            "row": row,
            "invite_url": invite_url,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_invitations_reviewer(
                review_session, reviewer.name
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
            build_invite_url=lambda token: str(
                request.url_for("reviewer_invite", token=token)
            ),
            correlation_id=request_correlation_id(),
        )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/invitations/regenerate-all")
def invitations_regenerate_all(
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-rotate every invitation token in the session. Each
    invitation flips to ``pending`` and ``sent_at`` / ``opened_at``
    clear; previously-issued URLs go stale uniformly. One batch
    ``invitations.regenerated`` audit event when at least one
    invitation was rotated."""
    _require_ready(review_session)
    invitations.regenerate_all_tokens(
        db,
        review_session=review_session,
        user=user,
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
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
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
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Outbox"
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Monitoring + reminders (Segment 9.3)
# --------------------------------------------------------------------------- #


@router.get("/sessions/{session_id}/monitoring")
def session_monitoring_redirect(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    """Segment 11C Part 1 PR 3 retired the Monitoring template; the
    consolidated Manage Invitations page (PR 2) absorbed its
    reviewer-centric surface. Existing bookmarks land here and 303
    forward to ``/invitations``."""
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/sessions/{session_id}/responses", response_class=HTMLResponse
)
def session_responses(
    request: Request,
    status: str = "all",
    q: str = "",
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Reviewee-centric coverage view (Segment 11C Part 1 PR 3).

    Each row classifies a reviewee per ``monitoring.AT_RISK_THRESHOLDS``
    (Complete / Adequate / At risk / No responses) based on the fraction
    of their assigned reviewers who have submitted. Bulk reminder funnels
    through the same ``invitations.send_reminders_to_incomplete`` helper
    the Manage Invitations page calls.

    ``status`` and ``q`` query params drive the per-page filter strip
    (Segment 11C Part 1 follow-up). Filter state is page-local; not
    persisted across navigations.
    """
    all_rows = views.build_responses_rows(db, review_session)
    rows = views.filter_responses_rows(all_rows, status=status, search=q)
    search_options = views.responses_search_options(all_rows)
    summary = monitoring.summary_counts(db, review_session)
    incomplete_count = summary.incomplete
    return _templates.TemplateResponse(
        request,
        "operator/session_responses.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "rows": rows,
            "total_row_count": len(all_rows),
            "filter_status": status,
            "filter_search": q,
            "filter_status_options": views.RESPONSES_STATUS_OPTIONS,
            "filter_search_options": search_options,
            "incomplete_count": incomplete_count,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Responses"
            ),
        },
    )


@router.get(
    "/sessions/{session_id}/responses/{reviewee_id}/detail",
    response_class=HTMLResponse,
)
def responses_reviewee_detail(
    request: Request,
    reviewee_id: int,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Drill-in from a Responses table row (Segment 11C Part 1 PR 3
    scaffold). Per-assignment / per-response detail lands in a future
    segment; this surface mirrors the row-level fields plus a list of
    the reviewers assigned to this reviewee."""
    reviewee = db.execute(
        select(Reviewee).where(
            Reviewee.id == reviewee_id,
            Reviewee.session_id == review_session.id,
        )
    ).scalar_one_or_none()
    if reviewee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    coverage = monitoring.per_reviewee_coverage(db, review_session)
    row = next((c for c in coverage if c.reviewee.id == reviewee.id), None)
    return _templates.TemplateResponse(
        request,
        "operator/session_responses_reviewee_detail.html",
        {
            "user": user,
            "session": review_session,
            "status_pills": views.session_status_pills(db, review_session),
            "reviewee": reviewee,
            "row": row,
            "is_ready": lifecycle.is_ready(review_session),
            "breadcrumbs": breadcrumbs.operator_session_responses_reviewee(
                review_session, reviewee.name
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
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/invitations/remind-incomplete"
)
def invitations_remind_incomplete(
    request: Request,
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk reminder dispatch from the consolidated Manage Invitations
    page (Segment 11C Part 1). Funnels through the same
    ``invitations.send_reminders_to_incomplete`` helper the (still-
    existing) Monitoring page uses; PR 3 retires the Monitoring
    counterpart endpoint."""
    _require_ready(review_session)
    invitations.send_reminders_to_incomplete(
        db,
        review_session=review_session,
        user=user,
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}/invitations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# The POST /sessions/{id}/monitoring/remind-incomplete endpoint retired
# in Segment 11C Part 1 PR 3. Its only caller was the (now-deleted)
# Monitoring template; bulk reminder dispatch funnels through
# ``POST /sessions/{id}/invitations/remind-incomplete`` (PR 2) instead.
