"""Setup-invite + email template editor (Invitation / Reminder /
Responses-received tabs). Slice 3 of the major refactor.

Source range in pre-refactor ``routes_operator.py``: 2576-2725.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import email_templates
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import _templates


router = APIRouter()


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
