"""Session-setup card view-shapes — the Setup overview rows on
session detail and the canonical session-level status pills row.

Slice 5 of the §12.B ladder (``guide/major_refactor.md``).

Owns ``SetupRow`` / ``build_setup_rows`` (the four rows on the
Session setup card on session detail) plus ``SessionStatusPills`` /
``session_status_pills`` (the standardized session-level status
row rendered by ``partials/session_setup_status_row.html``, which
appears on every session-scoped page so the chrome reads as a
single contract).

Source ranges in pre-PR-5 ``_legacy.py``: lines 37-101
(Setup card), 104-116 (``SessionStatusPills`` dataclass), 778-797
(``session_status_pills`` builder).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import assignments, csv_imports
from app.services import relationships as relationships_service


@dataclass
class SetupRow:
    label: str
    value: str
    manage_url: str
    manage_disabled: bool = False
    manage_disabled_reason: str | None = None


def build_setup_rows(
    db: Session, review_session: ReviewSession
) -> list[SetupRow]:
    """Rows for the Session setup card on session detail."""
    sid = review_session.id
    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    relationship_count = relationships_service.existing_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == sid)
        ).scalars()
    )
    instrument_count = len(instruments)
    if instrument_count == 0:
        instruments_value = "Number of instruments: 0"
    else:
        any_open = any(i.accepting_responses for i in instruments)
        all_open = all(i.accepting_responses for i in instruments)
        if all_open:
            status_word = "Open"
        elif not any_open:
            status_word = "Closed"
        else:
            status_word = "Mixed"
        instruments_value = (
            f"Number of instruments: {instrument_count}, Status: {status_word}"
        )

    return [
        SetupRow(
            label="Reviewers",
            value=f"Number of reviewers: {reviewer_count}",
            manage_url=f"/operator/sessions/{sid}/reviewers",
        ),
        SetupRow(
            label="Reviewees",
            value=f"Number of reviewees: {reviewee_count}",
            manage_url=f"/operator/sessions/{sid}/reviewees",
        ),
        SetupRow(
            label="Relationships",
            value=f"Number of relationships: {relationship_count}",
            manage_url=f"/operator/sessions/{sid}/relationships",
        ),
        SetupRow(
            label="Assignments",
            value=f"Number of assignments: {assignment_count}",
            manage_url=f"/operator/sessions/{sid}/assignments",
        ),
        SetupRow(
            label="Instruments",
            value=instruments_value,
            manage_url=f"/operator/sessions/{sid}/instruments",
        ),
        SetupRow(
            label="Email Invites",
            value="—",
            manage_url=f"/operator/sessions/{sid}/setupinvite",
        ),
    ]


@dataclass
class SessionStatusPills:
    """Counts shown on the standardized session-level status row
    (rendered by ``partials/session_setup_status_row.html``). The
    same numbers / flags appear on every session-scoped page so
    the chrome reads as a single contract."""

    reviewer_count: int
    reviewee_count: int
    relationship_count: int
    assignment_count: int
    instrument_count: int
    email_invites_set_up: bool


def session_status_pills(
    db: Session, review_session: ReviewSession
) -> SessionStatusPills:
    sid = review_session.id
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        relationship_count=relationships_service.existing_count(db, sid),
        assignment_count=assignments.existing_count(db, sid),
        instrument_count=len(
            list(
                db.execute(
                    select(Instrument).where(Instrument.session_id == sid)
                ).scalars()
            )
        ),
        # The Email Invites editor lands in Segment 15 — for now no
        # session is "set up" yet. When the editor ships, swap this
        # for a real check (e.g. a non-empty email template row).
        email_invites_set_up=False,
    )
