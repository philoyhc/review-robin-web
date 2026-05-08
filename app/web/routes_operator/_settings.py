"""Operator-level Settings page (per-operator SMTP credentials).
Slice 2 of the major refactor.

Source range in pre-refactor ``routes_operator.py``: 126-238.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db
from app.services import operator_settings
from app.services._secrets import MissingEncryptionKey
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.return_to import resolve_return_to
from app.web.routes_operator._shared import _templates


router = APIRouter()


def _settings_redirect_url(return_to_raw: str | None) -> str:
    """Save / Clear keep the operator on the Settings page (so they
    can verify their changes); the ``return_to`` query param rides
    along on the redirect so the back-link stays wired through the
    Save → reload cycle."""
    if return_to_raw:
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
