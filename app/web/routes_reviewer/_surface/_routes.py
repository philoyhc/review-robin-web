"""Reviewer surface — route handlers.

Owns the ``/me/sessions/{id}/{page_n}`` GET + the per-page Save +
the session-wide Submit / Recall / Clear POSTs + the consolidated
Save (post-Segment-18L). Each handler stays thin — the template
context comes from :func:`_surface_context` in ``_context``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.db.session import get_db
from app.services import date_formatting
from app.services import responses as responses_service
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from app.web import breadcrumbs
from app.web.deps import (
    get_or_create_user,
    request_correlation_id,
    require_reviewer_in_session,
)
from app.web.routes_reviewer._shared import (
    _templates,
    build_role_chips,
    reviewer_review_count_for_user,
    validate_page_n,
)

from ._context import (
    _load_assignments_with_relations,
    _pages_for_session,
    _require_session_accepting,
    _surface_context,
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
        return f"/me/sessions/{review_session.id}/summary"
    return f"/me/sessions/{review_session.id}"


@router.get("/sessions/{session_id}", response_class=HTMLResponse, response_model=None)
def review_surface_default_position(session_id: int) -> RedirectResponse:
    """Bare-URL fallback. 303s to ``/{id}/1`` (page 1) per the
    Segment 18L multi-page replan. Auth happens on the destination
    handler; the redirect is harmless without it.
    """
    return RedirectResponse(
        url=f"/me/sessions/{session_id}/1",
        status_code=status.HTTP_303_SEE_OTHER,
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
        session_zone = sessions_service.resolve_session_timezone(
            review_session
        )
        deadline_text = (
            date_formatting.format_datetime(
                review_session.deadline, session_zone
            )
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
        return _templates.TemplateResponse(
            request,
            "reviewer/pre_open.html",
            {
                "user": user,
                "session": review_session,
                "deadline_text": deadline_text,
                "deadline_timezone_label": deadline_timezone_label,
            },
        )
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
    context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
    context["reviewer_review_count"] = reviewer_review_count_for_user(db, user)
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

    The form on each page carries only that page's assignment inputs
    (the GET handler filters ``instrument_groups`` to the current
    page). A defense-in-depth filter still drops cross-page
    assignment ids so a stale form posting from a previous render
    can't accidentally write to other pages.

    Server-side value validation rejects per-upsert (Integer /
    Decimal range and step). Invalid upserts are not persisted; the
    surface re-renders inline with the typed value still in the box
    plus the Invalid-values warning card. Valid upserts in the same
    batch save through.
    """
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    pages = _pages_for_session(db, review_session.id)
    validate_page_n(page_n, pages)
    target_instrument_ids = {inst.id for inst in pages[page_n - 1]}
    target_assignment_ids = {
        a.id
        for a in _load_assignments_with_relations(
            db, session_id=review_session.id, reviewer_id=reviewer.id
        )
        if a.instrument_id in target_instrument_ids
    }
    upserts = [u for u in upserts if u.assignment_id in target_assignment_ids]
    result = responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if result.errors:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        context = _surface_context(
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            page_n=page_n,
            errors=result.errors,
            bad_values=bad_values,
            cookies=dict(request.cookies),
        )
        context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
        context["reviewer_review_count"] = reviewer_review_count_for_user(
            db, user
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
    return RedirectResponse(
        url=f"/me/sessions/{review_session.id}/{page_n}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --------------------------------------------------------------------------- #
# Segment 18L PR 1a — consolidated save endpoint.
#
# Walks every upsert in the form payload (no per-position filter) and
# persists in one ``responses_service.save_draft`` call. The new
# canonical save target for the upcoming single-page render in PR 1b.
# Audit emit registers ``assignments_touched`` + ``responses_saved``
# in ``detail.counts`` (PR 1a swapped the keys cleanly; the legacy
# ``saved`` + ``validation_errors`` retire in the same change).
#
# Lands inert: the template's <form action> still points at the
# legacy positional save endpoint. PR 1b flips the form action,
# drops the legacy POST + the per-position filter, and wires the
# inline error re-render. Until then this endpoint is only reachable
# directly (tests, scripted callers).
# --------------------------------------------------------------------------- #


@router.post(
    "/sessions/{session_id}/save",
    response_class=HTMLResponse,
    response_model=None,
)
async def reviewer_save_consolidated(
    request: Request,
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Save every upsert in the form payload in one round-trip.

    No per-position filter — the form normally carries inputs for
    every instrument the reviewer has assignments on (PR 1b's
    single-page render is the natural source). Server-side value
    validation rejects per-upsert as before; invalid upserts are not
    persisted, valid ones in the same batch save through. Errors
    surface as HTTP 400 with a JSON detail in PR 1a; PR 1b wires the
    inline single-page re-render that highlights the offending cells
    on top of the saved values.

    Always redirects on success to the bare session URL — which
    today 303s on to ``/{id}/1`` (positional render) and after PR 1b
    will be the single-page render directly. Either way the
    operator-visible behaviour from this endpoint is "go back to the
    surface".
    """
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    upserts = responses_service.parse_form_payload(
        {k: v for k, v in form.items() if isinstance(v, str)}
    )
    result = responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if result.errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "errors": [
                    {
                        "assignment_id": e.assignment_id,
                        "field_key": e.field_key,
                        "value": e.value,
                    }
                    for e in result.errors
                ],
            },
        )
    return RedirectResponse(
        url=f"/me/sessions/{review_session.id}",
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
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    string_form = {k: v for k, v in form.items() if isinstance(v, str)}
    upserts = responses_service.parse_form_payload(string_form)
    result = responses_service.submit(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        upserts=upserts,
        correlation_id=request_correlation_id(),
    )
    if not result.submitted:
        bad_values = {
            (e.assignment_id, e.field_key): e.value for e in result.errors
        }
        context = _surface_context(
            db=db,
            user=user,
            reviewer=reviewer,
            review_session=review_session,
            missing=result.missing,
            errors=result.errors,
            bad_values=bad_values,
            cookies=dict(request.cookies),
            show_incomplete_marks=not result.errors,
        )
        context["breadcrumbs"] = breadcrumbs.reviewer_session(review_session)
        context["reviewer_review_count"] = reviewer_review_count_for_user(
            db, user
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
    state = responses_service.reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    return RedirectResponse(
        url=submit_redirect_url(
            review_session,
            fully_submitted=(
                state.total_assignments > 0
                and state.pill_state == "submitted"
            ),
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/sessions/{session_id}/recall",
    response_class=HTMLResponse,
    response_model=None,
)
def reviewer_recall(
    reviewer_session: tuple[Reviewer, ReviewSession] = Depends(
        require_reviewer_in_session
    ),
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Roll the reviewer's submission back to draft and land them
    on the form to edit it. The summary page's "Recall my
    submission" button posts here.

    Gated on session status ``ready`` only — a session that's
    been closed (``expired``) or archived has no live form to
    return to, so recall is meaningless. Per-instrument
    ``accepting_responses`` flips by the operator don't block
    recall; the reviewer is putting their values back into the
    draft pool to keep editing them on whichever instruments
    are still open.
    """
    reviewer, review_session = reviewer_session
    lifecycle.observe_deadline(
        db, review_session, correlation_id=request_correlation_id()
    )
    db.refresh(review_session)
    if not lifecycle.is_ready(review_session):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Recall is only allowed while the session is ready; "
                f"session status is {review_session.status!r}."
            ),
        )
    responses_service.recall(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/me/sessions/{review_session.id}/1",
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
) -> RedirectResponse:
    reviewer, review_session = reviewer_session
    _require_session_accepting(db, review_session, reviewer)
    form = await request.form()
    if form.get("confirm") != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm checkbox required",
        )
    responses_service.clear_all(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return RedirectResponse(
        url=f"/me/sessions/{review_session.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
