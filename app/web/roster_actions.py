"""The Setup roster routes' shared action bodies (segment 22J).

Each roster's route module declares its own routes, since each roster's
form fields are its own (``reviewer_ids``, ``observer_ids``…) and are the
form's contract; what the bodies repeat lives here, driven by a
:class:`RosterKind`. A roster whose action genuinely differs keeps its
own body: Relationships' bulk inactivate, reactivate and delete
acknowledge a response loss and refuse a group clear.

Outside the routes package on ``roster_import``'s terms: the slices
import this module, and it reads the package's guards from ``_shared``
inside its functions, never at its top, so the two never import each
other at load (``spec/architecture.md``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services import observers as observers_service
from app.services import reviewees as reviewees_service
from app.services import reviewers as reviewers_service
from app.services.observers import ObserverOperationError
from app.services.reviewees import RevieweeOperationError
from app.services.reviewers import ReviewerOperationError


@dataclass(frozen=True)
class RosterKind:
    """What one roster's shared actions need to know about it.

    ``noun`` names a row (``reviewer``) and keys the service's id keyword
    (``reviewer_ids``) and the row anchor; ``slug`` is its page's path
    segment. ``guard`` is the ``_shared`` check every write runs first:
    ``"editable"`` for the Reviewers and Reviewees rosters, which lock
    once validated, ``"not_archived"`` for Observers, which do not."""

    noun: str
    slug: str
    model: type[Any]
    error: type[Exception]
    guard: str
    bulk_inactivate: Callable[..., object]
    bulk_reactivate: Callable[..., object]
    delete_selected: Callable[..., object]


REVIEWERS = RosterKind(
    noun="reviewer",
    slug="reviewers",
    model=Reviewer,
    error=ReviewerOperationError,
    guard="editable",
    bulk_inactivate=reviewers_service.bulk_inactivate,
    bulk_reactivate=reviewers_service.bulk_reactivate,
    delete_selected=reviewers_service.delete_selected,
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
    from app.web.deps import request_correlation_id

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
