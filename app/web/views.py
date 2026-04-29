"""View-shape adapters for operator templates.

Translate domain objects into row tuples / dataclasses that templates
iterate over. Service modules stay business-logic-only; templates stay
markup-only.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import assignments, csv_imports


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
    """Rows for the Session setup card on session detail.

    Instruments and Set up invites render with disabled Manage buttons in
    9.4B; their Manage targets land in 9.4C.
    """
    sid = review_session.id
    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == sid)
        ).scalars()
    )
    if instruments:
        any_open = any(i.accepting_responses for i in instruments)
        if len(instruments) == 1:
            instrument_status = "open" if any_open else "closed"
        else:
            instrument_status = (
                f"{len(instruments)} ({'some open' if any_open else 'all closed'})"
            )
    else:
        instrument_status = "—"

    return [
        SetupRow(
            label="Reviewers",
            value=str(reviewer_count),
            manage_url=f"/operator/sessions/{sid}/reviewers",
        ),
        SetupRow(
            label="Reviewees",
            value=str(reviewee_count),
            manage_url=f"/operator/sessions/{sid}/reviewees",
        ),
        SetupRow(
            label="Instruments",
            value=instrument_status,
            manage_url=f"/operator/sessions/{sid}/instruments",
        ),
        SetupRow(
            label="Assignments",
            value=str(assignment_count),
            manage_url=f"/operator/sessions/{sid}/assignments",
        ),
        SetupRow(
            label="Set up invites",
            value="—",
            manage_url=f"/operator/sessions/{sid}/setupinvite",
        ),
    ]
