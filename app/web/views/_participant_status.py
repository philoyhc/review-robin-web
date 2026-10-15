"""The ``/me`` row's session status (participant audit M6, author's
ruling 2026-10-15).

One rule for every role. "Open" and "Closed" say whether the review is
accepting responses; "Available" is the period after that when the
viewer's own role can still see something, which differs by role, so a
row past its deadline can read "Available" for an observer and "Closed"
for a reviewer on another session. The old labels gave an observer-only
row "open" past the deadline while a reviewer row beside it said
"closed", and an archived row "not opened".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    Reviewer,
    ReviewSession,
)
from app.services import session_lifecycle as lifecycle
from app.services import visibility_policies


@dataclass(frozen=True)
class ParticipantStatus:
    label: str
    css: str


NOT_OPEN_YET = ParticipantStatus("Not open yet", "pill-info")
OPEN = ParticipantStatus("Open", "pill-success")
AVAILABLE = ParticipantStatus("Available", "pill-success")
CLOSED = ParticipantStatus("Closed", "pill-error")
FINISHED = ParticipantStatus("Finished", "pill-lifecycle-archived")


def _reviewer_can_read_back(
    db: Session, review_session: ReviewSession, reviewer: Reviewer
) -> bool:
    """The reviewer has saved an answer, on a field the surface still
    shows, of an instrument whose ``peer_reviewer`` setting lets them
    read it back now."""
    instrument_ids = set(
        db.execute(
            select(Assignment.instrument_id)
            .join(Response, Response.assignment_id == Assignment.id)
            .join(
                InstrumentResponseField,
                InstrumentResponseField.id == Response.response_field_id,
            )
            .where(
                InstrumentResponseField.visible.is_(True),
                Assignment.session_id == review_session.id,
                Assignment.reviewer_id == reviewer.id,
                Assignment.include.is_(True),
            )
        ).scalars()
    )
    if not instrument_ids:
        return False
    policies = visibility_policies.peer_reviewer_policies(db, instrument_ids)
    return any(
        visibility_policies.reviewer_sees_own_responses(
            review_session, policies.get(instrument_id)
        )
        for instrument_id in instrument_ids
    )


def participant_session_status(
    db: Session,
    *,
    review_session: ReviewSession,
    roles: list[str],
    reviewer: Reviewer | None,
) -> ParticipantStatus:
    """The status pill for one ``/me`` row. ``roles`` is the row's role
    list, which carries ``reviewee`` only while a reviewee grant
    resolves (19F)."""
    if lifecycle.is_archived(review_session):
        return FINISHED
    if not (
        lifecycle.is_ready(review_session) or lifecycle.is_expired(review_session)
    ):
        return NOT_OPEN_YET
    if lifecycle.is_ready(review_session) and not lifecycle.deadline_has_passed(
        review_session
    ):
        return OPEN
    if "reviewee" in roles:
        return AVAILABLE
    if "observer" in roles and visibility_policies.observer_has_current_grant(
        db, review_session
    ):
        return AVAILABLE
    if reviewer is not None and _reviewer_can_read_back(
        db, review_session, reviewer
    ):
        return AVAILABLE
    return CLOSED


def participant_start_at(review_session: ReviewSession) -> datetime | None:
    """The ``/me`` Start column: when the session opened, once it has;
    a prepared session's scheduled opening before then; nothing for a
    draft, whose ``activated_at`` may be left from before a revert
    (participant audit M6)."""
    if lifecycle.is_validated(review_session):
        return review_session.scheduled_activate_at
    if lifecycle.is_draft(review_session):
        return None
    return review_session.activated_at
