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
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Request
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
from app.services import audit


INVITATION_KIND = "invitation"


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _new_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def _invite_url(request: Request, raw_token: str) -> str:
    return str(request.url_for("reviewer_invite", token=raw_token))


def _email_body(session: ReviewSession, invite_url: str) -> tuple[str, str]:
    subject = f"Invitation to review: {session.name}"
    body = (
        f"You've been invited to review for: {session.name}.\n"
        f"Open this link (sign in with your work email): {invite_url}\n"
    )
    return subject, body


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
            session_id=review_session.id,
            detail={
                "session_id": review_session.id,
                "count": len(new_ids),
                "invitation_ids": new_ids,
                "reviewer_ids": sorted(to_create),
            },
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
        session_id=invitation.session_id,
        detail={
            "invitation_id": invitation.id,
            "reviewer_id": invitation.reviewer_id,
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return RegenerateResult(raw_token=raw)


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
    request: Request,
    correlation_id: str | None = None,
) -> SendResult:
    """Mint a fresh token, write an outbox row, flip invitation to ``sent``.

    The DB only ever stores the sha256 hash, so each send rotates the token
    and the previous URL (if any) becomes stale. The raw token is preserved
    in the outbox row body so the operator can re-copy the link.
    """
    raw_token, token_hash = _new_token()
    invitation.token_hash = token_hash

    invite_url = _invite_url(request, raw_token)
    subject, body = _email_body(review_session, invite_url)

    outbox = EmailOutbox(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        invitation_id=invitation.id,
        kind=INVITATION_KIND,
        to_email=reviewer.email,
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
        session_id=review_session.id,
        detail={
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
        session_id=invitation.session_id,
        detail={
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


def _reminder_body(session: ReviewSession, invite_url: str) -> tuple[str, str]:
    subject = f"Reminder: review for {session.name}"
    body = (
        f"Reminder — your review for {session.name} isn't complete yet.\n"
        f"Open this link (sign in with your work email): {invite_url}\n"
    )
    return subject, body


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
    request: Request,
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
            request=request,
            correlation_id=correlation_id,
        )
        invitation.last_reminder_at = datetime.now(timezone.utc)
        db.flush()
        db.commit()
        return ReminderResult(
            outbox_id=result.outbox_id, fell_back_to_invitation=True
        )

    subject, body = _reminder_body(review_session, existing_url)
    outbox = EmailOutbox(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        invitation_id=invitation.id,
        kind=REMINDER_KIND,
        to_email=reviewer.email,
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
    request: Request,
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
            request=request,
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
            session_id=review_session.id,
            detail={
                "session_id": review_session.id,
                "count": len(sent_invitation_ids),
                "invitation_ids": sent_invitation_ids,
                "reviewer_ids": sent_reviewer_ids,
                "fell_back_count": fell_back,
            },
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
    "SendResult",
    "ReminderResult",
    "ReminderBatchResult",
    "InvitationRow",
    "hash_token",
    "generate_invitations",
    "regenerate_token",
    "send_invitation",
    "lookup_invitation_by_token",
    "record_open",
    "list_invitations_for_session",
    "list_outbox_for_session",
    "reviewers_eligible_for_invitation",
]
