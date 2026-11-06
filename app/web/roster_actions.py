"""The Setup roster routes' shared action bodies (segment 22J).

Each roster's route module declares its own routes, since each roster's
form fields are its own (``reviewer_ids``, ``observer_ids``…) and are the
form's contract; what the bodies repeat lives here, driven by a
:class:`RosterKind`. A roster whose action genuinely differs keeps its
own body: Relationships' bulk inactivate, reactivate and delete, and its
delete all, acknowledge a response loss and refuse a group clear. The
panel saves (self fields, field labels) and :func:`back_to_panel` take a
slug rather than a kind, since Relationships shares them.

Outside the routes package on ``roster_import``'s terms: the slices
import this module, and it reads the package's guards from ``_shared``
inside its functions, never at its top, so the two never import each
other at load (``spec/architecture.md``); ``tests/unit/test_import_order.py``
imports it first, alone.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services import csv_imports, participant_info
from app.services import observers as observers_service
from app.services import reviewees as reviewees_service
from app.services import reviewers as reviewers_service
from app.services.observers import ObserverOperationError
from app.services.reviewees import RevieweeOperationError
from app.services.reviewers import ReviewerOperationError
from app.web import urls
from app.web.deps import request_correlation_id


@dataclass(frozen=True)
class RosterKind:
    """What one roster's shared actions need to know about it.

    ``noun`` names a row (``reviewer``) and keys the service's id keyword
    (``reviewer_ids``) and the row anchor; ``slug`` is its page's path
    segment. ``guard`` is the ``_shared`` check every write runs first:
    ``"editable"`` for the Reviewers and Reviewees rosters, which lock
    once validated, ``"not_archived"`` for Observers, which do not.
    ``delete_all_acknowledges_loss`` is false for Observers alone:
    nothing references an observer, so deleting the roster loses no
    response (segment 19I Item 3)."""

    noun: str
    slug: str
    model: type[Any]
    error: type[Exception]
    guard: str
    bulk_inactivate: Callable[..., object]
    bulk_reactivate: Callable[..., object]
    delete_selected: Callable[..., object]
    delete_all: Callable[..., object]
    delete_all_acknowledges_loss: bool


REVIEWERS = RosterKind(
    noun="reviewer",
    slug="reviewers",
    model=Reviewer,
    error=ReviewerOperationError,
    guard="editable",
    bulk_inactivate=reviewers_service.bulk_inactivate,
    bulk_reactivate=reviewers_service.bulk_reactivate,
    delete_selected=reviewers_service.delete_selected,
    delete_all=csv_imports.delete_all_reviewers,
    delete_all_acknowledges_loss=True,
)
REVIEWEES = RosterKind(
    noun="reviewee",
    slug="reviewees",
    model=Reviewee,
    error=RevieweeOperationError,
    guard="editable",
    bulk_inactivate=reviewees_service.bulk_inactivate,
    bulk_reactivate=reviewees_service.bulk_reactivate,
    delete_selected=reviewees_service.delete_selected,
    delete_all=csv_imports.delete_all_reviewees,
    delete_all_acknowledges_loss=True,
)
OBSERVERS = RosterKind(
    noun="observer",
    slug="observers",
    model=Observer,
    error=ObserverOperationError,
    guard="not_archived",
    bulk_inactivate=observers_service.bulk_inactivate,
    bulk_reactivate=observers_service.bulk_reactivate,
    delete_selected=observers_service.delete_selected,
    delete_all=csv_imports.delete_all_observers,
    delete_all_acknowledges_loss=False,
)


def _guard(kind: RosterKind, review_session: ReviewSession) -> None:
    from app.web.routes_operator import _shared

    if kind.guard == "editable":
        _shared._require_editable(review_session)
    else:
        _shared._require_not_archived(review_session)


def _call(
    kind: RosterKind,
    action: Callable[..., object],
    db: Session,
    *,
    review_session: ReviewSession,
    ids: list[int],
    user: User,
) -> None:
    """Run a service action, its refusal answered 400 with its message."""
    try:
        action(
            db,
            review_session=review_session,
            user=user,
            correlation_id=request_correlation_id(),
            **{f"{kind.noun}_ids": ids},
        )
    except kind.error as exc:
        message = getattr(exc, "message", str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from exc


def _back(
    kind: RosterKind,
    request: Request,
    review_session: ReviewSession,
    ids: list[int],
    *,
    filter_status: str,
    filter_q: str,
    filter_offset: int,
) -> RedirectResponse:
    from app.web.routes_operator import _shared

    return _shared._redirect_keeping_selection(
        request,
        f"/operator/sessions/{review_session.public_id}/{kind.slug}",
        ids,
        filter_params=[("status", filter_status), ("q", filter_q)],
        offset=filter_offset,
        anchor=_shared._row_action_anchor(ids, noun=kind.noun),
    )


def bulk_set_active(
    kind: RosterKind,
    request: Request,
    *,
    active: bool,
    ids: list[int],
    filter_status: str,
    filter_q: str,
    filter_offset: int,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> RedirectResponse:
    """Inactivate (``active=False``) or reactivate the ticked rows, back to
    the page with the filters and the selection kept."""
    _guard(kind, review_session)
    action = kind.bulk_reactivate if active else kind.bulk_inactivate
    _call(kind, action, db, review_session=review_session, ids=ids, user=user)
    return _back(
        kind,
        request,
        review_session,
        ids,
        filter_status=filter_status,
        filter_q=filter_q,
        filter_offset=filter_offset,
    )


def bulk_delete(
    kind: RosterKind,
    request: Request,
    *,
    ids: list[int],
    confirm: str | None,
    acknowledge_response_loss: str | None,
    filter_status: str,
    filter_q: str,
    filter_offset: int,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> RedirectResponse:
    """Delete the ticked rows behind the Danger Zone's two gates (the
    confirm and, where answers would go, the loss acknowledgement). The
    redirect keeps the filters but not the ids: the rows are gone, so the
    page answers with the table card."""
    from app.web.routes_operator import _shared

    _guard(kind, review_session)
    _shared._require_delete_confirm(confirm)
    _shared._require_selected_response_loss_ack(
        db, model=kind.model, ids=ids, ack=acknowledge_response_loss
    )
    _call(kind, kind.delete_selected, db, review_session=review_session, ids=ids, user=user)
    return _back(
        kind,
        request,
        review_session,
        [],
        filter_status=filter_status,
        filter_q=filter_q,
        filter_offset=filter_offset,
    )


def back_to_panel(request: Request, review_session: ReviewSession, slug: str) -> RedirectResponse:
    """Back to the page with the Unlock panel open, on the roster card.

    Every control here lives inside the panel, and a bare redirect would
    close the panel the operator was working in: a save does not close
    it, the Lock control does (19P.1 rung 3b shipped that omission on
    Reviewers' delete all and had to fix it)."""
    return urls.redirect(
        request,
        url=f"/operator/sessions/{review_session.public_id}/{slug}?unlocked=1#roster-card",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def delete_all(
    kind: RosterKind,
    request: Request,
    *,
    confirm: str | None,
    acknowledge_response_loss: str | None,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> RedirectResponse:
    """The Danger Zone's Delete all, behind the confirm and, where answers
    would go, the loss acknowledgement."""
    from app.web.routes_operator import _shared

    _guard(kind, review_session)
    _shared._require_delete_confirm(confirm)
    if kind.delete_all_acknowledges_loss:
        _shared._require_response_loss_ack(db, review_session, acknowledge_response_loss)
    kind.delete_all(
        db,
        review_session=review_session,
        user=user,
        correlation_id=request_correlation_id(),
    )
    return back_to_panel(request, review_session, kind.slug)


async def save_self_fields(
    request: Request,
    *,
    participant: str,
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> RedirectResponse:
    """Save what a participant sees of their own entry: the ticked chips
    plus ``keep``, the selected keys the card offered no chip for, so a
    field with no data stays selected. 422 on an unknown key."""
    form = await request.form()
    keys = [str(v) for v in form.getlist("fields")]
    keys += [str(v) for v in form.getlist("keep")]
    try:
        # The service locks the session row: wait for it off the loop.
        await run_in_threadpool(
            participant_info.set_self_fields,
            db,
            review_session=review_session,
            user=user,
            participant=participant,
            keys=keys,
            correlation_id=request_correlation_id(),
        )
    except participant_info.SelfFieldsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return back_to_panel(request, review_session, f"{participant}s")


async def save_field_labels(
    request: Request,
    *,
    slug: str,
    source_type: str,
    slots: tuple[tuple[str, str], ...],
    review_session: ReviewSession,
    user: User,
    db: Session,
) -> RedirectResponse:
    """Save a roster's three labels; ``slots`` is its allowlist of
    ``(form_param, source_field)``."""
    from app.web.roster_import import _save_field_labels

    form = await request.form()
    submitted = {param: str(form.get(param, "")) for param, _ in slots}
    # The labels service locks the session row (findings Bc4): wait for
    # it off the event loop.
    await run_in_threadpool(
        _save_field_labels,
        db,
        review_session=review_session,
        user=user,
        source_type=source_type,
        slots=slots,
        submitted=submitted,
        correlation_id=request_correlation_id(),
    )
    return back_to_panel(request, review_session, slug)
