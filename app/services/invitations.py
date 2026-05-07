"""Invitation generation, token handling, and dev-mode email outbox.

Segment 9.2 ships per-reviewer invitation tokens that route through the
existing Easy Auth sign-in. Tokens are hashed with sha256 in the DB; the
raw token is shown to the operator at outbox-write time and stored in
the outbox row body for re-copy. No real SMTP — outbox rows synchronously
flip ``queued → sent`` and are visible on a per-session operator page.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    EmailOutbox,
    Invitation,
    ReviewSession,
    Reviewer,
    User,
)
from app.services import audit, email_templates


INVITATION_KIND = "invitation"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


# Subject + body rendering retired in Segment 11E PR 1; ``send_invitation``
# / ``send_reminder`` call ``email_templates.render_invitation`` /
# ``render_reminder`` instead, which pick up per-session overrides from
# ``ReviewSession.email_template_overrides`` and merge in the canonical
# five-tag merge field set (reviewer name, session name, deadline, help
# contact, invite URL).


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


@dataclass
class GenerateResult:
    created_count: int
    invitation_ids: list[int]


def _assigned_active_reviewer_ids(db: Session, session_id: int) -> list[int]:
    rows = db.execute(
        select(Reviewer.id)
        .join(Assignment, Assignment.reviewer_id == Reviewer.id)
        .where(
            Assignment.session_id == session_id,
            Assignment.include.is_(True),
            Reviewer.status == "active",
        )
        .distinct()
    ).scalars()
    return list(rows)


def generate_invitations(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> GenerateResult:
    """Idempotently create one Invitation per assigned active reviewer.

    Reviewers without at least one ``include=true`` assignment are skipped.
    Reviewers who already have an Invitation row in this session are left
    untouched (token + state preserved).
    """
    candidate_ids = set(_assigned_active_reviewer_ids(db, review_session.id))
    existing_ids = set(
        db.execute(
            select(Invitation.reviewer_id).where(
                Invitation.session_id == review_session.id
            )
        ).scalars()
    )
    to_create = candidate_ids - existing_ids

    new_ids: list[int] = []
    for reviewer_id in sorted(to_create):
        _, token_hash = _new_token()
        invitation = Invitation(
            session_id=review_session.id,
            reviewer_id=reviewer_id,
            token_hash=token_hash,
            status="pending",
        )
        db.add(invitation)
        db.flush()
        new_ids.append(invitation.id)

    if new_ids:
        audit.write_event(
            db,
            event_type="invitations.generated",
            summary=(
                f"Generated {len(new_ids)} invitation"
                f"{'' if len(new_ids) == 1 else 's'}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.set_changes(
                added=[
                    {"invitation_id": iid, "reviewer_id": rid}
                    for iid, rid in zip(new_ids, sorted(to_create))
                ]
            ),
            correlation_id=correlation_id,
        )
    db.commit()
    return GenerateResult(created_count=len(new_ids), invitation_ids=new_ids)


# --------------------------------------------------------------------------- #
# Regenerate
# --------------------------------------------------------------------------- #


@dataclass
class RegenerateResult:
    raw_token: str


def regenerate_token(
    db: Session,
    *,
    invitation: Invitation,
    user: User,
    correlation_id: str | None = None,
) -> RegenerateResult:
    """Rotate the token, reset the invitation to ``pending``."""
    raw, token_hash = _new_token()
    invitation.token_hash = token_hash
    invitation.status = "pending"
    invitation.sent_at = None
    invitation.opened_at = None
    db.flush()
    audit.write_event(
        db,
        event_type="invitation.regenerated",
        summary=f"Regenerated invitation #{invitation.id}",
        actor_user_id=user.id,
        session=invitation.session,
        refs={
            "invitation_id": invitation.id,
            "reviewer_id": invitation.reviewer_id,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return RegenerateResult(raw_token=raw)


@dataclass
class RegenerateAllResult:
    regenerated_count: int
    invitation_ids: list[int]


def regenerate_all_tokens(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> RegenerateAllResult:
    """Rotate tokens on every invitation in the session.

    Each invitation gets a fresh token; status flips to ``pending``
    and ``sent_at`` / ``opened_at`` clear. The previous URLs become
    stale uniformly. Emits a single batch ``invitations.regenerated``
    audit event when at least one invitation was rotated. No-op when
    the session has no invitations yet."""
    rows = list(
        db.execute(
            select(Invitation).where(
                Invitation.session_id == review_session.id
            )
        ).scalars()
    )
    rotated_ids: list[int] = []
    rotated_reviewer_ids: list[int] = []
    for invitation in rows:
        _, token_hash = _new_token()
        invitation.token_hash = token_hash
        invitation.status = "pending"
        invitation.sent_at = None
        invitation.opened_at = None
        rotated_ids.append(invitation.id)
        rotated_reviewer_ids.append(invitation.reviewer_id)
    if rotated_ids:
        db.flush()
        audit.write_event(
            db,
            event_type="invitations.regenerated",
            summary=(
                f"Regenerated {len(rotated_ids)} invitation"
                f"{'' if len(rotated_ids) == 1 else 's'}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.set_changes(
                updated=[
                    {"invitation_id": iid, "reviewer_id": rid}
                    for iid, rid in zip(rotated_ids, rotated_reviewer_ids)
                ]
            ),
            correlation_id=correlation_id,
        )
        db.commit()
    return RegenerateAllResult(
        regenerated_count=len(rotated_ids),
        invitation_ids=rotated_ids,
    )


# --------------------------------------------------------------------------- #
# Send (write outbox row, flip status)
# --------------------------------------------------------------------------- #


@dataclass
class SendResult:
    outbox_id: int
    raw_token: str


def send_invitation(
    db: Session,
    *,
    invitation: Invitation,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    build_invite_url: Callable[[str], str],
    correlation_id: str | None = None,
) -> SendResult:
    """Mint a fresh token, write an outbox row, flip invitation to ``sent``.

    The DB only ever stores the sha256 hash, so each send rotates the token
    and the previous URL (if any) becomes stale. The raw token is preserved
    in the outbox row body so the operator can re-copy the link.

    ``build_invite_url`` takes a raw token and returns the absolute invite
    URL. Routes pass ``request.url_for`` closed over the route name; a
    background worker (Segment 15 #34) passes a deployment-base-URL closure.
    """
    raw_token, token_hash = _new_token()
    invitation.token_hash = token_hash

    invite_url = build_invite_url(raw_token)
    subject, body = email_templates.render_invitation(
        review_session, reviewer, invite_url
    )
    cc_emails, bcc_emails = email_templates.cc_bcc_for(
        review_session, INVITATION_KIND
    )

    outbox = EmailOutbox(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        invitation_id=invitation.id,
        kind=INVITATION_KIND,
        to_email=reviewer.email,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
        subject=subject,
        body=body,
        status="queued",
    )
    db.add(outbox)
    db.flush()

    now = datetime.now(timezone.utc)
    outbox.status = "sent"
    outbox.sent_at = now
    invitation.status = "sent"
    invitation.sent_at = now
    invitation.opened_at = None
    db.flush()

    audit.write_event(
        db,
        event_type="invitation.sent",
        summary=(
            f"Sent invitation #{invitation.id} to {reviewer.email}"
        ),
        actor_user_id=user.id,
        session=review_session,
        refs={
            "invitation_id": invitation.id,
            "reviewer_id": reviewer.id,
            "outbox_id": outbox.id,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return SendResult(outbox_id=outbox.id, raw_token=raw_token)


# --------------------------------------------------------------------------- #
# Token follow
# --------------------------------------------------------------------------- #


def lookup_invitation_by_token(
    db: Session, raw_token: str
) -> tuple[Invitation, ReviewSession, Reviewer] | None:
    token_hash = hash_token(raw_token)
    row = db.execute(
        select(Invitation, ReviewSession, Reviewer)
        .join(ReviewSession, ReviewSession.id == Invitation.session_id)
        .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
        .where(Invitation.token_hash == token_hash)
    ).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


def record_open(
    db: Session,
    *,
    invitation: Invitation,
    user: User,
    correlation_id: str | None = None,
) -> bool:
    """Stamp ``opened_at`` on the first valid token follow.

    Returns True iff this call was the first open. Subsequent calls are
    no-ops and return False (idempotent).
    """
    if invitation.opened_at is not None:
        return False
    invitation.opened_at = datetime.now(timezone.utc)
    invitation.status = "opened"
    db.flush()
    audit.write_event(
        db,
        event_type="invitation.opened",
        summary=f"Invitation #{invitation.id} opened",
        actor_user_id=user.id,
        session=invitation.session,
        refs={
            "invitation_id": invitation.id,
            "reviewer_id": invitation.reviewer_id,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return True


# --------------------------------------------------------------------------- #
# Helpers for the operator surface
# --------------------------------------------------------------------------- #


@dataclass
class InvitationRow:
    invitation: Invitation
    reviewer: Reviewer


def list_invitations_for_session(
    db: Session, session_id: int
) -> list[InvitationRow]:
    rows = db.execute(
        select(Invitation, Reviewer)
        .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
        .where(Invitation.session_id == session_id)
        .order_by(Reviewer.email)
    ).all()
    return [InvitationRow(invitation=r[0], reviewer=r[1]) for r in rows]


def list_outbox_for_session(db: Session, session_id: int) -> list[EmailOutbox]:
    return list(
        db.execute(
            select(EmailOutbox)
            .where(EmailOutbox.session_id == session_id)
            .order_by(EmailOutbox.created_at.desc(), EmailOutbox.id.desc())
        ).scalars()
    )


def reviewers_eligible_for_invitation(
    db: Session, session_id: int
) -> list[Reviewer]:
    """Active reviewers with at least one include=true assignment."""
    ids = _assigned_active_reviewer_ids(db, session_id)
    if not ids:
        return []
    return list(
        db.execute(
            select(Reviewer).where(Reviewer.id.in_(ids)).order_by(Reviewer.email)
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# Reminders (Segment 9.3)
# --------------------------------------------------------------------------- #


REMINDER_KIND = "reminder"

_INVITE_URL_PATTERN = re.compile(r"https?://\S+/reviewer/invite/[A-Za-z0-9_\-]+")


def most_recent_invitation_url(
    db: Session, *, invitation_id: int
) -> str | None:
    """Pull the raw token URL from the most recent invitation outbox row.

    Reminders reuse the existing URL so the previously-sent link keeps
    working. Returns None if the invitation has never been sent.
    """
    row = db.execute(
        select(EmailOutbox)
        .where(
            EmailOutbox.invitation_id == invitation_id,
            EmailOutbox.kind == INVITATION_KIND,
        )
        .order_by(EmailOutbox.created_at.desc(), EmailOutbox.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    match = _INVITE_URL_PATTERN.search(row.body)
    return match.group(0) if match else None


# ``_reminder_body`` retired in Segment 11E PR 1 alongside ``_email_body``.


@dataclass
class ReminderResult:
    outbox_id: int
    fell_back_to_invitation: bool


def send_reminder(
    db: Session,
    *,
    invitation: Invitation,
    review_session: ReviewSession,
    reviewer: Reviewer,
    user: User,
    build_invite_url: Callable[[str], str],
    correlation_id: str | None = None,
) -> ReminderResult:
    """Send a reminder reusing the previously-issued invitation URL.

    Falls back to ``send_invitation`` (rotates the token, writes a fresh
    ``kind='invitation'`` outbox row) when no invitation outbox row exists
    for this invitation yet — so a single click always results in a
    deliverable message.
    """
    existing_url = most_recent_invitation_url(db, invitation_id=invitation.id)
    if existing_url is None:
        result = send_invitation(
            db,
            invitation=invitation,
            review_session=review_session,
            reviewer=reviewer,
            user=user,
            build_invite_url=build_invite_url,
            correlation_id=correlation_id,
        )
        invitation.last_reminder_at = datetime.now(timezone.utc)
        db.flush()
        db.commit()
        return ReminderResult(
            outbox_id=result.outbox_id, fell_back_to_invitation=True
        )

    subject, body = email_templates.render_reminder(
        review_session, reviewer, existing_url
    )
    cc_emails, bcc_emails = email_templates.cc_bcc_for(
        review_session, REMINDER_KIND
    )
    outbox = EmailOutbox(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        invitation_id=invitation.id,
        kind=REMINDER_KIND,
        to_email=reviewer.email,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
        subject=subject,
        body=body,
        status="queued",
    )
    db.add(outbox)
    db.flush()

    now = datetime.now(timezone.utc)
    outbox.status = "sent"
    outbox.sent_at = now
    invitation.last_reminder_at = now
    db.flush()
    db.commit()
    return ReminderResult(outbox_id=outbox.id, fell_back_to_invitation=False)


@dataclass
class ReminderBatchResult:
    sent_count: int
    invitation_ids: list[int]
    reviewer_ids: list[int]
    fell_back_count: int


def send_reminders_to_incomplete(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    build_invite_url: Callable[[str], str],
    correlation_id: str | None = None,
) -> ReminderBatchResult:
    """Bulk-send reminders to every reviewer classified as incomplete.

    Pulls the incomplete set from ``app.services.monitoring`` (avoids a
    circular import by importing inline). Writes one batch ``reminders.sent``
    audit event when at least one reminder was sent.
    """
    from app.services import monitoring  # local to avoid circular import

    rows = monitoring.per_reviewer_progress(db, review_session)
    sent_invitation_ids: list[int] = []
    sent_reviewer_ids: list[int] = []
    fell_back = 0
    for row in rows:
        if not row.is_incomplete or row.invitation is None:
            continue
        result = send_reminder(
            db,
            invitation=row.invitation,
            review_session=review_session,
            reviewer=row.reviewer,
            user=user,
            build_invite_url=build_invite_url,
            correlation_id=correlation_id,
        )
        sent_invitation_ids.append(row.invitation.id)
        sent_reviewer_ids.append(row.reviewer.id)
        if result.fell_back_to_invitation:
            fell_back += 1

    if sent_invitation_ids:
        audit.write_event(
            db,
            event_type="reminders.sent",
            summary=(
                f"Sent {len(sent_invitation_ids)} reminder"
                f"{'' if len(sent_invitation_ids) == 1 else 's'}"
            ),
            actor_user_id=user.id,
            session=review_session,
            payload=audit.set_changes(
                updated=[
                    {"invitation_id": iid, "reviewer_id": rid}
                    for iid, rid in zip(sent_invitation_ids, sent_reviewer_ids)
                ]
            ),
            context={"fell_back": fell_back},
            correlation_id=correlation_id,
        )
        db.commit()
    return ReminderBatchResult(
        sent_count=len(sent_invitation_ids),
        invitation_ids=sent_invitation_ids,
        reviewer_ids=sent_reviewer_ids,
        fell_back_count=fell_back,
    )


__all__ = [
    "INVITATION_KIND",
    "REMINDER_KIND",
    "GenerateResult",
    "RegenerateResult",
    "RegenerateAllResult",
    "SendResult",
    "ReminderResult",
    "ReminderBatchResult",
    "InvitationRow",
    "hash_token",
    "generate_invitations",
    "regenerate_token",
    "regenerate_all_tokens",
    "send_invitation",
    "lookup_invitation_by_token",
    "record_open",
    "list_invitations_for_session",
    "list_outbox_for_session",
    "reviewers_eligible_for_invitation",
]
