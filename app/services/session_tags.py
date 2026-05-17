"""Session tagging — free-form operator-chosen tags on sessions
(Segment 18A Part 2).

Tags are stored lowercased + trimmed in the ``session_tags`` table;
``(session_id, tag)`` is unique. This module is the read / write
layer; the operator-facing editors (the inline row expander) wire to
it in later 18A slices.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionTag, User
from app.services import audit

MAX_TAG_LENGTH = 64


def normalize_tag(raw: str) -> str:
    """Lowercase + trim a raw tag string.

    Raises ``ValueError`` if the result is empty or longer than the
    ``session_tags.tag`` column width.
    """
    tag = raw.strip().lower()
    if not tag:
        raise ValueError("Tag cannot be empty")
    if len(tag) > MAX_TAG_LENGTH:
        raise ValueError(f"Tag cannot exceed {MAX_TAG_LENGTH} characters")
    return tag


def tags_for_sessions(
    db: Session, session_ids: list[int]
) -> dict[int, list[str]]:
    """Tags for many sessions in one query, grouped by session id and
    sorted within each session. Every requested id is a key (empty
    list when the session carries no tags)."""
    grouped: dict[int, list[str]] = {sid: [] for sid in session_ids}
    if not session_ids:
        return grouped
    rows = db.execute(
        select(SessionTag.session_id, SessionTag.tag)
        .where(SessionTag.session_id.in_(session_ids))
        .order_by(SessionTag.tag)
    ).all()
    for session_id, tag in rows:
        grouped.setdefault(session_id, []).append(tag)
    return grouped


def vocabulary(db: Session, session_ids: list[int]) -> list[str]:
    """The distinct sorted tag set across the given sessions — the
    operator's tag vocabulary for the lobby filter strip."""
    if not session_ids:
        return []
    rows = db.execute(
        select(SessionTag.tag)
        .where(SessionTag.session_id.in_(session_ids))
        .distinct()
        .order_by(SessionTag.tag)
    ).scalars().all()
    return list(rows)


def add_tag(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    tag: str,
    correlation_id: str | None = None,
) -> bool:
    """Add a tag to a session. Idempotent — returns ``False`` when the
    session already carries the normalized tag, ``True`` when added."""
    normalized = normalize_tag(tag)
    already = db.execute(
        select(SessionTag.id).where(
            SessionTag.session_id == review_session.id,
            SessionTag.tag == normalized,
        )
    ).first()
    if already is not None:
        return False
    db.add(SessionTag(session_id=review_session.id, tag=normalized))
    db.flush()
    audit.write_event(
        db,
        event_type="session.tag_added",
        summary=f"Tag '{normalized}' added to session {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        context={"tag": normalized},
        correlation_id=correlation_id,
    )
    db.commit()
    return True


def set_tags(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    tags: list[str],
    correlation_id: str | None = None,
) -> tuple[list[str], list[str]]:
    """Replace a session's tag set with ``tags`` (raw free-form
    strings — each normalized, blanks skipped, duplicates collapsed).

    Adds the tags new to the session and removes the dropped ones,
    one ``session.tag_added`` / ``session.tag_removed`` audit event
    per change, in a single transaction. Returns ``(added, removed)``,
    each sorted.
    """
    desired: set[str] = set()
    for raw in tags:
        try:
            desired.add(normalize_tag(raw))
        except ValueError:
            continue
    current = set(
        db.execute(
            select(SessionTag.tag).where(
                SessionTag.session_id == review_session.id
            )
        ).scalars()
    )
    to_add = sorted(desired - current)
    to_remove = sorted(current - desired)

    for tag in to_add:
        db.add(SessionTag(session_id=review_session.id, tag=tag))
    for tag in to_remove:
        row = db.execute(
            select(SessionTag).where(
                SessionTag.session_id == review_session.id,
                SessionTag.tag == tag,
            )
        ).scalar_one()
        db.delete(row)
    db.flush()

    for tag in to_add:
        audit.write_event(
            db,
            event_type="session.tag_added",
            summary=f"Tag '{tag}' added to session {review_session.code}",
            actor_user_id=user.id,
            session=review_session,
            context={"tag": tag},
            correlation_id=correlation_id,
        )
    for tag in to_remove:
        audit.write_event(
            db,
            event_type="session.tag_removed",
            summary=f"Tag '{tag}' removed from session {review_session.code}",
            actor_user_id=user.id,
            session=review_session,
            context={"tag": tag},
            correlation_id=correlation_id,
        )
    db.commit()
    return (to_add, to_remove)


def remove_tag(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    tag: str,
    correlation_id: str | None = None,
) -> bool:
    """Remove a tag from a session. Idempotent — returns ``False`` when
    the session didn't carry the normalized tag, ``True`` when removed."""
    normalized = normalize_tag(tag)
    row = db.execute(
        select(SessionTag).where(
            SessionTag.session_id == review_session.id,
            SessionTag.tag == normalized,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    db.delete(row)
    db.flush()
    audit.write_event(
        db,
        event_type="session.tag_removed",
        summary=f"Tag '{normalized}' removed from session {review_session.code}",
        actor_user_id=user.id,
        session=review_session,
        context={"tag": normalized},
        correlation_id=correlation_id,
    )
    db.commit()
    return True
