"""Reviewees extract — Segment 12A-1 PR 2.

Streams the session's reviewee roster as a CSV whose column shape
matches the existing reviewee importer
(``app.services.csv_imports.parse_reviewee_csv``), so the file
round-trips with the upload flow on the Reviewees Manage page
and the Quick Setup card without conversion.

The ``PhotoLink`` column maps to ``Reviewee.profile_link``
(matches the importer at ``csv_imports.parse_reviewee_csv:336``).

Plan: ``guide/segment_12A-1_export.md`` PR 2.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession

__all__ = ["HEADER", "serialize_reviewees"]


# Header tuple matching the importer's required + optional columns
# (csv_imports.parse_reviewee_csv:265 / 336-339). Pinned so a
# rename on either side fails loud in a contract test.
HEADER: tuple[str, ...] = (
    "RevieweeName",
    "RevieweeEmail",
    "RevieweeTag1",
    "RevieweeTag2",
    "RevieweeTag3",
    "PhotoLink",
)


def serialize_reviewees(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s reviewees.

    First yield is ``HEADER``; subsequent yields are one tuple per
    reviewee in ``(status="active" first, then name, then
    email_or_identifier)`` order.
    """

    yield HEADER
    rows = (
        db.execute(
            select(Reviewee)
            .where(Reviewee.session_id == review_session.id)
            .order_by(
                (Reviewee.status != "active").asc(),
                Reviewee.name,
                Reviewee.email_or_identifier,
            )
        )
        .scalars()
        .all()
    )
    for reviewee in rows:
        yield (
            reviewee.name,
            reviewee.email_or_identifier,
            reviewee.tag_1 or "",
            reviewee.tag_2 or "",
            reviewee.tag_3 or "",
            reviewee.profile_link or "",
        )
