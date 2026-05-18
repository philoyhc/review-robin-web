"""Session-setup card view-shapes — the Setup overview rows on
session detail and the canonical session-level status pills row.

Slice 5 of the §12.B ladder (``guide/archive/major_refactor.md``).

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
from app.services import assignments, csv_imports, field_labels
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


# Raw CSV column name -> renamable (source_type, source_field)
# slot. Only the 12 in-scope friendly-label slots appear; columns
# with no renamable slot (ReviewerName, ReviewerEmail,
# IncludeAssignment) keep their canonical CSV name.
_FIELD_LABEL_SLOTS: dict[str, tuple[str, str]] = {
    "ReviewerTag1": ("reviewer", "tag_1"),
    "ReviewerTag2": ("reviewer", "tag_2"),
    "ReviewerTag3": ("reviewer", "tag_3"),
    "RevieweeName": ("reviewee", "name"),
    "RevieweeEmail": ("reviewee", "email_or_identifier"),
    "PhotoLink": ("reviewee", "profile_link"),
    "RevieweeTag1": ("reviewee", "tag_1"),
    "RevieweeTag2": ("reviewee", "tag_2"),
    "RevieweeTag3": ("reviewee", "tag_3"),
    "PairContextTag1": ("pair_context", "1"),
    "PairContextTag2": ("pair_context", "2"),
    "PairContextTag3": ("pair_context", "3"),
}


def friendly_fields_with_data(
    review_session: ReviewSession, raw_labels: list[str]
) -> list[str]:
    """Map raw CSV column names to friendly field labels for the
    "Fields with data" pills on the Setup pages.

    Columns that correspond to one of the 12 renamable slots
    resolve through the session's field-label config (operator
    override → builtin default), so the pill reads the same as the
    preview-table column header. Columns with no renamable slot
    keep their canonical CSV name.
    """
    return [
        field_labels.resolve(review_session, *_FIELD_LABEL_SLOTS[raw])
        if raw in _FIELD_LABEL_SLOTS
        else raw
        for raw in raw_labels
    ]
