"""Reviewer surface — route handlers.

Owns the ``/me/sessions/{id}/{page_n}`` GET + the per-page Save +
the session-wide Submit / Recall / Clear POSTs, plus the GET redirects
that catch a revisit of any of those POST addresses. Each handler stays thin — the template
context comes from :func:`_surface_context` in ``_context``.
"""
from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.web import urls
from app.db.models import Assignment, Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import date_formatting
from app.services import invitations as invitations_service
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.services.session_guard import SessionStateConflict
from app.web import views
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_reviewer_in_session,
)
from app.web.routes_reviewer._shared import (
    _templates,
    build_role_chips,
    validate_page_n,
)

from ._context import (
    _pages_for_session,
    _race_refusal,
    _surface_context,
    _write_refusal,
    page_assignments_for,
)


router = APIRouter(prefix="/me")


def submit_redirect_url(
    review_session: ReviewSession,
    *,
    fully_submitted: bool = False,
) -> str:
    """Where to send the reviewer after a successful submit.

    Returns the summary page URL (17B Phase 2 PR B) when the
    submit closed out the whole session — i.e. every assigned
    row now has ``submitted_at`` set — and the bare session URL
    otherwise (which 303s on to ``/1``). Post-Segment-18L the URL
    slot is the operator-defined page number, not the reviewer's
    last instrument position, so submit no longer attempts to
    return the reviewer to "the page they were on".
    """
    if fully_submitted:
        return f"/me/sessions/{review_session.public_id}/summary"
    return f"/me/sessions/{review_session.public_id}"


def _submitted_from_page(request: Request) -> int:
    """The page a blocked Submit re-renders (findings A7).

    The Submit button posts to ``/submit?page=N`` with the page it sat
    on, so the gaps card opens over that page rather than page 1. A
    missing or malformed value falls back to 1; ``_surface_context``
    clamps an out-of-range one the same way.
    """
    try:
        return int(request.query_params.get("page", "1"))
    except ValueError:
        return 1


