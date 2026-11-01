"""Operator-level Settings page: the default display timezone.
Slice 2 of the major refactor. The per-operator SMTP cards and their two
routes retired in 14C Item 1 (2026-11-01); their storage and service stay.

Source range in pre-refactor ``routes_operator.py``: 126-238.
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.web import urls
from app.db.models import User
from app.db.session import get_db
from app.services import date_formatting
from app.services import operator_settings
from app.web import breadcrumbs
from app.web.deps import get_or_create_user, request_correlation_id
from app.web.return_to import resolve_return_to
from app.web.routes_operator._shared import _templates


router = APIRouter()


def _settings_redirect_url(return_to_raw: str | None) -> str:
    """The timezone save keeps the operator on the Settings page (so
    they can verify the change); the ``return_to`` query param rides
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
    """Operator-level Settings page: the default display timezone.

    Honours ``?return_to=<path>`` per ``app.web.return_to`` (same
    allowlist as the About page) so the page surfaces a "← Back to
    {context}" link and Cancel routes to the originating surface.
    """
    db.refresh(user)
    current_timezone = operator_settings.get_display_timezone(user)
    target = resolve_return_to(return_to, db, viewer=user, routes=request.app.routes)

    # Wave 5 PR 5.1 — the operator-library section retired alongside
    # the Rule Builder + RuleSet library tier. The 15C Slice 5
    # listing (Personal RuleSets + session-copy counts) is gone;
    # PR 5.2 drops the underlying ``operator_rule_sets`` table.

    return _templates.TemplateResponse(
        request,
        "operator/operator_settings.html",
        {
            "user": user,
            "current_timezone": current_timezone,
            "timezone_sample": date_formatting.format_datetime(
                datetime.now(timezone.utc), current_timezone
            ),
            "timezone_options": operator_settings.timezone_options(),
            "return_to_raw": return_to,
            "return_to_url": target.url,
            "return_to_label": target.label,
            "breadcrumbs": breadcrumbs.operator_root(),
        },
    )


@router.post("/settings/timezone")
def operator_settings_save_timezone(
    request: Request, display_timezone: str = Form(...),
    return_to: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Persist the operator's default display timezone (Segment 18B
    PR 2). New sessions this operator creates inherit it; existing
    sessions keep their own per-session setting."""
    timezone_name = operator_settings.parse_display_timezone_input(
        display_timezone
    )
    if not operator_settings.is_valid_timezone(timezone_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown timezone {display_timezone!r}",
        )
    operator_settings.set_display_timezone(
        db,
        user=user,
        timezone_name=timezone_name,
        correlation_id=request_correlation_id(),
    )
    return urls.redirect(request,
        url=_settings_redirect_url(return_to),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Segment 18J Wave 2 PR iii-b3 — the operator RTD library tier is
# retired; the per-row delete handler that lived here is gone with
# the operator_response_type_definitions table.


# Wave 5 PR 5.1 — the per-library-RuleSet delete route retired
# alongside the rest of the operator-library surface. The
# ``operator_rule_sets`` table itself drops in PR 5.2.
