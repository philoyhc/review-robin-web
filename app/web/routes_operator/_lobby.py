"""Sessions lobby — the operator's "all my sessions" page + bulk
delete from that page. Slice 1 of the major refactor.

Source ranges in pre-refactor ``routes_operator.py``: 64-123.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.schemas.sessions import SessionCreate
from app.services import date_formatting
from app.services import session_clone
from app.services import sessions
from app.services import session_lifecycle as lifecycle
from app.services import session_tags
from app.web import breadcrumbs, views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_sys_admin_or_session_operator,
)
from app.web.routes_operator._shared import _templates


router = APIRouter()

# Cookie-backed personal sort for the sessions lobby — shares the
# ``rrw-sortable`` primitive with the Setup preview tables.
_LOBBY_SORT_KEYS = {
    "name", "code", "created_by", "created", "deadline", "timezone",
    "status",
}
# The archived-sessions table shows an "Archived" column where the
# lobby shows "Deadline" — backed by ``updated_at`` (an archived
# session is inert, so its last mutation is the archive itself).
_ARCHIVED_SORT_KEYS = {
    "name", "code", "created_by", "created", "archived", "timezone",
    "status",
}


def _session_sort_value(review_session: ReviewSession, key: str):
    """Sort-key resolver shared by the sessions-lobby and archived
    tables."""
    if key == "name":
        return review_session.name
    if key == "code":
        return review_session.code
    if key == "created_by":
        creator = review_session.created_by_user
        return creator.display_name or creator.email or ""
    if key == "created":
        return review_session.created_at
    if key == "deadline":
        return review_session.deadline
    if key == "archived":
        return review_session.updated_at
    if key == "timezone":
        return sessions.resolve_session_timezone(review_session)
    if key == "status":
        return review_session.status
    return None


@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    all_sessions = sessions.list_for_user(db, user)
    lobby_stats = {
        "total": len(all_sessions),
        "draft": sum(
            1 for s in all_sessions if s.status in ("draft", "validated")
        ),
        "activated": sum(1 for s in all_sessions if s.status == "ready"),
        "archived": sum(1 for s in all_sessions if s.status == "archived"),
    }
    # The main lobby table shows only non-archived sessions; archived
    # ones live on their own child page (Segment 18A Part 3). The
    # stats above still count them so the "archived" pill is accurate.
    review_sessions = [s for s in all_sessions if s.status != "archived"]
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name="rrw-sort-lobby",
        valid_keys=_LOBBY_SORT_KEYS,
    )
    review_sessions = views.apply_cookie_sort(
        review_sessions, sort_spec, value_resolver=_session_sort_value
    )
    session_ids = [s.id for s in review_sessions]
    return _templates.TemplateResponse(
        request,
        "operator/sessions_list.html",
        {
            "user": user,
            "sessions": review_sessions,
            "lobby_stats": lobby_stats,
            "tags_by_session": session_tags.tags_for_sessions(db, session_ids),
            "lobby_tags": session_tags.vocabulary(db, session_ids),
            "breadcrumbs": breadcrumbs.operator_root(),
        },
    )


@router.get("/sessions/archived", response_class=HTMLResponse)
def archived_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The archived-sessions child page (Segment 18A Part 3) — a
    stub: lists the operator's archived sessions. The full surface
    (Search card, tag-chip info card, bulk-only expander) follows."""
    archived = [
        s
        for s in sessions.list_for_user(db, user)
        if s.status == "archived"
    ]
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name="rrw-sort-archived",
        valid_keys=_ARCHIVED_SORT_KEYS,
    )
    archived = views.apply_cookie_sort(
        archived, sort_spec, value_resolver=_session_sort_value
    )
    session_ids = [s.id for s in archived]
    return _templates.TemplateResponse(
        request,
        "operator/sessions_archived.html",
        {
            "user": user,
            "sessions": archived,
            "tags_by_session": session_tags.tags_for_sessions(db, session_ids),
            "archived_tags": session_tags.vocabulary(db, session_ids),
            "breadcrumbs": breadcrumbs.operator_sessions_child("Archived"),
        },
    )


