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

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    EmailOutbox,
    Instrument,
    Invitation,
    Response,
    ReviewSession,
)
from app.services import assignments, csv_imports, field_labels
from app.services import invitations as invitations_service
from app.services.text import pluralize
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
            manage_url=f"/operator/sessions/{sid}/setup-invite",
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
    observer_count: int
    assignment_count: int
    instrument_count: int
    email_invites_set_up: bool
    invitations_state: str
    """One of ``"not_created"`` / ``"not_sent"`` / ``"partial_sent"`` /
    ``"all_sent"``. Distinguishes the two flavours of pre-send (no
    ``Invitation`` rows at all vs. rows generated but no outbox email
    delivered yet) so the chrome status strip can read them apart."""
    responses_reportable: bool
    """``True`` iff the session has any response activity at all
    (``responses_drafts > 0`` or ``responses_submitted > 0``) — the Responses
    pill then reports its counts (see ``responses_label``). ``False`` (pill
    reads ``Awaiting``) only while there are no responses yet. Data-driven, not
    lifecycle-driven: a session reverted to draft after responses came in still
    reports the numbers."""
    responses_drafts: int
    """Number of **in-progress reviews** — ``include`` assignments in the
    session that have at least one saved response but **no** submitted one
    (all ``submitted_at`` still null). Mutually exclusive per assignment with
    ``responses_submitted``. Always computed."""
    responses_submitted: int
    """Number of **submitted reviews** — ``include`` assignments in the
    session with at least one response bearing a ``submitted_at`` — reported
    over ``reviewee_count`` (reviewee-centric, matching the Responses page).
    Always computed."""

    @property
    def responses_label(self) -> str:
        """Composed Responses-pill text: ``<n> drafts / <m> submitted /
        <reviewees>``, omitting whichever of drafts / submitted is zero, or
        ``"Awaiting"`` when there is no response activity at all."""
        if not self.responses_reportable:
            return "Awaiting"
        parts: list[str] = []
        if self.responses_drafts:
            parts.append(
                f"{self.responses_drafts} "
                f"{pluralize(self.responses_drafts, 'draft')}"
            )
        if self.responses_submitted:
            parts.append(f"{self.responses_submitted} submitted")
        parts.append(str(self.reviewee_count))
        return " / ".join(parts)


_INVITATION_STATES: tuple[str, ...] = (
    "not_created",
    "not_sent",
    "partial_sent",
    "all_sent",
)


def _invitations_state(db: Session, session_id: int) -> str:
    """Compute the chrome-strip ``invitations`` pill state.

    ``not_created`` — zero ``Invitation`` rows for the session.
    ``not_sent`` — invitations exist; no reviewer has a ``sent``
      outbox row for their invitation yet.
    ``partial_sent`` — at least one but not every reviewer has a
      ``sent`` outbox row.
    ``all_sent`` — every reviewer with an invitation has a ``sent``
      outbox row.
    """
    invitation_reviewer_ids: set[int] = set(
        db.execute(
            select(Invitation.reviewer_id).where(
                Invitation.session_id == session_id
            )
        ).scalars()
    )
    if not invitation_reviewer_ids:
        return "not_created"
    sent_reviewer_ids: set[int] = set(
        db.execute(
            select(EmailOutbox.reviewer_id).where(
                EmailOutbox.session_id == session_id,
                EmailOutbox.kind == invitations_service.INVITATION_KIND,
                EmailOutbox.status == "sent",
                EmailOutbox.reviewer_id.is_not(None),
            )
        ).scalars()
    )
    if not sent_reviewer_ids:
        return "not_sent"
    if sent_reviewer_ids >= invitation_reviewer_ids:
        return "all_sent"
    return "partial_sent"


def session_status_pills(
    db: Session, review_session: ReviewSession
) -> SessionStatusPills:
    sid = review_session.id
    # Responses pill: "<n> drafts / <m> submitted / <reviewees>", omitting
    # whichever of drafts / submitted is zero, or "Awaiting" while there is no
    # response activity at all. Gate is data-driven, not lifecycle-driven — a
    # session reverted to draft after responses came in keeps reporting the
    # numbers. Both aggregates run on every session page (reviewee-centric,
    # counting distinct include-assignments = "reviews").
    responses_submitted = db.execute(
        select(func.count(distinct(Response.assignment_id)))
        .select_from(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == sid,
            Assignment.include.is_(True),
            Response.submitted_at.is_not(None),
        )
    ).scalar_one()
    responses_with_any = db.execute(
        select(func.count(distinct(Response.assignment_id)))
        .select_from(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(
            Assignment.session_id == sid,
            Assignment.include.is_(True),
        )
    ).scalar_one()
    # Drafts = assignments with saved responses but none submitted.
    responses_drafts = responses_with_any - responses_submitted
    responses_reportable = responses_with_any > 0
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        relationship_count=relationships_service.existing_count(db, sid),
        observer_count=csv_imports.existing_observer_count(db, sid),
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
        invitations_state=_invitations_state(db, sid),
        responses_reportable=responses_reportable,
        responses_drafts=responses_drafts,
        responses_submitted=responses_submitted,
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
