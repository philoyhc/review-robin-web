"""Operations row — Validate / Previews / Manage Invitations /
Outbox / Responses, plus the reminder dispatch endpoints.
Slice 9 of the major refactor.

Source ranges in pre-refactor ``routes_operator.py``:
460-525 (Validate), 2727-2868 (Previews + preview redirect),
3963-4423 (Manage Invitations + Outbox + Responses + reminders +
monitoring redirect).
"""

from __future__ import annotations

import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.db.session import get_db
from app.services import invitations, monitoring, validation
from app.services import session_lifecycle as lifecycle
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
)
from app.web.routes_operator._shared import _templates


router = APIRouter()


@router.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_session(
    request: Request,
    severity: str = "all",
    activate: int = 0,
    return_to: str | None = None,
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
            "activate_return_to": return_to,
            "breadcrumbs": breadcrumbs.operator_session_child(
                review_session, "Validate setup"
            ),
        },
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


# Per-session ``GET /sessions/{id}/outbox`` route retired 2026-05-11
# in favour of the inline outbox section on
# ``/operator/sys-admin/sessions`` (Sessions Diagnostics tab).
# Bookmarked URLs lose the route; users land on a 404. The Admin
# chrome is now the only canonical entry point.


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
