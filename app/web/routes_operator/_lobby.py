"""Sessions lobby — the operator's "all my sessions" page + bulk
delete from that page. Slice 1 of the major refactor.

Source ranges in pre-refactor ``routes_operator.py``: 64-123.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.web import urls
from app.config import settings
from app.db.models import ReviewSession, User
from app.db.session import get_db
from app.services import scheduled_events
from app.services import session_clone
from app.services import session_purge
from app.services import sessions
from app.services import session_guard
from app.services import session_lifecycle as lifecycle
from app.services import session_owners
from app.services import session_tags
from app.web import breadcrumbs, views
from app.web.deps import (
    OperatorAllowlistDenied,
    get_or_create_user,
    request_correlation_id,
    require_session_operator,
    require_sys_admin_or_session_operator,
)
from app.web.routes_operator._shared import (
    _templates,
    observe_scheduled_events_on_load,
    parse_session_deadline,
    session_payload_error,
)


router = APIRouter()

@router.get("/sessions", response_class=HTMLResponse)
def list_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    all_sessions = sessions.list_for_user(db, user)
    # The scheduled-event pass, before the stats and rows read their
    # status (``spec/lifecycle.md`` §8.3), for every listed session that
    # can still have something due. An expired one cannot, and would
    # otherwise take its lock on every load for the past entries.
    observe_scheduled_events_on_load(
        request,
        db,
        [s for s in all_sessions if s.status not in ("archived", "expired")],
    )
    # The main lobby table shows only non-archived sessions; archived
    # ones live on their own child page (Segment 18A Part 3). Every pill
    # counts what the lobby lists but the Archived pill, which counts
    # them (19X Item 9).
    lobby_stats = views.session_status_counts(all_sessions, archived_in_total=False)
    review_sessions = [s for s in all_sessions if s.status != "archived"]
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name="rrw-sort-lobby",
        valid_keys=views.LOBBY_SORT_KEYS,
    )
    review_sessions = views.apply_cookie_sort(
        review_sessions, sort_spec, value_resolver=views.session_sort_value
    )
    session_ids = [s.id for s in review_sessions]
    lobby_tags = session_tags.vocabulary(db, session_ids)
    return _templates.TemplateResponse(
        request,
        "operator/sessions_list.html",
        {
            "user": user,
            "sessions": review_sessions,
            "lobby_stats": lobby_stats,
            "tags_by_session": session_tags.tags_for_sessions(db, session_ids),
            "lobby_tags": lobby_tags,
            # 19S Item 7 — the row and bulk expanders' tag typeahead.
            # Wider than ``lobby_tags``, which feeds the filter strip and
            # so stays scoped to the rows shown.
            "tag_vocabulary": session_tags.vocabulary_for_user(db, user),
            "filter_options": views.sessions_filter_options(
                review_sessions, lobby_tags
            ),
            "breadcrumbs": breadcrumbs.operator_root(),
            "rehydrate_enabled": settings.rehydrate_enabled,
        },
    )


@router.get("/sessions/archived", response_class=HTMLResponse)
def archived_sessions(
    request: Request,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """The archived-sessions child page (Segment 18A Part 3).

    Opened as a stub whose docstring said the full surface — filter
    card, tag-chip info card, bulk-only expander — was still to come.
    All three shipped; the sentence outlived them and was still being
    edited as late as 19O Item 7 entry 15, which changed `Search` to
    `Filter` in it and left the promise standing.
    """
    archived = [
        s
        for s in sessions.list_for_user(db, user)
        if s.status == "archived"
    ]
    sort_spec = views.decode_cookie_sort_spec(
        cookies=dict(request.cookies),
        cookie_name="rrw-sort-archived",
        valid_keys=views.ARCHIVED_SORT_KEYS,
    )
    archived = views.apply_cookie_sort(
        archived, sort_spec, value_resolver=views.session_sort_value
    )
    session_ids = [s.id for s in archived]
    archived_tags = session_tags.vocabulary(db, session_ids)
    return _templates.TemplateResponse(
        request,
        "operator/sessions_archived.html",
        {
            "user": user,
            "sessions": archived,
            "tags_by_session": session_tags.tags_for_sessions(db, session_ids),
            "archived_tags": archived_tags,
            "filter_options": views.sessions_filter_options(
                archived, archived_tags
            ),
            "breadcrumbs": breadcrumbs.operator_sessions_child("Archived"),
        },
    )


@router.post("/sessions/bulk-tags")
def sessions_bulk_tags(
    request: Request, session_ids: list[int] = Form(default=[]),
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
    return urls.redirect(request,
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/bulk-unarchive")
def sessions_unarchive_selected(
    request: Request, session_ids: list[int] = Form(default=[]),
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
        try:
            lifecycle.unarchive_session(
                db,
                review_session=review_session,
                user=user,
                correlation_id=correlation_id,
            )
        except lifecycle.LifecycleError:
            # Unarchived by another request since this one read it (a
            # double submit): skipped, as the filter above skips it.
            db.rollback()
    return urls.redirect(request,
        url="/operator/sessions/archived",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/bulk-delete-archived")
def sessions_delete_archived_selected(
    request: Request, session_ids: list[int] = Form(default=[]),
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
    return urls.redirect(request,
        url="/operator/sessions/archived",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/lobby-edit")
def lobby_edit_submit(
    request: Request, name: str = Form(...),
    code: str = Form(...),
    deadline: str | None = Form(default=None),
    tags: str = Form(default=""),
    review_session: ReviewSession = Depends(require_session_operator),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Single-session expander Save on the sessions lobby.

    Tags are editable in any lifecycle state. Name / Code / Deadline
    are applied only while the session ``is_editable`` (``draft`` or
    ``validated``) — the gate Session Home's Details card uses, so the
    two pages agree (findings B2); the expander renders those boxes
    read-only otherwise, and this route ignores them server-side so a
    stale post can't slip past that gate. No change here demotes a
    ``validated`` session (findings Cc5, ``sessions.update_session``).
    """
    correlation_id = request_correlation_id()
    # The whole save runs under the session lock the scheduled-event
    # observers take, re-reading the row first (findings Bc3). Tags take
    # no state gate, so this is the bare lock, not a ``require_*``.
    session_guard.lock_session(db, review_session)

    # Checked before the tag write, so a taken code, a deadline that
    # does not fit the stored schedule, or a name too long refuses the
    # whole save rather than landing the tags alone (a taken code would
    # otherwise reach the unique constraint as a 500).
    payload = None
    if lifecycle.is_editable(review_session):
        try:
            sessions.ensure_code_available(
                db, code, exclude_session_id=review_session.id
            )
        except sessions.SessionCodeTakenError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        timezone_name = sessions.resolve_session_timezone(review_session)
        if sessions.datetime_box_unedited(
            review_session.deadline, deadline, timezone_name
        ):
            parsed_deadline = review_session.deadline
        else:
            parsed_deadline = parse_session_deadline(deadline, timezone_name)
        try:
            scheduled_events.validate_deadline_change(
                db, review_session, parsed_deadline
            )
        except scheduled_events.ScheduledActivateError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        # Only Name, Code and Deadline are on the expander; every other
        # field keeps its stored value.
        try:
            payload = sessions.edit_payload(
                review_session, name=name, code=code, deadline=parsed_deadline
            )
        except ValidationError as exc:
            raise session_payload_error(exc) from exc

    if payload is not None and sessions.payload_changes_session(
        review_session, payload
    ):
        sessions.update_session(
            db,
            review_session=review_session,
            user=user,
            payload=payload,
            correlation_id=correlation_id,
        )

    # After the schedule write, not before: the tag write commits, which
    # would release the session lock the End check took before the End
    # it checked is written (findings Bc3).
    session_tags.set_tags(
        db,
        review_session=review_session,
        user=user,
        tags=tags.split(","),
        correlation_id=correlation_id,
    )

    return urls.redirect(request,
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/{session_id}/clone")
def clone_session_submit(
    request: Request, mode: str = Form(...),
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
    # The clone's owner, re-read under the owner-add lock as on Create.
    if not session_owners.lock_owner_eligible(db, user):
        raise OperatorAllowlistDenied()
    clone = session_clone.clone_session(
        db,
        source=review_session,
        user=user,
        mode=mode,
        correlation_id=request_correlation_id(),
    )
    # 18R Item 4 Slice 5 — land on Session Home with the Session details
    # card open in edit mode (the Edit page is retired). The operator's
    # first task on a clone is to rename it, then review the cloned setup
    # on the same page. No fragment (19X Item 7).
    return urls.redirect(request,
        url=f"/operator/sessions/{clone.public_id}?editing=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/bulk-archive")
def sessions_archive_selected(
    request: Request, session_ids: list[int] = Form(default=[]),
    purge: list[str] = Form(default=[]),
    return_to: str = Form(default=""),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Purge-and-archive the ticked sessions — backs both the lobby
    expander's "Purge and archive" action and the Extract data page's
    Archive card (18R — archive harmonization).

    Filters server-side to caller-owned **archivable** sessions
    (``lifecycle.can_archive`` — any non-activated, non-archived session;
    an activated session must be paused first and is silently skipped).
    ``purge`` is any subset of ``responses`` / ``rosters`` / ``audit_log``,
    applied audit-log → responses → rosters before the archive; empty ⇒
    plain archive. ``return_to=archived`` lands on the archived-sessions
    index (the Extract data card's choice); otherwise the main lobby.
    """
    correlation_id = request_correlation_id()
    for session_id in session_ids:
        review_session = sessions.get_for_user(db, user, session_id)
        if review_session is None:
            continue
        try:
            session_purge.purge_and_archive(
                db,
                review_session=review_session,
                user=user,
                purge=purge,
                correlation_id=correlation_id,
            )
        except lifecycle.LifecycleError:
            # A refusal from the transitions under the lock: the row is
            # skipped rather than answering 500. A session archived by
            # another request first (a double submit) no longer reaches
            # this — purge_and_archive decides ``can_archive`` under the
            # lock before any purge and returns False.
            db.rollback()
    target = (
        "/operator/sessions/archived"
        if return_to == "archived"
        else "/operator/sessions"
    )
    return urls.redirect(request,
        url=target,
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/sessions/bulk-delete")
def sessions_delete_selected(
    request: Request, session_ids: list[int] = Form(default=[]),
    confirm: str | None = Form(default=None),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Bulk-delete the sessions ticked on the operator sessions list.

    Filters server-side to sessions the caller operates, in ``draft``,
    ``validated`` or ``expired`` (author's ruling, 2026-10-02: a
    finished session is deletable from the lobby as from its Home);
    ``ready`` (Activated) rows are silently skipped, and ``archived``
    ones are deleted from the archived page's own route. The lobby's
    row expander surfaces a "Yes, delete" checkbox and the Delete
    button — without ``confirm=true`` the request is rejected with
    ``400``, as the single-session route does. Each deletion goes through ``sessions.delete_session``
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
        if not (
            lifecycle.is_editable(review_session)
            or lifecycle.is_expired(review_session)
        ):
            continue
        try:
            sessions.delete_session(
                db,
                review_session=review_session,
                user=user,
                correlation_id=correlation_id,
            )
        except lifecycle.SessionStateConflict:
            # Activated since this request read it (findings Bc4): skipped,
            # as the filter above skips a ``ready`` row.
            db.rollback()
    return urls.redirect(request,
        url="/operator/sessions",
        status_code=status.HTTP_303_SEE_OTHER,
    )