@router.get("/sessions/{session_id}", response_class=HTMLResponse, response_model=None)
def review_surface_default_position(request: Request, session_id: str) -> RedirectResponse:
    """Bare-URL fallback. 303s to ``/{id}/1`` (page 1) per the
    Segment 18L multi-page replan. Auth happens on the destination
    handler; the redirect is harmless without it.
    """
    return urls.redirect(request,
        url=f"/me/sessions/{session_id}/1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# GETs on the surface's POST-only addresses (participant audit M10).
# After a refused Submit, or a Save that re-rendered with errors, the
# address bar holds the POST's URL; pressing Enter on it, or signing in
# again, asked for a page that only takes a POST and answered 405 or 422.
# Each now 303s to a page (Save and Submit to the page they were sent
# from, Recall to the summary, Clear to the session), gated there as usual.
# The three session actions are registered ahead of ``/{page_n}``, which
# would otherwise take ``submit`` / ``recall`` / ``clear`` as a page
# number and 422.
@router.get("/sessions/{session_id}/{page_n}/save", response_model=None)
def review_surface_save_revisited(request: Request, session_id: str, page_n: int) -> RedirectResponse:
    return urls.redirect(request,
        url=f"/me/sessions/{session_id}/{page_n}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/submit", response_model=None)
def review_surface_submit_revisited(
    request: Request, session_id: str
) -> RedirectResponse:
    # ``?page=N`` is the page Submit was pressed on; parsed to an int,
    # so nothing but a number reaches the Location.
    return urls.redirect(request,
        url=f"/me/sessions/{session_id}/{_submitted_from_page(request)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/recall", response_model=None)
def review_surface_recall_revisited(request: Request, session_id: str) -> RedirectResponse:
    # Recall is posted from the summary page.
    return urls.redirect(request,
        url=f"/me/sessions/{session_id}/summary",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/sessions/{session_id}/clear", response_model=None)
def review_surface_clear_revisited(request: Request, session_id: str) -> RedirectResponse:
    return urls.redirect(request,
        url=f"/me/sessions/{session_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _page_changed(
    db: Session,
    form: Mapping[str, str],
    review_session: ReviewSession,
    page_rows: list[Assignment],
) -> bool:
    """Whether a post that carries answers was made against a page whose
    rows, or whose rows' groups, have changed since (19V Item 2;
    findings R1, 2026-10-22). A post with no answers names no row, so it
    needs no digest."""
    if not any(key.startswith("response[") for key in form):
        return False
    return not responses_service.digest_matches(
        form.get(responses_service.PAGE_DIGEST_FIELD),
        review_session,
        page_rows,
        group_keys=responses_service.group_keys(
            db, assignments=page_rows, session_id=review_session.id
        ),
    )


def _pre_open_response(
    request: Request,
    user: User,
    reviewer: Reviewer,
    review_session: ReviewSession,
    *,
    extra: dict | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """The pre-open page, for a ``draft`` or ``validated`` session (an
    archived one never passes the gate). ``extra`` carries a refused
    write's notice (P3)."""
    session_zone = sessions_service.resolve_session_timezone(review_session)
    deadline_text = (
        date_formatting.format_datetime(review_session.deadline, session_zone)
        if review_session.deadline
        else None
    )
    deadline_timezone_label = (
        date_formatting.gmt_offset_zone_label(
            session_zone, at=review_session.deadline
        )
        if review_session.deadline
        else None
    )
    # A prepared session's scheduled opening (participant audit M3). A
    # draft can't open on a schedule until it is prepared again, so it
    # shows none.
    scheduled_open_at = (
        review_session.scheduled_activate_at
        if lifecycle.is_validated(review_session)
        else None
    )
    return _templates.TemplateResponse(
        request,
        "reviewer/pre_open.html",
        {
            "user": user,
            "session": review_session,
            "deadline_text": deadline_text,
            "deadline_timezone_label": deadline_timezone_label,
            "scheduled_open_text": (
                date_formatting.format_datetime(scheduled_open_at, session_zone)
                if scheduled_open_at
                else None
            ),
            "scheduled_open_timezone_label": (
                date_formatting.gmt_offset_zone_label(
                    session_zone, at=scheduled_open_at
                )
                if scheduled_open_at
                else None
            ),
            # participant info Item 3 — the reviewer's own roster
            # fields, so they can check them before the review opens.
            "reviewer_self_fields": views.reviewer_self_line_for(
                review_session, reviewer
            ),
            **(extra or {}),
        },
        status_code=status_code,
    )


def _refused_write_response(
    request: Request,
    db: Session,
    user: User,
    reviewer: Reviewer,
    review_session: ReviewSession,
    cause: str,
    *,
    action: str,
    page_n: int,
    form: Mapping[str, str],
    page_assignment_ids: list[int] | None = None,
    status_code: int = status.HTTP_403_FORBIDDEN,
) -> HTMLResponse:
    """A refused Save / Submit / Clear (participant audit P3, author's
    ruling 2026-10-15). Rather than the standalone error page, which
    threw away what the reviewer typed, the page they were on renders
    again, read-only as a GET would show it now, with a notice naming
    the cause and the typed answers listed as text to copy. A session
    that is neither ``ready`` nor ``expired`` renders the pre-open
    page with the same notice. HTTP 403, as before; 409 when the page
    changed under the post (19V Item 2), whose answers are listed bare
    because their ordinals no longer name the rows they were typed into.
    ``page_assignment_ids`` maps the typed answers' ordinals to rows."""
    extra = {
        "write_refused": views.write_refused_notice(
            review_session, cause, action=action
        ),
        "unsaved_answers": views.unsaved_answers(
            db,
            review_session,
            reviewer,
            form,
            page_assignment_ids=page_assignment_ids or [],
        ),
    }
    if not (
        lifecycle.is_ready(review_session)
        or lifecycle.is_expired(review_session)
    ):
        return _pre_open_response(
            request,
            user,
            reviewer,
            review_session,
            extra=extra,
            status_code=status_code,
        )
    pages = _pages_for_session(db, review_session.id)
    if not 1 <= page_n <= len(pages):
        page_n = 1
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        page_n=page_n,
        cookies=dict(request.cookies),
    )
    context.update(extra)
    context["role_chips"] = build_role_chips(
        db, user=user, review_session=review_session, active_role="reviewer"
    )
    return _templates.TemplateResponse(
        request,
        "reviewer/review_surface.html",
        context,
        status_code=status_code,
    )


@router.get(
    "/sessions/{session_id}/{page_n}",
    response_class=HTMLResponse,
    response_model=None,
)
def review_surface(
    request: Request,
    page_n: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Multi-page reviewer surface (Segment 18L replan). Renders
    one operator-defined page at a time. Pages are derived from
    ``Instrument.starts_new_page`` via
    ``_pages_for_session``; ``page_n`` is the 1-based page index
    from the URL.

    A "page" can contain one or many instruments — the operator
    chose the boundaries on the Setup → Instruments page in
    Segment 18M. Within a page, instruments stack without a
    horizontal separator; between pages, the reviewer navigates
    via the Prev / Next links in the page-nav row.
    """
    reviewer, review_session = reviewer_session
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not (
        lifecycle.is_ready(review_session)
        or lifecycle.is_expired(review_session)
    ):
        return _pre_open_response(request, user, reviewer, review_session)
    pages = _pages_for_session(db, review_session.id)
    validate_page_n(page_n, pages)
    context = _surface_context(
        db=db,
        user=user,
        reviewer=reviewer,
        review_session=review_session,
        page_n=page_n,
        cookies=dict(request.cookies),
    )
    context["role_chips"] = build_role_chips(
        db, user=user, review_session=review_session, active_role="reviewer"
    )
    return _templates.TemplateResponse(
        request, "reviewer/review_surface.html", context
    )


@router.post(
    "/sessions/{session_id}/{page_n}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save(
    request: Request,
    page_n: int,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    """Save the form's response inputs for the given operator-defined
    page (Segment 18L multi-page replan).

    The form on each page carries only that page's answers, each named
    by its row's ordinal among the page's assignments (19V Item 2), so
    an answer can only address a row on this page. A post made against
    a page whose rows have changed since is refused with 409 and saves
    nothing, rather than mapping ordinals onto the wrong rows.

    Server-side value validation rejects per-upsert (Integer /
    Decimal range and step). Invalid upserts are not persisted; the
    surface re-renders inline with the typed value still in the box
    plus the Invalid-values warning card. Valid upserts in the same
    batch save through.
    """
    reviewer, review_session = reviewer_session
    form = await request.form()
    string_form = {k: v for k, v in form.items() if isinstance(v, str)}
    page_rows = page_assignments_for(db, review_session, reviewer, page_n)
    page_ids = [a.id for a in page_rows]
    upserts = responses_service.parse_form_payload(
        string_form, page_assignment_ids=page_ids
    )
    page_changed = _page_changed(db, string_form, review_session, page_rows)
    # A refusal lists the typed answers under their rows only when the
    # form's ordinals still name them.
    listed_ids = [] if page_changed else page_ids
    # Off the event loop: the gate's deadline observer may wait on the
    # session row lock (findings Bc4).
    refusal = await run_in_threadpool(
        _write_refusal, db, review_session, reviewer
    )
    if refusal is not None:
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="save",
            page_n=page_n,
            form=string_form,
            page_assignment_ids=listed_ids,
        )
    validate_page_n(page_n, _pages_for_session(db, review_session.id))
    if page_changed:
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            views.REFUSED_PAGE_CHANGED,
            action="save",
            page_n=page_n,
            form=string_form,
            status_code=status.HTTP_409_CONFLICT,
        )
    # Off the event loop: the save waits on the session row lock to
    # re-check, under it, that the session still accepts (findings L3).
    try:
        result = await run_in_threadpool(
            responses_service.save_draft,
            db,
            review_session=review_session,
            reviewer=reviewer,
            user=user,
            upserts=upserts,
            correlation_id=request_correlation_id(),
        )
    except SessionStateConflict:
        refusal = await run_in_threadpool(
            _race_refusal, db, review_session, reviewer
        )
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="save",
            page_n=page_n,
            form=string_form,
            page_assignment_ids=listed_ids,
        )
    if result.errors:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        # Off the event loop, like the gate: the context runs the deadline
        # observer, which may wait on the session row lock (findings Bc4).
        context = await run_in_threadpool(
            _surface_context,
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            page_n=page_n,
            errors=result.errors,
            bad_values=bad_values,
            cookies=dict(request.cookies),
        )
        context["role_chips"] = build_role_chips(
            db,
            user=user,
            review_session=review_session,
            active_role="reviewer",
        )
        return _templates.TemplateResponse(
            request,
            "reviewer/review_surface.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return urls.redirect(request,
        url=f"/me/sessions/{review_session.public_id}/{page_n}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/submit",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_submit(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    reviewer, review_session = reviewer_session
    form = await request.form()
    string_form = {k: v for k, v in form.items() if isinstance(v, str)}
    # Submit is pressed on a page and carries that page's answers, named
    # by ordinal like a Save's (19V Item 2).
    page_rows = page_assignments_for(
        db, review_session, reviewer, _submitted_from_page(request)
    )
    page_ids = [a.id for a in page_rows]
    upserts = responses_service.parse_form_payload(
        string_form, page_assignment_ids=page_ids
    )
    page_changed = _page_changed(db, string_form, review_session, page_rows)
    listed_ids = [] if page_changed else page_ids
    # Off the event loop: the gate's deadline observer may wait on the
    # session row lock (findings Bc4).
    refusal = await run_in_threadpool(
        _write_refusal, db, review_session, reviewer
    )
    if refusal is not None:
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="submit",
            page_n=_submitted_from_page(request),
            form=string_form,
            page_assignment_ids=listed_ids,
        )
    if page_changed:
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            views.REFUSED_PAGE_CHANGED,
            action="submit",
            page_n=_submitted_from_page(request),
            form=string_form,
            status_code=status.HTTP_409_CONFLICT,
        )
    # Off the event loop, like the save (findings L3).
    try:
        result = await run_in_threadpool(
            responses_service.submit,
            db,
            review_session=review_session,
            reviewer=reviewer,
            user=user,
            upserts=upserts,
            correlation_id=request_correlation_id(),
        )
    except SessionStateConflict:
        refusal = await run_in_threadpool(
            _race_refusal, db, review_session, reviewer
        )
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="submit",
            page_n=_submitted_from_page(request),
            form=string_form,
            page_assignment_ids=listed_ids,
        )
    if not result.submitted:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        # Off the event loop, like the gate: the context runs the deadline
        # observer, which may wait on the session row lock (findings Bc4).
        context = await run_in_threadpool(
            _surface_context,
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            page_n=_submitted_from_page(request),
            missing=result.missing,
            errors=result.errors,
            bad_values=bad_values,
            cookies=dict(request.cookies),
            show_incomplete_marks=not result.errors,
        )
        context["role_chips"] = build_role_chips(
            db,
            user=user,
            review_session=review_session,
            active_role="reviewer",
        )
        return _templates.TemplateResponse(
            request,
            "reviewer/review_surface.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    invitations_service.queue_responses_received(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    return urls.redirect(request,
        url=submit_redirect_url(
            review_session,
            fully_submitted=(
                state.total_assignments > 0
                and state.pill_state == "submitted"
            ),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _recall_refused(review_session: ReviewSession) -> HTTPException:
    """The 403 a Recall gets when the review no longer allows it."""
    closed = lifecycle.is_ready(review_session) or lifecycle.is_expired(
        review_session
    )
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "This review has closed, so your submission can't be recalled."
            if closed
            else "This review is not currently open, so your "
            "submission can't be recalled."
        ),
    )


@router.post(
    "/sessions/{session_id}/recall",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewer_recall(
    request: Request, reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Roll the reviewer's submission back to draft and land them
    on the form to edit it. The summary page's "Recall my
    submission" button posts here.

    Gated on session status ``ready`` and the deadline not yet
    passed. A closed (``expired``) or archived session has no live
    form to return to, and past the deadline the form is read-only
    and Submit is refused, so a recall there would strand the
    reviewer at "Saved but not submitted" (participant audit M1,
    author's ruling 2026-10-15). The summary page hides the button
    in the same states; this refuses a stale or hand-made POST.
    """
    reviewer, review_session = reviewer_session
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not lifecycle.recall_allowed(review_session):
        raise _recall_refused(review_session)
    try:
        responses_service.recall(
            db,
            review_session=review_session,
            reviewer=reviewer,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except SessionStateConflict:
        # Closed or reverted since the check above (findings L3).
        db.rollback()
        db.refresh(review_session)
        raise _recall_refused(review_session) from None
    return urls.redirect(request,
        url=f"/me/sessions/{review_session.public_id}/1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/clear",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_clear(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> HTMLResponse | RedirectResponse:
    reviewer, review_session = reviewer_session
    # Off the event loop: the gate's deadline observer may wait on the
    # session row lock (findings Bc4).
    refusal = await run_in_threadpool(
        _write_refusal, db, review_session, reviewer
    )
    if refusal is not None:
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="clear",
            page_n=1,
            form={},
        )
    form = await request.form()
    if form.get("confirm") != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check the box to confirm before clearing your answers.",
        )
    # Off the event loop, like the save (findings L3).
    try:
        await run_in_threadpool(
            responses_service.clear_all,
            db,
            review_session=review_session,
            reviewer=reviewer,
            user=user,
            correlation_id=request_correlation_id(),
        )
    except SessionStateConflict:
        refusal = await run_in_threadpool(
            _race_refusal, db, review_session, reviewer
        )
        return await run_in_threadpool(
            _refused_write_response,
            request,
            db,
            user,
            reviewer,
            review_session,
            refusal,
            action="clear",
            page_n=1,
            form={},
        )
    return urls.redirect(request,
        url=f"/me/sessions/{review_session.public_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
