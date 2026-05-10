"""Relationships extract — Segment 12A-3 PR 1.

Streams the session's per-pair ``relationships`` rows as a CSV
whose column shape matches the existing relationships importer
(``app.services.relationships.parse_relationship_csv``), so the
file round-trips with the upload flow on the Relationships
Manage page (and the Quick Setup card's relationships slot)
without conversion.

Plan: ``guide/segment_12A-3_export_import_updates.md`` PR 1.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

__all__ = ["HEADER", "serialize_relationships"]


HEADER: tuple[str, ...] = (
    "ReviewerEmail",
    "RevieweeEmail",
    "PairContextTag1",
    "PairContextTag2",
    "PairContextTag3",
    "Status",
)


def serialize_relationships(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s relationships.

    First yield is ``HEADER``; subsequent yields are one tuple per
    relationship row in ``(status="active" first, then reviewer
    email, then reviewee email_or_identifier)`` order.
    """

    yield HEADER
    rows = (
        db.execute(
            select(Relationship, Reviewer, Reviewee)
            .join(Reviewer, Reviewer.id == Relationship.reviewer_id)
            .join(Reviewee, Reviewee.id == Relationship.reviewee_id)
            .where(Relationship.session_id == review_session.id)
            .order_by(
                (Relationship.status != "active").asc(),
                Reviewer.email,
                Reviewee.email_or_identifier,
            )
        )
        .all()
    )
    for relationship, reviewer, reviewee in rows:
        yield (
            reviewer.email,
            reviewee.email_or_identifier,
            relationship.tag_1 or "",
            relationship.tag_2 or "",
            relationship.tag_3 or "",
            relationship.status,
        )