@router.post("/sessions/bulk-tags")
def sessions_bulk_tags(
    session_ids: list[int] = Form(default=[]),
    tags: str = Form(default=""),
    op: str = Form(...),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Add or remove a set of tags across the ticked sessions — backs
    the bulk expander's "All tags to all" / "Remove from all".

    ``op="add"`` adds every tag in ``tags`` to each selected session;
    ``op="remove"`` removes them. Both are idempotent and skip blank /
    invalid tags. Tagging is not lifecycle-gated.
    """
    if op not in ("add", "remove"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown bulk-tag op {op!r}",
        )
    correlation_id = request_correlation_id()
    raw_tags = tags.split(",")
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None:
            continue
        for raw in raw_tags:
            try:
                if op == "add":
                    session_tags.add_tag(
                        db,
                        review_session=review_session,
                        user=user,
                        tag=raw,
                        correlation_id=correlation_id,
                    )
                else:
                    session_tags.remove_tag(
                        db,
                        review_session=review_session,
                        user=user,
                        tag=raw,
                        correlation_id=correlation_id,
                    )
            except ValueError:
                # Blank / over-long tag from the split — skip it.
                continue
    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/unarchive-selected")
def sessions_unarchive_selected(
    session_ids: list[int] = Form(default=[]),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Unarchive the ticked sessions — backs the archived-page bulk
    expander's Unarchive. Filters server-side to caller-owned archived
    sessions; anything not archived is silently skipped."""
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None or review_session.status != "archived":
            continue
        lifecycle.unarchive_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    return RedirectResponse(
        url="/operator/sessions/archived",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/delete-archived-selected")
def sessions_delete_archived_selected(
    session_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Delete the ticked archived sessions — backs the archived-page
    bulk expander's Delete. Requires the Allow-delete confirm; filters
    server-side to caller-owned archived sessions."""
    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None or review_session.status != "archived":
            continue
        sessions.delete_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    return RedirectResponse(
        url="/operator/sessions/archived",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/lobby-edit")
def lobby_edit_submit(
    name: str = Form(...),
    code: str = Form(...),
    deadline: str | None = Form(default=None),
    tags: str = Form(default=""),
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Single-session expander Save on the sessions lobby.

    Tags are editable in any lifecycle state. Name / Code / Deadline
    are applied only while the session is in ``draft`` — matching the
    Session Details edit affordance's draft-only gating; the expander
    renders those boxes read-only otherwise, and this route ignores
    them server-side so a stale post can't slip past that gate.
    """
    correlation_id = request_correlation_id()

    session_tags.set_tags(
        db,
        review_session=review_session,
        user=user,
        tags=tags.split(","),
        correlation_id=correlation_id,
    )

    if lifecycle.is_draft(review_session):
        timezone_name = sessions.resolve_session_timezone(review_session)
        parsed_deadline: datetime | None = None
        if deadline:
            try:
                parsed_deadline = date_formatting.parse_local_datetime(
                    deadline, timezone_name
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="deadline must be ISO-8601",
                ) from exc
        sessions.update_session(
            db,
            review_session=review_session,
            user=user,
            payload=SessionCreate(
                name=name,
                code=code,
                description=review_session.description,
                deadline=parsed_deadline,
                help_contact=review_session.help_contact,
            ),
            correlation_id=correlation_id,
        )

    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/clone")
def clone_session_submit(
    mode: str = Form(...),
    review_session: ReviewSession = Depends(
        require_sys_admin_or_session_operator
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Single-session expander Duplicate / Duplicate settings only.

    ``mode="all"`` clones the full setup incl. the roster;
    ``mode="config"`` clones the configuration shell only. Either way
    the clone is a fresh ``draft`` — the operator lands on it to
    rename it.
    """
    if mode not in session_clone.CLONE_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown clone mode {mode!r}",
        )
    clone = session_clone.clone_session(
        db,
        source=review_session,
        user=user,
        mode=mode,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/operator/sessions/{clone.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/archive-selected")
def sessions_archive_selected(
    session_ids: list[int] = Form(default=[]),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Archive the ticked sessions — backs the single-session expander
    Archive and the bulk Archive all.

    Filters server-side to caller-owned ``draft`` sessions; anything
    not in draft is silently skipped (archiving is draft-only). No
    confirm gate — archiving is reversible and deletes no data.
    """
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None:
            continue
        if not lifecycle.is_draft(review_session):
            continue
        lifecycle.archive_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/delete-selected")
def sessions_delete_selected(
    session_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-delete the sessions ticked on the operator sessions list.

    Filters server-side to caller-owned + editable (draft / validated)
    sessions; non-editable rows are silently skipped per the existing
    ``_require_editable`` posture. The Danger Zone card on the list
    page surfaces a confirm checkbox and an explicit destructive
    button — without ``confirm=true`` the request is rejected with
    ``400`` (matches the single-session ``/sessions/{id}/delete``
    handler). Each deletion goes through ``sessions.delete_session``
    which already cascades reviewers / reviewees / instruments /
    assignments / invitations / email_outbox rows + writes the
    ``session.deleted`` audit row."""

    if confirm != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None:
            continue
        if not lifecycle.is_editable(review_session):
            continue
        sessions.delete_session(
            db,
            review_session=review_session,
            user=user,
            correlation_id=correlation_id,
        )
    return RedirectResponse(
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )
