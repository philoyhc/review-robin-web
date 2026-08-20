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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import (
    date_formatting,
    operator_settings,
    permissions,
    responses,
    scheduled_events,
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
    _REVERT_RETURN_TO,
    _lifecycle_error_response,
    _quick_setup_unlocked,
    _redirect_url,
    _require_editable,
    _templates,
    parse_session_deadline,
)


router = APIRouter()


@router.get("/sessions/new", response_class=HTMLResponse)
def new_session_form(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    current_timezone = operator_settings.get_display_timezone(user)
    return _templates.TemplateResponse(
        request,
        "operator/session_new.html",
        {
            "user": user,
            "quick_setup": views.build_new_session_quick_setup_context(
                db, user
            ),
            "breadcrumbs": breadcrumbs.operator_new_session(),
            "current_timezone": current_timezone,
            "timezone_options": operator_settings.timezone_options(),
            "timezone_sample": date_formatting.format_datetime(
                datetime.now(timezone.utc), current_timezone
            ),
            # 18G PR 2B: the Create form has no existing session, so the
            # timeline starts empty. The template renders the block
            # only when at least one row is present.
            "schedule_timeline_rows": [],
        },
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
def session_detail(
    request: Request,
    quick_setup_error: str | None = Query(default=None),
    quick_setup_reason: str | None = Query(default=None),
    super_status: str | None = Query(default=None),
    super_button: str | None = Query(default=None),
    super_step: str | None = Query(default=None),
    super_error: str | None = Query(default=None),
    prepare_confirm: str | None = Query(default=None),
    editing: bool = Query(default=False),
    owners_error: str | None = Query(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    # Lazy observer for scheduled lifecycle events (Segment 18G).
    # Fires past-due triggers (activation PR 1B; auto-send invites
    # PR 2A) before rendering. ``build_invite_url`` closes over the
    # request so the invite-dispatch path can build absolute URLs.
    scheduled_events.observe_scheduled_events(
        db,
        review_session,
        correlation_id=request_correlation_id(),
        build_invite_url=lambda token: str(
            request.url_for("reviewer_invite", token=token)
        ),
    )
    setup_rows = views.build_setup_rows(db, review_session)
    workflow_ctx = views.build_workflow_card_context(
        db,
        review_session,
        return_to="home",
        super_failure=views.parse_super_failure(
            super_status, super_step, super_error, super_button
        ),
        prepare_confirm=prepare_confirm,
    )
    # 18R Item 4 Slice 2 (mock-up) — the same schedule input-value
    # prefills the Edit route builds, so the inert Session config card
    # can render filled edit boxes. Reused verbatim; the edit-mode
    # wiring in a later slice consumes them for real.
    session_tz = sessions.resolve_session_timezone(review_session)
    return _templates.TemplateResponse(
        request,
        "operator/session_detail.html",
        {
            "user": user,
            "session": review_session,
            "setup_rows": setup_rows,
            "status_pills": views.session_status_pills(db, review_session),
            "has_responses": lifecycle.session_has_responses(db, review_session),
            "quick_setup": views.build_quick_setup_context(
                db,
                review_session,
                user=user,
                is_unlocked=_quick_setup_unlocked(request, review_session),
                error_kind=quick_setup_error,
                error_reason=quick_setup_reason,
            ),
            "session_timezone_label": date_formatting.gmt_offset_zone_label(
                session_tz
            ),
            # Schedule input-value prefills for the Session config card
            # mock-up (18R Item 4 Slice 2) — mirror the Edit route.
            "scheduled_activate_at_input_value": (
                date_formatting.format_datetime_local(
                    review_session.scheduled_activate_at, session_tz
                )
            ),
            "deadline_input_value": date_formatting.format_datetime_local(
                review_session.deadline, session_tz
            ),
            "responses_release_at_input_value": (
                date_formatting.format_datetime_local(
                    review_session.responses_release_at, session_tz
                )
            ),
            "responses_release_until_input_value": (
                date_formatting.format_datetime_local(
                    review_session.responses_release_until, session_tz
                )
            ),
            "invite_offsets_input_value": ", ".join(
                review_session.invite_offsets or []
            ),
            "reminder_offsets_input_value": ", ".join(
                review_session.reminder_offsets or []
            ),
            # 18R Item 4 — display mode shows each offset + its resolved
            # send datetime (invites off Start, reminders off End).
            "invite_offset_rows": views.build_offset_display_rows(
                review_session.scheduled_activate_at,
                review_session.invite_offsets,
                session_tz,
            ),
            "reminder_offset_rows": views.build_offset_display_rows(
                review_session.deadline,
                review_session.reminder_offsets,
                session_tz,
            ),
            # 18R Item 4 — current owners + add-candidates for the Session
            # config card's Owners sub-card (mirrors the Edit page's Owners
            # card: Email / Name / Role / Joined / Action + Add owner).
            "config_owners": session_owners.list_owners(db, review_session),
            "config_owner_candidates": (
                session_owners.workspace_operator_candidates(db, review_session)
            ),
            # 18R Item 4 Slice 4 — owner add/remove errors surface inline on
            # the config Owners sub-card (redirected here from the routes).
            "owners_error": owners_error,
            # 18R Item 4 Slice 3 — edit-mode wiring for the Session details
            # card. ``config_editing`` is the canonical server state (from
            # ``?editing=1``), gated on the session actually being editable so a
            # stale link on an activated session degrades to display mode. The
            # timezone options + current zone feed the edit-mode timezone
            # datalist; the has-* signals lock the UI-settings checkboxes when a
            # roster has rows (mirrors the Edit page + service-layer guard).
            "config_editing": (
                editing
                and (
                    lifecycle.is_draft(review_session)
                    or lifecycle.is_validated(review_session)
                )
            ),
            "timezone_options": operator_settings.timezone_options(),
            "current_session_timezone": session_tz,
            "has_relationships": sessions._has_relationships(
                db, review_session.id
            ),
            "has_observers": sessions._has_observers(db, review_session.id),
            "breadcrumbs": breadcrumbs.operator_session(review_session),
            **workflow_ctx,
        },
    )


# --- Retired Edit page → Session Home redirect (18R Item 4 Slice 5b) --------
#
# The standalone Edit page and its GET/POST routes were deleted once every
# caller (UI links + tests) moved to Session Home's in-place config card
# (#session-config, edited via ?editing=1) and the shared /config POST route.
# This thin GET redirect preserves any stale ``/edit`` bookmarks; it keeps the
# ``require_session_operator`` gate so a non-owner still gets 403, not a bounce.
@router.get("/sessions/{session_id}/edit")
def session_edit_redirect(
    review_session: ReviewSession = Depends(require_session_operator),
) -> RedirectResponse:
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}?editing=1#session-config",
        # 308 (not 301) preserves the GET method and matches the other
        # legacy-URL shim (``/preview`` → operations); audit R11.
        status_code=status.HTTP_308_PERMANENT_REDIRECT,
    )


def _apply_session_config_form(
    *,
    db: Session,
    review_session: ReviewSession,
    user: User,
    name: str,
    code: str,
    description: str | None,
    deadline: str | None,
    scheduled_activate_at: str | None,
    invite_offsets: str | None,
    reminder_offsets: str | None,
    display_timezone: str,
    help_contact: str | None,
    relationships_enabled: bool,
    observers_enabled: bool,
    responses_release_at: str | None,
    responses_release_until: str | None,
) -> None:
    """Parse + validate + persist the session-config form fields.

    Shared by the (legacy) Edit page POST and the Session Home config-card
    POST (18R Item 4 Slice 3) — both surfaces edit the same scalar
    ``sessions`` columns via ``update_session`` (which never touches
    assignments or responses, so no response-loss ack gate). Raises
    ``HTTPException(422)`` on any field / ordering validation error.
    """
    # Editing session metadata (name / code / description / deadline /
    # help contact / timezone / scheduled_activate_at) touches only
    # scalar ``sessions`` columns.
    _require_editable(review_session)

    # 18B PR 5: the display timezone is a field of this form. Blank ⇒
    # leave the session's current zone unchanged. The deadline picker is
    # wall-clock in this zone.
    timezone_name = (
        operator_settings.parse_display_timezone_input(display_timezone)
        or sessions.resolve_session_timezone(review_session)
    )
    if not operator_settings.is_valid_timezone(timezone_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown timezone {timezone_name!r}",
        )

    parsed_deadline = parse_session_deadline(deadline, timezone_name)

    # 18G Part 1: optional Start anchor for scheduled activation.
    try:
        parsed_scheduled_activate_at = (
            scheduled_events.parse_and_validate_scheduled_activate_at(
                scheduled_activate_at, timezone_name=timezone_name
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 18G Part 2: optional auto-send invite offsets, validated against
    # the (possibly freshly-edited) Start.
    try:
        parsed_invite_offsets = (
            scheduled_events.parse_and_validate_invite_offsets(
                invite_offsets,
                scheduled_activate_at=parsed_scheduled_activate_at,
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # 18G Part 3: optional auto-send reminder offsets, validated
    # against the (possibly freshly-edited) deadline.
    try:
        parsed_reminder_offsets = (
            scheduled_events.parse_and_validate_reminder_offsets(
                reminder_offsets,
                deadline=parsed_deadline,
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Participant-model W14 + S12: Release-responses anchor + close
    # datetime. Until is validated against the (possibly freshly-
    # edited) anchor.
    try:
        parsed_responses_release_at = (
            scheduled_events.parse_and_validate_responses_release_at(
                responses_release_at, timezone_name=timezone_name
            )
        )
        parsed_responses_release_until = (
            scheduled_events.parse_and_validate_responses_release_until(
                responses_release_until,
                timezone_name=timezone_name,
                responses_release_at=parsed_responses_release_at,
            )
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Cross-field datetime ordering: Start ≤ End ≤ Release-from.
    # (Release-until > Release-from is checked inside its own
    # parser.) Runs after every individual parse so the operator
    # gets the field-level error before the ordering error.
    try:
        scheduled_events.validate_schedule_ordering(
            scheduled_activate_at=parsed_scheduled_activate_at,
            deadline=parsed_deadline,
            responses_release_at=parsed_responses_release_at,
        )
    except scheduled_events.ScheduledActivateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    correlation_id = request_correlation_id()
    sessions.set_session_display_timezone(
        db,
        review_session=review_session,
        user=user,
        timezone_name=timezone_name,
        correlation_id=correlation_id,
    )
    payload = SessionCreate(
        name=name,
        code=code,
        description=description or None,
        deadline=parsed_deadline,
        help_contact=help_contact or None,
        scheduled_activate_at=parsed_scheduled_activate_at,
        invite_offsets=parsed_invite_offsets,
        reminder_offsets=parsed_reminder_offsets,
        relationships_enabled=relationships_enabled,
        observers_enabled=observers_enabled,
        responses_release_at=parsed_responses_release_at,
        responses_release_until=parsed_responses_release_until,
    )
    sessions.update_session(
        db,
        review_session=review_session,
        user=user,
        payload=payload,
        correlation_id=correlation_id,
    )


@router.post("/sessions/{session_id}/config")
def session_config_submit(
    name: str = Form(...),
    code: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    scheduled_activate_at: str | None = Form(default=None),
    invite_offsets: str | None = Form(default=None),
    reminder_offsets: str | None = Form(default=None),
    display_timezone: str = Form(default=""),
    help_contact: str | None = Form(default=None),
    relationships_enabled: bool = Form(default=False),
    observers_enabled: bool = Form(default=False),
    responses_release_at: str | None = Form(default=None),
    responses_release_until: str | None = Form(default=None),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """18R Item 4 Slice 3 — Save from the Session Home config card.

    Same persistence path as the Edit page POST (shared helper), but
    redirects back to Session Home in **display** mode (no ``?editing``)
    — the operator saves in place instead of hopping to a child page.
    """
    _apply_session_config_form(
        db=db,
        review_session=review_session,
        user=user,
        name=name,
        code=code,
        description=description,
        deadline=deadline,
        scheduled_activate_at=scheduled_activate_at,
        invite_offsets=invite_offsets,
        reminder_offsets=reminder_offsets,
        display_timezone=display_timezone,
        help_contact=help_contact,
        relationships_enabled=relationships_enabled,
        observers_enabled=observers_enabled,
        responses_release_at=responses_release_at,
        responses_release_until=responses_release_until,
    )
    return RedirectResponse(
        url=f"/operator/sessions/{review_session.id}#session-config",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/delete-data")
def session_delete_data(
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
        # Align with the Workflow-card ``/workflow/activate`` failure
        # UX: bounce to the Session Home flash banner (via the shared
        # ``_redirect_url``) rather than raising an error page, so an
        # activation failure looks the same from either activate button
        # (audit R2).
        return RedirectResponse(
            url=_redirect_url(
                review_session.id,
                return_to,
                super_status="failed",
                super_button="activate",
                super_step="activate",
                super_error=str(exc),
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
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
    # 18R Item 4 Slice 4 — owner add/remove now land back on Session Home's
    # config card in edit mode (``?editing=1``), scrolled to the Owners
    # sub-card, instead of the (soon-retired) Edit page.
    base = f"/operator/sessions/{session_id}?editing=1#config-owners-card"
    if error_code:
        # Anchor stays at the end; the query params sit before the #.
        from urllib.parse import quote

        return (
            f"/operator/sessions/{session_id}"
            f"?editing=1&owners_error={quote(error_code, safe='')}"
            "#config-owners-card"
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
    # Segment 18S Item 3 — self-only for the relaxed (non-owner sys-admin)
    # path. A sys-admin who isn't a session operator reaches this route via
    # the ``require_sys_admin_or_session_operator`` bypass; they may add
    # **only themselves** (the audited self-add bootstrap). Adding anyone
    # else requires being an owner first. A real session operator (owner)
    # is unaffected and may add anyone.
    if not permissions.user_can_view_session(db, actor, review_session.id):
        if target.id != actor.id:
            return RedirectResponse(
                url=_owners_redirect_url(review_session.id, "self_only"),
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
    review_session: ReviewSession = Depends(require_session_operator),
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
