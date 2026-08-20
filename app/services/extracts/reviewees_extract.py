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
from app.services import field_label_csv

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
    # Segment 18P PR C — active / inactive soft-delete state. The
    # importer reads it back (blank / absent → active), so an
    # inactive reviewee round-trips as inactive.
    "Status",
)


def serialize_reviewees(
    db: Session, review_session: ReviewSession
) -> Iterable[tuple[str, ...]]:
    """Yield CSV rows for ``review_session``'s reviewees.

    First yield is the header; subsequent yields are one tuple per
    reviewee in ``(status="active" first, then name, then
    email_or_identifier)`` order.

    The header carries each renamed tag column's friendly label as a
    ``RevieweeTagN.<label>`` suffix (Segment 19C Item 1).
    """

    yield field_label_csv.labeled_header(review_session, HEADER)
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
            reviewee.status,
        )
