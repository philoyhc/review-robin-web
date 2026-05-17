"""Operator-triggered selective purge — Segment 18C.

Hard-deletes a chosen subset of a session's data — responses,
rosters, or the audit log — the finer-grained counterpart to the
whole-session ``sessions.delete_session``. Backs the "Purge and
archive" action on the Sessions-lobby row expander.

Every purge is a hard-delete with no undo. The delete order in
each function is foreign-key-safe (children before parents) so it
holds on the FK-enforcing Postgres CI database, not just SQLite.
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    Invitation,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import audit

__all__ = ["purge_responses", "purge_rosters", "purge_audit_log"]


def _assignment_ids(session_id: int):
    return select(Assignment.id).where(Assignment.session_id == session_id)


def purge_responses(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Hard-delete every response + invitation row for the session.

    Assignments and all setup retain. Email-outbox rows are kept as
    an email-history record but unlinked from the deleted invitations.
    """
    session_id = review_session.id
    responses = db.execute(
        delete(Response).where(
            Response.assignment_id.in_(_assignment_ids(session_id))
        )
    ).rowcount
    # Outbox rows carry a FK onto invitations — unlink before the
    # invitations are deleted.
    db.execute(
        update(EmailOutbox)
        .where(EmailOutbox.session_id == session_id)
        .values(invitation_id=None)
    )
    invitations = db.execute(
        delete(Invitation).where(Invitation.session_id == session_id)
    ).rowcount
    db.flush()
    audit.write_event(
        db,
        event_type="session.responses_purged",
        summary=f"Purged responses from session {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(responses=responses, invitations=invitations),
        correlation_id=correlation_id,
    )
    db.commit()


def purge_rosters(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Hard-delete the session's reviewers, reviewees and relationships.

    Assignments / responses / invitations carry foreign keys onto the
    rosters, so they cascade out too; instruments, RTDs, display /
    response fields and settings retain. Reverts the session to a
    setup skeleton with no people.
    """
    session_id = review_session.id
    responses = db.execute(
        delete(Response).where(
            Response.assignment_id.in_(_assignment_ids(session_id))
        )
    ).rowcount
    db.execute(
        update(EmailOutbox)
        .where(EmailOutbox.session_id == session_id)
        .values(reviewer_id=None, invitation_id=None)
    )
    invitations = db.execute(
        delete(Invitation).where(Invitation.session_id == session_id)
    ).rowcount
    assignments = db.execute(
        delete(Assignment).where(Assignment.session_id == session_id)
    ).rowcount
    relationships = db.execute(
        delete(Relationship).where(Relationship.session_id == session_id)
    ).rowcount
    reviewers = db.execute(
        delete(Reviewer).where(Reviewer.session_id == session_id)
    ).rowcount
    reviewees = db.execute(
        delete(Reviewee).where(Reviewee.session_id == session_id)
    ).rowcount
    db.flush()
    audit.write_event(
        db,
        event_type="session.rosters_purged",
        summary=f"Purged rosters from session {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(
            reviewers=reviewers,
            reviewees=reviewees,
            relationships=relationships,
            assignments=assignments,
            responses=responses,
            invitations=invitations,
        ),
        correlation_id=correlation_id,
    )
    db.commit()


def purge_audit_log(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    correlation_id: str | None = None,
) -> None:
    """Hard-delete every ``audit_event`` row for the session.

    The ``session.audit_log_purged`` event is written *after* the
    delete, so this record of the purge itself survives.
    """
    purged = db.execute(
        delete(AuditEvent).where(AuditEvent.session_id == review_session.id)
    ).rowcount
    db.flush()
    audit.write_event(
        db,
        event_type="session.audit_log_purged",
        summary=f"Purged audit log of session {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        payload=audit.counts(audit_events=purged),
        correlation_id=correlation_id,
    )
    db.commit()
