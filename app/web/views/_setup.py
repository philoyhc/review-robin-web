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
from app.services import instruments as instruments_service
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
    instruments_configured: int
    """How many of ``instrument_count`` pass
    ``instruments.is_configured`` — at least one visible response field
    and all three Band 1 links touched. The status row reports both, so
    an instrument that exists but cannot yet be answered stops reading
    as done (2026-09-07). Always ``<= instrument_count``."""

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
    instrument_total, instruments_configured = (
        instruments_service.configured_counts(db, sid)
    )
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        relationship_count=relationships_service.existing_count(db, sid),
        observer_count=csv_imports.existing_observer_count(db, sid),
        assignment_count=assignments.existing_count(db, sid),
        instrument_count=instrument_total,
        instruments_configured=instruments_configured,
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
# slot. Only the 12 in-scope friendly-label slots appear.
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


# Raw CSV column name -> the pill's text on one page, for columns
# where the renamable slots cannot supply it (Segment 19H Item 4a,
# 2026-09-09).
#
# Two different reasons land here, and they need the same answer.
# `ReviewerName` / `ReviewerEmail` have no slot at all, so they fell
# out as raw CSV names on a page whose preview columns say `Name` and
# `Email`. `RevieweeEmail` does have one — resolvable to a builtin
# default, though not operator-overridable — and on Relationships it
# resolved to the reviewee page's `Email` beside a preview column
# headed `Reviewee`.
# Same column, two pages, two headers: the mapping cannot be global,
# which is why it is keyed by surface and why it is consulted before
# the renamable slots rather than after.
_SURFACE_LABELS: dict[str, dict[str, str]] = {
    "reviewers": {"ReviewerName": "Name", "ReviewerEmail": "Email"},
    "reviewees": {},
    "relationships": {
        "ReviewerEmail": "Reviewer",
        "RevieweeEmail": "Reviewee",
    },
}


def friendly_fields_with_data(
    review_session: ReviewSession,
    raw_labels: list[str],
    *,
    surface: str,
) -> list[str]:
    """Map raw CSV column names to what the page's preview column says,
    for the "Fields with data" pills on the Setup pages.

    The pill and the preview-table header name the same column, so they
    read the same thing. Three sources, in order:

    1. ``_SURFACE_LABELS[surface]`` — this page's own header for a
       column the renamable slots cannot name correctly. It wins,
       because the preview header it mirrors is fixed: Relationships
       heads its two identifier columns ``Reviewer`` and ``Reviewee``,
       which is a different question from what the reviewee page calls
       its identifier column.
    2. the session's field-label config (operator override → builtin
       default) for one of the 12 in-scope field-label slots. Nine of
       those are operator-renamable; the three reviewee-identity slots
       resolve to a fixed builtin default and reject an override, which
       is why `_SURFACE_LABELS` is the only way to give `RevieweeEmail`
       a different word on a different page.
    3. the canonical CSV name, for anything else — ``Status`` on
       Relationships, whose preview header is also ``Status``.

    ``surface`` is keyword-only and required, and indexes rather than
    ``get``s: a page that forgets it, or misspells it, fails loudly
    instead of quietly rendering CSV column names again.
    """
    page_labels = _SURFACE_LABELS[surface]
    resolved: list[str] = []
    for raw in raw_labels:
        if raw in page_labels:
            resolved.append(page_labels[raw])
        elif raw in _FIELD_LABEL_SLOTS:
            resolved.append(
                field_labels.resolve(review_session, *_FIELD_LABEL_SLOTS[raw])
            )
        else:
            resolved.append(raw)
    return resolved


def chip_slots(
    presence: dict[str, bool], *, prefix: str
) -> dict[str, bool]:
    """Re-key a ``{"tag_1": bool, ...}`` presence map to the chip slot
    names a page's markup actually uses.

    The column-visibility primitive knows no slot vocabulary — it
    toggles ``col-hidden-{slot}`` for whatever slot a chip names — so
    each page picks its own. The Setup rosters, Invitations and
    Responses use ``tag-1``..``tag-3``; Assignments groups nine slots
    as ``rt1``..``rt3`` / ``et1``..``et3`` / ``p1``..``p3``. Both
    shapes are ``prefix`` + the slot number, which is why one mapper
    covers all six (Segment 19I Item 12 rung 2).

    Templates then read a flag instead of computing one. Before this,
    six templates each scanned their own row list with ``selectattr``
    — the divergence that let every one of them disagree with the
    roster.
    """
    return {
        f"{prefix}{key.removeprefix('tag_')}": value
        for key, value in presence.items()
    }
